#pragma once
#include "physical_rig.hpp"

namespace football_physics {
void constrainArmPose(const pes3::NativeBind &reference,float scale,Pose &pose,Vec root,Metrics &metrics);
// Joint-local limits for this skeleton (+Z up, arms down at rest). These
// game limits include scapular allowance; they are not patient ROM data.
// Separate axial twist from swing so a quaternion log cannot trade an elbow
// hyperextension for lateral bending, or a shoulder swing for unlimited roll.
inline Quat anatomicalArm(unsigned bone,Quat q){
  q=normalized(q);if(q[3]<0)for(float &v:q)v=-v;
  const bool elbow=bone==4 || bone==6;
  Quat twist=elbow?Quat{{q[0],0,0,q[3]}}:Quat{{0,0,q[2],q[3]}};
  twist=normalized(twist);
  Vec swing=logarithm(productRotation(q,inverseRotation(twist)));
  if(elbow){
    swing[0]=0;swing=capped(swing,.10f);
    const float bend=bounded(2*std::atan2(twist[0],twist[3]),-2.55f,-.025f);
    return normalized(productRotation(exponential(swing),exponential({{bend,0,0}})));
  }
  swing[2]=0;
  const float xLimit=swing[0]<0?2.70f:1.10f;
  const bool inward=(bone==3?swing[1]>0:swing[1]<0);
  const float yLimit=inward?.85f:2.70f;
  const float ellipse=std::sqrt(swing[0]*swing[0]/(xLimit*xLimit)+swing[1]*swing[1]/(yLimit*yLimit));
  if(ellipse>1)swing=scalePoint(swing,1/ellipse);
  const float roll=bounded(2*std::atan2(twist[2],twist[3]),-1.55f,1.55f);
  return normalized(productRotation(exponential(swing),exponential({{0,0,roll}})));
}
inline float armLimitError(unsigned bone,Quat q){return length(logarithm(productRotation(q,inverseRotation(anatomicalArm(bone,q)))));}
}
