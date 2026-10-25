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
 private:
  struct World;
  std::unique_ptr<World> state;
  unsigned builds=0;
};
}
