#pragma once
#include "../../../pes3/native_pose.hpp"
#include <algorithm>
#include <cmath>
namespace football_flight {
using Vec=pes3::Point;
inline float length(Vec p){return std::sqrt(pes3::dotPoint(p,p));}
inline Vec limit(Vec p,float maximum){return pes3::scalePoint(p,std::min(1.f,maximum/std::max(1e-6f,length(p))));}
// Angular impulse for a thin-shell ball (I=2/3 mr²). Only the tangential
// impulse contributes, bounded by friction. The surface point is measured
// on the current skin; labels such as 'outside' cannot create curve alone.
inline Vec contactSpin(Vec lever,Vec deltaVelocity,bool head=false){
  const float radius=.11f;
  if(!std::isfinite(length(lever))||!std::isfinite(length(deltaVelocity))||length(lever)<.02f)return {{0,0,0}};
  const Vec radial=pes3::scalePoint(lever,1/length(lever));
  const float normal=std::fabs(pes3::dotPoint(deltaVelocity,radial));
  const Vec tangent=limit(pes3::subtractPoint(deltaVelocity,pes3::scalePoint(radial,pes3::dotPoint(deltaVelocity,radial))),normal*(head?.22f:.38f));
  return limit(pes3::scalePoint(pes3::crossPoint(pes3::scalePoint(radial,radius),tangent),1.5f/(radius*radius)),head?22.f:52.f);
}
inline bool knuckle(Vec spin,float speed){return speed>19.f&&length(spin)<3.f;}
}
