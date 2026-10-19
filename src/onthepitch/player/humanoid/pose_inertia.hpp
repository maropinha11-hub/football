#pragma once
#include "../../../pes3/native_pose.hpp"
#include <algorithm>
#include <array>
#include <cmath>

namespace football_physics {
// Rotation-space inertialization: outgoing pose AND angular velocity decay
// with the exact critically damped spring. Equations informed by Holden's
// public Motion-Matching / spring.h (MIT). No translations or ball impulses.
class PoseInertia {
 public:
  using Pose=pes3::NativeRotations;using Vec=pes3::Point;using Quat=pes3::Rotation;
  void reset(){ready=false;epoch=~0ul;offset={};velocity={};previousVelocity={};trackingOrigin={};trackingDecay=0;}
  void observe(const Pose &target,const std::array<Vec,13> &targetVelocity,unsigned long key,bool transition=true){
    if(!ready){last=trackingOrigin=target;epoch=key;ready=true;return;}
    if(epoch==key)return;
    for(unsigned i=1;i<13;++i){
      offset[i]=transition?log(pes3::productRotation(last[i],pes3::inverseRotation(target[i]))):Vec{{0,0,0}};
      velocity[i]=transition?cap(pes3::subtractPoint(previousVelocity[i],targetVelocity[i]),12.f):Vec{{0,0,0}};
    }
    epoch=key;
  }
  void advance(float dt){
    dt=std::max(0.f,std::min(.025f,dt));const float y=2.f*.69314718056f/.065f,e=std::exp(-y*dt);
    trackingOrigin=last;trackingDecay=std::exp(-dt/.018f);
    for(unsigned i=1;i<13;++i){const auto j=pes3::addPoint(velocity[i],pes3::scalePoint(offset[i],y));
      offset[i]=pes3::scalePoint(pes3::addPoint(offset[i],pes3::scalePoint(j,dt)),e);
      velocity[i]=pes3::scalePoint(pes3::subtractPoint(velocity[i],pes3::scalePoint(j,y*dt)),e);
    }
  }
  void apply(const Pose &target,const std::array<Vec,13> &targetVelocity,const std::array<float,13> &mask,Pose &output,bool tracking=true){
    output=target;
    for(unsigned i=1;i<13;++i){
      Quat q;const float weight=std::max(0.f,std::min(1.f,mask[i]));
      if(pes3::unitRotation(pes3::productRotation(exp(pes3::scalePoint(offset[i],weight)),target[i]),q))output[i]=q;
      // A short tracking filter removes high-frequency source/requeue noise.
      // It uses a frozen previous-tick origin, so repeated contact queries
      // cannot advance it. Contact masks bypass it before the authored hit.
      const auto difference=log(pes3::productRotation(trackingOrigin[i],pes3::inverseRotation(output[i])));
      if(tracking&&pes3::unitRotation(pes3::productRotation(exp(pes3::scalePoint(difference,trackingDecay*weight)),output[i]),q))output[i]=q;
      previousVelocity[i]=pes3::addPoint(targetVelocity[i],pes3::scalePoint(velocity[i],weight));
    }
    last=output;
  }
  float maximumOffset()const{float result=0;for(auto v:offset)result=std::max(result,magnitude(v));return result;}
 private:
  static float magnitude(Vec v){return std::sqrt(pes3::dotPoint(v,v));}
  static Vec cap(Vec v,float maximum){return pes3::scalePoint(v,std::min(1.f,maximum/std::max(1e-8f,magnitude(v))));}
  static Vec log(Quat q){
    Quat n;if(!pes3::unitRotation(q,n))return {{0,0,0}};if(n[3]<0)for(auto &v:n)v=-v;
    const float s=std::sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]);const float f=s>1e-7f?2*std::atan2(s,n[3])/s:2.f;
    return {{n[0]*f,n[1]*f,n[2]*f}};
  }
  static Quat exp(Vec v){const float a=magnitude(v),f=a>1e-7f?std::sin(a*.5f)/a:.5f;return {{v[0]*f,v[1]*f,v[2]*f,std::cos(a*.5f)}};}
  Pose last{},trackingOrigin{};std::array<Vec,13> offset{},velocity{},previousVelocity{};
  float trackingDecay=0;
  unsigned long epoch=~0ul;bool ready=false;
};
}
