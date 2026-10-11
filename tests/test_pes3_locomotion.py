"""Owned API/domain regressions; original-code comparisons are separate tools."""
import ctypes as C
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/pes3'))
import direction_abi as direction
import prediction_abi as prediction
import special_abi as special
import variant_abi as variant
import chain_abi as chain


@unittest.skipUnless(shutil.which('g++'), 'g++ unavailable')
class LocomotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='pes3-locomotion-test-')
        folder = Path(cls.temp.name)
        source = folder / 'motion.cpp'
        source.write_text(direction.SOURCE + prediction.SOURCE + special.SOURCE + variant.SOURCE + chain.SOURCE)
        subprocess.run(['g++', '-std=c++14', '-O0', '-Wall', '-Wextra', '-Werror', '-fno-fast-math',
            '-ffp-contract=off', '-fsanitize=undefined', '-fno-sanitize-recover=all', '-shared', '-fPIC',
            '-I', str(ROOT / 'tools/pes3/recovered'), str(source), '-o', str(folder / 'motion.so')],
            check=True, capture_output=True)
        cls.lib = C.CDLL(str(folder / 'motion.so'))
        for abi in (direction, prediction, special, variant, chain): abi.configure(cls.lib)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def atomic(self, function, input, output_class, status=0):
        output = output_class.from_buffer_copy(b'\x2a' * C.sizeof(output_class))
        before = bytes(output)
        self.assertEqual(function(C.byref(input), C.byref(output)), status)
        self.assertEqual(bytes(output), before)

    def test_direction_rejects_nonfinite_extreme_delta_and_other_substate(self):
        for value in (math.nan, math.inf, -math.inf, 65537, 1e-40):
            i = direction.Input(substate=16); i.ball_far_xz[0] = value
            self.atomic(self.lib.select_direction, i, direction.Decision)
        i = direction.Input(substate=16); i.ball_far_xz[0] = 32768
        self.atomic(self.lib.select_direction, i, direction.Decision)
        i = direction.Input(substate=15)
        self.atomic(self.lib.select_direction, i, direction.Decision, -1)
        i = direction.Input(substate=16, direction_mask=16)
        self.atomic(self.lib.select_direction, i, direction.Decision)

    def test_direction_body_and_movement_have_distinct_rates(self):
        i = direction.Input(substate=16, ball_heading=16384, direction_mask=1, clip=304)
        i.ball_far_xz[1] = -1000
        out = direction.Decision()
        self.assertEqual(self.lib.select_direction(C.byref(i), C.byref(out)), 1)
        self.assertEqual((out.body_heading, out.movement_heading, out.substate), (384, 768, 1))
        i.clip = 28
        self.assertEqual(self.lib.select_direction(C.byref(i), C.byref(out)), 1)
        self.assertEqual((out.body_heading, out.movement_heading), (384, 384))
        i.clip = 216
        self.assertEqual(self.lib.select_direction(C.byref(i), C.byref(out)), 1)
        self.assertEqual((out.body_heading, out.movement_heading), (0, 0))

    def test_near_distance_truncates_coordinates_before_subtracting_and_wraps(self):
        i = direction.Input(substate=16)
        i.player_xz[:] = (-0.75, -0.75); i.ball_far_xz[:] = (-0.75, -0.75)
        i.ball_near_xz[:] = (0.75, 0.75)
        out = direction.Decision()
        self.assertEqual(self.lib.select_direction(C.byref(i), C.byref(out)), 1)
        self.assertEqual(out.near_squared_distance, 0)
        i.player_xz[:] = (-65536, -65536); i.ball_far_xz[:] = (-65536, -65536)
        i.ball_near_xz[:] = (65536, 65536)
        self.assertEqual(self.lib.select_direction(C.byref(i), C.byref(out)), 1)
        self.assertEqual(out.near_squared_distance, 0)  # 2 * 131072^2 wraps to zero.

    def predict(self, i, samples, count=129):
        out = prediction.Decision()
        self.assertEqual(self.lib.predict_chase(C.byref(i), samples, count, C.byref(out)), 1)
        return out

    def samples(self):
        samples = (prediction.Sample * 129)()
        for sample in samples: sample.validity = -1; sample.xyz[:] = (1000, -1000, 0)
        return samples

    def test_chase_deadzone_and_unconditional_last_sample(self):
        i = prediction.Input(position_divisor=256)
        samples = self.samples(); samples[0].xyz[0] = math.nan
        samples[128].xyz[:] = (97, -1000, 0)
        out = self.predict(i, samples)
        self.assertEqual((out.sample_index, out.amplitude, out.distance_truncated), (128, 2, 97))
        samples[1].xyz[:] = (96.75, 0, 0); samples[1].validity = 0
        out = self.predict(i, samples)
        self.assertEqual((out.sample_index, out.amplitude, out.distance_truncated), (1, 0, 96))
        samples[1].xyz[0] = 97
        self.assertEqual(self.predict(i, samples).amplitude, 256)

    def test_chase_checks_count_profiles_and_sample_domain_atomically(self):
        i = prediction.Input(position_divisor=256); samples = self.samples()
        out = prediction.Decision.from_buffer_copy(b'\x2a' * C.sizeof(prediction.Decision))
        for count in (0, 128):
            before = bytes(out)
            self.assertEqual(self.lib.predict_chase(C.byref(i), samples, count, C.byref(out)), 0)
            self.assertEqual(bytes(out), before)
        for field, value in (('position_divisor', 0), ('fpu_rounding', 2), ('division_rounding', 2), ('sqrt_rounding', 2)):
            bad = prediction.Input.from_buffer_copy(bytes(i)); setattr(bad, field, value)
            before = bytes(out)
            self.assertEqual(self.lib.predict_chase(C.byref(bad), samples, 129, C.byref(out)), 0)
            self.assertEqual(bytes(out), before)
        samples[1].xyz[1] = math.nan
        before = bytes(out)
        self.assertEqual(self.lib.predict_chase(C.byref(i), samples, 129, C.byref(out)), 0)
        self.assertEqual(bytes(out), before)

    def test_gate_distance_is_signed_and_axis_threshold_truncates(self):
        i = prediction.GateInput(other_squared_distance=262144, ball_axis_2c=2753, action_input_heading=49 * 256)
        out = C.c_uint8()
        self.assertEqual(self.lib.chase_gate(C.byref(i), C.byref(out)), 1); self.assertEqual(out.value, 1)
        for field, value in (('other_squared_distance', 262143), ('other_squared_distance', 0x80000000),
                ('ball_axis_2c', 2752.99), ('action_input_heading', 49 * 256 - 1)):
            bad = prediction.GateInput.from_buffer_copy(bytes(i)); setattr(bad, field, value)
            self.assertEqual(self.lib.chase_gate(C.byref(bad), C.byref(out)), 1); self.assertEqual(out.value, 0)
        i.ball_axis_2c = math.nan; out.value = 42
        self.assertEqual(self.lib.chase_gate(C.byref(i), C.byref(out)), 0); self.assertEqual(out.value, 42)

    def run_special(self, clip=61, **values):
        i = special.Input(); i.common.clip = clip; i.common.initial_amplitude = 8000
        i.common.current_amplitude = 4000; i.common.ball_amplitude = 4000; i.cap_squared_distance = 18497
        i.prediction_y_7cc = -1000
        for n, v in values.items():
            if hasattr(i.common, n): setattr(i.common, n, v)
            else: setattr(i, n, v)
        out = special.Decision()
        self.assertEqual(self.lib.select_special(C.byref(i), C.byref(out)), 1)
        return out

    def test_special_caps_and_restart_differ_from_height_transition(self):
        out = self.run_special(state_flags=1, clip_restart=1, timing_byte=9)
        self.assertEqual((out.decision.requested_clip, out.phase_130, out.writes), (62, 9, 3))
        out = self.run_special(state_flags=0, clip_restart=1, prediction_y_7cc=0, timing_byte=9)
        self.assertEqual((out.decision.requested_clip, out.phase_130, out.writes), (48, 0, 1))
        at = self.run_special(ball_amplitude=2000, cap_squared_distance=18496)
        after = self.run_special(ball_amplitude=2000, cap_squared_distance=18497)
        self.assertEqual(at.decision.selected_amplitude, 2000)
        self.assertGreater(after.decision.selected_amplitude, at.decision.selected_amplitude)

    def test_special_strict_distance_and_wrapped_products(self):
        self.assertEqual(self.run_special(62, state_flags=1, near_squared_distance=82943,
            ball_amplitude=10000).decision.selected_amplitude, 4352)
        self.assertEqual(self.run_special(62, state_flags=1, near_squared_distance=82944).decision.selected_amplitude, 5600)
        self.assertEqual(self.run_special(63, initial_amplitude=2147483647).decision.selected_amplitude, 214748364)
        # Wrapped absolute INT_MIN remains negative, and clears auxiliary134.
        out = self.run_special(current_amplitude=-2147483648, ball_amplitude=0, auxiliary_134=42)
        self.assertEqual((out.decision.auxiliary_134, out.decision.writes & 16), (0, 16))

    def test_special_unsupported_and_invalid_preserve_output(self):
        for clip, status in ((35, -1), (48, -1)):
            i = special.Input(); i.common.clip = clip
            self.atomic(self.lib.select_special, i, special.Decision, status)
        i = special.Input(); i.common.clip = 61; i.prediction_y_7cc = math.inf
        self.atomic(self.lib.select_special, i, special.Decision)

    def run_variant(self, clip, **values):
        i = variant.Input(); i.common.clip = clip; i.common.initial_amplitude = 8000
        i.common.current_amplitude = 8000; i.common.ball_amplitude = 4000; i.configuration_step = 1
        for n, v in values.items():
            if hasattr(i.common, n): setattr(i.common, n, v)
            else: setattr(i, n, v)
        out = variant.Decision()
        self.assertEqual(self.lib.select_variant(C.byref(i), C.byref(out)), 1)
        return out

    def test_variant_clip35_uses_distance_and_encoded_transition(self):
        out = self.run_variant(35, clip_restart=1, current_frame=10, near_squared_distance=102399)
        self.assertEqual((out.decision.selected_amplitude, out.transition_kind, out.encoded_start), (4000, 2, 0))
        out = self.run_variant(35, near_squared_distance=123905, ball_amplitude=10000)
        self.assertEqual((out.decision.selected_amplitude, out.auxiliary_133, out.writes), (11000, 1, 2))

    def test_variant_clip48_preserves_phase_request_and_flag_order(self):
        out = self.run_variant(48, ball_amplitude=4095, timing_byte=7, state_flags=2)
        self.assertEqual((out.decision.requested_clip, out.transition_kind, out.flags_1a0, out.phase_130), (62, 1, 3, 7))
        out = self.run_variant(48, direction_mask=1, current_frame=10.75)
        self.assertEqual((out.decision.requested_clip, out.transition_kind, out.comparison_frame), (47, 1, 10.75))
        self.assertEqual(self.run_variant(48, auxiliary_105=8).decision.change_clip, 0)

    def test_variant_clip864_keeps_714_encoding_and_flag_target(self):
        out = self.run_variant(864, clip_restart=1, flags_1b0=0x4000, roster_ac=50 << 4, amplitude_120=8000)
        self.assertEqual((out.decision.selected_amplitude, out.transition_kind, out.encoded_start), (7063, 2, 714))

    def test_variant_clip28_uses_stat_floors_and_ordinary_acceleration_numerator(self):
        out = self.run_variant(28, current_amplitude=0, amplitude_120=8000, roster_ab=98 << 1,
            roster_cc=86, roster_ac=88 << 4, roster_ae=72 << 2, attribute_12c=4)
        self.assertAlmostEqual(out.animation_rate, 946 / 768, places=6)
        self.assertEqual((out.decision.amplitude_before_speed, out.decision.selected_amplitude), (133, 0))
        self.assertEqual((out.decision.requested_clip, out.transition_kind), (47, 1))

    def test_variant_domain_and_unsupported_preserve_output(self):
        i = variant.Input(); i.common.clip = 61; i.configuration_step = 1
        self.atomic(self.lib.select_variant, i, variant.Decision, -1)
        i.common.clip = 35; i.current_frame = math.nan
        self.atomic(self.lib.select_variant, i, variant.Decision)
        i.current_frame = 0; i.configuration_step = 0
        self.atomic(self.lib.select_variant, i, variant.Decision)

    def test_chain_direction_feeds_both_distance_and_final_amplitude(self):
        i = chain.Input()
        i.direction.substate = i.selection.common.substate = 16
        i.direction.clip = i.selection.common.clip = 62
        i.direction.ball_far_xz[1] = -1000
        i.direction.ball_heading = 16384
        i.selection.common.initial_amplitude = 8000
        i.selection.common.ball_amplitude = 4000
        i.selection.common.state_flags = 1
        # Supplied near/difference fields are superseded by the direction result.
        i.selection.near_squared_distance = 0xffffffff
        out = chain.Decision()
        self.assertEqual(self.lib.step_locomotion(C.byref(i), C.byref(out)), 1)
        self.assertEqual((out.direction.body_heading, out.direction.movement_heading), (384, 768))
        self.assertEqual(out.direction.near_squared_distance, 0)
        self.assertEqual((out.decision.selected_amplitude, out.updated_amplitude), (4200, 290))
        i.direction.ball_near_xz[0] = 288  # 288^2 == 82944: strict special branch boundary.
        self.assertEqual(self.lib.step_locomotion(C.byref(i), C.byref(out)), 1)
        self.assertEqual(out.decision.selected_amplitude, 5600)

    def test_chain_inconsistent_fields_and_remaining_clips_are_atomic(self):
        i = chain.Input(); i.direction.substate = i.selection.common.substate = 16
        i.direction.clip = 62; i.selection.common.clip = 63
        self.atomic(self.lib.step_locomotion, i, chain.Decision)
        i.selection.common.clip = 62; i.speed.attribute_124 = 1
        self.atomic(self.lib.step_locomotion, i, chain.Decision)
        i.speed.attribute_124 = 0; i.direction.clip = i.selection.common.clip = 51
        self.atomic(self.lib.step_locomotion, i, chain.Decision, -1)


if __name__ == '__main__': unittest.main()
