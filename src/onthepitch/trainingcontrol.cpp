// Body-relative controls shared by the game and controller checks.
#include "trainingcontrol.hpp"

namespace training {
  void View::reset(float facing) {
    yaw = movementYaw = bodyYaw = facing; headYaw = 0; pitch = -0.12f;
    idleLook = 0; withBall = false; moving = false;
    travelYaw = facing; steeringAngle = 0; turnTime = 0;
  }
  void View::update(bool possession, float facing, const Vector3 &move, const Vector3 &look,
              float dt, float sensitivity, float recenter, bool canRepeat) {
    const bool nextMoving = move.GetLength() > 0.001f;
    if (possession != withBall) {
      // Preserve the view at the transition; never snap the head to a new heading.
      if (possession) { bodyYaw = yaw; headYaw = 0; }
      else { yaw = angle(bodyYaw + headYaw); headYaw = 0; }
      movementYaw = yaw;
      travelYaw = bodyYaw; moving = false; turnTime = 0;
      idleLook = 0;
    }
    withBall = possession;
    if (withBall) {
      // Request the actual direction, including a 180-degree reversal. Keep
      // that target through the original turn/touch rather than replacing
      // every stick direction with positive forward motion.
      if (nextMoving) {
        const float requested = std::atan2(-move.coords[0], move.coords[1]);
        if (!moving || std::fabs(angle(requested - steeringAngle)) > 0.02f) {
          travelYaw = angle(bodyYaw + requested);
          steeringAngle = requested;
          turnTime = 0;
        }
        if (std::fabs(requested) < 0.02f) {
          // Forward locks the current front; animated torso sway must not
          // feed back into a straight run or into independent head look.
          travelYaw = bodyYaw;
        } else {
          const float follow = angle(facing - bodyYaw) * (1 - std::exp(-14 * dt));
          bodyYaw = angle(bodyYaw + limit(follow, -6 * dt, 6 * dt));
          turnTime += dt;
          // A held direction becomes relative to the new front once the
          // body completes the previous turn. In particular, held down
          // requests another reversal, instead of chasing a moving 180°.
          if (canRepeat && turnTime >= 0.2f && std::fabs(angle(travelYaw - facing)) < 0.22f &&
              std::fabs(angle(travelYaw - bodyYaw)) < 0.3f) {
            travelYaw = angle(bodyYaw + requested);
            turnTime = 0;
          }
        }
      }
      headYaw = limit(headYaw - look.coords[0] * sensitivity * dt, -1.48f, 1.48f);
      // Forward means the new front; holding right keeps turning to the new
      // right. Head look is excluded from this body-relative reference.
      movementYaw = bodyYaw;
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
  Vector3 View::movement(const Vector3 &stick) const {
    if (withBall) return forward(travelYaw) * stick.GetLength();
    const Vector3 f = forward(movementYaw);
    const Vector3 right(f.coords[1], -f.coords[0], 0);
    return right * stick.coords[0] + f * stick.coords[1];
  }
}
