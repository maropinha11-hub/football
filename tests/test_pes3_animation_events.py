"""Temporal/contact-context regressions, separate from fresh original proofs."""
import ctypes as C
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
from event_abi import Anchor741, Input, SOURCE, configure
from replay import PLAYER_BASE, PLAYER_STRIDE
from study_states import actor_fields, selected_actors
from verify_animation_events import neighboring_float
from verify_event_vectors import safe_member


@unittest.skipUnless(shutil.which('g++'), 'g++ unavailable')
class EventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='pes3-event-tests-')
        folder = Path(cls.temp.name)
        (folder / 'events.cpp').write_text(SOURCE)
        subprocess.run(['g++', '-std=c++14', '-O0', '-Wall', '-Wextra', '-Werror',
                        '-fno-fast-math', '-ffp-contract=off', '-fsanitize=undefined',
                        '-fno-sanitize-recover=all', '-shared', '-fPIC',
                        '-I', str(ROOT / 'tools/pes3/recovered'), str(folder / 'events.cpp'),
                        '-o', str(folder / 'events.so')], check=True, capture_output=True)
        cls.lib = configure(C.CDLL(str(folder / 'events.so')))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def gate(self, value, marker=24, chop=0):
        output = C.c_uint(0x2A2A2A2A)
        self.assertEqual(self.lib.owned_phase_gate(C.byref(value), marker, chop, C.byref(output)), 1)
        return output.value

    def test_gate_has_open_lower_and_closed_upper_boundary(self):
        self.assertEqual(self.gate(Input(phase=23.5, step=1)), 0)
        self.assertEqual(self.gate(Input(phase=neighboring_float(23.5, 1), step=1)), 1)
        self.assertEqual(self.gate(Input(phase=24.5, step=1)), 1)
        self.assertEqual(self.gate(Input(phase=neighboring_float(24.5, 1), step=1)), 0)

    def test_fractional_step_and_negative_step(self):
        self.assertEqual(self.gate(Input(phase=24.125, step=0.25)), 1)
        self.assertEqual(self.gate(Input(phase=23.875, step=0.25)), 0)
        self.assertEqual(self.gate(Input(phase=24, step=0)), 0)
        self.assertEqual(self.gate(Input(phase=24, step=-1)), 0)

    def test_blend_and_cycle_flags_preserve_first_tick_exception(self):
        self.assertEqual(self.gate(Input(phase=24, step=1, blend_window=4)), 0)
        self.assertEqual(self.gate(Input(phase=24, step=1, cycle_fix=1)), 0)
        self.assertEqual(self.gate(Input(phase=24, step=1, blend_window=4, blend_tick=1)), 1)
        self.assertEqual(self.gate(Input(phase=24, step=1, cycle_fix=255, blend_tick=255)), 1)

    def test_signed_marker_conversion_uses_the_selected_profile(self):
        value = Input(phase=16777218, step=1)
        self.assertEqual(self.gate(value, marker=16777219, chop=0), 0)
        self.assertEqual(self.gate(value, marker=16777219, chop=1), 1)
        self.assertEqual(self.gate(Input(phase=-24, step=1), marker=-24), 1)

    def test_anchor_depends_on_context_and_preserves_signed_truncation(self):
        examples = ((-246, 0, (-70, -265, -156)),
                    (-245.25, 1, (-55, -235, -157)),
                    (-222, 1, (-55, -235, -157)),
                    (-221.25, 2, (-38, -209, -164)),
                    (-193, 2, (-38, -209, -164)),
                    (-192.25, 2, (-38, -209, -164)),
                    (-192, 3, (-20, -178, -173)),
                    (-158, 3, (-20, -178, -173)),
                    (-157, 4, (11, -149, -177)))
        for height, choice, xyz in examples:
            out = Anchor741()
            self.assertEqual(self.lib.owned_anchor_741(height, 0, C.byref(out)), 1)
            self.assertEqual((out.choice, tuple(out.xyz), out.reference_index), (choice, xyz, 7))

    def test_invalid_inputs_leave_outputs_untouched(self):
        for bad in (math.nan, math.inf, -math.inf):
            for value in (Input(phase=bad, step=1), Input(phase=24, step=bad)):
                out = C.c_uint(0x2A2A2A2A)
                self.assertEqual(self.lib.owned_phase_gate(C.byref(value), 24, 0, C.byref(out)), 0)
                self.assertEqual(out.value, 0x2A2A2A2A)
            out = Anchor741.from_buffer_copy(b'\x2a' * C.sizeof(Anchor741))
            before = bytes(out)
            self.assertEqual(self.lib.owned_anchor_741(bad, 0, C.byref(out)), 0)
            self.assertEqual(bytes(out), before)
        out = Anchor741.from_buffer_copy(b'\x2a' * C.sizeof(Anchor741))
        self.assertEqual(self.lib.owned_anchor_741(0, 2, C.byref(out)), 0)
        self.assertEqual(bytes(out), b'\x2a' * C.sizeof(Anchor741))
        self.assertEqual(self.lib.owned_anchor_741(3e38, 0, C.byref(out)), 0)


class StateStudyTests(unittest.TestCase):
    def test_player_switch_does_not_drop_the_actor_finishing_a_gesture(self):
        rows = [{'id': 5, 'action': 11}, {'id': 9, 'action': 5},
                {'id': 12, 'action': 137}, {'id': 13, 'action': 255}]
        self.assertEqual(selected_actors(rows, 5), [5, 9])
        self.assertEqual(selected_actors(rows, 12), [9, 12])
        with self.assertRaises(ValueError):
            selected_actors(rows, 0)

    def test_amplitude_is_a_signed_integer_not_a_float(self):
        ram = bytearray(PLAYER_BASE + PLAYER_STRIDE * 23)
        at = PLAYER_BASE + PLAYER_STRIDE * 9
        struct.pack_into('<i', ram, at + 0xE0, -17)
        struct.pack_into('<H', ram, at + 0xEA, 65535)
        struct.pack_into('<f', ram, at + 0x2E4, 48.25)
        value = actor_fields(ram, 9)
        self.assertEqual((value['amplitude_i32'], value['heading_u16'], value['phase']), (-17, 65535, 48.25))
        for bad in (-1, 0, 23):
            with self.assertRaises(ValueError):
                actor_fields(ram, bad)

    def test_offline_package_rejects_unsafe_and_noncanonical_names(self):
        for bad in ('../outside', '/absolute', 'dir\\outside', 'dir/../outside', 'dir//outside'):
            with self.assertRaises(ValueError):
                safe_member(bad)
        self.assertEqual(str(safe_member('recompiled/page-001.cpp')), 'recompiled/page-001.cpp')


if __name__ == '__main__':
    unittest.main()
