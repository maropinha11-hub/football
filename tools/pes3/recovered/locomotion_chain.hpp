#pragma once
// Composes the recovered direction -> selected dispatch -> speed segment.
// Explicit numeric helper boundaries; no memory, native units, action guesses
// or implicit fallback for the remaining special paths.
#include "locomotion_variants.hpp"

namespace pes3_selection {
struct ChainInput {
  pes3_motion::DirectionInput direction{};
  VariantInput selection{};
  std::uint32_t cap_squared_distance = 0;
  float prediction_y_7cc = 0;
  std::uint8_t roster_a3 = 0, reserved[3]{};
  SpeedInput speed{};
};
struct ChainDecision {
  pes3_motion::DirectionDecision direction{};
  Decision decision{};
  std::int32_t updated_amplitude = 0;
  std::uint32_t flags_1a0 = 0;
  float comparison_frame = 0;
  std::int32_t encoded_start = 0;
  float animation_rate = 0;
  std::uint8_t auxiliary_105 = 0, auxiliary_133 = 0, phase_130 = 0, writes = 0;
  // 0 none, 1 plain change+refresh, 2 phase, 3 encoded start.
  std::uint8_t transition_kind = 0, reserved[3]{};
};
inline int step_locomotion(const ChainInput& input, ChainDecision& output) {
  const auto& original = input.selection.common;
  if (input.direction.clip != original.clip || input.direction.substate != original.substate ||
      input.direction.body_heading != original.body_heading || input.direction.movement_heading != original.movement_heading ||
      input.direction.turn_heading != original.turn_heading || input.direction.direction_mask != original.direction_mask ||
      input.speed.attribute_124 != original.attribute_124 || input.speed.roster_ae != input.selection.roster_ae ||
      input.speed.mode_phase_5 != input.selection.mode_phase_5 || input.speed.mode_2 != input.selection.mode_2 ||
      input.speed.profile_flag != input.selection.profile_flag) return 0;
  ChainDecision result{};
  int status = pes3_motion::select_direction(input.direction, result.direction);
  if (status != 1) return status;
  auto v = input.selection;
  v.near_squared_distance = result.direction.near_squared_distance;
  v.body_input_difference = result.direction.body_input_difference;
  v.common.body_heading = result.direction.body_heading;
  v.common.movement_heading = result.direction.movement_heading;
  v.common.substate = result.direction.substate;
  result.flags_1a0 = original.state_flags;
  result.auxiliary_105 = v.auxiliary_105; result.auxiliary_133 = v.auxiliary_133;
  result.phase_130 = original.phase_130;
  if (original.clip == 61 || original.clip == 62 || original.clip == 63) {
    SpecialInput s{}; s.common = v.common;
    s.near_squared_distance = v.near_squared_distance; s.cap_squared_distance = input.cap_squared_distance;
    s.prediction_y_7cc = input.prediction_y_7cc; s.roster_a3 = input.roster_a3;
    s.timing_byte = v.timing_byte; s.auxiliary_105 = v.auxiliary_105;
    SpecialDecision d{}; status = select_special(s, d);
    if (status != 1) return status;
    result.decision = d.decision; result.auxiliary_105 = d.auxiliary_105; result.phase_130 = d.phase_130;
    result.writes = (d.writes & 1) | ((d.writes & 2) << 1);
    result.transition_kind = d.decision.change_clip ? 1 : 0;
  } else if (original.clip == 28 || original.clip == 35 || original.clip == 48 || original.clip == 864) {
    VariantDecision d{}; status = select_variant(v, d);
    if (status != 1) return status;
    result.decision = d.decision; result.flags_1a0 = d.flags_1a0;
    result.comparison_frame = d.comparison_frame; result.encoded_start = d.encoded_start;
    result.animation_rate = d.animation_rate; result.auxiliary_105 = d.auxiliary_105;
    result.auxiliary_133 = d.auxiliary_133; result.phase_130 = d.phase_130; result.writes = d.writes;
    result.transition_kind = d.decision.change_clip ? static_cast<std::uint8_t>(d.transition_kind) + 1 : 0;
  } else {
    status = static_cast<int>(select(v.common, result.decision));
    if (status != 1) return status;
    result.transition_kind = result.decision.change_clip ? 1 : 0;
    if (original.clip == 47) {
      if (!pes3_motion::coordinate(v.configuration_step) || v.configuration_step < 1.0f/256 ||
          v.configuration_step > 256 || v.fpu_rounding > 1 || v.division_rounding > 1) return 0;
      const int stat = scale_stat((v.roster_ab >> 1) & 127, 40) + scale_stat(v.roster_cc & 127, 20);
      auto rate = v.configuration_step;
      if (stat >= 101) {
        const auto product = pes3_motion::binary32(static_cast<double>(rate) * (stat + 768), v.fpu_rounding);
        rate = pes3_motion::binary32(static_cast<double>(product) / 768, v.division_rounding);
      }
      const auto minimum = pes3_motion::binary32(static_cast<double>(1.1f) * v.configuration_step, v.fpu_rounding);
      result.animation_rate = std::max(rate, minimum); result.writes |= 16;
    }
  }
  auto speed = input.speed;
  speed.current_amplitude = result.decision.amplitude_before_speed;
  speed.selected_amplitude = result.decision.selected_amplitude;
  result.updated_amplitude = step_speed(speed);
  output = result;
  return 1;
}
} // namespace pes3_selection
