#include "motion_match.hpp"
#include <algorithm>
#include <limits>

namespace pes3 {
namespace {
float bounded(float x) { return std::max(0.f,std::min(1.f,x)); }
Rotation interpolate(Rotation a,Rotation b,float weight) {
  float dot=0;for(unsigned i=0;i<4;++i)dot+=a[i]*b[i];
  if(dot<0)for(auto& v:b)v=-v;
  Rotation result;for(unsigned i=0;i<4;++i)result[i]=a[i]*(1-weight)+b[i]*weight;
  unitRotation(result,result);return result;
}
bool valid(const NativePose& p) {
  if(!std::isfinite(p.rootHeight)||p.rootHeight<-.5f||p.rootHeight>5)return false;
  for(const auto& q:p.local) { Rotation unit;if(!unitRotation(q,unit))return false; }
  for(const auto& p:p.positions)for(float v:p)if(!std::isfinite(v)||std::fabs(v)>10)return false;
  return true;
}
struct Features {
  NativePoints positions;
  std::array<Point,4> forwards;
};
Features features(const NativePose& pose) {
  Features result;result.positions=pose.positions;NativeRotations global;
  for(unsigned i=0;i<13;++i) {
    const int parent=nativeParents[i];
    global[i]=parent<0?pose.local[i]:productRotation(global[parent],pose.local[i]);
  }
  const unsigned bones[4]={0,2,9,12};
  for(unsigned i=0;i<4;++i)result.forwards[i]=rotatePoint(global[bones[i]],{{0,-1,0}});
  return result;
}
constexpr unsigned oppositeBone[13]={0,1,2,5,6,3,4,10,11,12,7,8,9};
Features reflected(const Features& source) {
  Features result;
  for(unsigned i=0;i<13;++i) {
    result.positions[i]=source.positions[oppositeBone[i]];result.positions[i][0]*=-1;
  }
  for(unsigned i=0;i<4;++i) {
    result.forwards[i]=source.forwards[i<2?i:5-i];result.forwards[i][0]*=-1;
  }
  return result;
}
float poseError(const Features& a,const Features& b,int contactBone) {
  // Compare native proportions and actor-relative joint positions, with
  // additional weight on the commanded foot/head and the supporting leg.
  const float weights[13]={1,1,2,.35f,.6f,.35f,.6f,.5f,1.5f,2,.5f,1.5f,2};
  float error=0,total=0;
  for(unsigned i=0;i<13;++i) {
    float w=weights[i]*(int(i)==contactBone?4.f:1.f);
    Point d=subtractPoint(a.positions[i],b.positions[i]);
    // Root X/Y belongs to the native simulation, never to the source bank.
    if(i==0)d[0]=d[1]=0;
    error+=w*dotPoint(d,d);total+=w;
  }
  // Prevent matching a backwards head/foot or reversed torso just because
  // its joint centers happen to occupy similar positions.
  for(unsigned i=0;i<4;++i) {
    const auto d=subtractPoint(a.forwards[i],b.forwards[i]);
    error+=.08f*dotPoint(d,d);total+=.08f;
  }
  return error/total;
}
Features approximate(const std::array<Features,17>& poses,float phase) {
  float index=bounded(phase)*16;
  unsigned lo=std::min(15u,unsigned(index));float w=index-lo;
  Features p=poses[lo];
  for(unsigned i=0;i<13;++i) {
    p.positions[i]=addPoint(scalePoint(p.positions[i],1-w),scalePoint(poses[lo+1].positions[i],w));
  }
  for(unsigned i=0;i<4;++i)p.forwards[i]=addPoint(scalePoint(p.forwards[i],1-w),scalePoint(poses[lo+1].forwards[i],w));
  return p;
}
}
float warpPhase(float time,float nativeContact,float sourceContact) {
  if(!std::isfinite(time)||!std::isfinite(nativeContact)||!std::isfinite(sourceContact))return 0;
  time=bounded(time);sourceContact=bounded(sourceContact);
  if(nativeContact<=0||nativeContact>=1)return time;
  return time<=nativeContact ? time/nativeContact*sourceContact :
    sourceContact+(time-nativeContact)/(1-nativeContact)*(1-sourceContact);
}
bool rebuildPose(const NativeBind& bind,NativePose& pose,bool groundSupport) {
  if(!std::isfinite(pose.rootHeight))return false;
  NativeRotations global;NativePoints points;
  for(unsigned i=0;i<13;++i) {
    if(!unitRotation(pose.local[i],pose.local[i]))return false;
    const int parent=nativeParents[i];
    global[i]=parent<0?pose.local[i]:productRotation(global[parent],pose.local[i]);
    points[i]=parent<0?Point{{0,0,pose.rootHeight}}:
      addPoint(points[parent],rotatePoint(global[parent],bind.offsets[i]));
  }
  if(groundSupport) {
    float minimum=std::numeric_limits<float>::max();
    for(unsigned foot=0;foot<2;++foot)for(unsigned corner=0;corner<8;++corner) {
      Point p;for(unsigned axis=0;axis<3;++axis)
        p[axis]=(corner&(1u<<axis))?bind.footMax[foot][axis]:bind.footMin[foot][axis];
      const unsigned ankle=foot?12:9;
      minimum=std::min(minimum,points[ankle][2]+rotatePoint(global[ankle],p)[2]);
    }
    const float lift=std::max(0.f,.008f-minimum);
    pose.rootHeight+=lift;for(auto& p:points)p[2]+=lift;
  }
  pose.positions=points;return valid(pose);
}
bool blendPose(const NativeBind& bind,const NativePose& a,const NativePose& b,
               float weight,NativePose& out,bool groundSupport) {
  if(!std::isfinite(weight)||!valid(a)||!valid(b))return false;
  weight=bounded(weight);NativePose p;
  p.rootHeight=a.rootHeight*(1-weight)+b.rootHeight*weight;
  for(unsigned i=0;i<13;++i)p.local[i]=interpolate(a.local[i],b.local[i],weight);
  if(!rebuildPose(bind,p,groundSupport))return false;
  out=p;return true;
}
bool mirrorPose(const NativeBind& bind,const NativePose& pose,NativePose& out) {
  if(!valid(pose))return false;
  NativePose result=pose;
  for(unsigned i=0;i<13;++i) {
    const auto& q=pose.local[oppositeBone[i]];
    result.local[i]={{q[0],-q[1],-q[2],q[3]}};
  }
  if(!rebuildPose(bind,result,true))return false;
  out=result;return true;
}
bool MotionMatcher::retarget(unsigned clip,float phase,NativePose& out) const {
  if(!bank)return false;
  Frame frame;if(!bank->sample(clip,phase,frame))return false;
  SourceRotations rotations;SourcePoints points;
  for(unsigned i=0;i<19;++i) {
    rotations[i]=frame.rig.bones[i].composed_rotation;
    const auto& p=frame.rig.bones[i].composed_translation;
    points[i]=scalePoint(sourcePointToNative({{p[0],p[1],p[2]}}),1.8f/670.5759f);
  }
  return retargetSkeleton(rotations,reference,points,referencePoints,bind,out);
}
bool MotionMatcher::initialize(const AnimationBank& source,const NativeBind& native) {
  library.clear();bank=&source;bind=native;
  if(source.count()<48)return false;
  Frame frame;if(!bank->sample(47,0,frame))return false;
  for(unsigned i=0;i<19;++i) {
    reference[i]=frame.rig.bones[i].composed_rotation;
    const auto& p=frame.rig.bones[i].composed_translation;
    referencePoints[i]=scalePoint(sourcePointToNative({{p[0],p[1],p[2]}}),1.8f/670.5759f);
  }
  for(unsigned clip=0;clip<bank->count();++clip) {
    Candidate candidate;candidate.clip=clip;bool ok=bank->duration(clip)>0;
    for(unsigned i=0;ok&&i<17;++i)ok=retarget(clip,bank->duration(clip)*i/16,candidate.poses[i]);
    if(ok)library.push_back(candidate);
  }
  return !library.empty();
}
MotionChoice MotionMatcher::choose(const MotionRequest& request) const {
  MotionChoice best;best.error=std::numeric_limits<float>::max();
  if(!std::isfinite(request.contact)||request.contact< -1||request.contact>1||
     (request.contactBone!=-1&&request.contactBone!=2&&request.contactBone!=9&&request.contactBone!=12))return best;
  for(const auto& pose:request.poses)if(!valid(pose))return best;
  std::array<Features,trajectorySamples> targets;
  for(unsigned i=0;i<trajectorySamples;++i)targets[i]=features(request.poses[i]);
  const bool contact=request.contact>=0 && request.contactBone>=0;
  for(const auto& candidate:library) {
    // Compute directional features once per sampled pose, rather than
    // rebuilding quaternion hierarchies for every possible contact clock.
    std::array<Features,17> measured;
    for(unsigned i=0;i<17;++i)measured[i]=features(candidate.poses[i]);
    for(unsigned mirror=0;mirror<2;++mirror) {
      if(mirror)for(auto& pose:measured)pose=reflected(pose);
      // A contact at an endpoint cannot be warped into the middle while
      // preserving that same endpoint. Constrain its source anchor as well.
      const unsigned firstAnchor=!contact?8:request.contact==0?0:request.contact==1?16:3;
      const unsigned lastAnchor=!contact?8:request.contact==0?0:request.contact==1?16:13;
      for(unsigned anchor=firstAnchor;anchor<=lastAnchor;++anchor) {
        const float sourceContact=anchor/16.f;
        float error=0;Features previous;
        for(unsigned i=0;i<trajectorySamples;++i) {
          const float phase=warpPhase(i/float(trajectorySamples-1),request.contact,sourceContact);
          auto pose=approximate(measured,phase);
          error+=poseError(targets[i],pose,request.contactBone);
          if(i) {
            // Match swing direction and excursion, not merely a static pose.
            for(unsigned bone:{2u,4u,6u,9u,12u}) {
              const auto sourceDelta=subtractPoint(pose.positions[bone],previous.positions[bone]);
              const auto nativeDelta=subtractPoint(request.poses[i].positions[bone],request.poses[i-1].positions[bone]);
              const auto d=subtractPoint(sourceDelta,nativeDelta);error+=.12f*dotPoint(d,d);
            }
          }
          previous=pose;
        }
        if(contact) {
          const float index=request.contact*(trajectorySamples-1);
          const unsigned lo=std::min(trajectorySamples-2,unsigned(index));const float w=index-lo;
          const auto target=addPoint(scalePoint(request.poses[lo].positions[request.contactBone],1-w),
                                    scalePoint(request.poses[lo+1].positions[request.contactBone],w));
          const auto source=measured[anchor].positions[request.contactBone];
          const auto d=subtractPoint(target,source);
          error+=4*dotPoint(d,d);
        }
        error/=trajectorySamples;
        if(error<best.error) { best.clip=candidate.clip;best.sourceContact=sourceContact;best.error=error;best.mirrored=mirror!=0; }
      }
    }
  }
  // Incompatible poses retain the working native animation. This bound is
  // an adapter policy, not an inferred PES threshold or physical unit scale.
  best.accepted=best.error<.12f;
  return best;
}
bool MotionMatcher::sample(const MotionChoice& choice,float time,float contact,NativePose& out) const {
  if(!(choice.accepted&&bank&&choice.clip<bank->count()&&std::isfinite(time)&&
    std::isfinite(contact)&&contact>=-1&&contact<=1&&std::isfinite(choice.sourceContact)&&
    choice.sourceContact>=0&&choice.sourceContact<=1))return false;
  if((contact==0&&choice.sourceContact!=0)||(contact==1&&choice.sourceContact!=1))return false;
  NativePose result;
  if(!retarget(choice.clip,warpPhase(time,contact,choice.sourceContact)*bank->duration(choice.clip),result))return false;
  if(choice.mirrored&&!mirrorPose(bind,result,result))return false;
  out=result;return true;
}
} // namespace pes3
