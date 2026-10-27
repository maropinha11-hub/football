#pragma once
#include "physical_rig.hpp"

namespace football_physics {
// Geometric reference only; it never changes a physical body or its root.
class BodyReference {
 public:
  static Pose standing(const pes3::NativeBind &bind,Quat heading){
    Pose q=bind.rotations;q[0]=normalized(productRotation(heading,exponential({{.10f,0,0}})));
    q[7]=q[10]=exponential({{-.10f,0,0}});q[8]=q[11]=exponential({{.20f,0,0}});
    q[9]=q[12]=exponential({{-.20f,0,0}});q[4]=q[6]=exponential({{-.35f,0,0}});return q;
  }
  static void fk(const pes3::NativeBind &bind,float scale,const Pose &q,Vec root,Points &p,Pose &global){
    p[0]=root;for(unsigned i=0;i<13;++i){const int parent=pes3::nativeParents[i];
      global[i]=parent<0?q[i]:normalized(productRotation(global[parent],q[i]));
      if(parent>=0)p[i]=addPoint(p[parent],rotatePoint(global[parent],scalePoint(bind.offsets[i],scale)));}
  }
};
}
