"""Isolated selected-model rounding experiments; never patch imported references.

Finite binary32 nearest/toward-zero comparisons only. This does not reproduce
PS2 overflow, accumulator precision, division units, flags or cycle timing.
"""
import builtins
import math
import struct
import types
from pathlib import Path

from pose import REFERENCE_HASHES
from savestate import digest


def nearest(number):
    result = struct.unpack('<f', struct.pack('<f', number))[0]
    if not math.isfinite(result): raise ValueError('nonfinite rounding experiment domain')
    return result


def chop(number):
    result = nearest(number)
    if abs(result) > abs(number):
        raw = struct.unpack('<I', struct.pack('<f', result))[0] - 1
        result = struct.unpack('<f', struct.pack('<I', raw))[0]
    return result


def classes(folder, fpu, vu, division=None, square_root=None):
    division = fpu if division is None else division
    square_root = fpu if square_root is None else square_root
    if any(mode not in ('nearest', 'chop') for mode in (fpu, vu, division, square_root)):
        raise ValueError('unknown arithmetic profile')
    for name, expected in REFERENCE_HASHES.items():
        if digest((folder / name).read_bytes()) != expected: raise ValueError('reference version changed')
    modules = {}
    def importing(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name in modules: return modules[name]
        return builtins.__import__(name, globals, locals, fromlist, level)
    def load(name, path):
        module = types.ModuleType('_pes3_' + name + '_' + fpu + '_' + vu)
        module.__file__ = str(path)
        module.__dict__['__builtins__'] = dict(vars(builtins), __import__=importing)
        exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
        modules[name] = module
        return module
    load('mips_integer_reference', folder / 'mips_integer_reference.py')
    floats = load('float_vector_model', folder / 'float_vector_model.py')
    floats.rounded = chop if fpu == 'chop' else nearest
    def vector(number):
        result = (chop if vu == 'chop' else nearest)(number)
        raw = struct.unpack('<I', struct.pack('<f', result))[0]
        if raw & 0x7f800000 == 0: return struct.unpack('<f', struct.pack('<I', raw & 0x80000000))[0]
        return result
    floats.vector_value = vector
    load('pose_math_model', folder / 'pose_math_model.py')
    pose = load('pose_reference', Path(__file__).with_name('pose_reference.py'))
    scratch = load('scratch_field_model', folder / 'scratch_field_model.py')
    class SelectedPose(pose.PoseReference, scratch.ScratchFloat):
        def __init__(self, ref): self.ref = ref
        def cop1(self, pc, word, registers):
            rs, rt, fs, fd = ((word >> n) & 31 for n in (21, 16, 11, 6))
            fn = word & 63
            if rs == 16 and fn in (3, 4):
                self.annul_delay = False
                left, right = floats.value(self.f[fs]), floats.value(self.f[rt])
                if not math.isfinite(left) or not math.isfinite(right):
                    raise ValueError('nonfinite division/sqrt experiment domain')
                if fn == 3:
                    if right == 0: raise ValueError('zero division experiment domain')
                    result = (chop if division == 'chop' else nearest)(left / right)
                else:
                    if fs != rt or left < 0: raise ValueError('sqrt outside selected same-register domain')
                    result = (chop if square_root == 'chop' else nearest)(math.sqrt(left))
                self.f[fd] = floats.bits(result)
                return None
            return super().cop1(pc, word, registers)
    return scratch.ScratchReference, SelectedPose
