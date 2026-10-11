#pragma once
// Semantic common decision of PES action 1/substate 16, original 018790E8..0187927C.
// Original integer amplitudes and unsigned-16 headings; no unit conversion,
// player pointers, clip poses, helper stubs or native action-number assumptions.
#include <cstdint>

namespace pes3_selection {
enum Write : std::uint8_t {
  Frame = 1, Amplitude = 2, Substate = 4, TurnHeading = 8, Auxiliary = 16
};
enum class Status : int { Invalid = 0, Selected = 1, SpecialClip = -1 };

struct Input {
  std::int32_t initial_amplitude = 0, current_amplitude = 0, ball_amplitude = 0, chase_amplitude = 0;
  std::uint32_t state_flags = 0, direction_mask = 0;
  std::uint16_t body_heading = 0, movement_heading = 0, clip = 0, substate = 0, turn_heading = 0;
  std::uint8_t player_id = 0, context_player = 0, attribute_124 = 0, phase_130 = 0, auxiliary_134 = 0;
  std::uint8_t chase_gate = 0, clip_restart = 0, reserved[3]{};
};
struct Decision {
  std::int32_t selected_amplitude = 0, amplitude_before_speed = 0;
  float frame_override = 0;
  std::uint16_t substate = 0, turn_heading = 0, requested_clip = 0, reserved16 = 0;
  std::uint32_t start_frame = 0;
  std::uint8_t auxiliary_134 = 0, change_clip = 0, refresh_window = 0, writes = 0;
  std::uint32_t reserved32 = 0;
};
inline bool special_clip(std::uint16_t clip) {
  switch (clip) {
    case 28: case 35: case 48: case 49: case 51: case 52: case 54: case 56: case 61:
    case 62: case 63: case 213: case 214: case 215: case 216: case 864: return true;
    default: return false;
  }
}
inline std::uint16_t separation(std::uint16_t a, std::uint16_t b) {
  const std::uint16_t delta = static_cast<std::uint16_t>(a - b);
  return delta > 32768 ? static_cast<std::uint16_t>(65536u - delta) : delta;
}
inline std::int32_t scaled_threshold(std::int32_t initial) {
  // SLL/SUBU wrap to 32 bits before the original signed divide by ten.
  const std::uint32_t raw = static_cast<std::uint32_t>(initial) * 7u;
  const std::int64_t value = raw < 0x80000000u ? raw : static_cast<std::int64_t>(raw) - 0x100000000ll;
  return static_cast<std::int32_t>(value / 10);
}
inline Status select(const Input& input, Decision& output) {
  if (input.direction_mask > 15 || input.chase_gate > 1 || input.clip_restart > 1) return Status::Invalid;
  if (special_clip(input.clip)) return Status::SpecialClip;
  Decision result{};
  result.amplitude_before_speed = input.current_amplitude;
  result.substate = input.substate;
  result.turn_heading = input.turn_heading;
  result.auxiliary_134 = input.auxiliary_134;
  if (input.clip == 47 && input.clip_restart) {
    result.frame_override = 24;
    result.writes |= Frame;
  }
  const auto request = [&result](std::uint16_t clip, std::uint32_t frame) {
    result.change_clip = 1;
    result.requested_clip = clip;
    result.start_frame = frame;
    result.refresh_window = 4;
  };
  if ((input.state_flags & 1u) && input.player_id == input.context_player) {
    result.auxiliary_134 = 0;
    result.writes |= Auxiliary;
    result.selected_amplitude = input.ball_amplitude;
    if (result.selected_amplitude < 5888 - 12 * input.attribute_124) request(61, 0);
  } else {
    bool common = true;
    if (!input.direction_mask || input.chase_gate) {
      result.selected_amplitude = input.chase_amplitude < input.initial_amplitude
        ? input.chase_amplitude : input.initial_amplitude;
      if (result.selected_amplitude < scaled_threshold(input.initial_amplitude)) {
        request(61, 0);
        common = false;
      }
    }
    if (common) {
      result.selected_amplitude = input.initial_amplitude;
      const auto angle = separation(input.body_heading, input.movement_heading) / 256u;
      if ((!input.phase_130 && input.current_amplitude < 1024) || angle >= 80) {
        request(47, 5);
        result.turn_heading = input.body_heading;
        result.substate = 55;
        result.writes |= TurnHeading | Substate;
        if (angle >= 80) {
          result.amplitude_before_speed = 0;
          result.writes |= Amplitude;
        }
      }
    }
  }
  output = result;
  return Status::Selected;
}
} // namespace pes3_selection
