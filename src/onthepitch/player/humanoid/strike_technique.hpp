#pragma once
#include <algorithm>
#include <cmath>
#include <string>
namespace football_strike {
enum class Technique { Instep, Inside, Outside, Toe, Knuckle };
inline float shortPassSpeed(unsigned charge){return 3.2f+19.f*std::pow(std::min(650u,charge)/650.f,1.3f);}
inline const char *name(Technique t){return t==Technique::Inside?"inside":t==Technique::Outside?"outside":t==Technique::Toe?"toe":t==Technique::Knuckle?"knuckle":"instep";}
// Body-local lateral ball position and requested opening. A preferred foot
// may reach across the body, but the native feasibility solver still owns it.
inline Technique choose(float power,float opening,float lateral,float speed,bool shot,bool right=true){
  if(!std::isfinite(power)||!std::isfinite(opening)||!std::isfinite(lateral)||!std::isfinite(speed))return Technique::Instep;
  const float side=right?1.f:-1.f;
  if(side*lateral<-.11f && std::fabs(opening)>.30f)return Technique::Outside;
  if(shot&&speed>3.8f&&power<.56f&&std::fabs(opening)<.35f)return Technique::Toe;
  if(shot&&power>.78f&&std::fabs(opening)<.18f&&std::fabs(lateral)<.12f)return Technique::Knuckle;
  if(power<.64f||std::fabs(opening)>.28f)return Technique::Inside;
  return Technique::Instep;
}
inline float followThroughLoad(float power,float speed,float opening,float pressure,bool header){
  auto unit=[](float v){return std::isfinite(v)?std::max(0.f,std::min(1.f,v)):0.f;};
  const float backwards=unit((std::fabs(opening)-1.1f)/1.8f),run=unit(speed/7.f);
  // Support demand is continuous: ordinary passes recruit the body; awkward
  // running releases can exhaust support. No random or unconditional falls.
  return 18.f+48.f*unit(power)+48.f*run*backwards+42.f*unit(pressure)+
    (header?32.f*run:0.f)+80.f*run*backwards*unit(power);
}
}
