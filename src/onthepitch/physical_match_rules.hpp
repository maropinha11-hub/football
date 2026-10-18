#pragma once
#include <algorithm>
#include <cmath>
namespace football_rules {
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
  const bool fall=sliding&&(speed>2.4f||behind);
  const bool reckless=sliding&&behind&&speed>4.5f;
  return {std::min(330.f,(sliding?155.f:65.f)+speed*(sliding?24.f:13.f)),fall,
    !ballFirst||reckless,1.f+(sliding?.45f:0.f)+(behind?.55f:0.f)+speed*.08f};
}
}
