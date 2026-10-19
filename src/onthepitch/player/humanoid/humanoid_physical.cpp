#include "humanoidbase.hpp"
#include "physical_rig.hpp"
#include "contact_resistance.hpp"
#include "body_contest.hpp"
#include "anatomical_arms.hpp"
#include "situational_profiles.hpp"
#include "../../physical_match_rules.hpp"
#include "../../reception_prediction.hpp"
#include "../../../main.hpp"
#include "../../match.hpp"
#include "../player.hpp"
#include "../controller/humancontroller.hpp"
#include <sstream>
#include <iomanip>

namespace {
football_physics::Vec point(const Vector3 &p){return {{p.coords[0],p.coords[1],p.coords[2]}};}
Vector3 vector(football_physics::Vec p){return Vector3(p[0],p[1],p[2]);}
football_physics::Quat rotation(const Quaternion &q){return {{q.elements[0],q.elements[1],q.elements[2],q.elements[3]}};}
Quaternion quaternion(football_physics::Quat q){return Quaternion(q[0],q[1],q[2],q[3]);}
}

bool HumanoidBase::PhysicalRigEnabled()const {
  return TrainingEnabled() && (PlayerMatchEnabled() || player->GetExternalController() || player==match->GetTrainingPartner()) &&
    GetConfiguration()->GetBool("training_physical_rig",false);
}
void HumanoidBase::ConfigurePhysicalRig(){
  if(physicalRig)return;
  physicalRig.reset(new football_physics::PhysicalRig);physicalRig->configure(pes3NativeReference,zMultiplier);
  printf("PHYSICAL_SITUATION_BANK actor=%d source_files=%zu profiles=%zu audited_pairs=%zu kind=procedural\n",player->GetID(),football_situations::kCatalogSourceFiles,football_situations::kProfileCount,football_situations::kCatalogCompatiblePairs);
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
  // CPU actors share the native full-body trip clips through the selector.
  // Do not duplicate the large optional additive bank for every teammate.
  if(PlayerMatchEnabled() && !player->GetExternalController()){
    printf("PHYSICAL_MATCH_ACTOR actor=%d team=%d skin_contacts=%d\n",player->GetID(),static_cast<Player*>(player)->GetTeamID(),UsesTrainingContacts()?1:0);
    return;
  }
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
  return GetPhysicalShirtPoint(other?other->GetPosition():spatialState.position+spatialState.bodyDirectionVec);
}
Vector3 HumanoidBase::GetPhysicalShirtPoint(const Vector3 &from)const{
  const Vector3 toward=(from-spatialState.position).Get2D().GetNormalized(spatialState.bodyDirectionVec);
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
bool HumanoidBase::BodyContestContact(const HumanoidBase &other,Vector3 &where,Vector3 &normal,float &depth)const{
  using namespace football_physics;
  if(!physicalRig||!other.physicalRig||!physicalRig->initialized()||!other.physicalRig->initialized())return false;
  const auto contact=bodyContact(bodyProxies(physicalRig->points(),physicalRig->worldRotations(),zMultiplier),
    bodyProxies(other.physicalRig->points(),other.physicalRig->worldRotations(),other.zMultiplier));
  where=vector(contact.point);normal=vector(contact.normal);depth=contact.penetration;return contact.touching;
}
bool HumanoidBase::PhysicalRigBusy()const {
  return PhysicalRigEnabled() && physicalRig && physicalRig->mode()!=football_physics::Mode::Active;
}
bool HumanoidBase::PhysicalStaggering()const {
  return PhysicalRigEnabled() && match->GetActualTime_ms()<physicalStaggerUntil &&
    ((interruptAnim==e_InterruptAnim_Trip && tripType==1) ||
     (currentAnim->functionType==e_FunctionType_Trip && currentAnim->anim->GetVariable("triptype")=="1"));
}
void HumanoidBase::ResetPhysicalRig(){
  if(physicalRig)physicalRig->reset();
  physicalRigTime=~0ul;physicalCollisionTime=0;buf_physicalRig.Clear();buf_physicalRootOffset.Clear();
  physicalSituationProfile=0;buf_situationState.Clear();
  physicalCutUntil=physicalBallImpactTime=physicalKeeperAttemptUntil=0;physicalIntentTime=~0ul;
  physicalPendingCut=Vector3(0);
  for(auto &buffer:buf_physicalAdditive)buffer.Clear();
  physicalGripForce=Vector3(0);physicalTraction=Vector3(0);physicalActionTime=physicalStaggerUntil=0;physicalPartnerPhase=0;physicalShield=false;physicalHandTargetActive=false;
}
void HumanoidBase::PhysicalCollision(const Vector3 &change){
  if(!PhysicalRigEnabled() || match->GetActualTime_ms()<physicalCollisionTime || change.GetLength()<.5f)return;
  physicalCollisionTime=match->GetActualTime_ms()+220;
  AddPhysicalImpulse(change*football_physics::PhysicalRig::mass*.30f);
}
void HumanoidBase::PhysicalDirectionChange(const Vector3 &desired){
  const auto now=match->GetActualTime_ms();
  if(!PhysicalRigEnabled()||physicalIntentTime==now||now<physicalCutUntil||PhysicalRigBusy()||PhysicalStaggering()||UpperReceptionActive())return;
  physicalIntentTime=now;
  const float speed=spatialState.movement.Get2D().GetLength();
  const float facing=spatialState.movement.GetNormalized(0).GetDotProduct(desired.GetNormalized(0));
  const float load=football_rules::cutImpulse(speed,desired.GetLength(),facing);
  if(load<25)return;
  physicalCutUntil=now+1400;
  AddPhysicalImpulse(spatialState.movement.GetNormalized(0)*load,Vector3(0,0,.38f));
  if(load>=35)physicalPendingCut=spatialState.movement.GetNormalized(0)*load;
  if(GetConfiguration()->GetBool("training_telemetry",false))printf("PHYSICAL_CUT t=%lu actor=%d speed=%.4f requested=%.4f facing=%.4f impulse=%.4f\n",now,player->GetID(),speed,desired.GetLength(),facing,load);
  if(!PlayerMatchEnabled()||!static_cast<Player*>(player)->HasPossession())return;
  std::vector<Player*> opponents;match->GetTeam(1-static_cast<Player*>(player)->GetTeamID())->GetActivePlayers(opponents);
  for(auto *other:opponents){
    auto *body=other->GetHumanoid();
    if((other->GetPosition()-spatialState.position).Get2D().GetLength()>1.5f||other->GetMovement().GetLength()<4.f||
       other->GetMovement().GetNormalized(0).GetDotProduct(spatialState.movement.GetNormalized(0))<.55f||now<body->physicalCutUntil)continue;
    body->physicalCutUntil=now+1600;
    body->AddPhysicalImpulse(other->GetMovement().GetNormalized(0)*std::min(100.f,load*.8f),Vector3(0,0,.35f));
    if(load*.8f>=35)body->physicalPendingCut=other->GetMovement().GetNormalized(0)*std::min(100.f,load*.8f);
    if(GetConfiguration()->GetBool("training_telemetry",false))printf("PHYSICAL_CUT_FOOTING t=%lu actor=%d carrier=%d impulse=%.4f\n",now,other->GetID(),player->GetID(),std::min(100.f,load*.8f));
  }
}
void HumanoidBase::TogglePhysicalRig(){
  const bool enabled=!GetConfiguration()->GetBool("training_physical_rig",false);
  if(PhysicalRigBusy())ResetPosition(spatialState.position,spatialState.position+spatialState.bodyDirectionVec);
  if(player->GetExternalController())player->GetExternalController()->Reset();
  GetConfiguration()->SetBool("training_physical_rig",enabled);ResetPhysicalRig();
  if(PlayerMatchEnabled()){
    std::vector<Player*> actors;match->GetTeam(0)->GetActivePlayers(actors);match->GetTeam(1)->GetActivePlayers(actors);
    for(auto *actor:actors)if(actor!=player){
      auto *body=actor->GetHumanoid();
      body->ResetPosition(actor->GetPosition(),actor->GetPosition()+actor->GetBodyDirectionVec());
      body->ResetPhysicalRig();
    }
  }else if(match->GetTrainingPartner() && match->GetTrainingPartner()!=player){
    auto *partner=match->GetTrainingPartner();
    partner->GetHumanoid()->ResetPosition(partner->GetPosition(),partner->GetPosition()+partner->GetBodyDirectionVec());
  }
  match->SpamMessage(enabled?"Fisica corporal: ligada | F8: impacto | F9: queda":"Fisica corporal: desligada",3500);
  printf("PHYSICAL_RIG_TOGGLE enabled=%d\n",enabled?1:0);fflush(stdout);
}
Vector3 HumanoidBase::PhysicalBalanceVelocity()const{return PhysicalRigEnabled() && physicalRig && match->GetActualTime_ms()>=physicalStaggerUntil?vector(physicalRig->balanceVelocity()):Vector3(0);}
Vector3 HumanoidBase::PhysicalContactVelocity(const Vector3 &desired)const{
  return PhysicalRigEnabled()?vector(football_physics::contactVelocity(point(desired),point(physicalTraction),physicalShield)):desired;
}
Vector3 HumanoidBase::SafeFirstPersonEye(const Vector3 &requested)const{
  Quaternion q[13];Vector3 p[13];
  const Vector3 origin=player->GetGeomPosition().Get2D();
  for(unsigned i=0;i<13;++i){const auto node=nodeMap.at(pes3::nativeBoneNames[i]);q[i]=node->GetDerivedRotation();p[i]=origin+(node->GetDerivedPosition()-origin)*zMultiplier;}
  // The caller already samples the rendered neck after the root offset.
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
  // A recoverable body blow selects the original full-body protective step,
  // rather than quantizing a small capture-point velocity into normal walking.
  const unsigned long now=match->GetActualTime_ms();
  if(!forceFall && value.GetLength()>=35.f && physicalRig->mode()==football_physics::Mode::Active &&
     now>=physicalStaggerUntil && interruptAnim==e_InterruptAnim_None &&
     (currentAnim->functionType==e_FunctionType_Movement || currentAnim->functionType==e_FunctionType_BallControl) &&
     !UpperReceptionActive() && match->GetBallRetainer()!=player){
    interruptAnim=e_InterruptAnim_Trip;tripType=1;tripDirection=value.Get2D().GetNormalized(spatialState.bodyDirectionVec);
    physicalStaggerUntil=now+1800;
    printf("PHYSICAL_STAGGER_REQUEST t=%lu actor=%d impulse=%.3f speed=%.3f\n",now,player->GetID(),value.GetLength(),spatialState.floatVelocity);
  }
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("PHYSICAL_RIG_IMPULSE t=%lu actor=%d impulse=[%.3f,%.3f,%.3f]\n",match->GetActualTime_ms(),player->GetID(),value.coords[0],value.coords[1],value.coords[2]);
}

void HumanoidBase::BuildSituationalInput(football_physics::Input &input){
  using football_situations::ActionKind;
  auto &context=input.situation;
  context.enabled=GetConfiguration()->GetBool("training_situational_motion",true) && !input.upperReception && !input.staggering;
  const auto type=currentAnim->functionType;
  const std::string part=currentAnim->anim->GetVariable("touch_bodypart");
  if(currentAnim->touchFrame>=0){
    if(type==e_FunctionType_ShortPass || type==e_FunctionType_LongPass)context.kind=ActionKind::Pass;
    if(type==e_FunctionType_Shot)context.kind=ActionKind::Shot;
    if(type==e_FunctionType_HighPass)context.kind=ActionKind::Cross;
    if(type==e_FunctionType_BallControl || type==e_FunctionType_Trap)context.kind=ActionKind::Control;
    // Interference/deflection clips can also make a header. Never let an
    // earlier foot action's fading torso offset move their contact point.
    if(part=="head")context.kind=ActionKind::Header;
  }
  // Keeper throws, catches, chest receptions and special/retained states
  // keep their authored contacting chain, including during an old fade.
  const bool nativeContact=currentAnim->touchFrame>=0 && part!="right_foot" && part!="left_foot" && part!="head";
  const bool special=!currentAnim->anim->GetVariable("incoming_special_state").empty() ||
    !currentAnim->anim->GetVariable("outgoing_special_state").empty() ||
    !currentAnim->anim->GetVariable("incoming_retain_state").empty() ||
    !currentAnim->anim->GetVariable("outgoing_retain_state").empty();
  if((nativeContact&&!currentAnim->touchMade) || special || type==e_FunctionType_Trip)context.enabled=false;
  const unsigned now=std::min<unsigned>(currentAnim->frameNum,currentAnim->positions.size()-1);
  const unsigned at=std::min<unsigned>(std::max(0,currentAnim->touchFrame),currentAnim->positions.size()-1);
  const int remaining=std::max(0,currentAnim->touchFrame-currentAnim->frameNum);
  const Vector3 meetingRoot=contactPositions[0]+(currentAnim->positions[at]-currentAnim->positions[now]);
  // The authored root already turns during a pass. Its current orientation
  // includes both that turn and the native heading adjustment; startAngle
  // alone would count an already-completed turn again.
  const Quaternion inverseBody=quaternion(input.pose[0]).GetInverse();
  const Vector3 ballLocal=inverseBody*(match->GetBall()->Predict(remaining*10)-meetingRoot);
  context.ball=point(ballLocal);
  context.incoming=point(inverseBody*(match->GetBall()->GetMovement()-spatialState.movement));
  Vector3 target=currentAnim->originatingCommand.touchInfo.desiredDirection;
  if(context.kind==ActionKind::Control)target=currentAnim->originatingCommand.desiredDirection;
  target=target.Get2D().GetNormalized(spatialState.bodyDirectionVec);
  context.direction=point(inverseBody*target);
  context.signedTurn=std::atan2(context.direction[0],-context.direction[1]);
  context.speed=currentAnim->incomingMovement.GetLength();
  context.power=clamp(currentAnim->originatingCommand.touchInfo.desiredPower,0.f,1.f);
  context.pressure=clamp((1.8f-input.opponentDistance)/1.4f,0.f,1.f);
  // The actual native pass target supplies the direction and power. Pressure
  // along that teammate's passing lane adds bracing demand without changing
  // the chosen pass, target, ball force or contact marker.
  const Player *teammate=currentAnim->originatingCommand.touchInfo.targetPlayer;
  if(teammate && context.kind==ActionKind::Pass){
    const Vector3 lane=(teammate->GetPosition()-spatialState.position).Get2D();
    if(lane.GetSquaredLength()>1.f){
      const float along=clamp(input.opponent[0]*lane.coords[0]+input.opponent[1]*lane.coords[1],0.f,lane.GetSquaredLength())/lane.GetSquaredLength();
      const Vector3 closest=lane*along;
      const float gap=(vector(input.opponent).Get2D()-closest).GetLength();
      if(along>.02f && along<.95f)context.pressure=std::max(context.pressure,clamp((1.1f-gap)/1.1f,0.f,1.f)*.7f);
    }
  }
  context.rightFoot=part!="left_foot";context.supportSide=context.rightFoot?-1:1;
  const float frames=std::max(1,currentAnim->anim->GetEffectiveFrameCount());
  context.phase=clamp(currentAnim->frameNum/frames,0.f,1.f);
  context.contactPhase=clamp(currentAnim->touchFrame/frames,.12f,.88f);
  context.contactMade=currentAnim->touchMade;
  const float turn=std::fabs(context.signedTurn)/pi;
  const float reach=clamp(ballLocal.Get2D().GetLength()/.85f,0.f,1.f);
  context.difficulty=clamp(.27f*context.speed/7.f+.19f*context.power+.34f*turn+.14f*context.pressure+.06f*reach,0.f,1.f);
  // Keep the accepted straight dribble intact. Contextual torso recruitment
  // is useful on cuts and contested touches, not on every ordinary foot tap.
  if(type==e_FunctionType_BallControl && context.kind==ActionKind::Control && turn<.18f && context.pressure<.4f)context.kind=ActionKind::None;
  const bool bodyReaction=physicalBallImpactTime&&match->GetActualTime_ms()-physicalBallImpactTime<700&&
    !input.action&&!input.upperReception&&!input.staggering;
  if(bodyReaction){
    context.kind=ActionKind::Control;context.incoming=point(inverseBody*physicalBallImpactVelocity);
    context.ball=point(inverseBody*(physicalBallImpactPosition-contactPositions[0]));
    context.phase=clamp((match->GetActualTime_ms()-physicalBallImpactTime+40)/740.f,0.f,1.f);
    context.contactPhase=.12f;context.contactMade=true;context.power=clamp(physicalBallImpactVelocity.GetLength()/25.f,0.f,1.f);
    context.difficulty=std::max(context.difficulty,context.power*.8f);context.preserveHead=context.power<.6f;
  }
  if(context.kind!=ActionKind::None){
    const float height=ballLocal.coords[2]+.85f;
    unsigned pattern=0;
    if(bodyReaction)pattern=physicalBallImpactPosition.coords[2]>1.1f?18:16;
    else if(context.kind==ActionKind::Header)pattern=type==e_FunctionType_Trap?17:context.pressure>.4f?23:11;
    else if(context.kind==ActionKind::Control && type==e_FunctionType_Trap)pattern=part.find("knee")!=std::string::npos||part.find("thigh")!=std::string::npos?16:part.find("shoulder")!=std::string::npos?15:height>1.15f?18:turn>.12f?26:22;
    else if(context.kind==ActionKind::Pass&&turn>.2f)pattern=20;
    else if(context.kind==ActionKind::Cross&&context.speed>3.f)pattern=24;
    else if(context.kind==ActionKind::Shot&&context.power>.75f)pattern=21;
    else if((context.kind==ActionKind::Shot || context.kind==ActionKind::Pass || context.kind==ActionKind::Cross) && height>.45f)pattern=12;
    else if((context.kind==ActionKind::Shot || context.kind==ActionKind::Cross) && context.power>.75f)pattern=14;
    else if((context.kind==ActionKind::Pass || context.kind==ActionKind::Shot) && turn>.25f &&
      ((context.rightFoot && ballLocal.coords[0]<-.06f)||(!context.rightFoot && ballLocal.coords[0]>.06f)))pattern=13;
    else if(context.pressure>.65f)pattern=8;
    else if(turn>.62f)pattern=6;
    else if(height>.75f)pattern=2;
    else if(match->GetBall()->GetMovement().GetLength()>4.f && !static_cast<Player*>(player)->HasPossession())pattern=7;
    else if(context.kind==ActionKind::Cross)pattern=5;
    else if(context.kind==ActionKind::Shot && context.power>.55f)pattern=3;
    else if(context.kind==ActionKind::Pass && std::fabs(context.signedTurn)>.35f)pattern=4;
    else if(std::fabs(context.signedTurn)>.40f)pattern=1;
    if(pattern==0&&context.kind!=ActionKind::Control)pattern=28+unsigned(std::min(3.f,context.speed/2.f));
    const auto &profile=football_situations::profileFor(context.kind,std::max(context.power,context.difficulty),context.pressure,turn,reach,pattern);
    context.pattern=profile.pattern;
    physicalSituationProfile=profile.id;context.trunkGain=profile.trunkGain;context.armGain=profile.armGain;context.followThroughGain=profile.followThroughGain;
  }
}

void HumanoidBase::UpdatePhysicalRigPose(){
  if(!PhysicalRigEnabled())return;
  ConfigurePhysicalRig();
  football_physics::Input input;
    for(unsigned i=0;i<13;++i)input.pose[i]=rotation(contactLocal[i]);
    input.pelvis=point(contactPositions[0]);input.velocity=point(spatialState.movement);
    input.forward=point(spatialState.bodyDirectionVec);input.upperReception=UpperReceptionActive();
    input.useInertia=GetConfiguration()->GetBool("training_motion_matching",true);
    input.trackMotion=GetConfiguration()->GetBool("training_motion_tracking",true);
    input.inertialTransition=!MotionMixerActive();
    input.adaptiveMotion=input.useInertia;
    input.motionEpoch=motionEpoch;input.preserveLook=player->GetExternalController()!=nullptr;
    input.ball=point(match->GetBall()->Predict(0)-contactPositions[0]);
    input.ballVelocity=point(match->GetBall()->GetMovement()-spatialState.movement);
    Player *last=match->GetLastTouchPlayer();
    const bool freeBall=!match->GetBallRetainer()&&
      (last!=player||static_cast<Player*>(player)->GetLastTouchType()==e_TouchType_Accidental)&&
      (!last||last->GetTeamID()==static_cast<Player*>(player)->GetTeamID()||(last->GetPosition()-match->GetBall()->Predict(0)).Get2D().GetLength()>1.15f);
    if(input.adaptiveMotion){
      const auto reception=football_reception::predict([&](unsigned ms){return point(match->GetBall()->Predict(ms));},point(spatialState.position),point(spatialState.movement),point(match->GetBall()->GetMovement()),freeBall);
      input.receiving=reception.valid;input.receiveTime=reception.time;input.receiveHeight=reception.height/zMultiplier;
    }
    const std::string contactPart=currentAnim->anim->GetVariable("touch_bodypart");
    input.bodyContact=input.upperReception||(currentAnim->touchFrame>=0&&!currentAnim->touchMade&&
      contactPart!="left_foot"&&contactPart!="right_foot"&&currentAnim->touchFrame-currentAnim->frameNum<=12);
    if(input.useInertia){
      input.inertiaMask.fill(1.f);input.inertiaMask[0]=0;
      const int next=std::min(currentAnim->frameNum+1,currentAnim->anim->GetEffectiveFrameCount());
      for(unsigned i=1;i<13;++i){Quaternion q;Vector3 p;currentAnim->anim->GetKeyFrame(pes3::nativeBoneNames[i],next,q,p);
        input.poseVelocity[i]=football_physics::capped(football_physics::scalePoint(football_physics::logarithm(football_physics::productRotation(rotation(q),football_physics::inverseRotation(input.pose[i]))),100.f),16.f);
      }
      const int remaining=currentAnim->touchFrame-currentAnim->frameNum;
      if(currentAnim->touchFrame>=0&&!currentAnim->touchMade){
        const float release=football_physics::smooth((remaining-3)/12.f);
        for(unsigned i=7;i<13;++i)input.inertiaMask[i]=release;
        const std::string part=currentAnim->anim->GetVariable("touch_bodypart");
        if(part!="left_foot"&&part!="right_foot")for(unsigned i=1;i<=6;++i)input.inertiaMask[i]=release;
      }
      if(input.upperReception)for(unsigned i=1;i<=6;++i)input.inertiaMask[i]=0;
      if(input.preserveLook)input.inertiaMask[2]=0;
    }
    input.protect=physicalShield;
    input.gripped=physicalGripForce.GetLength()>5;
    input.handTargetActive=physicalHandTargetActive;input.handTarget=point(physicalHandTarget);
    input.staggering=PhysicalStaggering();
    input.action=currentAnim->functionType!=e_FunctionType_Movement && currentAnim->functionType!=e_FunctionType_BallControl;
    // Preserve the authored preparation pose while a one-touch action is
    // queued. Its current base can still be locomotion during interception.
    input.action=input.action || (player->GetExternalController() && static_cast<HumanController*>(player->GetExternalController())->GetActionMode()!=0);
    std::vector<Player*> opponents;match->GetTeam(1-static_cast<Player*>(player)->GetTeamID())->GetActivePlayers(opponents);
    for(auto *opponent:opponents) {
      const Vector3 delta=opponent->GetPosition()-spatialState.position;
      if(delta.GetLength()<input.opponentDistance){input.opponentDistance=delta.GetLength();input.opponent=point(delta);}
    }
    input.passiveTracking=PlayerMatchEnabled() && !player->GetExternalController() && input.opponentDistance>2.f && !input.staggering && !input.gripped;
    BuildSituationalInput(input);
    // Anticipate small reach corrections. The existing skin contact gate
    // remains responsible for accepting an actual ball impulse.
    const int remaining=currentAnim->touchFrame-currentAnim->frameNum;
    const std::string part=currentAnim->anim->GetVariable("touch_bodypart");
    if(UsesTrainingContacts() && currentAnim->touchFrame>=0 && !currentAnim->touchMade && remaining>=0 && remaining<=24 &&
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
      if(input.useInertia)printf("MOTION_INERTIA t=%lu actor=%d epoch=%lu offset=%.6f lower=%.5f\n",physicalRigTime,player->GetID(),input.motionEpoch,d.inertiaOffset,input.inertiaMask[12]);
      if(input.adaptiveMotion)printf("PHYSICAL_ADAPTIVE t=%lu actor=%d stance=%.6f anticipate=%.6f receiving=%d arrival=%.4f height=%.4f\n",physicalRigTime,player->GetID(),d.stanceOffset,d.receiveAnticipation,input.receiving?1:0,input.receiveTime,input.receiveHeight);
      if(after || input.staggering)printf("PHYSICAL_SUPPORT t=%lu actor=%d mode=%d stagger=%d muscles=%.5f torque=%.5f contacts=%u\n",physicalRigTime,player->GetID(),after,input.staggering?1:0,d.muscleEffort,d.supportTorque,d.groundContacts);
      printf("PHYSICAL_ARM_LIMITS t=%lu actor=%d error=%.7f penetration=%.6f left=[%.5f,%.5f,%.5f,%.5f] right=[%.5f,%.5f,%.5f,%.5f]\n",physicalRigTime,player->GetID(),d.armLimitError,d.armPenetration,
        physicalRig->pose()[4][0],physicalRig->pose()[4][1],physicalRig->pose()[4][2],physicalRig->pose()[4][3],
        physicalRig->pose()[6][0],physicalRig->pose()[6][1],physicalRig->pose()[6][2],physicalRig->pose()[6][3]);
    }
    if(GetConfiguration()->GetBool("training_telemetry",false) && physicalRigTime%20==0 && physicalRig->metrics().situation.weight>.001f){
      const auto &d=physicalRig->metrics();const auto &s=d.situation;
      printf("PHYSICAL_SITUATION t=%lu actor=%d action=%d profile=%u source=%s frame=%d difficulty=%.6f phase=%.6f weight=%.6f trunk=%.6f arms=%.6f foot_error=%.8f root_error=%.8f rate=%.6f pressure=%.6f support=%d\n",physicalRigTime,player->GetID(),int(s.kind),physicalSituationProfile,currentAnim->anim->GetName().c_str(),currentAnim->frameNum,s.difficulty,s.phase,s.weight,d.situationTrunk,d.situationArms,d.situationFootError,d.situationRootError,s.angularRate,input.situation.pressure,input.situation.supportSide);
    }
  } else physicalRig->evaluate(input);
  if(!physicalRig || !physicalRig->initialized())return;
  for(unsigned i=0;i<13;++i){contactLocal[i]=quaternion(physicalRig->pose()[i]);contactGlobal[i]=quaternion(physicalRig->worldRotations()[i]);contactPositions[i]=vector(physicalRig->points()[i]);}
  const unsigned observed[6]={0,9,12,2,4,6};
  const unsigned long sampleTime=match->GetActualTime_ms();
  if(motionSampleTime!=sampleTime){
    for(unsigned i=0;i<6;++i)motionPreviousPositions[i]=motionCurrentPositions[i];
    motionSampleValid=motionSampleTime>0&&sampleTime-motionSampleTime<=20;
    motionSampleRate=1000.f/std::max(1ul,sampleTime-motionSampleTime);
    motionSampleTime=sampleTime;
  }
  for(unsigned i=0;i<6;++i)motionCurrentPositions[i]=contactPositions[observed[i]];
  if(motionSampleValid)for(unsigned i=0;i<5;++i){
    const Vector3 relative=((motionCurrentPositions[i+1]-motionCurrentPositions[0])-(motionPreviousPositions[i+1]-motionPreviousPositions[0]))*(motionSampleRate/zMultiplier);
    const Vector3 v=relative+(motionCurrentPositions[0]-motionPreviousPositions[0])*motionSampleRate;
    motionJointVelocities[i]=v.GetNormalized(Vector3(0))*std::min(30.f,v.GetLength());
  }
  if(currentAnim->anim->GetVariable("imported_mocap")=="true"&&GetConfiguration()->GetBool("training_telemetry",false)&&match->GetActualTime_ms()%50==0)
    printf("MOCAP_ACTIVE t=%lu actor=%d source=%s frame=%d function=%d root_height=%.5f\n",match->GetActualTime_ms(),player->GetID(),currentAnim->anim->GetName().c_str(),currentAnim->frameNum,int(currentAnim->functionType),contactPositions[0].coords[2]);
  if(player->GetExternalController()&&GetConfiguration()->GetBool("training_motion_diagnostics",false)){
    std::ostringstream row;row<<std::fixed<<std::setprecision(7)<<"MOTION_SIM t="<<match->GetActualTime_ms()<<" pose=";
    for(unsigned i=0;i<13;++i){const auto q=contactLocal[i];row<<(i?";":"")<<q.elements[0]<<','<<q.elements[1]<<','<<q.elements[2]<<','<<q.elements[3];}
    printf("%s\n",row.str().c_str());
  }
}

void HumanoidBase::PhysicalActionContact(const Vector3 &incoming){
  if(currentAnim->anim->GetVariable("physical_heel")=="true")physicalHeelTime=match->GetActualTime_ms();
  const bool pass=currentAnim->functionType==e_FunctionType_ShortPass || currentAnim->functionType==e_FunctionType_LongPass;
  const std::string part=currentAnim->anim->GetVariable("touch_bodypart");
  const bool header=part=="head";
  if(!PhysicalRigEnabled() || match->GetActualTime_ms()<physicalActionTime ||
      (!pass && currentAnim->functionType!=e_FunctionType_Shot && currentAnim->functionType!=e_FunctionType_HighPass) ||
      (!header && part!="right_foot" && part!="left_foot"))return;
  const float speed=currentAnim->incomingMovement.GetLength();
  const Vector3 outgoing=match->GetBall()->GetMovement();
  const float turn=std::fabs(spatialState.bodyDirectionVec.GetAngle2D(outgoing.Get2D()));
  const float power=clamp(std::max(currentAnim->originatingCommand.touchInfo.desiredPower,
      currentAnim->originatingCommand.touchInfo.inputPower),0.f,1.f);
  const float effort=football_rules::strikeLoad(power,speed,turn,header);
  if(effort<.28f)return;
  physicalActionTime=match->GetActualTime_ms()+750;
  const Vector3 recoil=(incoming-outgoing)*.43f;
  // The extra load represents support demand during the follow-through,
  // applied only AFTER the ball is hit. It never manufactures a ball touch
  // or replaces the authored supporting foot before contact.
  const float demand=(pass?.65f:header?.65f:1.f)*(15.f+45.f*effort);
  const Vector3 direction=outgoing.Get2D().GetNormalized(spatialState.bodyDirectionVec);
  AddPhysicalImpulse(recoil-direction*demand,Vector3(0,0,header?.35f:.22f));
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("PHYSICAL_STRIKE_BALANCE t=%lu actor=%d power=%.4f speed=%.3f turn=%.3f effort=%.4f impulse=%.4f header=%d\n",match->GetActualTime_ms(),player->GetID(),power,speed,turn,effort,(recoil-direction*demand).GetLength(),header?1:0);
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
  if(interruptAnim==e_InterruptAnim_Trip && tripType==1){
    Animation *selected=nullptr;float best=1e9f;
    const Vector3 direction=tripDirection.GetRotated2D(-spatialState.angle);
    for(auto *clip:anims->GetAnimations())if(clip->GetAnimType()=="trip" && clip->GetVariable("triptype")=="1"){
      const float cost=80.f*(1.f-direction.GetDotProduct(GetVectorFromString(clip->GetVariable("bumpdirection"))))+
        2.f*std::fabs(clip->GetIncomingVelocity()-spatialState.floatVelocity);
      if(cost<best){best=cost;selected=clip;}
    }
    interruptAnim=e_InterruptAnim_None;tripType=0;
    if(selected){
      currentAnim->anim=selected;currentAnim->frameNum=0;currentAnim->functionType=e_FunctionType_Trip;
      physicalStaggerUntil=match->GetActualTime_ms()+selected->GetFrameCount()*10+200;
      printf("PHYSICAL_STAGGER_CLIP t=%lu actor=%d clip=%s frames=%d speed=%.3f\n",match->GetActualTime_ms(),player->GetID(),selected->GetName().c_str(),selected->GetFrameCount(),spatialState.floatVelocity);
    }
  }
  // The solo partner has no tactical team simulation. Play its full-body
  // support step here, without requesting AI commands at the clip's end.
  if(currentAnim->functionType==e_FunctionType_Trip){
    Animation *clip=currentAnim->anim;const int frame=currentAnim->frameNum;
    Quaternion ignored;Vector3 before,after;
    clip->GetKeyFrame("player",std::max(0,frame-1),ignored,before);clip->GetKeyFrame("player",frame,ignored,after);
    if(frame>0)OffsetPosition((after-before).Get2D().GetRotated2D(spatialState.angle));
    animApplyBuffer.anim=clip;animApplyBuffer.frameNum=frame;animApplyBuffer.position=spatialState.position-after.Get2D().GetRotated2D(spatialState.angle);
    animApplyBuffer.orientation=spatialState.angle;animApplyBuffer.smooth=true;animApplyBuffer.noPos=false;
    SampleContactAnimation(clip,frame,spatialState.position,spatialState.angle,false,contactLocal,contactGlobal,contactPositions);
    UpdatePhysicalRigPose();
    if(++currentAnim->frameNum>=clip->GetEffectiveFrameCount()){currentAnim->functionType=e_FunctionType_Movement;physicalPartnerPhase=0;}
    return;
  }
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
  auto limitRenderedArms=[&](){
    football_physics::Pose pose;for(unsigned i=0;i<13;++i)pose[i]=rotation(nodeMap.at(pes3::nativeBoneNames[i])->GetRotation());
    football_physics::Metrics metrics;
    // The renderer interpolates native tracks and additive deltas separately.
    // Re-project this final blend as well: limiting the 100 Hz simulation
    // alone does not constrain the actual pose shown between its samples.
    football_physics::constrainArmPose(pes3NativeReference,1.f,pose,{{0,0,.96f}},metrics);
    for(unsigned i:{3u,4u,5u,6u})nodeMap.at(pes3::nativeBoneNames[i])->SetRotation(quaternion(pose[i]),false);
    if(GetConfiguration()->GetBool("training_telemetry",false))
      printf("PHYSICAL_ARM_RENDER t=%lu error=%.7f penetration=%.6f\n",fetchedbuf_animApplyBuffer.snapshotTime_ms,metrics.armLimitError,metrics.armPenetration);
  };
  if(!fetchedPhysicalRagdoll){
    const bool coherent=fetchedbuf_animApplyBuffer.motionMatched&&GetConfiguration()->GetBool("training_coherent_pose",true);
    if(coherent){
      // Interpolate the executed pose once, at the same timestamp as the ball.
      // Interpolating a source pose and its inverse/additive correction
      // separately does not reconstruct this pose during a clip transition.
      const auto &bind=pes3NativeReference.offsets[0];
      nodeMap.at("body")->SetPosition(Vector3(bind[0],bind[1],bind[2]),false);
      humanoidNode->SetPosition(fetchedContactRoot+Vector3(0,0,fetchedContactHeight/zMultiplier-bind[2]),false);
      nodeMap.at("body")->SetRotation(fetchedContactLocal[0],false);
      for(unsigned i=7;i<13;++i)nodeMap.at(pes3::nativeBoneNames[i])->SetRotation(fetchedContactLocal[i],false);
    }else humanoidNode->SetPosition(humanoidNode->GetPosition()+fetchedPhysicalRootOffset,false);
    const bool observeSituation=player->GetExternalController() && fetchedSituationState.coords[0]>.001f &&
      GetConfiguration()->GetBool("training_telemetry",false);
    Quaternion nativeUpper[7];
    if(observeSituation)for(unsigned i=1;i<7;++i)nativeUpper[i]=nodeMap.at(pes3::nativeBoneNames[i])->GetRotation();
    if(!coherent)PutTrainingContactPose();
    Vector3 supportLeft,supportRight,supportRoot;
    if(observeSituation){
      humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
      supportLeft=nodeMap.at("left_ankle")->GetDerivedPosition();supportRight=nodeMap.at("right_ankle")->GetDerivedPosition();supportRoot=nodeMap.at("body")->GetDerivedPosition();
    }
    // Observe the rendered upper-chain adaptation separately from the
    // existing (bounded) native foot-reach correction below.
    for(unsigned i:{1u,2u,3u,4u,5u,6u}){
      auto node=nodeMap.at(pes3::nativeBoneNames[i]);
      const Quaternion delta=Quaternion(QUATERNION_IDENTITY).GetSlerped(1-fetchedContactBlend,fetchedPhysicalAdditive[i]);
      node->SetRotation(coherent?fetchedContactLocal[i]:(delta*node->GetRotation()).GetNormalized(),false);
    }
    float situationFootError=0,situationRootError=0;
    if(observeSituation){
      humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
      situationFootError=std::max((supportLeft-nodeMap.at("left_ankle")->GetDerivedPosition()).GetLength(),(supportRight-nodeMap.at("right_ankle")->GetDerivedPosition()).GetLength());
      situationRootError=(supportRoot-nodeMap.at("body")->GetDerivedPosition()).GetLength();
    }
    for(unsigned i:{7u,8u,9u,10u,11u,12u}){
      auto node=nodeMap.at(pes3::nativeBoneNames[i]);
      const Quaternion delta=Quaternion(QUATERNION_IDENTITY).GetSlerped(1-fetchedContactBlend,fetchedPhysicalAdditive[i]);
      if(!coherent)node->SetRotation((delta*node->GetRotation()).GetNormalized(),false);
    }
    if(coherent)PutTrainingContactPose(); // Already identical; retain skin-contact diagnostics.
    limitRenderedArms();
    humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
    PutTrainingHeadLook();
    if(player->GetExternalController()&&GetConfiguration()->GetBool("training_motion_diagnostics",false)){
      float lowerError=0;
      for(unsigned i=7;i<13;++i)lowerError=std::max(lowerError,football_physics::length(football_physics::logarithm(football_physics::productRotation(rotation(nodeMap.at(pes3::nativeBoneNames[i])->GetRotation()),football_physics::inverseRotation(rotation(fetchedContactLocal[i]))))));
      std::ostringstream row;row<<std::fixed<<std::setprecision(7)<<"MOTION_RENDER t="<<match->GetPreviousPutTime_ms()<<" snapshot="<<fetchedbuf_animApplyBuffer.snapshotTime_ms<<" coherent="<<(coherent?1:0)<<" frame="<<fetchedbuf_animApplyBuffer.frameNum<<" lower_error="<<lowerError<<" pose=";
      for(unsigned i=0;i<13;++i){const auto q=nodeMap.at(pes3::nativeBoneNames[i])->GetRotation();
        row<<(i?";":"")<<q.elements[0]<<','<<q.elements[1]<<','<<q.elements[2]<<','<<q.elements[3];}
      printf("%s\n",row.str().c_str());
    }
    if(observeSituation){
      float trunk=0,arms=0;
      for(unsigned i:{1u,3u,4u,5u,6u}){
        const auto current=rotation(nodeMap.at(pes3::nativeBoneNames[i])->GetRotation());
        const float delta=football_physics::length(football_physics::logarithm(football_physics::productRotation(current,football_physics::inverseRotation(rotation(nativeUpper[i])))));
        if(i==1)trunk=delta;else arms=std::max(arms,delta);
      }
      printf("PHYSICAL_SITUATION_RENDER t=%lu actor=%d action=%d source=%s frame=%d weight=%.6f difficulty=%.6f trunk=%.6f arms=%.6f foot_error=%.8f root_error=%.8f\n",fetchedbuf_animApplyBuffer.snapshotTime_ms,player->GetID(),int(std::round(fetchedSituationState.coords[2])),fetchedbuf_animApplyBuffer.anim->GetName().c_str(),fetchedbuf_animApplyBuffer.frameNum,fetchedSituationState.coords[0],fetchedSituationState.coords[1],trunk,arms,situationFootError,situationRootError);
    }
    return;
  }
  auto body=nodeMap.at("body");const auto &bind=pes3NativeReference.offsets[0];
  body->SetPosition(Vector3(bind[0],bind[1],bind[2]),false);
  humanoidNode->SetPosition(fetchedContactRoot+Vector3(0,0,fetchedContactHeight/zMultiplier-bind[2]),false);
  for(unsigned i=0;i<13;++i)nodeMap.at(pes3::nativeBoneNames[i])->SetRotation(fetchedContactLocal[i],false);
  limitRenderedArms();
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
