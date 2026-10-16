#include "humanoidbase.hpp"
#include "physical_rig.hpp"
#include "../../../main.hpp"
#include "../../match.hpp"
#include "../player.hpp"
#include "../controller/humancontroller.hpp"

namespace {
football_physics::Vec point(const Vector3 &p){return {{p.coords[0],p.coords[1],p.coords[2]}};}
Vector3 vector(football_physics::Vec p){return Vector3(p[0],p[1],p[2]);}
football_physics::Quat rotation(const Quaternion &q){return {{q.elements[0],q.elements[1],q.elements[2],q.elements[3]}};}
Quaternion quaternion(football_physics::Quat q){return Quaternion(q[0],q[1],q[2],q[3]);}
}

bool HumanoidBase::PhysicalRigEnabled()const {
  return UsesTrainingContacts() && (player->GetExternalController() || player==match->GetTrainingPartner()) &&
    GetConfiguration()->GetBool("training_physical_rig",false);
}
void HumanoidBase::ConfigurePhysicalRig(){
  if(physicalRig)return;
  physicalRig.reset(new football_physics::PhysicalRig);physicalRig->configure(pes3NativeReference,zMultiplier);
  football_physics::RecoveryMotion motions[2];
  const char *names[]={"000_stand_up_from_front.anim","000_stand_up_from_back.anim"};
  for(unsigned side=0;side<2;++side){
    Animation clip;clip.Load(std::string("media/animations/movement_special/idle/special/")+names[side]);
    for(int frame=0;frame<clip.GetFrameCount();++frame){
      football_physics::RecoveryKey key;Quaternion q;Vector3 p;
      clip.GetKeyFrame("player",frame,q,p);key.pelvis=point(p);
      for(unsigned i=0;i<13;++i){clip.GetKeyFrame(pes3::nativeBoneNames[i],frame,q,p);key.pose[i]=rotation(q);}
      motions[side].push_back(key);
    }
  }
  physicalRig->setRecoveryMotions(std::move(motions[0]),std::move(motions[1]));
  std::vector<football_physics::BalanceMotion> bank;
  unsigned sources=0;
  for(auto *clip:anims->GetAnimations())if(clip->GetAnimType()=="trip" && clip->GetVariable("triptype")=="1"){
    ++sources;
    const auto push=point(GetVectorFromString(clip->GetVariable("bumpdirection")));
    for(float gain:{.55f,.75f,1.f,1.25f})for(float cadence:{1.f,1.2f})for(float lateral:{-.035f,.035f}){
      football_physics::BalanceMotion motion;motion.push=push;motion.speed=clip->GetIncomingVelocity()/cadence;motion.gain=gain;motion.lateral=lateral;
      const int frames=int((clip->GetFrameCount()-1)*cadence)+1;
      for(int frame=0;frame<frames;++frame){
        football_physics::RecoveryKey key;Quaternion q;Vector3 p;
        const float phase=frame/cadence;const int a=int(phase),b=std::min(a+1,clip->GetFrameCount()-1);Quaternion qb;Vector3 pb;
        clip->GetKeyFrame("player",a,q,p);clip->GetKeyFrame("player",b,qb,pb);key.pelvis=point(p*(1-(phase-a))+pb*(phase-a));
        for(unsigned i=0;i<13;++i){clip->GetKeyFrame(pes3::nativeBoneNames[i],a,q,p);clip->GetKeyFrame(pes3::nativeBoneNames[i],b,qb,pb);key.pose[i]=football_physics::blended(rotation(q),rotation(qb),phase-a);}
        const float envelope=std::sin(pi*float(frame)/std::max(1,frames-1));
        key.pose[1]=football_physics::normalized(football_physics::productRotation(football_physics::exponential({{0,lateral*envelope,0}}),key.pose[1]));
        motion.frames.push_back(key);
      }
      bank.push_back(std::move(motion));
    }
  }
  printf("PHYSICAL_BALANCE_BANK actor=%d sources=%u variants=%u kind=native_procedural\n",player->GetID(),sources,unsigned(bank.size()));
  physicalRig->setBalanceMotions(std::move(bank));
}
void HumanoidBase::SetPhysicalGrip(const Vector3 &where,const Vector3 &force){physicalGripPoint=where;physicalGripForce=force;}
Vector3 HumanoidBase::GetPhysicalShirtPoint()const{
  Player *other=player==match->GetTrainingPartner()?match->GetTrainingPlayer():match->GetTrainingPartner();
  const Vector3 toward=other?(other->GetPosition()-spatialState.position).Get2D().GetNormalized(spatialState.bodyDirectionVec):spatialState.bodyDirectionVec;
  const Vector3 probe=contactPositions[1]+contactGlobal[1]*Vector3(0,0,.33f)*zMultiplier+toward*.5f;
  Vector3 surface;ContactSurface(probe,"trunk",contactGlobal,contactPositions,&surface);
  return surface;
}
float HumanoidBase::PhysicalHandDistance(const Vector3 &where)const{
  if(!physicalRig || !physicalRig->initialized())return 100;
  float distance=100;
  for(unsigned elbow:{4u,6u}){
    const auto hand=football_physics::addPoint(physicalRig->points()[elbow],football_physics::rotatePoint(physicalRig->worldRotations()[elbow],{{0,0,-.25f*zMultiplier}}));
    distance=std::min(distance,(where-vector(hand)).GetLength());
  }
  return distance;
}
bool HumanoidBase::PhysicalRigBusy()const {
  return PhysicalRigEnabled() && physicalRig && physicalRig->mode()!=football_physics::Mode::Active;
}
void HumanoidBase::ResetPhysicalRig(){
  if(physicalRig)physicalRig->reset();
  physicalRigTime=~0ul;physicalCollisionTime=0;buf_physicalRig.Clear();fetchedPhysicalRig=false;
  for(auto &buffer:buf_physicalAdditive)buffer.Clear();
  physicalGripForce=Vector3(0);physicalActionTime=0;physicalPartnerPhase=0;physicalShield=false;physicalHandTargetActive=false;
}
void HumanoidBase::PhysicalCollision(const Vector3 &change){
  if(!PhysicalRigEnabled() || match->GetActualTime_ms()<physicalCollisionTime || change.GetLength()<.5f)return;
  physicalCollisionTime=match->GetActualTime_ms()+220;
  AddPhysicalImpulse(change*football_physics::PhysicalRig::mass*.18f);
}
void HumanoidBase::TogglePhysicalRig(){
  const bool enabled=!GetConfiguration()->GetBool("training_physical_rig",false);
  if(PhysicalRigBusy())ResetPosition(spatialState.position,spatialState.position+spatialState.bodyDirectionVec);
  if(player->GetExternalController())player->GetExternalController()->Reset();
  GetConfiguration()->SetBool("training_physical_rig",enabled);ResetPhysicalRig();
  if(match->GetTrainingPartner() && match->GetTrainingPartner()!=player){
    auto *partner=match->GetTrainingPartner();
    partner->GetHumanoid()->ResetPosition(partner->GetPosition(),partner->GetPosition()+partner->GetBodyDirectionVec());
  }
  match->SpamMessage(enabled?"Fisica corporal: ligada | F8: impacto | F9: queda":"Fisica corporal: desligada",3500);
  printf("PHYSICAL_RIG_TOGGLE enabled=%d\n",enabled?1:0);fflush(stdout);
}
Vector3 HumanoidBase::PhysicalBalanceVelocity()const{return PhysicalRigEnabled() && physicalRig?vector(physicalRig->balanceVelocity()):Vector3(0);}
Vector3 HumanoidBase::SafeFirstPersonEye(const Vector3 &requested)const{
  Quaternion q[13];Vector3 p[13];
  const Vector3 origin=player->GetGeomPosition().Get2D();
  for(unsigned i=0;i<13;++i){const auto node=nodeMap.at(pes3::nativeBoneNames[i]);q[i]=node->GetDerivedRotation();p[i]=origin+(node->GetDerivedPosition()-origin)*zMultiplier;}
  Vector3 eye=requested;
  // Keep the camera sphere outside the torso and the moving upper arms.
  // These are rendered joints, not the older simulation snapshot.
  for(unsigned iteration=0;iteration<4;++iteration)for(unsigned bone:{0u,1u,3u,4u,5u,6u}){
    Vector3 a=p[bone],b=bone==0?p[1]:bone==1?p[2]:bone==3||bone==5?p[bone+1]:p[bone]+q[bone]*Vector3(0,0,-.25f*zMultiplier);
    const Vector3 axis=b-a;const float along=clamp((eye-a).GetDotProduct(axis)/std::max(.00001f,axis.GetSquaredLength()),0.f,1.f);
    const Vector3 closest=a+axis*along;
    const float radius=(bone<=1?.17f:.055f)*zMultiplier+.065f;
    if((eye-closest).GetLength()<radius)eye=closest+(eye-closest).GetNormalized(q[1]*Vector3(0,-1,0))*radius;
  }
  float gap=100;
  for(unsigned iteration=0;iteration<3;++iteration){
    Vector3 surface;gap=ContactSurface(eye,"trunk",q,p,&surface)+.11f;
    if(gap>=.065f)break;
    eye=surface+(eye-surface).GetNormalized(q[1]*Vector3(0,-1,0))*.065f;
  }
  gap=ContactSurface(eye,"trunk",q,p)+.11f;
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("PHYSICAL_EYE t=%lu clearance=%.6f correction=%.6f\n",fetchedbuf_animApplyBuffer.snapshotTime_ms,gap,(eye-requested).GetLength());
  return eye;
}
void HumanoidBase::AddPhysicalImpulse(const Vector3 &value,const Vector3 &lever,bool forceFall){
  if(!PhysicalRigEnabled())return;
  ConfigurePhysicalRig();
  physicalRig->impulse(point(value),point(lever),forceFall);
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("PHYSICAL_RIG_IMPULSE t=%lu impulse=[%.3f,%.3f,%.3f]\n",match->GetActualTime_ms(),value.coords[0],value.coords[1],value.coords[2]);
}

void HumanoidBase::UpdatePhysicalRigPose(){
  if(!PhysicalRigEnabled())return;
  ConfigurePhysicalRig();
  football_physics::Input input;
    for(unsigned i=0;i<13;++i)input.pose[i]=rotation(contactLocal[i]);
    input.pelvis=point(contactPositions[0]);input.velocity=point(spatialState.movement);
    input.forward=point(spatialState.bodyDirectionVec);input.upperReception=UpperReceptionActive();
    input.protect=physicalShield;
    input.gripped=physicalGripForce.GetLength()>5;
    input.handTargetActive=physicalHandTargetActive;input.handTarget=point(physicalHandTarget);
    input.action=currentAnim->functionType!=e_FunctionType_Movement && currentAnim->functionType!=e_FunctionType_BallControl;
    // Preserve the authored preparation pose while a one-touch action is
    // queued. Its current base can still be locomotion during interception.
    input.action=input.action || (player->GetExternalController() && static_cast<HumanController*>(player->GetExternalController())->GetActionMode()!=0);
    std::vector<Player*> opponents;match->GetTeam(player==match->GetTrainingPartner()?0:1)->GetActivePlayers(opponents);
    for(auto *opponent:opponents) {
      const Vector3 delta=opponent->GetPosition()-spatialState.position;
      if(delta.GetLength()<input.opponentDistance){input.opponentDistance=delta.GetLength();input.opponent=point(delta);}
    }
    // Anticipate small reach corrections. The existing skin contact gate
    // remains responsible for accepting an actual ball impulse.
    const int remaining=currentAnim->touchFrame-currentAnim->frameNum;
    const std::string part=currentAnim->anim->GetVariable("touch_bodypart");
    if(currentAnim->touchFrame>=0 && !currentAnim->touchMade && remaining>=0 && remaining<=24 &&
       (part=="right_foot" || part=="left_foot" || part=="head" || part=="trunk")) {
      Quaternion q[13],global[13];Vector3 p[13];
      const unsigned frame=std::min<unsigned>(currentAnim->touchFrame,currentAnim->positions.size()-1);
      const unsigned now=std::min<unsigned>(currentAnim->frameNum,currentAnim->positions.size()-1);
      const Vector3 root=contactPositions[0].Get2D()+currentAnim->positions[frame]-currentAnim->positions[now];
      SampleContactAnimation(currentAnim->anim,float(currentAnim->touchFrame),root,startAngle,false,q,global,p);
      const Vector3 predicted=match->GetBall()->Predict(remaining*10);Vector3 skin;
      const float gap=ContactSurface(predicted,part,global,p,&skin);
      if(gap>0 && gap<.14f) {
        input.reachBone=part=="right_foot"?12:part=="left_foot"?9:part=="head"?2:1;
        input.reach=point((predicted-skin).GetNormalized(Vector3(1,0,0))*std::min(gap,.12f));
        input.reachWeight=football_physics::smooth((24-remaining)/12.f);
      }
    }
  if(physicalRigTime!=match->GetActualTime_ms()) {
    physicalRigTime=match->GetActualTime_ms();
    const int before=int(physicalRig->mode());physicalRig->step(input);
    const int after=int(physicalRig->mode());
    if(after==int(football_physics::Mode::Recovering)){
      // Align the support to the actual weighted skin, not only to capsule
      // joint endpoints. The same reference skin is used by ball contacts.
      float lowest=100;
      for(unsigned mesh=0;mesh<weightedVerticesVec.size();++mesh)for(const auto &vertex:weightedVerticesVec[mesh]){
        const float *data=&uniqueFullbodyMesh[mesh].data[vertex.vertexID*3];
        const Vector3 original(data[0],data[1],data[2]);Vector3 skinned(0);
        for(const auto &bone:vertex.bones){const int i=contactJointBone[bone.jointID];if(i<0)continue;
          skinned+=(quaternion(physicalRig->worldRotations()[i])*(original-joints[bone.jointID].origPos*zMultiplier)+vector(physicalRig->points()[i]))*bone.weight;
        }
        lowest=std::min(lowest,skinned.coords[2]);
      }
      if(std::isfinite(lowest) && lowest<10)physicalRig->alignRecoverySurface(lowest);
    }
    if(after!=before){printf("PHYSICAL_RIG_STATE t=%lu from=%d to=%d\n",physicalRigTime,before,after);fflush(stdout);}
    if(after && !before){upperReceptionClip=nullptr;upperReceptionWeight=0;currentAnim->touchMade=true;}
    if(after || before) {
      OffsetPosition(vector(physicalRig->points()[0]).Get2D()-spatialState.position);
      spatialState.movement=Vector3(0);spatialState.floatVelocity=0;
      animApplyBuffer.position=spatialState.position;animApplyBuffer.noPos=true;
    }
    if(before && !after){
      const Vector3 root=spatialState.position,focus=root+vector(football_physics::rotatePoint(physicalRig->worldRotations()[0],{{0,-1,0}})).Get2D().GetNormalized(spatialState.bodyDirectionVec);
      ResetPosition(root,focus);
      if(player->GetExternalController())player->GetExternalController()->Reset();
      printf("PHYSICAL_RIG_RECOVERED t=%lu\n",match->GetActualTime_ms());fflush(stdout);return;
    }
    if(GetConfiguration()->GetBool("training_telemetry",false) && physicalRigTime%50==0) {
      const auto &d=physicalRig->metrics();const auto root=physicalRig->points()[0];const auto q=physicalRig->worldRotations()[0];
      if(player->GetExternalController())printf("PHYSICAL_RIG_FRAME {\"t\":%lu,\"mode\":%d,\"root\":[%.5f,%.5f,%.5f],\"lean\":%.5f,\"turn\":%.5f,\"reach\":%.5f,\"support_margin\":%.5f,\"effort\":%.5f,\"ground_contacts\":%u,\"ground_correction\":%.6f,\"angular_speed\":%.5f,\"energy\":%.5f,\"joint_error\":%.6f,\"self_penetration\":%.6f,\"brace\":%.2f,\"recovery_phase\":%.4f,\"root_q\":[%.6f,%.6f,%.6f,%.6f]}\n",
        physicalRigTime,after,root[0],root[1],root[2],d.lean,d.turnRate,d.reach,d.supportMargin,d.effort,d.groundContacts,d.penetration,d.angularSpeed,d.kineticEnergy,d.jointError,d.selfPenetration,d.brace,d.recoveryPhase,q[0],q[1],q[2],q[3]);
      printf("PHYSICAL_BALANCE t=%lu actor=%d phase=%d risk=%.5f step=%.5f choice=%d arm_speed=%.5f elbow=%.5f\n",physicalRigTime,player->GetID(),d.balancePhase,d.balanceRisk,d.stepDemand,d.balanceChoice,d.armSpeed,d.elbowAngle);
    }
  } else physicalRig->evaluate(input);
  if(!physicalRig || !physicalRig->initialized())return;
  for(unsigned i=0;i<13;++i){contactLocal[i]=quaternion(physicalRig->pose()[i]);contactGlobal[i]=quaternion(physicalRig->worldRotations()[i]);contactPositions[i]=vector(physicalRig->points()[i]);}
}

void HumanoidBase::PhysicalActionContact(){
  if(!PhysicalRigEnabled() || match->GetActualTime_ms()<physicalActionTime ||
      (currentAnim->functionType!=e_FunctionType_Shot && currentAnim->functionType!=e_FunctionType_HighPass))return;
  const Vector3 velocity=currentAnim->incomingMovement;
  const Vector3 kick=currentAnim->originatingCommand.touchInfo.desiredDirection;
  const float speed=velocity.GetLength();
  const float turn=std::fabs(velocity.GetNormalized(spatialState.bodyDirectionVec).GetAngle2D(kick));
  if(speed<5.8f || turn<.9f)return;
  physicalActionTime=match->GetActualTime_ms()+1000;
  // A difficult running strike first perturbs the supported body. A nearby
  // body collision may then exhaust that balance; no random fall is injected.
  const float effort=clamp((speed-5.8f)/2.f,0.f,1.f)*clamp((turn-.9f)/1.5f,0.f,1.f);
  AddPhysicalImpulse(kick.Get2D().GetNormalized(spatialState.bodyDirectionVec)*(25.f+40.f*effort),Vector3(0,0,.20f));
  if(GetConfiguration()->GetBool("training_telemetry",false))printf("PHYSICAL_STRIKE_BALANCE t=%lu speed=%.3f turn=%.3f effort=%.4f\n",match->GetActualTime_ms(),speed,turn,effort);
}

void HumanoidBase::ProcessPhysicalMotion(){
  // The native animation process normally refreshes this pointer each tick.
  // Its mental-image history only retains 300 ms; a physical fall can last
  // several seconds and must never leave a dangling snapshot for pose offsets.
  currentMentalImage=match->GetMentalImage(0);
  // Native idle is the recovery target. The physical body owns the root;
  // gameplay actions are not queued while it is falling or getting up.
  Animation *idle=anims->GetAnim(GetIdleMovementAnimID());
  SampleContactAnimation(idle,0,spatialState.position,spatialState.angle,false,contactLocal,contactGlobal,contactPositions);
  UpdatePhysicalRigPose();ProcessTrainingBodyContact();
}

void HumanoidBase::ProcessPhysicalPartner(){
  if(PhysicalRigBusy()){ProcessPhysicalMotion();return;}
  currentMentalImage=match->GetMentalImage(0);
  spatialState.movement=match->GetTrainingPartnerVelocity();
  spatialState.floatVelocity=spatialState.movement.GetLength();
  Animation *clip=anims->GetAnim(GetIdleMovementAnimID());
  if(spatialState.floatVelocity>.2f){
    for(auto *candidate:anims->GetAnimations())if(candidate->GetAnimType()=="movement" && candidate->GetIncomingVelocity()>1.5f && candidate->GetIncomingVelocity()<4.f &&
        std::fabs(candidate->GetOutgoingAngle())<.02f && std::fabs(candidate->GetIncomingBodyAngle())<.05f && candidate->GetVariable("incoming_special_state").empty()) {clip=candidate;break;}
  }
  if(spatialState.floatVelocity>.2f){
    spatialState.directionVec=spatialState.movement.GetNormalized(0);
    const float turn=std::atan2(spatialState.bodyDirectionVec.GetCrossProduct(spatialState.directionVec).coords[2],spatialState.bodyDirectionVec.GetDotProduct(spatialState.directionVec));
    spatialState.bodyDirectionVec=spatialState.bodyDirectionVec.GetRotated2D(clamp(turn,-.018f,.018f));
    spatialState.angle=std::atan2(spatialState.bodyDirectionVec.coords[0],-spatialState.bodyDirectionVec.coords[1]);
  }
  const float cadence=spatialState.floatVelocity>.2f?clamp(spatialState.floatVelocity/std::max(.5f,clip->GetIncomingVelocity()),.12f,1.2f):1.f;
  physicalPartnerPhase=std::fmod(physicalPartnerPhase+cadence,float(std::max(1,clip->GetEffectiveFrameCount())));
  const int frame=int(physicalPartnerPhase);
  Quaternion ignored;Vector3 translation;clip->GetKeyFrame("player",frame,ignored,translation);
  const Vector3 origin=spatialState.position-translation.Get2D().GetRotated2D(spatialState.angle);
  animApplyBuffer.anim=clip;animApplyBuffer.frameNum=frame;animApplyBuffer.position=origin;
  animApplyBuffer.orientation=spatialState.angle;animApplyBuffer.smooth=true;animApplyBuffer.noPos=false;
  SampleContactAnimation(clip,frame,spatialState.position,spatialState.angle,false,contactLocal,contactGlobal,contactPositions);
  UpdatePhysicalRigPose();
}

void HumanoidBase::PutPhysicalRig(){
  if(!fetchedPhysicalRig)return;
  if(!fetchedPhysicalRagdoll){
    PutTrainingContactPose();
    for(unsigned i:{1u,3u,4u,5u,6u,7u,8u,9u,10u,11u,12u}){
      auto node=nodeMap.at(pes3::nativeBoneNames[i]);
      const Quaternion delta=Quaternion(QUATERNION_IDENTITY).GetSlerped(1-fetchedContactBlend,fetchedPhysicalAdditive[i]);
      node->SetRotation((delta*node->GetRotation()).GetNormalized(),false);
    }
    humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
    PutTrainingHeadLook();
    return;
  }
  auto body=nodeMap.at("body");const auto &bind=pes3NativeReference.offsets[0];
  body->SetPosition(Vector3(bind[0],bind[1],bind[2]),false);
  humanoidNode->SetPosition(fetchedContactRoot+Vector3(0,0,fetchedContactHeight/zMultiplier-bind[2]),false);
  for(unsigned i=0;i<13;++i)nodeMap.at(pes3::nativeBoneNames[i])->SetRotation(fetchedContactLocal[i],false);
  humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
  if(GetConfiguration()->GetBool("training_telemetry",false)) {
    float maximumError=0;
    for(unsigned i=1;i<13;++i) {
      const auto node=nodeMap.at(pes3::nativeBoneNames[i]);
      const auto parent=nodeMap.at(pes3::nativeBoneNames[pes3::nativeParents[i]]);
      const auto &offset=pes3NativeReference.offsets[i];
      maximumError=std::max(maximumError,std::fabs((node->GetDerivedPosition()-parent->GetDerivedPosition()).GetLength()-Vector3(offset[0],offset[1],offset[2]).GetLength()));
    }
    printf("PHYSICAL_RIG_RENDER t=%lu length_error=%.8f root_height=%.5f\n",fetchedbuf_animApplyBuffer.snapshotTime_ms,maximumError,fetchedContactHeight);
  }
}
