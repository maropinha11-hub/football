#pragma once
#include "../../../pes3/native_pose.hpp"
#include <algorithm>
#include <cmath>

namespace football_reception {
using Rotation=pes3::Rotation;
// Chest/hip separation is anatomical, even when the arrival axis is behind
// the receiver. Preserve authored lean; never wind the spine around the pelvis.
inline Rotation boundedSpine(Rotation relative) {
  Rotation q;if(!pes3::unitRotation(relative,q))return {{0,0,0,1}};
  if(q[3]<0)for(auto &v:q)v=-v;
  const float n=std::hypot(q[2],q[3]);
  Rotation twist=n>1e-6f?Rotation{{0,0,q[2]/n,q[3]/n}}:Rotation{{0,0,0,1}};
  Rotation swing=pes3::productRotation(q,pes3::inverseRotation(twist));
  const float yaw=std::max(-.96f,std::min(.96f,2.f*std::atan2(twist[2],twist[3])));
  Rotation limited{{0,0,std::sin(yaw*.5f),std::cos(yaw*.5f)}};
  const float angle=2.f*std::acos(std::min(1.f,std::fabs(swing[3])));
  if(angle>.85f){
    const float s=std::hypot(swing[0],swing[1]);
    if(s>1e-6f)swing={{swing[0]/s*std::sin(.425f),swing[1]/s*std::sin(.425f),0,std::cos(.425f)}};
  }
  return pes3::productRotation(swing,limited);
}
inline float fade(float phase,float abort) {
  if(abort<0)return 1;
  const float t=std::max(0.f,std::min(1.f,(phase-abort)/12.f));
  return 1-t*t*(3-2*t);
}
}
