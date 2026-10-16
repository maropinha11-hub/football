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
  return UsesTrainingContacts() && player->GetExternalController() &&
    GetConfiguration()->GetBool("training_physical_rig",false);
}
bool HumanoidBase::PhysicalRigBusy()const {
  return PhysicalRigEnabled() && physicalRig && physicalRig->mode()!=football_physics::Mode::Active;
}
void HumanoidBase::ResetPhysicalRig(){
  if(physicalRig)physicalRig->reset();
  physicalRigTime=~0ul;physicalCollisionTime=0;buf_physicalRig.Clear();fetchedPhysicalRig=false;
  for(auto &buffer:buf_physicalAdditive)buffer.Clear();
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
  match->SpamMessage(enabled?"Fisica corporal: ligada | F8: impacto | F9: queda":"Fisica corporal: desligada",3500);
  printf("PHYSICAL_RIG_TOGGLE enabled=%d\n",enabled?1:0);fflush(stdout);
}
void HumanoidBase::AddPhysicalImpulse(const Vector3 &value,const Vector3 &lever){
  if(!PhysicalRigEnabled())return;
  if(!physicalRig){physicalRig.reset(new football_physics::PhysicalRig);physicalRig->configure(pes3NativeReference,zMultiplier);}
  physicalRig->impulse(point(value),point(lever));
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("PHYSICAL_RIG_IMPULSE t=%lu impulse=[%.3f,%.3f,%.3f]\n",match->GetActualTime_ms(),value.coords[0],value.coords[1],value.coords[2]);
}

void HumanoidBase::UpdatePhysicalRigPose(){
  if(!PhysicalRigEnabled())return;
  if(!physicalRig){physicalRig.reset(new football_physics::PhysicalRig);physicalRig->configure(pes3NativeReference,zMultiplier);}
  football_physics::Input input;
    for(unsigned i=0;i<13;++i)input.pose[i]=rotation(contactLocal[i]);
    input.pelvis=point(contactPositions[0]);input.velocity=point(spatialState.movement);
    input.forward=point(spatialState.bodyDirectionVec);input.upperReception=UpperReceptionActive();
    input.action=currentAnim->functionType!=e_FunctionType_Movement && currentAnim->functionType!=e_FunctionType_BallControl;
    // Preserve the authored preparation pose while a one-touch action is
    // queued. Its current base can still be locomotion during interception.
    input.action=input.action || static_cast<HumanController*>(player->GetExternalController())->GetActionMode()!=0;
    std::vector<Player*> opponents;match->GetTeam(1)->GetActivePlayers(opponents);
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
    if(after!=before){printf("PHYSICAL_RIG_STATE t=%lu from=%d to=%d\n",physicalRigTime,before,after);fflush(stdout);}
    if(after && !before){upperReceptionClip=nullptr;upperReceptionWeight=0;currentAnim->touchMade=true;}
    if(after || before) {
      OffsetPosition(vector(physicalRig->points()[0]).Get2D()-spatialState.position);
      spatialState.movement=Vector3(0);spatialState.floatVelocity=0;
      animApplyBuffer.position=spatialState.position;animApplyBuffer.noPos=true;
    }
    if(before && !after){
      const Vector3 root=spatialState.position,focus=root+spatialState.bodyDirectionVec;
      ResetPosition(root,focus);
      if(player->GetExternalController())player->GetExternalController()->Reset();
      printf("PHYSICAL_RIG_RECOVERED t=%lu\n",match->GetActualTime_ms());fflush(stdout);return;
    }
    if(GetConfiguration()->GetBool("training_telemetry",false) && physicalRigTime%50==0) {
      const auto &d=physicalRig->metrics();const auto root=physicalRig->points()[0];const auto q=physicalRig->worldRotations()[0];
      printf("PHYSICAL_RIG_FRAME {\"t\":%lu,\"mode\":%d,\"root\":[%.5f,%.5f,%.5f],\"lean\":%.5f,\"turn\":%.5f,\"reach\":%.5f,\"support_margin\":%.5f,\"effort\":%.5f,\"ground_contacts\":%u,\"ground_correction\":%.6f,\"angular_speed\":%.5f,\"energy\":%.5f,\"joint_error\":%.6f,\"root_q\":[%.6f,%.6f,%.6f,%.6f]}\n",
        physicalRigTime,after,root[0],root[1],root[2],d.lean,d.turnRate,d.reach,d.supportMargin,d.effort,d.groundContacts,d.penetration,d.angularSpeed,d.kineticEnergy,d.jointError,q[0],q[1],q[2],q[3]);
    }
  } else physicalRig->evaluate(input);
  if(!physicalRig || !physicalRig->initialized())return;
  for(unsigned i=0;i<13;++i){contactLocal[i]=quaternion(physicalRig->pose()[i]);contactGlobal[i]=quaternion(physicalRig->worldRotations()[i]);contactPositions[i]=vector(physicalRig->points()[i]);}
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
