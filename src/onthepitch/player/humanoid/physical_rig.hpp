#pragma once
// Native-rig physics experiment. SI units, +Z up, fixed-step integration.
// No source motion data, trained policy or proprietary animation is embedded.
#include "../../../pes3/native_pose.hpp"
#include "situational_action.hpp"
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
  // 0 approved hybrid, 1 generated locomotion reference, 2 free-body lab.
  unsigned controller=0;
  Pose pose{};
  Vec pelvis{{0,0,.96f}},velocity{{0,0,0}},forward{{0,-1,0}};
  Vec reach{{0,0,0}},opponent{{0,0,0}};
  Vec handTarget{{0,0,0}};
  Vec receptionSupport{{0,0,0}};int receptionSupportBone=-1;
  int reachBone=-1;
  float reachWeight=0,opponentDistance=100;
  Vec ballImpact{{0,0,0}},ballImpactLever{{0,0,.5f}};float ballImpactAge=-1;
  bool action=false,upperReception=false,protect=false,handTargetActive=false,gripped=false;
  bool matchedReference=false;
  bool staggering=false,passiveTracking=false,touchPending=false,grounding=false;
  football_situations::Context situation;
};
struct Metrics {
  float lean=0,turnRate=0,supportMargin=0,effort=0,reach=0,penetration=0;
  float angularSpeed=0,kineticEnergy=0,jointError=0;
  unsigned groundContacts=0;
  float selfPenetration=0,brace=0,recoveryPhase=0;
  float balanceRisk=0,stepDemand=0,armSpeed=0,elbowAngle=0;
  float armLimitError=0,armPenetration=0;
  float muscleEffort=0,supportTorque=0;
  float protectiveReach=0,fallControl=0;
  unsigned physicalWorldBuilds=0,protectiveHands=0;
  unsigned supportFeet=0;
  bool arrestedFall=false;
  unsigned dynamicSegments=0;
  float fullBodyUpright=0,fullBodyHeight=0,fullBodySpeed=0,fullBodyTorque=0,fullBodyResidual=0;
  float motorError=0,motorAcceleration=0;
  unsigned neuralMotorSamples=0;
  float counterbalance=0;
  float supportSink=0,supportTilt=0,supportKnee=0,supportFootError=0;
  float plantedCorrection=0;
  float recoveryStep=0,recoveryLift=0,recoverySupportError=0;
  int recoveryFoot=-1;
  football_situations::ActionMetrics situation;
  float situationTrunk=0,situationArms=0,situationFootError=0,situationRootError=0;
  int balancePhase=0,balanceChoice=-1;
};
struct RecoveryKey { Pose pose{}; Vec pelvis{{0,0,0}}; };
using RecoveryMotion=std::vector<RecoveryKey>;
struct BalanceMotion {RecoveryMotion frames;Vec push{{0,-1,0}};float speed=0,gain=1,lateral=0;};

class ArticulatedBody;
class BalanceController;
class ProceduralReference;
class PhysicalRig {
 public:
  PhysicalRig();
  ~PhysicalRig();
  void configure(const pes3::NativeBind &bind,float heightScale);
  void setRecoveryMotions(RecoveryMotion front,RecoveryMotion back);
  void setBalanceMotions(std::vector<BalanceMotion> motions);
  void setSharedBalanceMotions(std::shared_ptr<const std::vector<BalanceMotion>> motions);
  void reset();
  void impulse(Vec newtonSeconds,Vec lever={{0,0,.35f}},bool forceFall=false);
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
  bool fullyDynamic()const{return controller==2;}
  const Pose &additivePose()const{return additive;}
  Vec balanceVelocity()const;
  bool adoptContactHand(Vec target);
  int activeHandBone()const{return handInitialized?handShoulder+1:-1;}
  float renderWeight()const{return state==Mode::Active?0.f:1.f;}
  float age()const{return stateAge;}
  static constexpr float mass=84.f;
 private:
  void forwardKinematics();
  void updateSupportStep(const Input &input,const Points &source,float dt,float impulseSize);
  void applySupportStep(const Input &input);
  void solveLeg(unsigned hip,Vec target,float edgeMargin=.003f);
  void reachHand(unsigned shoulder,Vec target,float weight);
  void separateArms();
  void recover(const Input &input);
  void groundRecovery();
  pes3::NativeBind reference{};
  Pose local{},world{};
  Pose additive{};
  std::unique_ptr<ArticulatedBody> articulated;
  std::unique_ptr<BalanceController> balance;
  std::unique_ptr<ProceduralReference> procedural;
  unsigned controller=0;
  float fullBodyWarmup=0;Pose fullBodyStanding{};
  Input proceduralInput;
  std::shared_ptr<const std::vector<BalanceMotion>> balanceMotions=std::make_shared<const std::vector<BalanceMotion>>();
  int balanceChoice=-1,handShoulder=3;
  float balanceMotionTime=0,handEnvelope=0,handDt=.01f;
  bool forcedFall=false,handUpdatePending=false,handInitialized=false;
  bool deliberateFall=false;
  float fallStandingHeight=.96f,arrestTime=0;
  Quat handPose[2];
  Vec handVelocity[2]{};
  Vec lastHandTarget{{0,0,0}};
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
  Vec counterTilt{{0,0,0}},counterTiltVelocity{{0,0,0}};
  Vec impactReflex{{0,0,0}},impactReflexVelocity{{0,0,0}};
  Vec supportTilt{{0,0,0}},supportTiltVelocity{{0,0,0}};
  float supportSink=0,supportSinkVelocity=0;
  Vec sourceFeet[2]{},plantAnchor[2]{},plantOffset[2]{};
  float plantAge[2]={0,0},plantHeight[2]={0,0};
  bool sourceFeetReady=false;
  int recoveryFoot=-1;
  float stepTime=0,stepDuration=.44f,stepCooldown=0,stepRelease=0;
  Vec stepStart{},stepTarget{},stepSupport{},stepOffset[2]{};
  Vec pendingImpulse{{0,0,0}},pendingTorque{{0,0,0}},reachOffset{{0,0,0}};
  std::array<Vec,13> reachOffsets{};
  Vec recoveryStart{{0,0,0}};
  float scale=1,stateAge=0,filteredTurn=0,settled=0,unstableTime=0;
  bool ready=false;
  Mode state=Mode::Active;
  Metrics debug{};
  football_situations::ActionLayer situationLayer;
};
}
