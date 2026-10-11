#pragma once
// Post-direction branches 28/35/48/864 from 0187866C..0187927C.
// Original integer/float units. Phase/encoded transition requests remain
// distinct from plain animation_change; no pose, native clip or unit guesses.
#include "locomotion_special.hpp"
#include "locomotion_prediction.hpp"

namespace pes3_selection {
enum class TransitionKind : std::uint8_t { None = 0, Phase = 1, Encoded = 2 };
struct VariantInput {
  Input common{};
  std::uint32_t near_squared_distance = 0, flags_1b0 = 0;
  std::int32_t amplitude_120 = 0;
  float current_frame = 0, configuration_step = 1;
  std::uint16_t body_input_difference = 0, roster_ac = 0, roster_ae = 0;
  std::uint8_t roster_ab = 0, roster_cc = 0, attribute_12c = 0;
  std::uint8_t auxiliary_105 = 0, auxiliary_133 = 0, timing_byte = 0;
  std::uint8_t mode_phase_5 = 0, mode_2 = 0, fpu_rounding = 0, division_rounding = 0;
  std::uint16_t reserved = 0;
  std::int32_t profile_flag = 0;
};
struct VariantDecision {
  Decision decision{};
  std::uint32_t flags_1a0 = 0;
  float comparison_frame = 0, animation_rate = 0;
  std::int32_t encoded_start = 0;
  std::uint8_t auxiliary_105 = 0, auxiliary_133 = 0, phase_130 = 0, writes = 0;
  // writes: auxiliary105=1, auxiliary133=2, phase130=4, flags1a0=8, rate138=16.
  TransitionKind transition_kind = TransitionKind::None;
  std::uint8_t reserved[3]{};
};
inline int scale_stat(unsigned value, unsigned floor) {
  return value > floor ? static_cast<int>(100 * (value - floor) / (100 - floor)) : 0;
}
inline std::int32_t variant_brake(const VariantInput& i, std::int32_t target, int divisor) {
  if (i.profile_flag) divisor = divisor * 5 / 6;
  const auto current = i.common.current_amplitude;
  if (current > target) {
    divisor = divisor * 3 / 2;
    if (deceleration_condition(i.mode_phase_5, i.mode_2)) divisor = divisor * 11 / 10;
    const int step = (6400 - 12 * i.common.attribute_124) / divisor;
    if (step >= current) return 0;
    return std::max(wrapped_signed(static_cast<std::int64_t>(current) - step), target);
  }
  const auto changed = wrapped_signed(static_cast<std::int64_t>(current) + (6400 - 12 * i.common.attribute_124) / divisor);
  return std::min(changed, target);
}
inline int select_variant(const VariantInput& input, VariantDecision& output) {
  const auto& c = input.common;
  if (c.direction_mask > 15 || c.chase_gate > 1 || c.clip_restart > 1 ||
      input.fpu_rounding > 1 || input.division_rounding > 1) return 0;
  if (c.clip != 28 && c.clip != 35 && c.clip != 48 && c.clip != 864) return -1;
  if (!pes3_motion::coordinate(input.current_frame) || !std::isfinite(input.configuration_step) ||
      input.configuration_step < 1.0f / 256 || input.configuration_step > 256) return 0;
  VariantDecision result{};
  auto& d = result.decision;
  d.amplitude_before_speed = c.current_amplitude;
  d.substate = c.substate; d.turn_heading = c.turn_heading; d.auxiliary_134 = c.auxiliary_134;
  result.flags_1a0 = c.state_flags;
  result.auxiliary_105 = input.auxiliary_105; result.auxiliary_133 = input.auxiliary_133;
  result.phase_130 = c.phase_130;
  const auto request = [&result, &d](TransitionKind kind, std::uint16_t clip, float frame, int encoded) {
    d.change_clip = 1; d.requested_clip = clip;
    result.transition_kind = kind; result.comparison_frame = frame; result.encoded_start = encoded;
  };
  if (c.clip == 35 || c.clip == 864) {
    if (c.clip_restart) request(TransitionKind::Encoded, 47, 0, c.clip == 864 ? 714 : 0);
    else { result.auxiliary_133 = 1; result.writes |= 2; }
    d.selected_amplitude = c.initial_amplitude;
    if (c.clip == 35) {
      if (input.near_squared_distance < 102400u && !c.direction_mask)
        d.selected_amplitude = std::min(d.selected_amplitude, c.ball_amplitude);
      if (input.near_squared_distance >= 123905u)
        d.selected_amplitude = std::max(c.initial_amplitude, percent(c.ball_amplitude, 110, 100));
    } else if (input.flags_1b0 & 0x4000u) {
      const int scale = scale_stat((input.roster_ac >> 4) & 127, 50);
      d.selected_amplitude = wrapped_signed(static_cast<std::int64_t>(input.amplitude_120) - 640 - 3 * (99 - scale));
    }
  } else if (c.clip == 48) {
    d.selected_amplitude = c.chase_gate ? std::min(c.chase_amplitude, c.initial_amplitude) : c.initial_amplitude;
    if (!c.direction_mask && !input.auxiliary_105 && c.ball_amplitude < 4096) {
      result.auxiliary_105 = 8; result.phase_130 = input.timing_byte;
      result.flags_1a0 |= 1; result.writes |= 1 | 4 | 8;
      request(TransitionKind::Phase, 62, 0, 0);
    } else if (!input.auxiliary_105) {
      const auto threshold = wrapped_signed(static_cast<std::int64_t>(c.initial_amplitude) - 256);
      if (d.selected_amplitude >= threshold && c.current_amplitude >= threshold)
        request(TransitionKind::Phase, 47, input.current_frame, 0);
    }
  } else {
    const int rate_stat = scale_stat((input.roster_ab >> 1) & 127, 40) + scale_stat(input.roster_cc & 127, 20);
    auto rate = input.configuration_step;
    if (rate_stat >= 101) {
      const auto product = pes3_motion::binary32(static_cast<double>(rate) * (rate_stat + 768), input.fpu_rounding);
      rate = pes3_motion::binary32(static_cast<double>(product) / 768, input.division_rounding);
    }
    result.animation_rate = std::max(rate, input.configuration_step); result.writes |= 16;
    const int scale = scale_stat((input.roster_ac >> 4) & 127, 50);
    const auto target = wrapped_signed(static_cast<std::int64_t>(input.amplitude_120) - 640 - 3 * (99 - scale));
    const int divisor = input.attribute_12c + 48 - scale_stat((input.roster_ae >> 2) & 127, 50) / 10;
    d.amplitude_before_speed = variant_brake(input, target, divisor); d.writes |= Amplitude;
    d.selected_amplitude = 0;
    if (input.near_squared_distance < 65536u && !(input.flags_1b0 & 0x4000u) &&
        (!c.direction_mask || input.body_input_difference < 15))
      request(TransitionKind::Phase, 47, input.current_frame, 0);
  }
  output = result;
  return 1;
}
} // namespace pes3_selection
