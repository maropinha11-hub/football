#pragma once
#include "physical_rig.hpp"

// Procedural adaptations of the native receiving actions. These operate on
// joint rotations and the actor root; limb lengths always come from the skin
// bind. Ball contacts are subsequently rebound/tested against that same skin.
namespace football_reach {
using namespace football_physics;
inline void fk(const pes3::NativeBind &bind,const Pose &pose,Vec root,Pose &world,Points &points){
  for(unsigned i=0;i<13;++i){const int parent=pes3::nativeParents[i];
    world[i]=parent<0?pose[i]:normalized(productRotation(world[parent],pose[i]));
    points[i]=parent<0?root:addPoint(points[parent],rotatePoint(world[parent],bind.offsets[i]));
  }
}
inline void leg(const pes3::NativeBind &bind,Pose &pose,Vec root,unsigned hip,Vec target){
  Pose world;Points p;fk(bind,pose,root,world,p);
  const unsigned knee=hip+1,ankle=hip+2;
  const float a=length(bind.offsets[knee]),b=length(bind.offsets[ankle]);
  const Vec axis=unit(subtractPoint(target,p[hip]));
  const float d=bounded(length(subtractPoint(target,p[hip])),std::fabs(a-b)+.002f,a+b-.002f);
  target=addPoint(p[hip],scalePoint(axis,d));
  Vec pole=rotatePoint(world[0],{{0,-1,0}});
  pole=unit(subtractPoint(pole,scalePoint(axis,dotPoint(axis,pole))));
  const float along=(a*a-b*b+d*d)/(2*d);
  const Vec bend=addPoint(addPoint(p[hip],scalePoint(axis,along)),scalePoint(pole,std::sqrt(std::max(0.f,a*a-along*along))));
  const Quat upper=normalized(productRotation(pes3::swingRotation(unit(subtractPoint(p[knee],p[hip])),unit(subtractPoint(bend,p[hip]))),world[hip]));
  pose[hip]=normalized(productRotation(inverseRotation(world[0]),upper));fk(bind,pose,root,world,p);
  const Quat lower=normalized(productRotation(pes3::swingRotation(unit(subtractPoint(p[ankle],p[knee])),unit(subtractPoint(target,p[knee]))),world[knee]));
  pose[knee]=normalized(productRotation(inverseRotation(world[hip]),lower));
}
inline float jump(float seconds,float apexHeight,float takeoff=.12f){
  if(apexHeight<=0||seconds<=takeoff)return 0;
  const float v=std::sqrt(2*9.81f*apexHeight),t=seconds-takeoff;
  return std::max(0.f,v*t-.5f*9.81f*t*t);
}
inline float envelope(float frame,float contact,float end){
  return smooth(frame/std::max(1.f,contact))*smooth((end-frame)/std::max(1.f,end-contact));
}
}
