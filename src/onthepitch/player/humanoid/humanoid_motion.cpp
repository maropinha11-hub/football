#include "humanoidbase.hpp"
#include "motion_matching.hpp"
#include "frame_motion_matching.hpp"
#include "strike_technique.hpp"
#include "pes_pose_matching.hpp"
#include "utils/animationextensions/footballanimationextension.hpp"
#include "../../../main.hpp"
#include "../../match.hpp"
#include <map>

void HumanoidBase::ComposeMatchedReference(football_physics::Input &input){
  using namespace football_physics;
  if(input.controller!=2||input.action||input.touchPending||input.upperReception||input.staggering||PhysicalRigBusy()||length(input.velocity)<.15f){
    if(fullMotionPlayer)fullMotionPlayer->reset();return;
  }
  if(!fullMotionPlayer)fullMotionPlayer.reset(new FrameMotionPlayer);
  static boost::weak_ptr<AnimCollection> owner;
  static std::shared_ptr<const ReferenceLibrary> cached;
  auto point=[](Vector3 p){return Vec{{p.coords[0],p.coords[1],p.coords[2]}};};
  auto rotation=[](Quaternion q){return Quat{{q.elements[0],q.elements[1],q.elements[2],q.elements[3]}};};
  if(owner.lock()!=anims||!cached){
    auto bank=std::make_shared<ReferenceLibrary>();unsigned id=0;
    for(Animation *clip:anims->GetAnimations()){
      const unsigned clipID=id++;
      if(clip->GetAnimType()!="movement"||clip->GetEffectiveFrameCount()<4||
         !clip->GetVariable("incoming_special_state").empty()||!clip->GetVariable("outgoing_special_state").empty()||
         !clip->GetVariable("incoming_retain_state").empty()||!clip->GetVariable("outgoing_retain_state").empty())continue;
      const int end=clip->GetEffectiveFrameCount();
      auto rootAt=[&](int f){Quaternion q;Vector3 root;clip->GetKeyFrame("player",std::min(f,end),q,root);
        if(f>end)root+=Vector3(0,-clip->GetOutgoingVelocity(),0).GetRotated2D(clip->GetOutgoingAngle())*((f-end)*.01f);
        return root;};
      auto sample=[&](int f,Quaternion *q,Quaternion *global,Vector3 *p){
        Vector3 unused;p[0]=Vector3(0,0,(pes3NativeReference.offsets[0][2]+rootAt(f).coords[2])*zMultiplier);
        for(unsigned bone=0;bone<13;++bone)clip->GetKeyFrame(pes3::nativeBoneNames[bone],std::min(f,end),q[bone],unused);
        ContactForwardKinematics(q,global,p);};
      for(int frame=0;frame<=end;++frame){
        ReferenceFrame row;row.clip=clipID;row.frame=frame;row.end=end;
        Quaternion q[13],global[13],nq[13],ng[13];Vector3 p[13],next[13];
        sample(frame,q,global,p);sample(frame+1,nq,ng,next);
        for(unsigned bone=0;bone<13;++bone){row.pose[bone]=rotation(q[bone]);
          row.velocity[bone]=scalePoint(logarithm(productRotation(rotation(nq[bone]),inverseRotation(row.pose[bone]))),100.f);}
        row.height=p[0].coords[2];
        const unsigned joints[5]={9,12,2,4,6};
        for(unsigned j=0;j<5;++j){row.feature.positions[j]=point(p[joints[j]]-p[0]);
          row.feature.velocities[j]=point(((next[joints[j]]-next[0])-(p[joints[j]]-p[0]))*100.f);}
        const Vector3 origin=rootAt(frame);
        for(unsigned t=0;t<3;++t){const int future=frame+(t+1)*15;
          row.feature.trajectory[t]=point((rootAt(future)-origin).Get2D());
          Quaternion futureQ;Vector3 ignored;clip->GetKeyFrame("body",std::min(future,end),futureQ,ignored);
          row.feature.facing[t]=point(futureQ*Vector3(0,-1,0));}
        for(unsigned side=0;side<2;++side){const unsigned foot=side?12:9;
          row.support[side]=p[foot].coords[2]<.12f&&std::fabs((next[foot]-p[foot]).coords[2])<.004f?1.f:0.f;}
        bank->frames.push_back(row);
      }
    }
    owner=anims;cached=bank;
    printf("FRAME_REFERENCE_BANK frames=%zu source=native_locomotion contact_actions=excluded\n",bank->frames.size());fflush(stdout);
  }
  fullMotionPlayer->library=cached;
  MotionFeature query;const unsigned joints[5]={9,12,2,4,6};
  const bool actual=physicalRig&&physicalRig->initialized();
  Quaternion heading;heading.SetAngleAxis(spatialState.angle,Vector3(0,0,1));
  const Quaternion inverse=heading.GetInverse();
  const auto &positions=actual?physicalRig->points():Points{};
  for(unsigned j=0;j<5;++j){const Vector3 p=actual?Vector3(positions[joints[j]][0]-positions[0][0],positions[joints[j]][1]-positions[0][1],positions[joints[j]][2]-positions[0][2]):contactPositions[joints[j]]-contactPositions[0];
    query.positions[j]=point(inverse*p);}
  fullMotionPlayer->observeQuery(query,.01f);
  const Vector3 desired=inverse*Vector3(input.velocity[0],input.velocity[1],input.velocity[2]);
  for(unsigned t=0;t<3;++t){query.trajectory[t]=point(desired*((t+1)*.15f));query.facing[t]={{0,-1,0}};}
  std::array<float,2> support{{0,0}};
  if(actual)for(unsigned side=0;side<2;++side)support[side]=positions[side?12:9][2]<.12f?1.f:0.f;
  Pose chosen;float height;
  if(!fullMotionPlayer->step(query,support,.01f,chosen,height))return;
  const Quat head=input.pose[2];
  input.pose=chosen;input.pose[0]=normalized(productRotation(rotation(heading),chosen[0]));input.pose[2]=head;
  input.pelvis[2]=height;input.matchedReference=true;
  if(GetConfiguration()->GetBool("training_telemetry",false)&&match->GetActualTime_ms()%100==0){
    const auto &frame=cached->frames[fullMotionPlayer->selectedIndex()];const auto &found=fullMotionPlayer->lastSearch;
    printf("FRAME_REFERENCE_MATCH t=%lu clip=%u frame=%u indexed=%zu tested=%u cost=%.6f kind=locomotion\n",match->GetActualTime_ms(),frame.clip,frame.frame,cached->frames.size(),found.tested,found.cost);
  }
}

void HumanoidBase::RankMotionMatches(DataSet &candidates,const PlayerCommand &command){
  if(!PhysicalRigEnabled() || candidates.empty())return;
  using namespace football_physics;
  const unsigned joints[5]={9,12,2,4,6};
  auto extract=[&](Animation *clip,int frame,float yaw){
    auto rootAt=[&](int f){Quaternion q;Vector3 p;const int end=clip->GetEffectiveFrameCount();
      clip->GetKeyFrame("player",std::min(f,end),q,p);
      if(f>end)p+=Vector3(0,-clip->GetOutgoingVelocity(),0).GetRotated2D(clip->GetOutgoingAngle())*((f-end)*.01f);
      return p;
    };
    auto sample=[&](int f,Quaternion *global,Vector3 *positions){
      Quaternion local[13];Vector3 unused;positions[0]=rootAt(f).GetRotated2D(yaw);
      Quaternion turn;turn.SetAngleAxis(yaw,Vector3(0,0,1));
      for(unsigned i=0;i<13;++i)clip->GetKeyFrame(pes3::nativeBoneNames[i],std::min(f,clip->GetEffectiveFrameCount()),local[i],unused);
      local[0]=turn*local[0];ContactForwardKinematics(local,global,positions);
    };
    MotionFeature result;Quaternion q[13],nextQ[13];Vector3 p[13],next[13];
    sample(frame,q,p);sample(frame+1,nextQ,next);
    for(unsigned i=0;i<5;++i){
      Vector3 position=p[joints[i]]-p[0];Vector3 velocity=(next[joints[i]]-p[joints[i]])*100;
      result.positions[i]={{position.coords[0],position.coords[1],position.coords[2]}};
      result.velocities[i]={{velocity.coords[0],velocity.coords[1],velocity.coords[2]}};
    }
    const Vector3 origin=rootAt(frame);
    for(unsigned i=0;i<3;++i){const int future=frame+int(i+1)*15;sample(future,q,p);
      Vector3 trajectory=(rootAt(future)-origin).Get2D().GetRotated2D(yaw);
      Vector3 facing=q[0]*Vector3(0,-1,0);
      result.trajectory[i]={{trajectory.coords[0],trajectory.coords[1],0}};
      result.facing[i]={{facing.coords[0],facing.coords[1],0}};
    }
    return result;
  };
  MotionFeature query=extract(currentAnim->anim,currentAnim->frameNum,startAngle-spatialState.angle);
  MotionFeature pesQuery=query;
  for(unsigned i=0;i<5;++i){
    const Vector3 actual=(contactPositions[joints[i]]-contactPositions[0]).GetRotated2D(-spatialState.angle);
    pesQuery.positions[i]={{actual.coords[0],actual.coords[1],actual.coords[2]}};
  }
  const Vector3 desired=(command.useDesiredMovement?command.desiredDirection*command.desiredVelocityFloat:spatialState.movement).GetRotated2D(-spatialState.angle);
  const Vector3 facing=(command.useDesiredLookAt?command.desiredLookAt-spatialState.position:spatialState.bodyDirectionVec).Get2D().GetRotated2D(-spatialState.angle).GetNormalized(Vector3(0,-1,0));
  for(unsigned i=0;i<3;++i){const float time=(i+1)*.15f;
    query.trajectory[i]={{desired.coords[0]*time,desired.coords[1]*time,0}};
    query.facing[i]={{facing.coords[0],facing.coords[1],0}};
    pesQuery.trajectory[i]=query.trajectory[i];pesQuery.facing[i]=query.facing[i];
  }
  // Contact clips enter at their authored beginning. This is a constrained
  // motion-matching search: native reach/timing feasibility still follows it.
  // Jumping to arbitrary kick frames would discard the ball-contact marker.
  static std::map<const Animation*,MotionFeature> database;
  // Forward kinematics scales offsets to this actor's height. The learned
  // descriptor then normalizes by that same height; sharing a descriptor
  // extracted for another player distorts both pose and support features.
  // Preserve the native cache/cost path and key imported entries by scale.
  static std::map<std::pair<const Animation*,float>,MotionFeature> pesDatabase;
  static boost::weak_ptr<AnimCollection> databaseOwner;
  if(databaseOwner.lock()!=anims){database.clear();pesDatabase.clear();databaseOwner=anims;}
  std::map<int,float> costs;
  const bool preferRight=command.desiredFunctionType==e_FunctionType_BallControl;
  const bool strike=command.desiredFunctionType==e_FunctionType_ShortPass||command.desiredFunctionType==e_FunctionType_LongPass||command.desiredFunctionType==e_FunctionType_Shot||command.desiredFunctionType==e_FunctionType_HighPass;
  const Vector3 ballLocal=(match->GetBall()->Predict(100)-spatialState.position).GetRotated2D(-spatialState.angle);
  const Vector3 aim=command.touchInfo.desiredDirection.GetRotated2D(-spatialState.angle);
  const float opening=std::atan2(aim.coords[0],-aim.coords[1]);
  const auto technique=football_strike::choose(command.touchInfo.desiredPower,opening,ballLocal.coords[0],spatialState.floatVelocity,command.desiredFunctionType==e_FunctionType_Shot);
  const auto learnedQuery=football_pes_matching::features(pesQuery,contactPositions[0].coords[2],zMultiplier);
  float nearestOpponent=30;
  std::vector<Player*> opposition;match->GetTeam(1-static_cast<Player*>(player)->GetTeamID())->GetActivePlayers(opposition);
  for(auto *other:opposition)nearestOpponent=std::min(nearestOpponent,(other->GetPosition()-spatialState.position).Get2D().GetLength());
  unsigned pesCompared=0;
  for(int id:candidates){auto *clip=anims->GetAnim(id);
    auto found=database.find(clip);if(found==database.end())found=database.emplace(clip,extract(clip,0,0)).first;
    costs[id]=motionCost(query,found->second);
    if(clip->GetVariable("pes_bulk")=="true"){
      const auto key=std::make_pair(static_cast<const Animation*>(clip),zMultiplier);
      auto scaled=pesDatabase.find(key);
      if(scaled==pesDatabase.end())scaled=pesDatabase.emplace(key,extract(clip,0,0)).first;
      Quaternion ignored;Vector3 root;clip->GetKeyFrame("player",0,ignored,root);
      costs[id]=football_pes_matching::cost(learnedQuery,football_pes_matching::features(scaled->second,(.96f+root.coords[2])*zMultiplier,zMultiplier));
      auto extension=boost::static_pointer_cast<FootballAnimationExtension>(clip->GetExtension("football"));
      Vector3 contact;int frame=-1;
      if(extension&&extension->GetFirstTouch(contact,frame)){
        const Vector3 arrival=(match->GetBall()->Predict(std::max(0,frame)*10)-spatialState.position).GetRotated2D(-spatialState.angle);
        const Vector3 error=arrival-Vector3(contact.coords[0],contact.coords[1],contact.coords[2]*zMultiplier);
        costs[id]+=.4f*std::min(9.f,error.Get2D().GetSquaredLength())+2.f*error.coords[2]*error.coords[2];
        costs[id]+=.8f*std::max(0,frame)*.01f;
        // Shorter preparation is preferable under real opponent pressure.
        costs[id]+=.25f*std::max(0.f,2.f-nearestOpponent)*frame*.01f;
      }
      const Vector3 end=spatialState.position+clip->GetOutgoingMovement().GetRotated2D(spatialState.angle)*.35f;
      costs[id]+=2.f*std::max(0.f,std::fabs(end.coords[0])-pitchHalfW)+2.f*std::max(0.f,std::fabs(end.coords[1])-pitchHalfH);
      ++pesCompared;
    }
    if(command.useDesiredTripDirection){
      // Pose continuity is a secondary preference for impacts. A front brace
      // may resemble idle more closely than a side step, but cannot recover
      // a lateral blow. Preserve the native incident-direction constraint.
      const Vector3 incident=command.desiredTripDirection.GetRotated2D(-spatialState.angle).Get2D().GetNormalized(Vector3(0,-1,0));
      const Vector3 authored=GetVectorFromString(clip->GetVariable("bumpdirection")).Get2D().GetNormalized(incident);
      costs[id]+=80.f*(1.f-incident.GetDotProduct(authored));
    }
    if(preferRight && clip->GetVariable("touch_bodypart")!="right_foot")costs[id]+=10.f;
    if(strike && clip->GetVariable("touch_bodypart").find("foot")!=std::string::npos){
      if(clip->GetVariable("touch_bodypart")=="left_foot")costs[id]+=2.f;
      const auto style=clip->GetVariable("physical_technique");
      if(!style.empty())costs[id]+=style==football_strike::name(technique)?-4.f:8.f;
    }
  }
  std::stable_sort(candidates.begin(),candidates.end(),[&](int a,int b){return costs[a]<costs[b];});
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("MOTION_MATCH t=%lu candidates=%zu indexed=%zu choice=%d cost=%.6f function=%d\n",match->GetActualTime_ms(),candidates.size(),database.size(),candidates.front(),costs[candidates.front()],int(command.desiredFunctionType));
  if(pesCompared&&GetConfiguration()->GetBool("training_telemetry",false))
    printf("PES_LEARNED_MATCH t=%lu actor=%d compared=%u dimensions=50 choice=%s cost=%.6f opponent=%.4f\n",
      match->GetActualTime_ms(),player->GetID(),pesCompared,anims->GetAnim(candidates.front())->GetName().c_str(),costs[candidates.front()],nearestOpponent);
}
