// Deterministic controls and contact math shared by training and its checks.
#ifndef FOOTBALL_TRAINING_CONTROL_HPP
#define FOOTBALL_TRAINING_CONTROL_HPP
#include "base/math/vector3.hpp"
#include <cmath>
#include <algorithm>

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

struct View {
  float yaw = 0, headYaw = 0, pitch = -0.12f, movementYaw = 0, bodyYaw = 0;
  float idleLook = 0;
  bool withBall = false, moving = false;
  void reset(float facing) {
    yaw = movementYaw = bodyYaw = facing; headYaw = 0; pitch = -0.12f;
    idleLook = 0; withBall = false; moving = false;
  }
  void update(bool possession, float facing, const Vector3 &move, const Vector3 &look,
              float dt, float sensitivity = 2.1f, float recenter = 1.3f) {
    const bool nextMoving = move.GetLength() > 0.001f;
    if (possession != withBall) {
      // Preserve the view at the transition; never snap the head to a new heading.
      if (possession) { bodyYaw = yaw; headYaw = 0; }
      else { yaw = angle(bodyYaw + headYaw); headYaw = 0; }
      movementYaw = yaw;
      idleLook = 0;
    }
    withBall = possession;
    if (withBall) {
      bodyYaw = angle(bodyYaw + angle(facing - bodyYaw) * (1 - std::exp(-7 * dt)));
      headYaw = limit(headYaw - look.coords[0] * sensitivity * dt, -1.48f, 1.48f);
      // The left-stick frame stays fixed throughout a turn; looking around never steers it.
      if (!nextMoving) movementYaw = bodyYaw;
    } else {
      yaw = angle(yaw - look.coords[0] * sensitivity * dt);
      bodyYaw = yaw;
      movementYaw = yaw;
    }
    pitch = limit(pitch - look.coords[1] * sensitivity * 0.75f * dt, -1.30f, 0.95f);
    if (look.GetLength() > 0.001f) idleLook = 0;
    else {
      idleLook += dt;
      if (withBall && idleLook > 0.45f) {
        const float keep = std::exp(-recenter * dt);
        headYaw *= keep;
        pitch = -0.12f + (pitch + 0.12f) * keep;
      }
    }
    yaw = withBall ? angle(bodyYaw + headYaw) : yaw;
    moving = nextMoving;
  }
  Vector3 movement(const Vector3 &stick) const {
    const Vector3 f = forward(movementYaw);
    const Vector3 right(f.coords[1], -f.coords[0], 0);
    return right * stick.coords[0] + f * stick.coords[1];
  }
};

struct Shot { float speed, elevation; };
inline Shot shot(float charge, float ability, bool chip, bool freeKick) {
  const float p = limit(charge, 0, 1);
  if (chip) return {10 + 12 * p, (34 + 15 * p) * pi / 180};
  const float maximum = 28 + 7 * limit(ability, 0, 1);
  // A firm short press stays low; a long press gains height as well as speed.
  return {11 + (maximum - 11) * std::pow(p, 0.65f),
          (2.5f + (freeKick ? 20.0f : 17.5f) * p * p) * pi / 180};
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
