#pragma once

#include "../../../pes3/native_pose.hpp"

// Small, deterministic adaptations of the existing native action clips. These
// are procedural offsets, not captured animations or a learned ragdoll policy.
// The layer deliberately does not own roots, legs, ball contact or physics.
namespace football_situations {

enum class ActionKind { None=0, Pass=1, Shot=2, Cross=3, Header=4, Control=5 };

struct Context {
  ActionKind kind=ActionKind::None;
  pes3::Point direction{{0,-1,0}}; // Body-local +X right, -Y forward.
  pes3::Point incoming{{0,0,0}}; // Ball velocity relative to the player, in body axes.
  pes3::Point ball{{0,-.35f,-.85f}}; // Offset from the native pelvis.
  float speed=0, power=0, pressure=0, signedTurn=0;
  float phase=0, contactPhase=.5f, difficulty=0;
  float trunkGain=1, armGain=1, followThroughGain=1;
  int supportSide=-1;
  unsigned pattern=0; // Thirty-two contextual curves; the catalog restricts eligibility per action.
  bool rightFoot=true, contactMade=false, preserveHead=true, enabled=true;
};

struct ActionMetrics {
  ActionKind kind=ActionKind::None; // Last action while its offsets fade.
  float torsoBend=0, torsoTwist=0, shoulderAmplitude=0;
  float torsoAngle=0, armsAngle=0;
  float angularRate=0, difficulty=0, phase=0, weight=0;
};

// This reception layer changes arms only: torso/head/contact chains and legs
// keep their authored transforms. It is sampled by contact and render alike.
void adaptChestArms(std::array<pes3::Rotation,7> &pose,float phase,float contact,
                    float duration,float speed,float incomingSide);

class ActionLayer {
 public:
  void reset();
  // Exactly once per simulation tick. All state has fixed size; this does not
  // allocate, sample clips, apply impulses or change an animation's cadence.
  // kind=None fades to locomotion; enabled=false explicitly resets/disables.
  void step(const Context &context,float dt=.01f);
  // Evaluate from a fresh native pose. Repeated evaluation within one tick is
  // idempotent; neither the filter nor its metrics advance here. Pelvis and leg
  // rotations (0,7..12) are left byte-identical. A header changes arms only.
  // For other actions preserveHead retains head orientation, while the native
  // contact solver must still run afterwards against the changed torso skin.
  void evaluate(const Context &context,const pes3::NativeBind &bind,float scale,
                pes3::NativeRotations &pose,pes3::Point pelvis) const;
  const ActionMetrics &metrics() const { return metrics_; }

 private:
  std::array<pes3::Point,7> offset_{};
  std::array<pes3::Point,7> velocity_{};
  ActionKind kind_=ActionKind::None;
  ActionMetrics metrics_{};
};

} // namespace football_situations
