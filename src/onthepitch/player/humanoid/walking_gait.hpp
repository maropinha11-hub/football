#pragma once
#include "physical_rig.hpp"

namespace football_walk {
using namespace football_physics;
// A walking cycle has overlapping support, not the flight phase of a
// retimed jog. Coordinates are relative to the pelvis, forward is -Y.
inline Vec foot(float phase,float stride,float lateral){
  phase-=std::floor(phase);
  const float stance=.64f;
  if(phase<stance)return {{lateral,stride*(phase/stance-.5f),0}};
  const float swing=(phase-stance)/(1-stance);
  const float eased=swing*swing*(3-2*swing);
  return {{lateral,stride*(.5f-eased),.045f*std::pow(std::sin(3.14159265f*swing),2.f)}};
}
inline void pose(const pes3::NativeBind &bind,Pose &local,Vec pelvis,float phase,float stride){
  Points p{};Pose world{};
  auto fk=[&](){p[0]=pelvis;for(unsigned i=0;i<13;++i){const int parent=pes3::nativeParents[i];
    world[i]=parent<0?local[i]:normalized(productRotation(world[parent],local[i]));
    if(parent>=0)p[i]=addPoint(p[parent],rotatePoint(world[parent],bind.offsets[i]));}};
  // Start with the native rest chain so a running knee fold cannot remain
  // baked into this cycle. All link lengths still come from the same model.
  for(unsigned i=7;i<13;++i)local[i]=bind.rotations[i];
  fk();
  for(unsigned side=0;side<2;++side){
    const unsigned hip=side?10:7,knee=hip+1,ankle=hip+2;
    const float legPhase=phase+.5f*side;
    const Vec offset=foot(legPhase,stride,p[ankle][0]-pelvis[0]);
    Vec target=addPoint(pelvis,rotatePoint(world[0],{{offset[0],offset[1],0}}));
    target[2]=.075f+offset[2];
    const float a=length(subtractPoint(p[knee],p[hip])),b=length(subtractPoint(p[ankle],p[knee]));
    const Vec direction=unit(subtractPoint(target,p[hip]));
    const float distance=bounded(length(subtractPoint(target,p[hip])),std::fabs(a-b)+.001f,a+b-.001f);
    target=addPoint(p[hip],scalePoint(direction,distance));
    const Vec forward=rotatePoint(world[0],{{0,-1,0}});
    const Vec pole=unit(subtractPoint(forward,scalePoint(direction,dotPoint(forward,direction))));
    const float along=(a*a-b*b+distance*distance)/(2*distance);
    const Vec bend=addPoint(addPoint(p[hip],scalePoint(direction,along)),scalePoint(pole,std::sqrt(std::max(0.f,a*a-along*along))));
    const Quat upper=normalized(productRotation(pes3::swingRotation(unit(subtractPoint(p[knee],p[hip])),unit(subtractPoint(bend,p[hip]))),world[hip]));
    local[hip]=normalized(productRotation(inverseRotation(world[0]),upper));fk();
    const Quat lower=normalized(productRotation(pes3::swingRotation(unit(subtractPoint(p[ankle],p[knee])),unit(subtractPoint(target,p[knee]))),world[knee]));
    local[knee]=normalized(productRotation(inverseRotation(world[hip]),lower));fk();
    // Small heel/toe roll while the sole has a support phase.
    const float t=legPhase-std::floor(legPhase);
    const float roll=t<.64f?.10f*std::sin(3.14159265f*(2*t/.64f-1)):-.08f*std::sin(3.14159265f*(t-.64f)/.36f);
    local[ankle]=normalized(productRotation(inverseRotation(world[knee]),productRotation(world[0],exponential({{roll,0,0}}))));fk();
  }
}
inline void upperBody(const pes3::NativeBind &bind,Pose &pose,float phase){
  const float swing=std::sin(6.28318531f*phase),transfer=std::sin(12.5663706f*phase);
  // Walking carries the arms lower, opens the elbows and counter-rotates
  // the trunk. Retiming the jogging arms retained its unmistakable run pose.
  pose[1]=normalized(productRotation(bind.rotations[1],exponential({{.045f,.024f*swing,.035f*swing}})));
  for(unsigned side=0;side<2;++side){const unsigned shoulder=side?5:3,elbow=shoulder+1;const float sign=side?-1.f:1.f;
    pose[shoulder]=normalized(productRotation(bind.rotations[shoulder],exponential({{.22f*sign*swing,sign*-.06f,.025f*transfer}})));
    pose[elbow]=normalized(productRotation(bind.rotations[elbow],exponential({{-.28f-.05f*sign*swing,0,0}})));
  }
}
}
