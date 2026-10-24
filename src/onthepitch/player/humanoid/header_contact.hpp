#pragma once
#include <algorithm>
#include <cmath>

namespace football_header {
inline float bounded(float x,float lo,float hi){return std::isfinite(x)?std::max(lo,std::min(hi,x)):lo;}
// Load backwards, cross the authored pose at impact, then follow through.
// Zero displacement at the contact frame preserves its real skin marker;
// the nonzero derivative supplies a visible, moving heading surface.
inline float pitch(float secondsFromImpact){
  if(secondsFromImpact<-.28f || secondsFromImpact>.42f)return 0;
  if(secondsFromImpact<-.12f){const float t=(secondsFromImpact+.28f)/.16f;return -.18f*t*t*(3-2*t);}
  if(secondsFromImpact<=.12f)return .18f*std::sin(secondsFromImpact*13.0899694f);
  const float t=(secondsFromImpact-.12f)/.30f;return .18f*(1-t*t*(3-2*t));
}
inline float speed(float power,float incoming,float headDrive,bool shot){
  power=bounded(power,0,1);incoming=bounded(incoming,0,25);headDrive=bounded(headDrive,0,7);
  return bounded((shot?6.5f:3.2f)+(shot?7.5f:5.8f)*power+.18f*incoming+.60f*headDrive,3.2f,shot?18.f:13.f);
}
}
