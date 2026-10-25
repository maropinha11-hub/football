#include "balance_controller.hpp"
#include "learned_balance_policy.hpp"

namespace football_physics {
void BalanceController::addImpulse(Vec impulse,Vec torque){
  if(length(impulse)>25.f)stepArmed=true;
  impulse[2]=0;
  disturbance=capped(addPoint(disturbance,scalePoint(impulse,1/PhysicalRig::mass)),5.f);
  // Most of a torso impact is transmitted through the planted lower body.
  // Keep the residual rotation separate from the translational disturbance.
  angular=capped(addPoint(angular,scalePoint(torque,.12f/14.f)),1.5f);
}
bool BalanceController::step(float dt,float height,float stance,float speed,bool braced,bool held){
  const float omega=std::sqrt(9.81f/bounded(height,.65f,1.2f));
  // Momentum must first displace the supported body. Discarding it with an
  // exponential every tick made sustained pressure look like a rigid wall.
  displacement=capped(addPoint(displacement,scalePoint(subtractPoint(disturbance,scalePoint(displacement,5.f)),dt)),.22f);
  const Vec capture=addPoint(displacement,addPoint(scalePoint(disturbance,1/omega),scalePoint(crossPoint(angular,{{0,0,1}}),.4f/omega)));
  const float support=.095f+bounded(stance,.10f,.42f)*.5f;
  const float availableStep=(held?.08f:.52f+std::min(.12f,speed*.02f))*(braced?1.15f:1.f);
  const float distance=length(capture);
  Vec suggested{{0,0,0}},hip{{0,0,0}};
  for(unsigned axis=0;axis<2;++axis)
    football_balance_ml::predict(displacement[axis],disturbance[axis],bounded(height,.68f,1.2f),bounded(stance,.10f,.42f),braced,suggested[axis],hip[axis]);
  if(distance<.03f)suggested=hip={{0,0,0}};
  hipStrategy=addPoint(hipStrategy,capped(subtractPoint(hip,hipStrategy),1.6f*dt));
  margin=support-distance;
  stepDemand=std::max(0.f,distance-support);
  risk=distance/(support+availableStep);
  phase=distance<.035f?0:distance<=support?1:2;
  // A failed recovery is accumulated over time. Crossing a force threshold
  // for one tick no longer switches a standing player straight to ragdoll.
  if(risk>1.f)failureTime+=dt;else failureTime=std::max(0.f,failureTime-dt*2.f);
  if(stepDemand>.08f && stepArmed){
    committedStep=unit(capture,{{0,0,0}});
    stepRemaining=held?.20f:braced?.44f:.52f;stepArmed=false;
  }
  if(risk<.05f && stepRemaining<=0)stepArmed=true;
  Vec wanted=capped(scalePoint(suggested,3.5f),1.15f);
  // The learned proposal cannot step against the measured disturbance or
  // exceed the finite reachable capture deficit.
  if(dotPoint(wanted,capture)<0)wanted={{0,0,0}};
  wanted=capped(wanted,std::min(1.15f,stepDemand*3.5f));
  // Finish one support step instead of abandoning it when the initial upper
  // body sway decays. The native gait may be up to 270 ms from its next
  // transition. This commitment contains no position/foot teleport.
  if(stepRemaining>0){
    stepRemaining=std::max(0.f,stepRemaining-dt);
    if(dotPoint(wanted,committedStep)<.20f)wanted=scalePoint(committedStep,.20f);
  }
  correction=addPoint(correction,capped(subtractPoint(wanted,correction),4.f*dt));
  const float damping=risk>1.f?1.4f:braced?4.2f:3.5f;
  disturbance=scalePoint(disturbance,std::exp(-damping*dt));
  angular=scalePoint(angular,std::exp(-5.f*dt));
  if(failureTime>.28f){phase=3;return true;}
  return false;
}
Vec BalanceController::lean()const{
  return capped(addPoint(scalePoint(crossPoint({{0,0,1}},disturbance),.14f),crossPoint({{0,0,1}},hipStrategy)),.32f);
}
}
