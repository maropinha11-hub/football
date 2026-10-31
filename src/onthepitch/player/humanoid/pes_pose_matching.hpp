#pragma once
#include "motion_matching.hpp"
#include "learned_pes_pose_metric.hpp"
#include <array>
#include <limits>

namespace football_pes_matching {
using Feature=std::array<float,50>;
inline Feature features(const football_physics::MotionFeature &f,float height,float bodyScale){
  Feature v{};unsigned at=0;const float s=std::max(.01f,bodyScale);
  for(const auto &p:f.positions)for(float x:p)v[at++]=x/s;
  for(const auto &p:f.velocities)for(float x:p)v[at++]=x/s;
  for(const auto &p:f.trajectory)for(float x:p)v[at++]=x;
  for(const auto &p:f.facing)for(float x:p)v[at++]=x;
  for(unsigned foot=0;foot<2;++foot)v[at++]=(height+f.positions[foot][2])/s<.12f&&std::fabs(f.velocities[foot][2]/s)<.4f?1:0;
  return v;
}
inline float cost(const Feature &a,const Feature &b){
  float result=0;
  for(unsigned i=0;i<50;++i){
    if(!std::isfinite(a[i])||!std::isfinite(b[i]))return std::numeric_limits<float>::infinity();
    const float d=(a[i]-b[i])*scale[i];result+=d*d;
  }
  return result;
}
}
