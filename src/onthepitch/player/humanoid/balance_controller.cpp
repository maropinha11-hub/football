#include "balance_controller.hpp"

namespace football_physics {
void BalanceController::addImpulse(Vec impulse,Vec torque){
  impulse[2]=0;
  disturbance=capped(addPoint(disturbance,scalePoint(impulse,1/PhysicalRig::mass)),5.f);
  // Most of a torso impact is transmitted through the planted lower body.
  // Keep the residual rotation separate from the translational disturbance.
  angular=capped(addPoint(angular,scalePoint(torque,.12f/14.f)),1.5f);
}
bool BalanceController::step(float dt,float height,float stance,float speed,bool braced,bool held){
  const float omega=std::sqrt(9.81f/bounded(height,.65f,1.2f));
  const Vec capture=addPoint(scalePoint(disturbance,1/omega),scalePoint(crossPoint(angular,{{0,0,1}}),.4f/omega));
  const float support=.095f+bounded(stance,.10f,.42f)*.5f;
  const float availableStep=(held?.08f:.46f+std::min(.12f,speed*.02f))*(braced?1.15f:1.f);
  const float distance=length(capture);
  margin=support-distance;
  stepDemand=std::max(0.f,distance-support);
  risk=distance/(support+availableStep);
  phase=distance<.035f?0:distance<=support?1:2;
  // A failed recovery is accumulated over time. Crossing a force threshold
  // for one tick no longer switches a standing player straight to ragdoll.
  if(risk>1.f)failureTime+=dt;else failureTime=std::max(0.f,failureTime-dt*2.f);
  const Vec wanted=scalePoint(unit(capture,{{0,0,0}}),std::min(1.15f,stepDemand*3.5f));
  correction=addPoint(correction,capped(subtractPoint(wanted,correction),4.f*dt));
  const float damping=risk>1.f?.75f:braced?4.2f:3.5f;
  disturbance=scalePoint(disturbance,std::exp(-damping*dt));
  angular=scalePoint(angular,std::exp(-5.f*dt));
  if(failureTime>.28f){phase=3;return true;}
  return false;
}
Vec BalanceController::lean()const{
  return capped(scalePoint(crossPoint({{0,0,1}},disturbance),.14f),.20f);
}
}
