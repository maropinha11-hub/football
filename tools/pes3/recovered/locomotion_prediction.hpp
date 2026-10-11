#pragma once
// Recovered 01854F20 chase prediction and predicate part of 017D5990.
// Forecast positions and selected other-player distance are owned inputs.
// Explicit finite host binary32 profiles; not a complete PS2 FPU model.
#include <cmath>
#include <cstdint>
#include <cstring>
#include "locomotion_direction.hpp"
#include "locomotion_speed.hpp"

namespace pes3_motion {
inline float binary32(double number, std::uint8_t chop) {
  float result = static_cast<float>(number);
  if (chop && std::fabs(static_cast<double>(result)) > std::fabs(number)) {
    std::uint32_t bits;
    std::memcpy(&bits, &result, 4); --bits; std::memcpy(&result, &bits, 4);
  }
  return result;
}
struct ForecastSample { float xyz[3]{}; std::int32_t validity = 0; };
struct ChaseInput {
  float player_xz[2]{}, position_divisor = 256;
  std::uint8_t roster_a3 = 0, fpu_rounding = 0, division_rounding = 0, sqrt_rounding = 0;
};
struct ChaseDecision {
  std::int32_t amplitude = 0;
  std::uint16_t sample_index = 0, reserved = 0;
  std::int32_t distance_truncated = 0;
};
inline int predict_chase(const ChaseInput& input, const ForecastSample* samples, unsigned count, ChaseDecision& output) {
  if (!samples || count < 129 || input.fpu_rounding > 1 || input.division_rounding > 1 || input.sqrt_rounding > 1 ||
      !coordinate(input.player_xz[0]) || !coordinate(input.player_xz[1]) ||
      !coordinate(input.position_divisor) || input.position_divisor <= 0) return 0;
  for (unsigned i = 1; i <= 128; ++i) for (float number : samples[i].xyz) if (!coordinate(number)) return 0;
  const int cutoff = (-144 * ((input.roster_a3 >> 2) + 148)) / 183;
  std::uint16_t index = 1;
  for (; index < 128; ++index)
    if (samples[index].validity >= 0 && samples[index].xyz[1] >= cutoff) break;
  const auto dx = binary32(static_cast<double>(input.player_xz[0]) - samples[index].xyz[0], input.fpu_rounding);
  const auto dz = binary32(static_cast<double>(input.player_xz[1]) - samples[index].xyz[2], input.fpu_rounding);
  const auto xx = binary32(static_cast<double>(dx) * dx, input.fpu_rounding);
  const auto zz = binary32(static_cast<double>(dz) * dz, input.fpu_rounding);
  const auto sum = binary32(static_cast<double>(xx) + zz, input.fpu_rounding);
  const auto root = binary32(std::sqrt(static_cast<double>(sum)), input.sqrt_rounding);
  const auto distance = static_cast<std::int32_t>(root);
  const int excess = distance >= 97 ? distance - 96 : 0;
  const auto scaled = binary32(static_cast<double>(excess) * input.position_divisor, input.fpu_rounding);
  const auto amplitude = binary32(static_cast<double>(scaled) / index, input.division_rounding);
  if (!(amplitude >= 0 && amplitude < 2147483648.0f)) return 0;
  ChaseDecision result{};
  result.amplitude = static_cast<std::int32_t>(amplitude);
  result.sample_index = index;
  result.distance_truncated = distance;
  output = result;
  return 1;
}
struct ChaseGateInput {
  std::uint32_t other_squared_distance = 0;
  float ball_axis_2c = 0, prediction_y_7b4 = 0;
  std::uint16_t action_input_heading = 0, body_heading = 0;
  std::uint8_t roster_a3 = 0, reserved[3]{};
};
inline int chase_gate(const ChaseGateInput& input, std::uint8_t& output) {
  if (!coordinate(input.ball_axis_2c) || !coordinate(input.prediction_y_7b4)) return 0;
  std::uint8_t result = 0;
  if (pes3_selection::wrapped_signed(input.other_squared_distance) >= 262144) {
    const int axis = static_cast<std::int32_t>(input.ball_axis_2c);
    const int magnitude = axis < 0 ? -axis : axis;
    const int cutoff = (-64 * ((input.roster_a3 >> 2) + 148)) / 183;
    if ((magnitude >= 2753 || input.prediction_y_7b4 < cutoff) &&
        separation(input.action_input_heading, input.body_heading) / 256 >= 49) result = 1;
  }
  output = result;
  return 1;
}
} // namespace pes3_motion
