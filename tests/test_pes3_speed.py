import ctypes as C
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/pes3'))
from speed_abi import Input, SOURCE, configure


@unittest.skipUnless(shutil.which('g++'), 'g++ unavailable')
class SpeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='pes3-speed-test-')
        folder = Path(cls.temp.name); (folder / 'speed.cpp').write_text(SOURCE)
        include = Path(__file__).resolve().parents[1] / 'tools/pes3/recovered'
        subprocess.run(['g++', '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
            '-I', str(include), str(folder / 'speed.cpp'), '-o', str(folder / 'speed.so')], check=True, capture_output=True)
        cls.lib = configure(C.CDLL(str(folder / 'speed.so')))

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def run_case(self, **values):
        value = Input(current_amplitude=8000, selected_amplitude=4000)
        for name, item in values.items(): setattr(value, name, item)
        return self.lib.step_speed(C.byref(value))

    def test_zero_target_preserves_current_including_negative_amplitude(self):
        for current in (-2147483648, -1, 0, 8000, 2147483647):
            self.assertEqual(self.run_case(current_amplitude=current, selected_amplitude=0), current)

    def test_profile_and_mode_change_braking_but_exception_modes_do_not(self):
        self.assertEqual(self.run_case(), 7807)  # 6400 / (22 * 3 / 2) = 193.
        self.assertEqual(self.run_case(mode_phase_5=1), 7823)  # 33 * 11 / 10 = 36.
        self.assertEqual(self.run_case(profile_flag=1), 7763)  # (22 * 5 / 6) * 3 / 2 = 27.
        for mode in (4, 16): self.assertEqual(self.run_case(mode_phase_5=1, mode_2=mode), 7807)

    def test_stat_mask_uses_bits_two_to_eight_not_upper_roster_bits(self):
        self.assertEqual(self.run_case(roster_ae=508), self.run_case(roster_ae=65535))
        self.assertEqual(self.run_case(roster_ae=200), self.run_case(roster_ae=204))
        self.assertNotEqual(self.run_case(roster_ae=508), self.run_case(roster_ae=200))

    def test_acceleration_clamps_to_target_but_integer_sum_wraps_first(self):
        self.assertEqual(self.run_case(current_amplitude=3999), 4000)
        self.assertEqual(self.run_case(current_amplitude=2147483647, selected_amplitude=2147483647), -2147483359)

    def test_near_zero_braking_stops_before_subtracting(self):
        self.assertEqual(self.run_case(current_amplitude=1, selected_amplitude=-1), 0)


if __name__ == '__main__': unittest.main()
