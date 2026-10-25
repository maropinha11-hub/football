#pragma once
#include "physical_rig.hpp"

namespace football_physics {
// Momentum/support controller with a learned reduced capture-point planner.
// This does not synthesize football skills or replace native locomotion.
class BalanceController {
 public:
  void addImpulse(Vec impulse,Vec torque);
  bool step(float dt,float height,float stance,float speed,bool braced,bool held);
  Vec velocity()const{return correction;}
  Vec lean()const;
  Vec remainingImpulse()const{return scalePoint(disturbance,PhysicalRig::mass);}
  Vec supportOffset()const{return displacement;}
  float risk=0,stepDemand=0,margin=0;
  int phase=0;
 private:
  Vec disturbance{{0,0,0}},angular{{0,0,0}},correction{{0,0,0}};
  Vec committedStep{{0,0,0}};
  Vec displacement{{0,0,0}},hipStrategy{{0,0,0}};
  float stepRemaining=0;
  bool stepArmed=true;
  float failureTime=0;
};
}
