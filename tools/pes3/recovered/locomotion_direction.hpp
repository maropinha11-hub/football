#pragma once
// Owned direction decision from 018783B0..0187866C plus exact quantized helpers.
// Selected host binary32 subtraction + truncation; original internal units.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include "locomotion_tables.hpp"

namespace pes3_motion {
static_assert(sizeof(float) == 4 && std::numeric_limits<float>::is_iec559, "binary32 required");
struct DirectionInput {
  float player_xz[2]{}, ball_far_xz[2]{}, ball_near_xz[2]{};
  std::uint16_t body_heading = 0, movement_heading = 0, ball_heading = 0;
  std::uint16_t turn_heading = 0, clip = 0, substate = 16;
  std::uint32_t direction_mask = 0;
};
struct DirectionDecision {
  std::uint32_t near_squared_distance = 0;
  std::uint16_t target_heading = 0, body_heading = 0, movement_heading = 0, substate = 0;
  std::uint16_t ball_heading_span = 0, body_input_difference = 0, body_target_difference = 0;
  std::uint16_t action_input_heading = 0;
};
inline std::uint16_t separation(std::uint16_t a, std::uint16_t b) {
  const auto delta = static_cast<std::uint16_t>(a - b);
  return delta > 32768 ? static_cast<std::uint16_t>(65536u - delta) : delta;
}
inline std::uint16_t turn_towards(std::uint16_t target, std::uint16_t current, std::uint16_t limit) {
  const auto delta = static_cast<std::uint16_t>(target - current);
  if (delta < 32768) return limit >= delta ? target : static_cast<std::uint16_t>(current + limit);
  const auto backward = static_cast<std::uint16_t>(65536u - delta);
  return limit >= backward ? target : static_cast<std::uint16_t>(current - limit);
}
inline std::uint16_t action_heading(std::uint32_t mask, std::uint16_t body, std::uint16_t remembered, std::uint16_t clip) {
  if (mask) return input_headings[mask]; // Caller validates 0..15.
  return clip == 37 || clip == 38 || clip == 598 || clip == 599
    ? remembered : static_cast<std::uint16_t>((body + 4096u) & 0xe000u);
}
inline std::uint16_t direction_from_axes(std::int32_t a0, std::int32_t a1) {
  const auto x = a0 < 0 ? -a0 : a0, y = a1 < 0 ? -a1 : a1;
  if (x == 0 && y == 0) return 0;
  const auto angle = angles[(std::min(x, y) << 8) / std::max(x, y)];
  if (a1 >= 0) {
    if (a0 >= 0) return y < x ? 16384 - angle : angle;
    return y < x ? 49152 + angle : static_cast<std::uint16_t>(65536 - angle);
  }
  if (a0 >= 0) return y < x ? 16384 + angle : 32768 - angle;
  return y < x ? 49152 - angle : 32768 + angle;
}
inline bool coordinate(float number) {
  return std::isfinite(number) && std::fabs(number) <= 65536 &&
    (number == 0 || std::fpclassify(number) == FP_NORMAL);
}
inline std::uint32_t squared_distance(float x, float z, float other_x, float other_z) {
  const auto dx = static_cast<std::int64_t>(static_cast<std::int32_t>(x)) - static_cast<std::int32_t>(other_x);
  const auto dz = static_cast<std::int64_t>(static_cast<std::int32_t>(z)) - static_cast<std::int32_t>(other_z);
  return static_cast<std::uint32_t>(dx * dx) + static_cast<std::uint32_t>(dz * dz);
}
inline int select_direction(const DirectionInput& input, DirectionDecision& output) {
  if (input.direction_mask > 15) return 0;
  for (unsigned axis = 0; axis < 2; ++axis)
    if (!coordinate(input.player_xz[axis]) || !coordinate(input.ball_far_xz[axis]) || !coordinate(input.ball_near_xz[axis])) return 0;
  const volatile float fx = input.ball_far_xz[0] - input.player_xz[0];
  const volatile float fz = input.ball_far_xz[1] - input.player_xz[1];
  const auto dx = static_cast<std::int32_t>(fx), dz = static_cast<std::int32_t>(fz);
  if (dx < -32767 || dx > 32767 || dz < -32767 || dz > 32767) return 0;
  if (input.substate != 16) return -1;
  auto target = direction_from_axes(-dz, dx);
  auto span = separation(target, input.ball_heading);
  const auto requested = action_heading(input.direction_mask, input.body_heading, input.turn_heading, input.clip);
  bool adjusted = false;
  if (span <= 12288) {
    const auto movement_ball = separation(input.movement_heading, input.ball_heading);
    const bool target_side = static_cast<std::uint16_t>(target - input.movement_heading) <= 32768;
    const bool ball_side = static_cast<std::uint16_t>(input.ball_heading - input.movement_heading) <= 32768;
    if (movement_ball <= 3072 || target_side != ball_side) {
      const auto intermediate = turn_towards(requested, target, 2048);
      target = turn_towards(intermediate, target, span / 2);
      adjusted = true;
    }
  }
  if (!adjusted && span <= 8192) {
    span = std::min<std::uint16_t>(span, 2048);
    target = turn_towards(input.ball_heading, target, span / 2);
  }
  DirectionDecision result{};
  result.target_heading = target;
  result.body_heading = input.body_heading;
  result.movement_heading = input.movement_heading;
  result.substate = separation(input.body_heading, target) / 256 >= 32 ? 1 : input.substate;
  result.near_squared_distance = squared_distance(input.player_xz[0], input.player_xz[1], input.ball_near_xz[0], input.ball_near_xz[1]);
  result.ball_heading_span = span;
  result.body_input_difference = separation(input.body_heading, requested) / 256;
  result.body_target_difference = separation(input.body_heading, target);
  result.action_input_heading = requested;
  switch (input.clip) {
    case 48: case 28: case 29: case 30: case 33: case 32: case 31:
      result.body_heading = turn_towards(target, input.body_heading, 384);
      result.movement_heading = result.body_heading;
      break;
    case 216: case 215: case 214: case 213: case 56: case 54: case 613: break;
    default:
      result.body_heading = turn_towards(target, input.body_heading, 384);
      result.movement_heading = turn_towards(target, input.movement_heading, 768);
  }
  output = result;
  return 1;
}
} // namespace pes3_motion
