#pragma once
// Native-rig physics experiment. SI units, +Z up, fixed-step integration.
// No source motion data, trained policy or proprietary animation is embedded.
#include "../../../pes3/native_pose.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <memory>
#include <vector>

namespace football_physics {
using Vec=pes3::Point;
using Quat=pes3::Rotation;
using Pose=pes3::NativeRotations;
using Points=pes3::NativePoints;
using pes3::addPoint;
using pes3::subtractPoint;
using pes3::scalePoint;
using pes3::dotPoint;
using pes3::crossPoint;
using pes3::rotatePoint;
using pes3::productRotation;
using pes3::inverseRotation;
inline float bounded(float v,float lo,float hi){return std::max(lo,std::min(hi,v));}
inline float length(Vec v){return std::sqrt(dotPoint(v,v));}
inline Vec unit(Vec v,Vec fallback={{0,0,1}}){return length(v)>1e-7f?scalePoint(v,1/length(v)):fallback;}
inline Vec capped(Vec v,float maximum){return scalePoint(v,std::min(1.f,maximum/std::max(1e-7f,length(v))));}
inline Quat normalized(Quat q){Quat r{{0,0,0,1}};pes3::unitRotation(q,r);return r;}
inline Quat exponential(Vec v){float a=length(v);if(a<1e-7f)return normalized({{v[0]*.5f,v[1]*.5f,v[2]*.5f,1}});return {{v[0]*std::sin(a*.5f)/a,v[1]*std::sin(a*.5f)/a,v[2]*std::sin(a*.5f)/a,std::cos(a*.5f)}};}
inline Vec logarithm(Quat q){q=normalized(q);if(q[3]<0)for(float &v:q)v=-v;float s=std::sqrt(q[0]*q[0]+q[1]*q[1]+q[2]*q[2]);float f=s>1e-7f?2*std::atan2(s,q[3])/s:2;return {{q[0]*f,q[1]*f,q[2]*f}};}
inline Quat blended(Quat a,Quat b,float t){if(dotPoint({{a[0],a[1],a[2]}},{{b[0],b[1],b[2]}})+a[3]*b[3]<0)for(float &v:b)v=-v;for(unsigned i=0;i<4;++i)a[i]=a[i]*(1-t)+b[i]*t;return normalized(a);}
inline float smooth(float v){v=bounded(v,0,1);return v*v*(3-2*v);}

enum class Mode { Active=0,Falling=1,Recovering=2 };
struct Input {
  Pose pose{};
  Vec pelvis{{0,0,.96f}},velocity{{0,0,0}},forward{{0,-1,0}};
  Vec reach{{0,0,0}},opponent{{0,0,0}};
  Vec handTarget{{0,0,0}};
  int reachBone=-1;
  float reachWeight=0,opponentDistance=100;
  bool action=false,upperReception=false,protect=false,handTargetActive=false;
};
struct Metrics {
  float lean=0,turnRate=0,supportMargin=0,effort=0,reach=0,penetration=0;
  float angularSpeed=0,kineticEnergy=0,jointError=0;
  unsigned groundContacts=0;
  float selfPenetration=0,brace=0,recoveryPhase=0;
};
struct RecoveryKey { Pose pose{}; Vec pelvis{{0,0,0}}; };
using RecoveryMotion=std::vector<RecoveryKey>;

class ArticulatedBody;
class PhysicalRig {
 public:
  PhysicalRig();
  ~PhysicalRig();
  void configure(const pes3::NativeBind &bind,float heightScale);
  void setRecoveryMotions(RecoveryMotion front,RecoveryMotion back);
  void reset();
  void impulse(Vec newtonSeconds,Vec lever={{0,0,.35f}});
  void step(const Input &input,float dt=.01f);
  // Re-sample a native animation phase within the same simulation tick.
  // This never advances momentum, balance filters or the reach envelope.
  void evaluate(const Input &input);
  void alignRecoverySurface(float minimumHeight){if(state==Mode::Recovering){root[2]+=bounded(.003f-minimumHeight,-.10f,.10f);forwardKinematics();}}
  const Pose &pose()const{return local;}
  const Points &points()const{return positions;}
  const Pose &worldRotations()const{return world;}
  Mode mode()const{return state;}
  const Metrics &metrics()const{return debug;}
  bool initialized()const{return ready;}
  const Pose &additivePose()const{return additive;}
  float renderWeight()const{return state==Mode::Active?0.f:1.f;}
  float age()const{return stateAge;}
  static constexpr float mass=75.f;
 private:
  void forwardKinematics();
  void solveLeg(unsigned hip,Vec target);
  void reachHand(unsigned shoulder,Vec target,float weight);
  void separateArms();
  void recover(const Input &input);
  void groundRecovery();
  pes3::NativeBind reference{};
  Pose local{},world{};
  Pose additive{};
  std::unique_ptr<ArticulatedBody> articulated;
  Pose recoveryPose{};
  RecoveryMotion recoveryFront,recoveryBack;
  const RecoveryMotion *recoveryMotion=nullptr;
  Quat recoveryYaw{{0,0,0,1}};
  float recoveryDuration=2;
  float protection=0;
  Pose physicalUpper{};
  bool physicalUpperValid=false;
  Points positions{};
  std::array<Vec,13> angularVelocity{};
  Vec root{{0,0,.96f}},rootVelocity{{0,0,0}},previousVelocity{{0,0,0}};
  Vec filteredAcceleration{{0,0,0}},lastForward{{0,-1,0}},sway{{0,0,0}},swayVelocity{{0,0,0}};
  Vec pendingImpulse{{0,0,0}},pendingTorque{{0,0,0}},reachOffset{{0,0,0}};
  std::array<Vec,13> reachOffsets{};
  Vec recoveryStart{{0,0,0}};
  float scale=1,stateAge=0,filteredTurn=0,settled=0,unstableTime=0;
  bool ready=false;
  Mode state=Mode::Active;
  Metrics debug{};
};
}
