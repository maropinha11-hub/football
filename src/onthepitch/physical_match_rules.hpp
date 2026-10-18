#pragma once
#include <algorithm>
#include <cmath>
namespace football_rules {
inline float cutImpulse(float speed,float requestedSpeed,float facing){
  if(!std::isfinite(speed)||!std::isfinite(requestedSpeed)||!std::isfinite(facing)||speed<4.8f)return 0;
  const float stop=std::max(0.f,(speed-requestedSpeed-2.f)/5.f);
  const float reverse=requestedSpeed>.8f?std::max(0.f,(-facing-.15f)/.85f):0.f;
  return std::min(140.f,std::max(0.f,(speed-4.8f))*32.f*std::max(stop,reverse));
}
inline bool incomingReception(float gap,float height,float closing,float speed,bool freeBall){
  return freeBall&&std::isfinite(gap)&&std::isfinite(height)&&std::isfinite(closing)&&std::isfinite(speed)&&
    gap<1.15f&&height>.08f&&height<2.15f&&closing>.25f&&speed>1.1f&&speed<19.f;
}
inline bool rareHeel(float facing,float speed,float power,float pressure,float ownGoal,unsigned long elapsed){
  return facing<-.55f&&speed<3.f&&power<.48f&&pressure<.75f&&ownGoal>26.f&&elapsed>=30000;
}
inline bool excessiveHold(float seconds,float force,bool fallen){
  return std::isfinite(seconds)&&std::isfinite(force)&&
    ((fallen&&force>30)||(seconds>.75f&&force>140)||(seconds>1.5f&&force>70));
}
inline float strikeLoad(float power,float speed,float turn,bool header){
  auto unit=[](float f){return std::isfinite(f)?std::max(0.f,std::min(1.f,f)):0.f;};
  return unit(.55f*unit(power)+.20f*unit(speed/8)+.25f*unit(std::fabs(turn)/3.14159265f)+(header?.08f:0));
}
inline bool rearReception(float facing,float relativeSpeed,float distance){
  // A slow reachable ball can still be hooked with the heel. A fast ball
  // behind the shoulders needs a turn before an automatic control is queued.
  return std::isfinite(facing)&&std::isfinite(relativeSpeed)&&std::isfinite(distance)&&
    !(facing<-.35f && (relativeSpeed>4.f || distance>.65f));
}
struct Tackle {float impulse;bool fall,foul;float severity;};
inline Tackle tackle(bool sliding,float speed,bool behind,bool ballFirst){
  speed=std::isfinite(speed)?std::max(0.f,std::min(9.f,speed)):0.f;
  const bool fall=(sliding&&(speed>2.f||behind))||(!ballFirst&&((behind&&speed>3.7f)||speed>5.8f));
  const bool reckless=sliding&&behind&&speed>4.5f;
  return {std::min(330.f,(sliding?155.f:65.f)+speed*(sliding?24.f:13.f)),fall,
    !ballFirst||reckless,1.f+(sliding?.45f:0.f)+(behind?.55f:0.f)+speed*.08f};
}
}
