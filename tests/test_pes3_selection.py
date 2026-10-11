import ctypes as C
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/pes3'))
from selection_abi import Input, Decision, SOURCE


@unittest.skipUnless(shutil.which('g++'), 'g++ unavailable')
class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='pes3-selector-test-')
        folder = Path(cls.temp.name)
        (folder / 'selector.cpp').write_text(SOURCE)
        include = Path(__file__).resolve().parents[1] / 'tools/pes3/recovered'
        subprocess.run(['g++', '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                        '-I', str(include), str(folder / 'selector.cpp'), '-o', str(folder / 'selector.so')],
                       check=True, capture_output=True)
        cls.lib = C.CDLL(str(folder / 'selector.so'))
        cls.lib.select_locomotion.argtypes = [C.POINTER(Input), C.POINTER(Decision)]
        cls.lib.select_locomotion.restype = C.c_int

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def run_case(self, **values):
        i = Input(initial_amplitude=8000, current_amplitude=2048, chase_amplitude=8000,
                  direction_mask=1, clip=304, player_id=10, context_player=10, substate=16)
        for name, value in values.items(): setattr(i, name, value)
        out = Decision()
        self.assertEqual(self.lib.select_locomotion(C.byref(i), C.byref(out)), 1)
        return out

    def test_ball_threshold_is_strict_and_branch_exclusive(self):
        for ball, change in ((4687, 1), (4688, 0), (4689, 0)):
            r = self.run_case(state_flags=1, attribute_124=100, ball_amplitude=ball, current_amplitude=0)
            self.assertEqual((r.selected_amplitude, r.change_clip), (ball, change))
            self.assertEqual(r.substate, 16)
            self.assertEqual(r.auxiliary_134, 0)
            if change: self.assertEqual((r.requested_clip, r.start_frame, r.refresh_window), (61, 0, 4))

    def test_chase_limit_and_common_fallthrough(self):
        low = self.run_case(direction_mask=0, chase_amplitude=5599)
        self.assertEqual((low.requested_clip, low.selected_amplitude), (61, 5599))
        equal = self.run_case(direction_mask=0, chase_amplitude=5600)
        self.assertEqual((equal.change_clip, equal.selected_amplitude), (0, 8000))

    def test_turn_threshold_wrap_and_amplitude_reset(self):
        below = self.run_case(body_heading=65535, movement_heading=20478)
        self.assertEqual(below.change_clip, 0)
        equal = self.run_case(body_heading=65535, movement_heading=20479)
        self.assertEqual((equal.requested_clip, equal.start_frame, equal.substate), (47, 5, 55))
        self.assertEqual(equal.amplitude_before_speed, 0)
        self.assertEqual(equal.turn_heading, 65535)

    def test_slow_restart_requires_phase_flag_and_preserves_amplitude(self):
        low = self.run_case(current_amplitude=1023)
        self.assertEqual((low.requested_clip, low.amplitude_before_speed), (47, 1023))
        self.assertEqual(self.run_case(current_amplitude=1024).change_clip, 0)
        self.assertEqual(self.run_case(current_amplitude=0, phase_130=1).change_clip, 0)

    def test_clip_47_restart_preserves_original_time_override(self):
        r = self.run_case(clip=47, clip_restart=1)
        self.assertEqual((r.frame_override, r.writes & 1, r.change_clip), (24, 1, 0))

    def test_wrapped_integer_product_changes_chase_threshold(self):
        # INT_MAX*7 wraps to 2147483641 before signed divide by ten.
        r = self.run_case(initial_amplitude=2147483647, chase_amplitude=214748363, direction_mask=0)
        self.assertEqual((r.requested_clip, r.selected_amplitude), (61, 214748363))

    def test_special_and_invalid_inputs_preserve_output(self):
        for name, value, expected in (('clip', 35, -1), ('clip', 61, -1), ('clip', 864, -1), ('direction_mask', 16, 0),
                                      ('chase_gate', 2, 0), ('clip_restart', 2, 0)):
            i = Input(); setattr(i, name, value)
            out = Decision.from_buffer_copy(b'\x2a' * C.sizeof(Decision)); before = bytes(out)
            self.assertEqual(self.lib.select_locomotion(C.byref(i), C.byref(out)), expected)
            self.assertEqual(bytes(out), before)


if __name__ == '__main__': unittest.main()
