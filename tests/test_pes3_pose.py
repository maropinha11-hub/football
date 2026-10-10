import ctypes as C
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/pes3'))
from pose import skeleton, pose_fields
from retarget import prepare, PARENTS, PAIRS
from verify_pose_ops import SOURCE
from lift import generate
from replay import LiftResult


class SkeletonTests(unittest.TestCase):
    def memory(self):
        ram = bytearray(8192)
        nodes = [0x100 + 0x110 * i for i in range(19)]
        struct.pack_into('<I', ram, 0x1800, nodes[0])
        for i, at in enumerate(nodes):
            struct.pack_into('<III', ram, at + 0x104,
                             nodes[i + 1] if i < 18 else 0, nodes[i - 1] if i else 0, 0)
        return ram, nodes

    def test_valid_chain_has_topological_parents(self):
        ram, nodes = self.memory()
        spec = skeleton(ram, 0x1800)
        self.assertEqual(spec['nodes'], nodes)
        self.assertEqual(spec['parents'], [-1, *range(18)])
        self.assertEqual(len(pose_fields(ram, spec)['matrix_bits']), 19)

    def test_cycle_rejected(self):
        ram, nodes = self.memory(); struct.pack_into('<I', ram, nodes[-1] + 0x104, nodes[0])
        with self.assertRaisesRegex(ValueError, 'cadeia'): skeleton(ram, 0x1800)

    def test_foreign_parent_rejected(self):
        ram, nodes = self.memory(); struct.pack_into('<I', ram, nodes[3] + 0x108, 0x80)
        with self.assertRaisesRegex(ValueError, 'relação'): skeleton(ram, 0x1800)

    def test_asymmetric_mirror_pair_rejected(self):
        ram, nodes = self.memory(); struct.pack_into('<I', ram, nodes[3] + 0x10c, nodes[4])
        with self.assertRaisesRegex(ValueError, 'assimétrico'): skeleton(ram, 0x1800)

    def test_short_and_unaligned_chain_rejected(self):
        ram, nodes = self.memory(); struct.pack_into('<I', ram, nodes[2] + 0x104, 0)
        with self.assertRaisesRegex(ValueError, '19'): skeleton(ram, 0x1800)
        with self.assertRaisesRegex(ValueError, 'desalinhado'): skeleton(ram, 0x1801)

    def test_nonfinite_pose_rejected(self):
        ram, nodes = self.memory(); struct.pack_into('<I', ram, nodes[2] + 0x50, 0x7fc00000)
        with self.assertRaisesRegex(ValueError, 'não finita'): pose_fields(ram, skeleton(ram, 0x1800))


class RetargetTests(unittest.TestCase):
    def evidence(self): return {'parents': PARENTS, 'mirror_pairs': PAIRS, 'state_sha256': 'a' * 64}

    def test_native_mapping_retains_unresolved_calibration(self):
        result = prepare(self.evidence(), ROOT / 'data/media/objects/players/player.object')
        self.assertEqual(result['native_animation_channels'], 14)
        self.assertEqual(result['native_skeletal_nodes'], 13)
        self.assertFalse(result['runtime_enabled'])
        self.assertFalse(result['axes_calibrated'])
        self.assertFalse(result['left_right_calibrated'])
        thigh = next(r for r in result['targets'] if r['name'] == 'left_thigh')
        self.assertEqual([r['ancestor_chain'] for r in thigh['pes_candidates']], [[0, 1, 2], [0, 1, 3]])

    def test_changed_topology_rejected(self):
        data = dict(self.evidence(), parents=[-1] * 19)
        with self.assertRaisesRegex(ValueError, 'hierarquia'): prepare(data, ROOT / 'data/media/objects/players/player.object')


@unittest.skipUnless(shutil.which('g++'), 'g++ unavailable')
class SemanticPoseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        folder = Path(cls.temp.name)
        (folder / 'pose_ops.cpp').write_text(SOURCE)
        (folder / 'pose_ops.hpp').write_bytes((ROOT / 'tools/pes3/recovered/pose_ops.hpp').read_bytes())
        subprocess.run(['g++', '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror', '-fno-fast-math',
                        '-ffp-contract=off', '-shared', '-fPIC', str(folder / 'pose_ops.cpp'), '-o', str(folder / 'ops.so')],
                       check=True, capture_output=True)
        cls.library = C.CDLL(str(folder / 'ops.so'))
        cls.library.pose_op.argtypes = [C.c_uint, C.POINTER(C.c_float), C.POINTER(C.c_float), C.c_float, C.POINTER(C.c_float)]
        cls.library.pose_op.restype = C.c_int
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def run_op(self, operation, a, b=(0, 0, 0, 1), alpha=0):
        out = (C.c_float * 16)(*[23] * 16)
        status = self.library.pose_op(operation, (C.c_float * 4)(*a), (C.c_float * 4)(*b), alpha, out)
        return status, list(out)

    def test_identity_matrix_column_major(self):
        status, out = self.run_op(1, (0, 0, 0, 1))
        self.assertEqual(status, 1)
        self.assertEqual(out, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])

    def test_quaternion_conjugate_returns_identity(self):
        status, out = self.run_op(0, (.5, .5, .5, .5), (-.5, -.5, -.5, .5))
        self.assertEqual((status, out[:4]), (1, [0, 0, 0, 1]))

    def test_rotation_preserves_translation_fourth_lane(self):
        status, out = self.run_op(2, (0, 0, 0, 1), (3, -2, 7, 0))
        self.assertEqual((status, out[:4]), (1, [3, -2, 7, 0]))

    def test_opposite_sign_blend_uses_shortest_arc(self):
        status, out = self.run_op(3, (0, 0, 0, 1), (0, 0, 0, -1), .5)
        self.assertEqual((status, out[:4]), (1, [0, 0, 0, 1]))

    def test_invalid_operation_weight_and_nonfinite_preserve_output(self):
        for op, vector, weight in ((9, (0, 0, 0, 1), 0), (3, (0, 0, 0, 1), 1.2),
                                   (3, (0, 0, 0, 1), math.nan), (1, (math.inf, 0, 0, 1), 0)):
            status, out = self.run_op(op, vector, alpha=weight)
            self.assertEqual((status, out), (0, [23] * 16))


@unittest.skipUnless(shutil.which('g++'), 'g++ unavailable')
class PoseLiftTests(unittest.TestCase):
    def test_initial_fpu_inputs_and_likely_delay_slot(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'native'
            words = {0x100: (17 << 26) | (16 << 21) | (13 << 16) | (12 << 11) | 50,
                     0x104: (17 << 26) | (8 << 21) | (3 << 16) | 2,
                     0x108: 0x24020007, 0x10c: 0x24020009, 0x110: 0x03e00008, 0x114: 0}
            generate(words, out)
            subprocess.run(['g++', '-std=c++17', '-O0', '-shared', '-fPIC', str(out / 'lifted_program.cpp'),
                            '-o', str(out / 'lift.so')], check=True, capture_output=True)
            native = C.CDLL(str(out / 'lift.so'))
            native.pes3_run_lifted_f32.argtypes = [C.POINTER(C.c_uint8), C.POINTER(C.c_uint8), C.c_uint32,
                C.POINTER(C.c_uint64), C.c_uint32, C.POINTER(C.c_uint32), C.c_uint32, C.POINTER(LiftResult)]
            ram, scratch = bytearray(32 * 1024 * 1024), bytearray(16384)
            for pc, w in words.items(): struct.pack_into('<I', ram, pc, w)
            rb, sb = (C.c_uint8 * len(ram)).from_buffer(ram), (C.c_uint8 * len(scratch)).from_buffer(scratch)
            for other, expected in ((1., 7), (2., 9)):
                floats = (C.c_uint32 * 32)(); floats[12] = 0x3f800000
                floats[13] = struct.unpack('<I', struct.pack('<f', other))[0]
                result = LiftResult()
                self.assertEqual(native.pes3_run_lifted_f32(rb, sb, 0x100, None, 0, floats, 20, C.byref(result)), 0)
                self.assertEqual(result.registers[2], expected)


if __name__ == '__main__': unittest.main()
