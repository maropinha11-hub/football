#pragma once
#include "physical_rig.hpp"

namespace football_physics {
// Bullet 3.25 rigid bodies and joint constraints, owned by one training actor.
class ArticulatedBody {
 public:
  ArticulatedBody();
  ~ArticulatedBody();
  void start(const pes3::NativeBind &bind,float scale,const Pose &pose,Vec pelvis,Vec velocity,Vec impulse,Vec lever,bool tracking=false);
  void release(const pes3::NativeBind &bind,float scale,const Pose &pose,Vec pelvis,Vec velocity,Vec impulse,Vec lever);
  void track(const pes3::NativeBind &bind,float scale,const Pose &target,Vec pelvis,float dt,Vec impulse,Pose &output,Metrics &metrics);
  void impulse(Vec value,Vec lever);
  void step(float dt,Pose &pose,Vec &pelvis,Metrics &metrics);
  // Separate experimental path: all links, including root and shoes, have
  // mass. References drive internal torques, never transforms or root forces.
  void motor(const pes3::NativeBind &bind,float scale,const Pose &target,Vec initialPelvis,
             Vec desiredVelocity,float dt,Vec impulse,Pose &pose,Vec &pelvis,Metrics &metrics,
             const float *residual=nullptr,bool supportFeedback=true,const float *actions=nullptr);
  void motorObservation(float *features)const;
  static constexpr unsigned motorFeatures=12,motorActions=36;
  static constexpr unsigned fullFeatures=148;
  void fullObservation(const Pose &reference,Vec command,float phase,const float *previousActions,float *features)const;
  // Read-only outcome of an isolated copy, used to verify the tangent-space
  // dynamics model against Bullet before accepting its torque controller.
  static std::array<float,3> validateDynamics(const pes3::NativeBind &bind,unsigned joint,unsigned axis,float torque);
 private:
  struct World;
  std::unique_ptr<World> state;
  unsigned builds=0;
};
}
