#pragma once
#include <algorithm>
#include <cmath>
namespace football_pass {
struct Flight { float horizontal,vertical,time,distance; };
inline float chargedRange(unsigned charge,bool cross){
  const float amount=std::min(800u,charge)/800.f;
  return (cross?4.f:2.5f)+(cross?51.f:24.f)*amount;
}
// Flat-pitch reference for planning, with the native 10 ms integration,
// quadratic air drag, ground braking and bounce. Live turf, spin and contact
// difficulty still produce variation; this is a range estimate, not a magnet.
inline float range(float horizontal,float vertical,float height,float time) {
  float x=0,z=std::max(.11f,height),vx=horizontal,vz=vertical;
  const unsigned steps=std::max(1u,unsigned(std::round(time*100)));
  for(unsigned i=0;i<steps;++i){
    vz-=.0981f;
    const float speed=std::sqrt(vx*vx+vz*vz);
    const float drag=std::max(0.f,1-.00015f*speed);vx*=drag;vz*=drag;
    const float grass=std::max(0.f,std::min(1.f,1-(z-.11f)/.025f));
    x+=vx*.01f;z+=vz*.01f;
    if(z<.11f){z=.11f;if(vz<0)vz=std::max(0.f,-vz*.70f-.06f);}
    if(z<.135f)vx=std::max(0.f,vx-(.04f*vx*vx+1.6f)*grass*.01f);
  }
  return x;
}
inline Flight plan(float distance,bool cross,float height=.11f) {
  distance=std::max(cross?3.f:2.f,std::min(cross?55.f:32.f,std::isfinite(distance)?distance:2.f));
  const float time=cross?std::max(.85f,std::min(2.65f,.70f+.037f*distance)):
    std::max(.75f,std::min(3.f,.70f+.070f*distance));
  float vertical=cross?4.905f*time+(.85f-std::max(.11f,height))/time+.55f:
    std::max(.2f,.70f+.025f*distance);
  float low=0,high=36;
  for(unsigned i=0;i<17;++i){const float mid=(low+high)*.5f;
    if(range(mid,vertical,height,time)<distance)low=mid;else high=mid;}
  return {(low+high)*.5f,vertical,time,distance};
}
}
