#pragma once
// Recovered post-direction branches for clips 61/62/63, to 0187927C.
// Helper gate/prediction/restart values and cap-distance are explicit inputs.
#include <algorithm>
#include <cstdint>
#include "locomotion_selection.hpp"
#include "locomotion_direction.hpp"
#include "locomotion_speed.hpp"

namespace pes3_selection {
struct SpecialInput {
  Input common{};
  std::uint32_t near_squared_distance = 0, cap_squared_distance = 0;
  float prediction_y_7cc = 0;
  std::uint8_t roster_a3 = 0, timing_byte = 0, auxiliary_105 = 0, reserved = 0;
};
struct SpecialDecision {
  Decision decision{};
  std::uint8_t auxiliary_105 = 0, phase_130 = 0, writes = 0, reserved = 0;
};
inline std::int32_t percent(std::int32_t value, std::uint32_t multiplier, int divisor) {
  return wrapped_signed(static_cast<std::uint32_t>(value) * multiplier) / divisor;
}
inline int select_special(const SpecialInput& input, SpecialDecision& output) {
  const auto& c = input.common;
  if (c.direction_mask > 15 || c.chase_gate > 1 || c.clip_restart > 1) return 0;
  if (c.clip != 61 && c.clip != 62 && c.clip != 63) return -1;
  if (c.clip == 61 && !pes3_motion::coordinate(input.prediction_y_7cc)) return 0;
  SpecialDecision result{};
  auto& d = result.decision;
  d.amplitude_before_speed = c.current_amplitude;
  d.substate = c.substate;
  d.turn_heading = c.turn_heading;
  d.auxiliary_134 = c.auxiliary_134;
  result.auxiliary_105 = input.auxiliary_105;
  result.phase_130 = c.phase_130;
  if (c.clip == 62 || c.clip == 63) {
    if ((c.state_flags & 1u) && input.near_squared_distance < 82944u) {
      auto target = percent(c.ball_amplitude, 105u, 100);
      if (c.clip == 62) target = std::min(std::max(target, 3328 - 12 * c.attribute_124), 4352 - 12 * c.attribute_124);
      else target = std::max(std::min(target, 2816), 1280);
      d.selected_amplitude = target;
    } else {
      d.selected_amplitude = percent(c.initial_amplitude, c.clip == 62 ? 7u : 5u, 10);
    }
  } else {
    auto difference = wrapped_signed(static_cast<std::int64_t>(c.current_amplitude) - c.ball_amplitude);
    if (difference <= 0) difference = wrapped_signed(-static_cast<std::int64_t>(difference));
    if (difference < 1025) { d.auxiliary_134 = 0; d.writes |= Auxiliary; }
    auto target = c.direction_mask && c.chase_gate ? c.chase_amplitude
      : std::max(percent(c.current_amplitude, 90u, 100), 4352 - 12 * c.attribute_124);
    target = std::max(target, percent(c.ball_amplitude, 9u, 10));
    target = std::max(target, 2048);
    target = std::min(target, percent(c.initial_amplitude, 9u, 10));
    d.selected_amplitude = input.cap_squared_distance <= 18496u ? std::min(target, c.ball_amplitude) : target;
    const auto request = [&result, &d](std::uint16_t clip) {
      d.requested_clip = clip; d.change_clip = 1; d.refresh_window = 4;
      result.auxiliary_105 = 8; result.writes |= 1;
    };
    const int threshold = (-64 * ((input.roster_a3 >> 2) + 148)) / 183;
    if (input.prediction_y_7cc > static_cast<float>(threshold) && !(c.state_flags & 1u)) request(48);
    else if (c.clip_restart) {
      result.phase_130 = input.timing_byte; result.writes |= 2;
      request(62);
    }
  }
  output = result;
  return 1;
}
} // namespace pes3_selection
