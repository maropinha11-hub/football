#pragma once
#include "physical_rig.hpp"
namespace football_physics {
// Quasi-static motor/ground resistance to an opposing shirt force. Forces
// still feed the reciprocal impulse and balance solvers. This only reduces
// intended locomotion; it does not move an actor or alter a ball contact.
inline Vec contactVelocity(Vec desired,Vec force,bool braced){
  const float speed=length(desired);if(speed<1e-6f)return desired;
  const Vec direction=scalePoint(desired,1/speed);
  const float opposing=std::max(0.f,-dotPoint(force,direction));
  const float unsupported=std::max(0.f,opposing-(braced?180.f:0.f));
  const float reduction=unsupported/(PhysicalRig::mass*2.5f);
  return scalePoint(direction,std::max(0.f,speed-reduction));
}
}
