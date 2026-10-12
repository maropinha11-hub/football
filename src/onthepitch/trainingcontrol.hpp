// Deterministic controls and contact math shared by training and its checks.
#ifndef FOOTBALL_TRAINING_CONTROL_HPP
#define FOOTBALL_TRAINING_CONTROL_HPP
#include "base/math/vector3.hpp"
#include <cmath>
#include <algorithm>
#include <string>

namespace training {
using blunted::Vector3;
constexpr float pi = 3.14159265358979323846f;
inline float limit(float value, float low, float high) { return std::max(low, std::min(high, value)); }
inline float angle(float value) { return std::atan2(std::sin(value), std::cos(value)); }
inline Vector3 forward(float yaw) { return Vector3(std::cos(yaw), std::sin(yaw), 0); }
inline Vector3 radialStick(const Vector3 &value, float deadzone) {
  const float length = value.GetLength();
  if (length <= deadzone) return Vector3(0);
  return value.GetNormalized(0) * limit((length - deadzone) / (1 - deadzone), 0, 1);
}

// Continuous cross-axis correction preserves diagonal control and analog speed.
inline Vector3 movementStick(const Vector3 &value, float deadzone) {
  Vector3 result = radialStick(value, deadzone);
  const float speed = result.GetLength();
  const int major = std::fabs(result.coords[0]) > std::fabs(result.coords[1]) ? 0 : 1;
  const int minor = 1 - major;
  const float cross = std::max(0.0f, std::fabs(result.coords[minor]) - std::fabs(result.coords[major]) * 0.08f) / 0.92f;
  result.coords[minor] = std::copysign(cross, result.coords[minor]);
  return result.GetNormalized(0) * speed;
}
inline float shotCharge(int held_ms) { return limit((held_ms - 40) / 480.0f, 0, 1); }
// Brake into a sharp cut while the last touch still carries the ball away.
inline float turnSpeed(float requested, float ballAlignment, float ballSpeed) {
  return ballSpeed > 1.0f && ballAlignment < -0.25f ? std::min(requested, 1.8f) : requested;
}
// Apply the cut at the accepted foot contact, after reception/error blends.
// Otherwise old momentum can send the ball forward after a backwards touch.
inline Vector3 finishControlTouch(Vector3 touch, const Vector3 &oldBall,
                                 Vector3 direction, float speed) {
  direction = direction.Get2D().GetNormalized(0);
  if (speed > 0.1f && direction.GetLength() > 0.5f &&
      (oldBall.Get2D().GetNormalized(0).GetDotProduct(direction) < -0.25f ||
       touch.Get2D().GetNormalized(0).GetDotProduct(direction) < -0.25f)) {
    const Vector3 cut = direction * std::min(2.5f, speed);
    touch.coords[0] = cut.coords[0];
    touch.coords[1] = cut.coords[1];
  }
  return touch;
}
// Baseline training player: right-footed, with a useful but less precise left foot.
inline float controlQuality(const std::string &bodypart) {
  return bodypart == "left_foot" || bodypart == "left_lowerleg" ? 0.72f : 1.0f;
}

struct View {
  float yaw = 0, headYaw = 0, pitch = -0.12f, movementYaw = 0, bodyYaw = 0;
  float idleLook = 0;
  float travelYaw = 0, steeringAngle = 0, turnTime = 0;
  bool withBall = false, moving = false;
  void reset(float facing);
  void update(bool possession, float facing, const Vector3 &move, const Vector3 &look,
              float dt, float sensitivity = 2.1f, float recenter = 1.3f, bool canRepeat = true);
  Vector3 movement(const Vector3 &stick) const;
};

struct Shot { float speed, elevation; };
inline Shot shot(float charge, float ability, bool chip, bool freeKick) {
  const float p = limit(charge, 0, 1);
  if (chip) return {10 + 12 * p, (34 + 15 * p) * pi / 180};
  const float maximum = 28 + 7 * limit(ability, 0, 1);
  // A firm short press stays low; a long press gains height as well as speed.
  return {11 + (maximum - 11) * std::pow(p, 0.65f),
          (2.5f + (freeKick ? 20.0f : 17.5f) * std::pow(p, 1.35f)) * pi / 180};
}

// Preserve leg lengths and the animated knee's bend plane; clamp unreachable targets.
struct LegPose { Vector3 knee, ankle; };
inline LegPose legPose(const Vector3 &hip, const Vector3 &knee, const Vector3 &ankle, const Vector3 &target) {
  const float upper = (knee - hip).GetLength(), lower = (ankle - knee).GetLength();
  const Vector3 axis = (target - hip).GetNormalized(Vector3(0, 0, -1));
  const float distance = limit((target - hip).GetLength(), std::fabs(upper - lower) + 0.001f, upper + lower - 0.001f);
  const float along = (upper * upper + distance * distance - lower * lower) / (2 * distance);
  const float across = std::sqrt(std::max(0.0f, upper * upper - along * along));
  Vector3 bend = knee - hip - axis * (knee - hip).GetDotProduct(axis);
  const Vector3 fallback = std::fabs(axis.coords[1]) < 0.9f ? Vector3(0, -1, 0) : Vector3(1, 0, 0);
  bend = bend.GetNormalized((fallback - axis * fallback.GetDotProduct(axis)).GetNormalized(Vector3(1, 0, 0)));
  return {hip + axis * along + bend * across, hip + axis * distance};
}

struct Contact { bool hit = false; float time = 1; Vector3 point, normal; };
inline Vector3 closest(const Vector3 &p, const Vector3 &a, const Vector3 &b) {
  const Vector3 ab = b - a;
  return a + ab * limit((p - a).GetDotProduct(ab) / std::max(ab.GetDotProduct(ab), 0.000001f), 0, 1);
}
// Sweep a sphere against a capsule. The radius already includes the ball radius.
inline Contact sweep(const Vector3 &from, const Vector3 &to, const Vector3 &a,
                     const Vector3 &b, float radius) {
  Contact hit;
  const Vector3 delta = to - from;
  const Vector3 offset = from - closest(from, a, b);
  if (offset.GetLength() < radius) {
    hit.hit = true; hit.time = 0;
    hit.normal = offset.GetNormalized((-delta).GetNormalized(Vector3(1, 0, 0)));
    hit.point = closest(from, a, b) + hit.normal * radius;
    return hit;
  }
  auto sphere = [&](const Vector3 &center) {
    const Vector3 oc = from - center;
    const float aa = delta.GetDotProduct(delta), bb = oc.GetDotProduct(delta);
    const float cc = oc.GetDotProduct(oc) - radius * radius;
    const float disc = bb * bb - aa * cc;
    if (aa > 0.0000001f && disc >= 0) {
      const float t = (-bb - std::sqrt(disc)) / aa;
      if (t >= 0 && t <= hit.time) {
        hit.hit = true; hit.time = t; hit.point = from + delta * t;
        hit.normal = (hit.point - center).GetNormalized(Vector3(1, 0, 0));
      }
    }
  };
  sphere(a); sphere(b);
  const Vector3 axis = b - a;
  const float length2 = axis.GetDotProduct(axis);
  if (length2 > 0.000001f) {
    const Vector3 oc = from - a;
    const float da = delta.GetDotProduct(axis), oa = oc.GetDotProduct(axis);
    const Vector3 d = delta - axis * (da / length2), o = oc - axis * (oa / length2);
    const float aa = d.GetDotProduct(d), bb = o.GetDotProduct(d);
    const float disc = bb * bb - aa * (o.GetDotProduct(o) - radius * radius);
    if (aa > 0.0000001f && disc >= 0) {
      const float t = (-bb - std::sqrt(disc)) / aa, axial = oa + t * da;
      if (t >= 0 && t <= hit.time && axial >= 0 && axial <= length2) {
        hit.hit = true; hit.time = t; hit.point = from + delta * t;
        hit.normal = (hit.point - closest(hit.point, a, b)).GetNormalized(Vector3(1, 0, 0));
      }
    }
  }
  return hit;
}
inline Vector3 rebound(const Vector3 &velocity, const Vector3 &normal, float restitution) {
  const float inward = velocity.GetDotProduct(normal);
  if (inward >= 0) return velocity;
  const Vector3 tangent = velocity - normal * inward;
  return tangent * 0.82f - normal * inward * restitution;
}
}
#endif
