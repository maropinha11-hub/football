#pragma once
#include "walking_gait.hpp"

namespace football_physics {
// A pose generator, not a learned locomotion policy. It shares measured
// link lengths with the native model and never alters the animation files.
class ProceduralReference {
 public:
  void reset(){phase=weight=0;ready=false;}
  Input compose(const Input &source,const pes3::NativeBind &bind,float scale,float dt){
    if(source.matchedReference)return source;
    Input out=source;
    const float speed=length(source.velocity);
    const bool free=!source.action&&!source.touchPending&&!source.upperReception&&!source.staggering;
    if(!ready)ready=true;
    weight=bounded(weight+(free?dt/.25f:-dt/.10f),0,1);
    const float stride=bounded(.32f+speed*.16f,.32f,.78f)*scale;
    phase+=std::min(speed,3.5f)*dt/(stride/football_walk::stanceFraction);
    phase-=std::floor(phase);
    Pose pose=bind.rotations;
    pose[2]=source.pose[2]; // Preserve the camera's existing anatomical head aim.
    const Vec up=rotatePoint(source.pose[0],{{0,0,1}});
    const Quat heading=normalized(productRotation(pes3::swingRotation(up,{{0,0,1}}),source.pose[0]));
    pose[0]=normalized(productRotation(heading,exponential({{.10f,0,0}})));
    pose[4]=pose[6]=exponential({{-.35f,0,0}});
    pose[7]=pose[10]=exponential({{-.10f,0,0}});
    pose[8]=pose[11]=exponential({{.20f,0,0}});
    pose[9]=pose[12]=exponential({{-.20f,0,0}});
    Vec pelvis=source.pelvis;pelvis[2]=.935f*scale;
    if(speed>.1f){
      auto scaled=bind;for(auto &offset:scaled.offsets)offset=scalePoint(offset,scale);
      Vec travel=rotatePoint(inverseRotation(heading),source.velocity);travel[2]=0;
      pelvis[2]=football_walk::pelvisHeight(scaled,phase,stride,travel);
      football_walk::pose(scaled,pose,pelvis,phase,stride,travel);
      football_walk::upperBody(scaled,pose,phase);
    }
    const float mix=source.controller==2?1.f:smooth(weight);
    for(unsigned i=0;i<13;++i)out.pose[i]=blended(source.pose[i],pose[i],free?mix:0.f);
    if(free)out.pelvis[2]=source.pelvis[2]*(1-mix)+pelvis[2]*mix;
    return out;
  }
 private:
  float phase=0,weight=0;bool ready=false;
};
}
