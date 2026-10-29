#pragma once
// Explicit visual review of a locally supplied, already retargeted clip.
// This never registers an animation candidate or generates a ball contact.
#include "utils/animation.hpp"
#include "pes3/native_pose.hpp"
#include <stdexcept>

class TrainingPosePreview {
  blunted::Animation clip;
public:
  explicit TrainingPosePreview(const std::string& path){
    clip.Load(path);
    if(clip.GetVariable("type")!="trainingpose"||clip.GetFrameCount()<2||clip.GetFrameCount()>10001)
      throw std::runtime_error("Invalid training pose preview");
    for(const auto* name:pes3::nativeBoneNames){
      blunted::Quaternion q;blunted::Vector3 p;
      if(!clip.GetKeyFrame(name,0,q,p,true,false))throw std::runtime_error("Missing native preview bone");
    }
  }
  bool sample(unsigned long time,int heldFrame,const pes3::NativeBind& bind,pes3::NativePose& out)const{
    const int frame=std::min(clip.GetFrameCount()-1,heldFrame<0?int(time/10):heldFrame);
    pes3::NativePose pose;pes3::NativeRotations world;
    blunted::Quaternion q;blunted::Vector3 p;
    if(!clip.GetKeyFrame("player",frame,q,p,false,true)||!std::isfinite(p.coords[2])||p.coords[2]<0||p.coords[2]>4)return false;
    pose.rootHeight=p.coords[2];
    for(unsigned i=0;i<13;++i){
      if(!clip.GetKeyFrame(pes3::nativeBoneNames[i],frame,q,p,true,false)||
         !pes3::unitRotation({{q.elements[0],q.elements[1],q.elements[2],q.elements[3]}},pose.local[i]))return false;
      const int parent=pes3::nativeParents[i];
      world[i]=parent<0?pose.local[i]:pes3::productRotation(world[parent],pose.local[i]);
      pose.positions[i]=parent<0?pes3::Point{{0,0,pose.rootHeight}}:
        pes3::addPoint(pose.positions[parent],pes3::rotatePoint(world[parent],bind.offsets[i]));
    }
    out=pose;return true;
  }
};
