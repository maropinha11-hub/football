#include "humanoidbase.hpp"
#include "motion_matching.hpp"
#include "learned_motion_metric.hpp"
#include "../../../main.hpp"
#include "../../match.hpp"
#include <fstream>
#include <iomanip>
#include <map>

namespace football_physics {
struct NativeMotionBank {
  std::map<const Animation*,MotionClipIndex> clips;
  std::size_t frames=0;
  bool exported=false,announced=false;
};
}

int HumanoidBase::MotionEntryFrame(int id)const{
  const auto found=motionEntryFrames.find(id);
  return found==motionEntryFrames.end()?0:found->second;
}

bool HumanoidBase::MotionMixerActive()const{
  return motionBlendFrom&&currentAnim->functionType==e_FunctionType_Movement&&PhysicalRigEnabled()&&
    GetConfiguration()->GetBool("training_motion_matching",true)&&GetConfiguration()->GetBool("training_motion_mixer",true);
}

void HumanoidBase::BeginMotionBlend(int incomingId,e_FunctionType function,int entry){
  if(!PhysicalRigEnabled()||!GetConfiguration()->GetBool("training_motion_matching",true)||
      !GetConfiguration()->GetBool("training_motion_mixer",true)||function!=e_FunctionType_Movement||
      currentAnim->functionType!=e_FunctionType_Movement||!physicalRig||!physicalRig->initialized()){
    motionBlendFrom=nullptr;return;
  }
  if(incomingId==currentAnim->id&&entry>=currentAnim->frameNum&&entry<=currentAnim->frameNum+2)return;
  motionBlendFrom=currentAnim->anim;motionBlendFrame=std::max(0,currentAnim->frameNum-1);
  motionBlendStart=match->GetActualTime_ms();
  const float begin=std::min(1.f,(motionBlendFrame+1)/std::min(16.f,float(motionBlendFrom->GetEffectiveFrameCount()+1)));
  motionBlendFacing=startAngle+currentAnim->rotationSmuggle.begin*(1-begin)+currentAnim->rotationSmuggle.end*begin;
  Quaternion local[13],global[13];Vector3 positions[13];
  SampleContactAnimation(motionBlendFrom,motionBlendFrame,spatialState.position,motionBlendFacing,false,local,global,positions);
  for(unsigned i=0;i<13;++i){const auto &q=physicalRig->motionPose()[i];
    motionBlendCarry[i]=(Quaternion(q[0],q[1],q[2],q[3])*local[i].GetInverse()).GetNormalized();}
  motionBlendHeight=contactPositions[0].coords[2]-physicalRig->rootOffset()[2]-positions[0].coords[2];
}

void HumanoidBase::BlendMotionPose(Quaternion *pose,Vector3 &root){
  if(!MotionMixerActive())return;
  const unsigned long elapsed=match->GetActualTime_ms()-motionBlendStart;
  if(elapsed>=140)return;
  const float weight=std::sin(.5f*pi*elapsed/140.f);
  float phase=motionBlendFrame+elapsed*.1f;
  const float end=motionBlendFrom->GetEffectiveFrameCount();
  if(motionBlendFrom->GetVariable("loop")=="true"&&end>0)phase=std::fmod(phase,end);
  else phase=std::min(phase,end);
  Quaternion local[13],global[13];Vector3 positions[13];
  SampleContactAnimation(motionBlendFrom,phase,root,motionBlendFacing,false,local,global,positions);
  for(unsigned i=0;i<13;++i){
    const Quaternion carry=motionBlendCarry[i].GetSlerped(weight,QUATERNION_IDENTITY);
    const Quaternion outgoing=(carry*local[i]).GetNormalized();
    pose[i]=outgoing.GetSlerped(weight,pose[i]).GetNormalized();
  }
  root.coords[2]=root.coords[2]*weight+(positions[0].coords[2]+motionBlendHeight*(1-weight))*(1-weight);
  if(GetConfiguration()->GetBool("training_telemetry",false)&&elapsed%20==0)
    printf("MOTION_MIXER t=%lu actor=%d age=%lu weight=%.6f source_phase=%.4f source=%s\n",match->GetActualTime_ms(),player->GetID(),elapsed,weight,phase,motionBlendFrom->GetName().c_str());
}

void HumanoidBase::RankMotionMatches(DataSet &candidates,const PlayerCommand &command){
  motionEntryFrames.clear();
  if(!PhysicalRigEnabled() || candidates.empty())return;
  using namespace football_physics;
  const bool adaptive=GetConfiguration()->GetBool("training_motion_matching",true);
  if(command.desiredFunctionType==e_FunctionType_Movement&&command.useDesiredMovement&&command.desiredVelocityFloat<.15f){
    auto stationary=candidates;
    stationary.erase(std::remove_if(stationary.begin(),stationary.end(),[&](int id){auto *clip=anims->GetAnim(id);
      return clip->GetVariable("imported_mocap")=="true"&&std::atof(clip->GetVariable("source_speed_mps").c_str())>.15f;
    }),stationary.end());
    if(!stationary.empty())candidates.swap(stationary);
  }
  const unsigned joints[5]={9,12,2,4,6};
  auto extract=[&](Animation *clip,int frame,float yaw){
    auto rootAt=[&](int f){Quaternion q;Vector3 p;const int end=clip->GetEffectiveFrameCount();
      clip->GetKeyFrame("player",std::min(f,end),q,p);
      if(f>end)p+=Vector3(0,-clip->GetOutgoingVelocity(),0).GetRotated2D(clip->GetOutgoingAngle())*((f-end)*.01f);
      return p;
    };
    auto sample=[&](int f,Quaternion *global,Vector3 *positions){
      Quaternion local[13];Vector3 unused;
      positions[0]=rootAt(f).GetRotated2D(yaw)+Vector3(0,0,.96f*zMultiplier);
      Quaternion turn;turn.SetAngleAxis(yaw,Vector3(0,0,1));
      for(unsigned i=0;i<13;++i)clip->GetKeyFrame(pes3::nativeBoneNames[i],std::min(f,clip->GetEffectiveFrameCount()),local[i],unused);
      local[0]=turn*local[0];ContactForwardKinematics(local,global,positions);
    };
    MotionFeature result;Quaternion q[13],nextQ[13];Vector3 p[13],next[13];
    sample(frame,q,p);sample(frame+1,nextQ,next);
    const Vector3 rootVelocity=(next[0]-p[0])*100;
    for(unsigned i=0;i<5;++i){
      const Vector3 position=(p[joints[i]]-p[0])/zMultiplier;
      const Vector3 velocity=((next[joints[i]]-next[0])-(p[joints[i]]-p[0]))*(100/zMultiplier)+rootVelocity;
      result.positions[i]={{position.coords[0],position.coords[1],position.coords[2]}};
      result.velocities[i]={{velocity.coords[0],velocity.coords[1],velocity.coords[2]}};
      if(i<2){
        const float height=p[joints[i]].coords[2]/zMultiplier;
        result.contacts[i]=clamp((.13f-height)/.09f,0.f,1.f)*clamp((1.4f-velocity.Get2D().GetLength())/1.4f,0.f,1.f);
      }
    }
    const Vector3 origin=rootAt(frame);
    for(unsigned i=0;i<3;++i){const int future=frame+int(i+1)*15;sample(future,q,p);
      const Vector3 trajectory=(rootAt(future)-origin).Get2D().GetRotated2D(yaw),facing=q[0]*Vector3(0,-1,0);
      result.trajectory[i]={{trajectory.coords[0],trajectory.coords[1],0}};
      result.facing[i]={{facing.coords[0],facing.coords[1],0}};
    }
    return result;
  };
  // Weak ownership avoids stale Animation* entries after an entire animation
  // collection is destroyed, while all 22 actors share the canonical cache.
  static std::map<const AnimCollection*,std::weak_ptr<NativeMotionBank>> banks;
  if(!motionBank){
    motionBank=banks[anims.get()].lock();
    if(!motionBank){motionBank=std::make_shared<NativeMotionBank>();banks[anims.get()]=motionBank;}
  }
  auto &database=*motionBank;
  auto index=[&](Animation *clip)->const MotionClipIndex&{
    auto found=database.clips.find(clip);
    if(found==database.clips.end()){
      MotionClipIndex entry;
      for(int frame=0;frame<=std::max(0,clip->GetEffectiveFrameCount()-2);frame+=2){
        MotionFrame row;row.frame=frame;row.feature=motionVector(extract(clip,frame,0));
        if(std::all_of(row.feature.begin(),row.feature.end(),[](float x){return std::isfinite(x);}))entry.frames.push_back(row);
      }
      entry.build();database.frames+=entry.frames.size();found=database.clips.emplace(clip,std::move(entry)).first;
    }
    return found->second;
  };
  const std::string dump=GetConfiguration()->Get("training_motion_dump","");
  if(!dump.empty()&&!database.exported){
    std::ofstream out(dump);out<<std::setprecision(8);unsigned id=0;
    for(auto *clip:anims->GetAnimations()){
      for(const auto &entry:index(clip).frames){
        out<<"{\"clip\":"<<id<<",\"name\":"<<std::quoted(clip->GetName())<<",\"kind\":"<<std::quoted(clip->GetAnimType())<<",\"frame\":"<<entry.frame<<",\"feature\":[";
        for(unsigned f=0;f<motionDimensions;++f){if(f)out<<',';out<<entry.feature[f];}out<<"]}\n";
      }
      ++id;
    }
    database.exported=bool(out);
    printf("MOTION_DATABASE_EXPORT clips=%zu frames=%zu dimensions=%u written=%d\n",database.clips.size(),database.frames,motionDimensions,database.exported?1:0);
  }
  MotionFeature query=extract(currentAnim->anim,currentAnim->frameNum,startAngle-spatialState.angle);
  // Query the executed skeleton, including upper-body balance, rather than
  // pretending the last clip's unsmoothed first pose is still being displayed.
  for(unsigned i=0;i<5;++i){
    const Vector3 p=((contactPositions[joints[i]]-contactPositions[0])/zMultiplier).GetRotated2D(-spatialState.angle);
    query.positions[i]={{p.coords[0],p.coords[1],p.coords[2]}};
    if(motionSampleValid){const Vector3 v=motionJointVelocities[i].GetRotated2D(-spatialState.angle);
      query.velocities[i]={{v.coords[0],v.coords[1],v.coords[2]}};
      if(i<2)query.contacts[i]=clamp((.13f-contactPositions[joints[i]].coords[2]/zMultiplier)/.09f,0.f,1.f)*clamp((1.4f-v.Get2D().GetLength())/1.4f,0.f,1.f);
    }
  }
  const Vector3 desired=(command.useDesiredMovement?command.desiredDirection*command.desiredVelocityFloat:spatialState.movement).GetRotated2D(-spatialState.angle);
  const Vector3 velocity=spatialState.movement.GetRotated2D(-spatialState.angle);
  const Vector3 facing=(command.useDesiredLookAt?command.desiredLookAt-spatialState.position:spatialState.bodyDirectionVec).Get2D().GetRotated2D(-spatialState.angle).GetNormalized(Vector3(0,-1,0));
  const Vector3 nowFacing=spatialState.bodyDirectionVec.GetRotated2D(-spatialState.angle);
  for(unsigned i=0;i<3;++i){const float time=(i+1)*.15f;
    const Vector3 trajectory=adaptive?desired*time+(velocity-desired)*((1-std::exp(-9.f*time))/9.f):desired*time;
    const Vector3 direction=(facing*(1-std::exp(-8.f*time))+nowFacing*std::exp(-8.f*time)).GetNormalized(facing);
    query.trajectory[i]={{trajectory.coords[0],trajectory.coords[1],0}};
    query.facing[i]={{direction.coords[0],direction.coords[1],0}};
  }
  const MotionVector queryVector=motionVector(query);MotionMetric metric;
  if(adaptive&&kMotionMetricTrained)for(unsigned i=0;i<motionDimensions;++i)metric.scale[i]=kMotionMetricScale[i];
  std::map<int,float> costs;unsigned tested=0;
  const bool preferRight=command.desiredFunctionType==e_FunctionType_BallControl;
  for(int id:candidates){auto *clip=anims->GetAnim(id);
    // Phase jumps are legal only in a steady, non-contact locomotion cycle.
    // Turns, starts, stops, kicks, catches and receptions retain their full
    // authored preparation and the native contact-feasibility solver.
    bool phases=adaptive&&command.desiredFunctionType==e_FunctionType_Movement&&
      clip->GetIncomingVelocity()>.5f&&std::fabs(clip->GetIncomingVelocity()-clip->GetOutgoingVelocity())<.15f&&
      std::fabs(clip->GetOutgoingAngle())<.025f&&std::fabs(clip->GetIncomingBodyAngle()-clip->GetOutgoingBodyAngle())<.05f;
    int earliest=0;
    const int latest=std::max(0,clip->GetEffectiveFrameCount()-std::min(14,clip->GetEffectiveFrameCount()/2));
    if(phases&&clip==currentAnim->anim){
      if(currentAnim->frameNum<=latest)earliest=currentAnim->frameNum;
      else phases=false;
    }
    auto result=index(clip).search(queryVector,metric,phases,earliest,phases?latest:0);
    if(!std::isfinite(result.cost))result=index(clip).search(queryVector,metric,false);
    if(phases&&clip==currentAnim->anim)result.frame=currentAnim->frameNum;
    costs[id]=result.cost;motionEntryFrames[id]=result.frame;tested+=result.tested;
    if(phases&&clip==currentAnim->anim&&GetConfiguration()->GetBool("training_motion_continuity",true))costs[id]*=.95f;
    if(command.useDesiredTripDirection){
      const Vector3 incident=command.desiredTripDirection.GetRotated2D(-spatialState.angle).Get2D().GetNormalized(Vector3(0,-1,0));
      const Vector3 authored=GetVectorFromString(clip->GetVariable("bumpdirection")).Get2D().GetNormalized(incident);
      costs[id]+=80.f*(1.f-incident.GetDotProduct(authored));
    }
    if(preferRight&&clip->GetVariable("touch_bodypart")!="right_foot")costs[id]+=10.f;
  }
  std::stable_sort(candidates.begin(),candidates.end(),[&](int a,int b){return costs[a]<costs[b];});
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("MOTION_MATCH t=%lu actor=%d candidates=%zu indexed=%zu frames=%zu tested=%u choice=%d entry=%d cost=%.6f function=%d adaptive=%d learned=%d source=%s\n",match->GetActualTime_ms(),player->GetID(),candidates.size(),database.clips.size(),database.frames,tested,candidates.front(),MotionEntryFrame(candidates.front()),costs[candidates.front()],int(command.desiredFunctionType),adaptive?1:0,kMotionMetricTrained?1:0,anims->GetAnim(candidates.front())->GetName().c_str());
}
