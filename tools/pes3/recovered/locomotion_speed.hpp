#pragma once
// Numeric rewrite of 0187927C..0187930C, including stat scaling and 018A3A60.
// Amplitudes are original integer units per call, not metres per second.
#include <cstdint>

namespace pes3_selection {
struct SpeedInput {
  std::int32_t current_amplitude = 0, selected_amplitude = 0;
  std::uint16_t roster_ae = 0;
  std::uint8_t attribute_124 = 0, mode_phase_5 = 0, mode_2 = 0, reserved[3]{};
  std::int32_t profile_flag = 0;
};
inline std::int32_t wrapped_signed(std::int64_t value) {
  const auto bits = static_cast<std::uint32_t>(value);
  return static_cast<std::int32_t>(bits < 0x80000000u ? bits : static_cast<std::int64_t>(bits) - 0x100000000ll);
}
inline bool deceleration_condition(std::uint8_t phase, std::uint8_t mode) {
  return phase == 1 && mode != 4 && mode != 16;
}
inline std::int32_t step_speed(const SpeedInput& input) {
  const auto current = input.current_amplitude, target = input.selected_amplitude;
  if (target == 0) return current; // Original tail skips the update.
  const int stat = (input.roster_ae >> 2) & 127;
  const int scaled = stat > 50 ? 2 * (stat - 50) : 0;
  int divisor = input.attribute_124 + 22 - scaled / 10;
  if (input.profile_flag) divisor = divisor * 5 / 6;
  const int numerator = 6400 - 12 * input.attribute_124;
  if (current > target) {
    divisor = divisor * 3 / 2;
    if (deceleration_condition(input.mode_phase_5, input.mode_2)) divisor = divisor * 11 / 10;
    // The minimum divisor for this input domain is positive (>= 5).
    const int step = numerator / divisor;
    if (step >= current) return 0;
    const auto changed = wrapped_signed(static_cast<std::int64_t>(current) - step);
    return changed < target ? target : changed;
  }
  const auto changed = wrapped_signed(static_cast<std::int64_t>(current) + numerator / divisor);
  return changed > target ? target : changed;
}
} // namespace pes3_selection
