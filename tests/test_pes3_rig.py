"""Semantic rig invariants independent of captured PES outputs."""
import ctypes as C
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/pes3'))
from rig import Rig, SOURCE

bits = lambda v: struct.unpack('<I', struct.pack('<f', v))[0]
number = lambda v: struct.unpack('<f', struct.pack('<I', v))[0]

def simple():
    r = Rig(); r.flags[:] = [1, 1, 0, 0]
    for i, b in enumerate(r.bones):
        b.parent, b.mirror = i - 1, -1
        b.local_rotation[:] = list(map(bits, [0, 0, 0, 1]))
        b.local_translation[:] = list(map(bits, [1 if i else 0, 0, 0, 0]))
        b.mirror_correction[:] = list(map(bits, [0, 0, 0, 1]))
    return r

@unittest.skipUnless(shutil.which('g++'), 'g++ unavailable')
class RigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='pes3-rig-test-')
        folder = Path(cls.temp.name)
        tool = Path(__file__).resolve().parents[1] / 'tools/pes3/recovered'
        (folder / 'test.cpp').write_text(SOURCE)
        subprocess.run(['g++', '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror', '-fno-fast-math',
                        '-ffp-contract=off', '-shared', '-fPIC', '-I', str(tool), str(folder / 'test.cpp'),
                        '-o', str(folder / 'test.so')], check=True, capture_output=True)
        cls.lib = C.CDLL(str(folder / 'test.so'))
        cls.lib.rig_op.argtypes = [C.c_uint, C.POINTER(Rig), C.c_uint, C.c_uint, C.c_uint, C.c_float, C.c_int]
        cls.lib.rig_op.restype = C.c_int

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def work(self): return (Rig * 3)(simple(), simple(), simple())
    def op(self, op, work, d=0, weight=.5, all_trans=0):
        return self.lib.rig_op(op, work, d, 1, 2, weight, all_trans)

    def test_matrix_composition_uses_implicit_homogeneous_one(self):
        w = self.work(); self.assertEqual(self.op(0, w), 1)
        self.assertEqual(number(w[0].bones[18].composed_translation[0]), 18)
        self.assertEqual(number(w[0].bones[0].local_translation[3]), 1)
        self.assertEqual(number(w[0].bones[18].matrix[15]), 1)
        self.assertEqual(number(w[0].bones[18].local_translation[3]), 0)

    def test_quaternion_branch_preserves_matrix_and_original_flags(self):
        w = self.work(); w[0].bones[0].matrix[0] = bits(.25)
        self.assertEqual(self.op(1, w), 1)
        self.assertEqual(w[0].flags[1], 7)
        self.assertEqual(w[0].bones[0].matrix[0], bits(.25))
        self.assertEqual(number(w[0].bones[18].composed_translation[0]), 18)

    def test_composed_to_local_roundtrip_on_identity_rig(self):
        w = self.work(); self.assertEqual(self.op(0, w), 1)
        w[0].flags[1] = 2
        self.assertEqual(self.op(2, w), 1)
        for i in range(1, 19):
            self.assertEqual(number(w[0].bones[i].local_translation[0]), 1)
            self.assertEqual(number(w[0].bones[i].local_translation[3]), 0)

    def test_matrix_to_quaternion_covers_identity_and_three_half_turns(self):
        for diag, expected in [([1, 1, 1], [0, 0, 0, 1]), ([1, -1, -1], [1, 0, 0, 0]),
                               ([-1, 1, -1], [0, 1, 0, 0]), ([-1, -1, 1], [0, 0, 1, 0])]:
            w = self.work(); w[0].flags[1] = 4
            for b in w[0].bones:
                b.matrix[:] = list(map(bits, [diag[0], 0, 0, 0, 0, diag[1], 0, 0, 0, 0, diag[2], 0, 0, 0, 0, 1]))
            self.assertEqual(self.op(1, w), 1)
            self.assertEqual(list(map(number, w[0].bones[0].composed_rotation)), expected)

    def test_mirror_gate_preserves_input_when_disabled_or_already_aligned(self):
        for flags, gate in [(0x49, 0), (0x41, 1)]:
            w = self.work(); w[0].flags[1] = flags; w[0].flags[2] = gate
            before = bytes(w); self.assertEqual(self.op(5, w), 1)
            self.assertEqual(bytes(w), before)

    def test_mix_root_only_preserves_source_a_nonroot_translation(self):
        w = self.work()
        w[1].bones[0].local_translation[0] = bits(2)
        w[2].bones[0].local_translation[0] = bits(6)
        w[2].bones[1].local_translation[0] = bits(10)
        self.assertEqual(self.op(7, w, weight=.25), 1)
        self.assertEqual(number(w[0].bones[0].local_translation[0]), 3)
        self.assertEqual(number(w[0].bones[1].local_translation[0]), 1)

    def test_mix_all_translation_and_destination_alias(self):
        for destination in (0, 1, 2):
            w = self.work(); w[2].bones[1].local_translation[0] = bits(9)
            self.assertEqual(self.op(7, w, d=destination, all_trans=1), 1)
            self.assertEqual(number(w[destination].bones[1].local_translation[0]), 5)

    def test_invalid_rig_and_unknown_decode_preserve_all_outputs(self):
        for kind in ('parent', 'pair', 'nonfinite', 'decode', 'weight'):
            w = self.work(); op = 0; weight = .5
            if kind == 'parent': w[0].bones[1].parent = 1
            elif kind == 'pair': w[0].bones[2].mirror = 3
            elif kind == 'nonfinite': w[0].bones[0].matrix[0] = 0x7fc00000
            elif kind == 'decode': w[0].flags[1] = 0; op = 2
            else: op = 7; weight = float('nan')
            before = bytes(w); self.assertEqual(self.op(op, w, weight=weight), 0)
            self.assertEqual(bytes(w), before)

if __name__ == '__main__': unittest.main()
