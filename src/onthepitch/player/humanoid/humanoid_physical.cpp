#include "native_contact_timing.hpp"
#include "humanoidbase.hpp"
#include "physical_rig.hpp"
#include "contact_resistance.hpp"
#include "body_contest.hpp"
#include "anatomical_arms.hpp"
#include "situational_profiles.hpp"
#include "strike_technique.hpp"
#include "header_contact.hpp"
#include "walking_gait.hpp"
#include "../../physical_match_rules.hpp"
#include "../../reception_prediction.hpp"
#include "../../../main.hpp"
#include "../../match.hpp"
#include "../player.hpp"
#include "../controller/humancontroller.hpp"
#include "../analog_locomotion.hpp"
#include "utils/animationextensions/footballanimationextension.hpp"
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
  const char *receptions[]={"000_knee.anim","000_crotch.anim","000_chest.anim"};
  for(auto *clip:anims->GetAnimations())for(unsigned kind=0;kind<3;++kind)for(unsigned side=0;side<2;++side)
    if(clip->GetName()==std::string("media/animations/trap/idle/highballs/")+receptions[kind]+(side?"_mirror":""))physicalReceptionClips[kind][side]=clip;
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
  }
  static const AnimCollection *cachedCollection=nullptr;
  static std::weak_ptr<const std::vector<football_physics::BalanceMotion>> cachedBank;
  if(cachedCollection==anims.get())if(auto shared=cachedBank.lock()){
    physicalRig->setSharedBalanceMotions(shared);
    printf("%s actor=%d sources=%u variants=%u shared=1 kind=native_procedural\n",player->GetExternalController()?"PHYSICAL_BALANCE_BANK":"PHYSICAL_CPU_BALANCE_BANK",player->GetID(),unsigned(shared->size()/16),unsigned(shared->size()));return;
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
  printf("%s actor=%d sources=%u variants=%u shared=1 kind=native_procedural\n",player->GetExternalController()?"PHYSICAL_BALANCE_BANK":"PHYSICAL_CPU_BALANCE_BANK",player->GetID(),sources,unsigned(bank.size()));
  auto shared=std::make_shared<const std::vector<football_physics::BalanceMotion>>(std::move(bank));
  cachedCollection=anims.get();cachedBank=shared;physicalRig->setSharedBalanceMotions(shared);
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
bool HumanoidBase::BeginPhysicalHandHold(const Vector3 &where){
  if(!physicalRig||!physicalRig->adoptContactHand(point(where)))return false;
  if(GetConfiguration()->GetBool("training_telemetry",false))printf("PHYSICAL_GRIP_HAND t=%lu actor=%d bone=%d\n",match->GetActualTime_ms(),player->GetID(),physicalRig->activeHandBone());
  return true;
}
float HumanoidBase::PhysicalHandDistance(const Vector3 &where,bool holding)const{
  if(!physicalRig || !physicalRig->initialized())return 100;
  float distance=100;
  const int active=physicalRig->activeHandBone();
  for(unsigned elbow:{4u,6u}){
    // Acquisition can use either real hand. After adoption the same hand
    // must maintain the shirt; the opposite idle arm cannot fake continuity.
    if(holding&&active>=0&&int(elbow)!=active)continue;
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
void HumanoidBase::ResetPhysicalRig(bool clearHistory){
  if(physicalRig)physicalRig->reset();
  physicalRigTime=~0ul;physicalCollisionTime=0;if(clearHistory)buf_physicalRig.Clear();
  physicalWalkWeight=physicalWalkPhase=0;physicalWalkWanted=false;physicalRootDelta=Vector3(0);buf_physicalRootDelta.Clear();
  physicalReceptionWeight=physicalReceptionPhase=physicalReceptionApplied=0;physicalReceptionClip=nullptr;
  physicalReceptionContactAt=physicalReceptionEpisodeAt=0;physicalReceptionPart.clear();
  physicalSituationProfile=0;buf_situationState.Clear();
  physicalCutUntil=physicalBallImpactTime=physicalKeeperAttemptUntil=0;physicalIntentTime=~0ul;
  physicalPendingCut=Vector3(0);
  if(clearHistory)for(auto &buffer:buf_physicalAdditive)buffer.Clear();
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
Vector3 HumanoidBase::SafeFirstPersonEye(const Vector3 &requested,float clearance)const{
  Quaternion q[13];Vector3 p[13];
  const Vector3 origin=player->GetGeomPosition().Get2D();
  for(unsigned i=0;i<13;++i){const auto node=nodeMap.at(pes3::nativeBoneNames[i]);q[i]=node->GetDerivedRotation();p[i]=origin+(node->GetDerivedPosition()-origin)*zMultiplier;}
  // The caller already samples the rendered neck after the root offset.
  Vector3 eye=requested;
  // Arms may cross the view without moving the observer's head. The upper
  // torso proxy must stop below the neck: a capsule ending at the neck was
  // incorrectly pushing the anatomical eye on every step and body turn.
  for(unsigned iteration=0;iteration<4;++iteration)for(unsigned bone:{0u,1u}){
    Vector3 a=p[bone],b=bone==0?p[1]:p[1]+(p[2]-p[1])*.65f;
    const Vector3 axis=b-a;const float along=clamp((eye-a).GetDotProduct(axis)/std::max(.00001f,axis.GetSquaredLength()),0.f,1.f);
    const Vector3 closest=a+axis*along;
    const float radius=.16f*zMultiplier+clearance;
    if((eye-closest).GetLength()<radius)eye=closest+(eye-closest).GetNormalized(q[1]*Vector3(0,-1,0))*radius;
  }
  float gap=100;
  for(unsigned iteration=0;iteration<3;++iteration){
    Vector3 surface;gap=ContactSurface(eye,"trunk",q,p,&surface)+.11f;
    if(gap>=clearance)break;
    eye=surface+(eye-surface).GetNormalized(q[1]*Vector3(0,-1,0))*clearance;
  }
  gap=ContactSurface(eye,"trunk",q,p)+.11f;
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("PHYSICAL_EYE t=%lu clearance=%.6f correction=%.6f near=%.6f required=%.6f\n",fetchedbuf_animApplyBuffer.snapshotTime_ms,gap,(eye-requested).GetLength(),training::eyeNearPlane,clearance);
  return eye;
}
void HumanoidBase::AddPhysicalImpulse(const Vector3 &value,const Vector3 &lever,bool forceFall){
  if(!PhysicalRigEnabled())return;
  ConfigurePhysicalRig();
  physicalRig->impulse(point(value),point(lever),forceFall);
  // Moderate blows use a generated support step. Strong blows still select
  // the original full-body protective clip before yielding to a dynamic fall.
  const unsigned long now=match->GetActualTime_ms();
  if(!forceFall && (value.GetLength()>=160.f||(value.GetLength()>=70.f&&spatialState.floatVelocity>=4.8f)) && physicalRig->mode()==football_physics::Mode::Active &&
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
  using football_situations::ContactStyle;
  if(part=="head")context.style=type==e_FunctionType_Trap||type==e_FunctionType_BallControl?ContactStyle::HeadCushion:ContactStyle::HeadRedirect;
  else if(part=="trunk"||part=="middle")context.style=ContactStyle::Chest;
  else if(part.find("thigh")!=std::string::npos||part.find("upperleg")!=std::string::npos)context.style=ContactStyle::Thigh;
  else if(part.find("knee")!=std::string::npos||part.find("lowerleg")!=std::string::npos)context.style=ContactStyle::Shin;
  else if(part.find("foot")!=std::string::npos){
    const float height=ballLocal.coords[2]+.96f*zMultiplier;
    if(height>.4f)context.style=ContactStyle::Volley;
    else if(height>.17f&&match->GetBall()->GetMovement().coords[2]>.7f)context.style=ContactStyle::HalfVolley;
    else if(type==e_FunctionType_Shot&&context.power>.5f)context.style=ContactStyle::Instep;
    else context.style=((context.rightFoot&&ballLocal.coords[0]<-.06f)||(!context.rightFoot&&ballLocal.coords[0]>.06f))?ContactStyle::Outside:ContactStyle::Inside;
    const auto technique=currentAnim->anim->GetVariable("physical_technique");
    if(height<.40f){
      if(technique=="toe")context.style=ContactStyle::Toe;
      else if(technique=="knuckle")context.style=ContactStyle::Knuckle;
      else if(technique=="inside"&&context.kind==ActionKind::Shot)context.style=ContactStyle::Placed;
      else if(technique=="outside")context.style=ContactStyle::Outside;
    }
  }
  // Straight controlled dribbling receives a subtle upper-body response;
  // the original root, lower-body pose and contact event stay authoritative.
  bool anticipate=false;
  if(context.kind==ActionKind::None&&!input.action&&!input.upperReception&&!input.staggering&&!match->GetBallRetainer()){
    Player *last=match->GetLastTouchPlayer();
    const bool free=!last||last!=player&&(last->GetTeamID()==static_cast<Player*>(player)->GetTeamID()||
      (last->GetPosition()-match->GetBall()->Predict(0)).Get2D().GetLength()>1.15f);
    const auto plan=football_reception::predict([&](unsigned ms){return point(match->GetBall()->Predict(ms));},point(spatialState.position),point(spatialState.movement),point(match->GetBall()->GetMovement()),free);
    if(plan.valid&&plan.time<.7f){
      anticipate=true;context.kind=ActionKind::Control;context.enabled=true;
      context.ball=point(inverseBody*(vector(plan.point)-contactPositions[0]));
      context.phase=.05f+.19f*(1-plan.time/.7f);context.contactPhase=.32f;context.contactMade=false;
      context.power=clamp(match->GetBall()->GetMovement().GetLength()/24.f,0.f,1.f);context.difficulty=std::max(.35f,context.power);
      context.style=plan.height>1.65f?ContactStyle::HeadCushion:plan.height>1.f?ContactStyle::Chest:plan.height>.4f?ContactStyle::Thigh:plan.height>.2f?ContactStyle::Shin:ContactStyle::Inside;
      if(GetConfiguration()->GetBool("training_telemetry",false)&&match->GetActualTime_ms()%100==0)
        printf("RECEPTION_PREPARE t=%lu actor=%d arrival=%.5f height=%.5f gap=%.5f style=%u\n",match->GetActualTime_ms(),player->GetID(),plan.time,plan.height,plan.gap,unsigned(context.style));
    }
  }
  const bool bodyReaction=physicalBallImpactTime&&match->GetActualTime_ms()-physicalBallImpactTime<700&&
    (!input.action||(type==e_FunctionType_Trap&&currentAnim->touchMade))&&!input.upperReception&&!input.staggering;
  if(bodyReaction){
    context.kind=ActionKind::Control;context.incoming=point(inverseBody*physicalBallImpactVelocity);
    context.ball=point(inverseBody*(physicalBallImpactPosition-contactPositions[0]));
    context.phase=clamp((match->GetActualTime_ms()-physicalBallImpactTime+40)/740.f,0.f,1.f);
    context.contactPhase=.12f;context.contactMade=true;context.power=clamp(physicalBallImpactVelocity.GetLength()/25.f,0.f,1.f);
    context.difficulty=std::max(context.difficulty,context.power*.8f);context.preserveHead=context.power<.6f;
    context.style=context.power>.70f||physicalBallImpactPart=="back"?ContactStyle::DrivenImpact:
      physicalBallImpactPart=="neck"||physicalBallImpactPart=="head"?ContactStyle::HeadCushion:
      physicalBallImpactPart.find("thigh")!=std::string::npos?ContactStyle::Thigh:
      physicalBallImpactPart.find("knee")!=std::string::npos?ContactStyle::Shin:
      physicalBallImpactPart.find("foot")!=std::string::npos||physicalBallImpactPart.find("ankle")!=std::string::npos?ContactStyle::Inside:ContactStyle::Chest;
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
    if(context.style==ContactStyle::Volley)pattern=35;
    else if(context.style==ContactStyle::HalfVolley)pattern=36;
    else if(context.style==ContactStyle::HeadCushion)pattern=37;
    else if(context.style==ContactStyle::HeadRedirect)pattern=38;
    else if(context.style==ContactStyle::Chest)pattern=39;
    else if(context.style==ContactStyle::Thigh)pattern=40;
    else if(context.style==ContactStyle::Shin)pattern=41;
    else if(context.style==ContactStyle::DrivenImpact)pattern=42;
    else if(context.kind==ActionKind::Cross&&context.speed>3.f)pattern=45;
    else if(context.kind==ActionKind::Pass&&turn>.5f)pattern=46;
    else if(context.kind==ActionKind::Control&&turn>.18f)pattern=ballLocal.coords[0]>.0f?43:44;
    else if(context.kind==ActionKind::Control)pattern=context.style==ContactStyle::Outside?33:32;
    else if(context.style==ContactStyle::Instep)pattern=34;
    else if(context.incoming[0]*context.incoming[0]+context.incoming[1]*context.incoming[1]>100.f)pattern=47;
    if(context.style==ContactStyle::Toe)pattern=context.speed>3.f?69:49;
    else if(context.style==ContactStyle::Placed)pattern=50;
    else if(context.style==ContactStyle::Knuckle)pattern=52;
    else if(context.kind==ActionKind::Header)pattern=context.pressure>.45f?78:context.speed>3.f?53:height>1.65f?54:55;
    else if(context.kind==ActionKind::Control&&turn<.18f&&context.style!=ContactStyle::DrivenImpact)pattern=context.speed<2.f?57:context.pressure>.4f?56:58;
    else if(context.kind==ActionKind::Pass&&turn<.18f&&context.speed<2.f)pattern=77;
    else if(context.kind==ActionKind::Shot&&turn>.5f)pattern=76;
    else if(context.style==ContactStyle::Outside)pattern=context.kind==ActionKind::Cross?75:context.speed>3.f?74:51;
    else if(context.kind==ActionKind::Cross&&height>1.f)pattern=70;
    const auto &profile=football_situations::profileFor(context.kind,std::max(context.power,context.difficulty),context.pressure,turn,reach,pattern);
    context.pattern=profile.pattern;
    physicalSituationProfile=profile.id;context.trunkGain=profile.trunkGain;context.armGain=profile.armGain;context.followThroughGain=profile.followThroughGain;
    if(context.kind==ActionKind::Pass){context.trunkGain=std::max(context.trunkGain,1.15f);context.armGain=std::max(context.armGain,1.12f);}
    if(context.kind==ActionKind::Control&&turn<.18f&&context.pressure<.4f&&!anticipate&&!bodyReaction){context.trunkGain*=.80f;context.armGain*=.78f;}
    if(anticipate||bodyReaction){context.trunkGain=std::max(context.trunkGain,1.05f);context.armGain=std::max(context.armGain,1.12f);}
  }
}

void HumanoidBase::ComposeWalkingReference(football_physics::Input &input,bool advance){
  using namespace football_physics;
  auto *clip=currentAnim->anim;
  bool walking=spatialState.floatVelocity>.10f&&spatialState.floatVelocity<1.65f;
  if(player->GetExternalController()){
    auto *human=static_cast<HumanController*>(player->GetExternalController());
    const float strength=human->GetHIDevice()->GetDirection().GetLength();
    walking=strength>.01f&&strength<=football_input::walkingStickLimit&&!human->SprintButtonDown()&&!match->TrainingReceivingBall();
  }
  const bool wanted=currentAnim->functionType==e_FunctionType_Movement&&walking&&
    spatialState.floatVelocity>.10f&&!input.action&&!input.upperReception&&!input.staggering;
  const float stride=bounded(.38f+spatialState.movement.Get2D().GetLength()*.12f,.38f,.62f);
  {
    if(wanted&&!physicalWalkWanted){
      physicalWalkEntry=physicalRig->initialized()?physicalRig->pose():input.pose;
      physicalWalkHeight=physicalRig->initialized()?physicalRig->points()[0][2]:input.pelvis[2];
      physicalWalkPhase=float(currentAnim->frameNum)/std::max(1,clip->GetFrameCount()-1);
    }
    if(!wanted&&physicalWalkWanted){physicalWalkExit=physicalRig->pose();physicalWalkHeight=physicalRig->points()[0][2];}
    physicalWalkWanted=wanted;
  }
  if(advance){
    float release=.18f;
    if(currentAnim->touchFrame>=0&&!currentAnim->touchMade)
      release=std::max(.025f,std::min(release,(currentAnim->touchFrame-currentAnim->frameNum)*.005f));
    physicalWalkWeight=bounded(physicalWalkWeight+(wanted?.01f/.20f:-.01f/release),0,1);
    if(wanted){
      physicalWalkPhase+=spatialState.movement.Get2D().GetLength()*.01f/(stride/.64f);
      physicalWalkPhase-=std::floor(physicalWalkPhase);
    }
  }
  if(physicalWalkWeight<=0)return;
  const float weight=smooth(physicalWalkWeight);
  if(wanted){
    auto bind=pes3NativeReference;for(auto &offset:bind.offsets)offset=scalePoint(offset,zMultiplier);
    auto pose=input.pose;
    Vec pelvis=input.pelvis;pelvis[2]=(pes3NativeReference.offsets[0][2]-.08f+.012f*std::cos(12.5663706f*physicalWalkPhase))*zMultiplier;
    Vec travel=rotatePoint(inverseRotation(pose[0]),point(spatialState.movement));travel[2]=0;
    football_walk::pose(bind,pose,pelvis,physicalWalkPhase,stride,travel);
    football_walk::upperBody(bind,pose,physicalWalkPhase);
    for(unsigned bone=1;bone<13;++bone)input.pose[bone]=blended(physicalWalkEntry[bone],pose[bone],weight);
    input.pelvis[2]=physicalWalkHeight*(1-weight)+pelvis[2]*weight;
  }else{
    for(unsigned bone=1;bone<13;++bone)input.pose[bone]=blended(input.pose[bone],physicalWalkExit[bone],weight);
    input.pelvis[2]=input.pelvis[2]*(1-weight)+physicalWalkHeight*weight;
  }
}

void HumanoidBase::ComposeReceptionReference(football_physics::Input &input,bool advance){
  using namespace football_physics;
  physicalReceptionApplied=0;
  const unsigned long now=match->GetActualTime_ms();
  const Vector3 ball=match->GetBall()->Predict(0);
  bool active=false;float phase=physicalReceptionPhase;
  const bool available=GetConfiguration()->GetBool("training_situational_motion",true)&&!input.staggering&&!input.upperReception&&!PhysicalRigBusy()&&!match->GetBallRetainer()&&!input.gripped&&!input.handTargetActive;
  const bool ownKick=match->GetLastTouchPlayer()==player&&static_cast<Player*>(player)->GetLastTouchType()==e_TouchType_Intentional_Kicked;
  if(available&&!ownKick){
    const bool recent=physicalReceptionContactAt&&now-physicalReceptionContactAt<520;
    auto plan=football_reception::predict([&](unsigned ms){return point(match->GetBall()->Predict(ms));},point(spatialState.position),point(spatialState.movement),point(match->GetBall()->GetMovement()),true);
    const Vector3 local=quaternion(input.pose[0]).GetInverse()*(vector(plan.point)-spatialState.position);
    if(recent&&!physicalReceptionClip){
      const float height=physicalBallImpactPosition.coords[2]-spatialState.position.coords[2];
      const unsigned kind=height<1.02f?0:height<1.20f?1:2;
      const Vector3 hit=quaternion(input.pose[0]).GetInverse()*(physicalBallImpactPosition-spatialState.position);
      physicalReceptionClip=physicalReceptionClips[kind][hit.coords[0]>.10f?1:0];
    }
    if(recent&&physicalReceptionClip){
      Vector3 ignored;int contact=0;
      boost::static_pointer_cast<FootballAnimationExtension>(physicalReceptionClip->GetExtension("football"))->GetFirstTouch(ignored,contact);
      phase=std::min(float(physicalReceptionClip->GetEffectiveFrameCount()),contact+(now-physicalReceptionEpisodeAt)/14.f);active=true;
    }else if(plan.valid&&plan.time<.60f&&plan.gap<.85f&&plan.height>.28f&&plan.height<1.65f&&local.coords[1]<.22f){
      const unsigned kind=plan.height<1.02f?0:plan.height<1.20f?1:2;
      const unsigned mirror=local.coords[0]>.10f?1:0;
      if(physicalReceptionWeight<.05f||!physicalReceptionClip){
        physicalReceptionClip=physicalReceptionClips[kind][mirror];
        // Before the first real contact this clock is a committed arrival
        // deadline. A skin contact replaces it with the absorption epoch.
        // Re-predicting the closest root point every tick could indefinitely
        // hold frame zero instead of playing the preparation.
        physicalReceptionEpisodeAt=now+unsigned(plan.time*1000);
      }
      if(physicalReceptionClip){
        Vector3 ignored;int contact=0;
        boost::static_pointer_cast<FootballAnimationExtension>(physicalReceptionClip->GetExtension("football"))->GetFirstTouch(ignored,contact);
        phase=bounded(contact-(float(physicalReceptionEpisodeAt)-float(now))/14.f,0.f,float(contact));active=true;
      }
    }
  }
  if(input.action||input.touchPending)active=false;
  if(advance){physicalReceptionPhase=phase;physicalReceptionWeight=bounded(physicalReceptionWeight+(active?.01f/.14f:-.01f/.18f),0,.90f);}
  if(!physicalReceptionClip||physicalReceptionWeight<=.001f)return;
  float weight=smooth(physicalReceptionWeight);
  // Hand the contacting chain back to the native action, then keep it
  // there. Re-enabling this layer when touchMade became true pulled a
  // grounded control foot back into an old high-reception pose.
  if(currentAnim->functionType!=e_FunctionType_Movement)
    weight*=input.touchPending?smooth((currentAnim->touchFrame-currentAnim->frameNum)/12.f):0.f;
  if(input.upperReception||input.staggering||PhysicalRigBusy())weight=0;
  if(weight<.001f)return;
  physicalReceptionApplied=weight;
  Quaternion oldLocal[13],oldWorld[13];Vector3 oldPoints[13];
  for(unsigned bone=0;bone<13;++bone)oldLocal[bone]=quaternion(input.pose[bone]);
  oldPoints[0]=vector(input.pelvis);ContactForwardKinematics(oldLocal,oldWorld,oldPoints);
  Quaternion local[13],world[13];Vector3 points[13];
  SampleContactAnimation(physicalReceptionClip,physicalReceptionPhase,vector(input.pelvis),spatialState.angle,false,local,world,points);
  const Quat head=productRotation(input.pose[1],input.pose[2]);
  for(unsigned bone=1;bone<13;++bone)if(bone!=2)input.pose[bone]=blended(input.pose[bone],rotation(local[bone]),weight);
  input.pose[2]=normalized(productRotation(inverseRotation(input.pose[1]),head));
  input.pelvis[2]=input.pelvis[2]*(1-.35f*weight)+points[0].coords[2]*.35f*weight;
  const bool mirror=physicalReceptionClip->GetName().find("_mirror")!=std::string::npos;
  input.receptionSupportBone=mirror?12:9;input.receptionSupport=point(oldPoints[input.receptionSupportBone]);
  input.grounding=false;input.passiveTracking=false;
  if(advance&&GetConfiguration()->GetBool("training_telemetry",false)&&now%50==0)
    printf("PHYSICAL_RECEIVE_REFERENCE t=%lu actor=%d source=%s phase=%.4f weight=%.5f support=%d contact=%d\n",now,player->GetID(),physicalReceptionClip->GetName().c_str(),physicalReceptionPhase,weight,input.receptionSupportBone,physicalReceptionContactAt&&now-physicalReceptionContactAt<520?1:0);
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
    input.staggering=PhysicalStaggering();
    input.action=currentAnim->functionType!=e_FunctionType_Movement && currentAnim->functionType!=e_FunctionType_BallControl;
    input.touchPending=currentAnim->touchFrame>=0&&!currentAnim->touchMade;
    input.grounding=(currentAnim->functionType==e_FunctionType_Movement||
      (currentAnim->functionType==e_FunctionType_BallControl&&currentAnim->touchMade))&&spatialState.floatVelocity>.15f&&
      spatialState.floatVelocity<4.8f&&(currentAnim->anim->GetVariable("training_walk_support")=="overlap"||
      spatialState.movement.GetNormalized(0).GetDotProduct(spatialState.bodyDirectionVec)<.65f);
    // Preserve the authored preparation pose while a one-touch action is
    // queued. Its current base can still be locomotion during interception.
    input.action=input.action || (player->GetExternalController() && static_cast<HumanController*>(player->GetExternalController())->GetActionMode()!=0);
    std::vector<Player*> opponents;match->GetTeam(1-static_cast<Player*>(player)->GetTeamID())->GetActivePlayers(opponents);
    for(auto *opponent:opponents) {
      const Vector3 delta=opponent->GetPosition()-spatialState.position;
      if(delta.GetLength()<input.opponentDistance){input.opponentDistance=delta.GetLength();input.opponent=point(delta);}
    }
    input.passiveTracking=PlayerMatchEnabled() && !player->GetExternalController() && input.opponentDistance>2.f &&
      spatialState.movement.GetLength()<.20f && !input.action && !input.staggering && !input.gripped;
    ComposeWalkingReference(input,physicalRigTime!=match->GetActualTime_ms());
    ComposeReceptionReference(input,physicalRigTime!=match->GetActualTime_ms());
    BuildSituationalInput(input);
    if(input.situation.kind!=football_situations::ActionKind::None)input.passiveTracking=false;
    if(physicalBallImpactTime&&match->GetActualTime_ms()-physicalBallImpactTime<600){
      input.ballImpact=point(physicalBallImpactVelocity);input.ballImpactAge=(match->GetActualTime_ms()-physicalBallImpactTime)*.001f;
      input.ballImpactLever=point(physicalBallImpactPosition-contactPositions[0]);
      input.passiveTracking=false;
    }
    // Anticipate small reach corrections. The existing skin contact gate
    // remains responsible for accepting an actual ball impulse.
    const int remaining=currentAnim->touchFrame-currentAnim->frameNum;
    const std::string part=currentAnim->anim->GetVariable("touch_bodypart");
    const bool saveHand=currentAnim->functionType==e_FunctionType_Deflect&&(part=="left_lowerarm"||part=="right_lowerarm");
    if(UsesTrainingContacts() && currentAnim->contactLegOffset.GetLength()<.0001f && currentAnim->touchFrame>=0 && !currentAnim->touchMade && remaining>=0 && remaining<=24 &&
       (part=="right_foot" || part=="left_foot" || part=="head" || part=="trunk" || saveHand)) {
      Quaternion q[13],global[13];Vector3 p[13];
      const unsigned frame=std::min<unsigned>(currentAnim->touchFrame,currentAnim->positions.size()-1);
      const unsigned now=std::min<unsigned>(currentAnim->frameNum,currentAnim->positions.size()-1);
      Vector3 root=contactPositions[0].Get2D()+currentAnim->positions[frame]-currentAnim->positions[now];
      // The native approach keeps moving the whole player toward the ball.
      // Predict that remaining approach too: otherwise a small heel contact
      // is corrected toward an obsolete root and misses despite having time
      // to reach. Keep the existing slow, bounded reach and exact skin gate.
      const float count=currentAnim->touchFrame+1.f;
      for(int f=currentAnim->frameNum+1;f<=currentAnim->touchFrame;++f)
        root+=currentAnim->actionSmuggle*(football_contact::approachWeight(f,unsigned(count))/count);
      SampleContactAnimation(currentAnim->anim,float(currentAnim->touchFrame),root,startAngle,false,q,global,p);
      const Vector3 predicted=match->GetBall()->Predict(remaining*10);Vector3 skin;
      const float gap=ContactSurface(predicted,part,global,p,&skin);
      // Aim a contacting hand slightly into the expected ball path rather
      // than leaving it at fragile mathematical tangency. The visible arm
      // moves gradually; acceptance still uses the unchanged real skin gate.
      const float reachGap=gap+(saveHand?.030f:0.f);
      if(reachGap>0 && gap<.14f) {
        input.reachBone=part=="right_foot"?12:part=="left_foot"?9:part=="head"?2:part=="left_lowerarm"?4:part=="right_lowerarm"?6:1;
        input.reach=point((predicted-skin).GetNormalized(Vector3(1,0,0))*std::min(reachGap,.12f));
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
      const float priorHeight=contactPositions[0].coords[2];
      ResetPosition(root,focus,true);
      SampleContactAnimation(currentAnim->anim,0,root,spatialState.angle,false,contactLocal,contactGlobal,contactPositions);
      if(GetConfiguration()->GetBool("training_telemetry",false))printf("PHYSICAL_RECOVERY_HANDOFF t=%lu from_z=%.6f to_z=%.6f frame=%d\n",match->GetActualTime_ms(),priorHeight,contactPositions[0].coords[2],currentAnim->frameNum);
      if(player->GetExternalController())player->GetExternalController()->Reset();
      printf("PHYSICAL_RIG_RECOVERED t=%lu\n",match->GetActualTime_ms());fflush(stdout);return;
    }
    if(GetConfiguration()->GetBool("training_telemetry",false) && physicalRigTime%50==0) {
      const auto &d=physicalRig->metrics();const auto root=physicalRig->points()[0];const auto q=physicalRig->worldRotations()[0];
      if(player->GetExternalController())printf("PHYSICAL_RIG_FRAME {\"t\":%lu,\"mode\":%d,\"root\":[%.5f,%.5f,%.5f],\"lean\":%.5f,\"turn\":%.5f,\"reach\":%.5f,\"support_margin\":%.5f,\"effort\":%.5f,\"ground_contacts\":%u,\"ground_correction\":%.6f,\"angular_speed\":%.5f,\"energy\":%.5f,\"joint_error\":%.6f,\"self_penetration\":%.6f,\"brace\":%.2f,\"recovery_phase\":%.4f,\"root_q\":[%.6f,%.6f,%.6f,%.6f]}\n",
        physicalRigTime,after,root[0],root[1],root[2],d.lean,d.turnRate,d.reach,d.supportMargin,d.effort,d.groundContacts,d.penetration,d.angularSpeed,d.kineticEnergy,d.jointError,d.selfPenetration,d.brace,d.recoveryPhase,q[0],q[1],q[2],q[3]);
      if(input.grounding)printf("PHYSICAL_FOOT_PLANT t=%lu actor=%d correction=%.6f\n",physicalRigTime,player->GetID(),d.plantedCorrection);
      if(d.recoveryStep>.001f)printf("PROCEDURAL_SUPPORT_STEP t=%lu actor=%d foot=%d weight=%.6f lift=%.6f support_error=%.6f pending=%d\n",physicalRigTime,player->GetID(),d.recoveryFoot,d.recoveryStep,d.recoveryLift,d.recoverySupportError,input.touchPending?1:0);
      printf("PHYSICAL_BALANCE t=%lu actor=%d phase=%d risk=%.5f step=%.5f choice=%d arm_speed=%.5f elbow=%.5f counter=%.5f\n",physicalRigTime,player->GetID(),d.balancePhase,d.balanceRisk,d.stepDemand,d.balanceChoice,d.armSpeed,d.elbowAngle,d.counterbalance);
      if(physicalRigTime%100==0)printf("ML_MUSCLE t=%lu actor=%d human=%d samples=%u error=%.6f acceleration=%.6f passive=%d\n",physicalRigTime,player->GetID(),player->GetExternalController()?1:0,d.neuralMotorSamples,d.motorError,d.motorAcceleration,input.passiveTracking?1:0);
      if(d.supportSink>1e-5f||d.supportTilt>1e-5f)printf("PHYSICAL_SUPPORT_COMPLIANCE t=%lu actor=%d sink=%.6f tilt=%.6f knee=%.6f foot_error=%.7f pending=%d\n",physicalRigTime,player->GetID(),d.supportSink,d.supportTilt,d.supportKnee,d.supportFootError,input.touchPending?1:0);
      if(after || input.staggering)printf("PHYSICAL_SUPPORT t=%lu actor=%d mode=%d stagger=%d muscles=%.5f torque=%.5f contacts=%u\n",physicalRigTime,player->GetID(),after,input.staggering?1:0,d.muscleEffort,d.supportTorque,d.groundContacts);
      printf("PHYSICAL_ARM_LIMITS t=%lu actor=%d error=%.7f penetration=%.6f left=[%.5f,%.5f,%.5f,%.5f] right=[%.5f,%.5f,%.5f,%.5f]\n",physicalRigTime,player->GetID(),d.armLimitError,d.armPenetration,
        physicalRig->pose()[4][0],physicalRig->pose()[4][1],physicalRig->pose()[4][2],physicalRig->pose()[4][3],
        physicalRig->pose()[6][0],physicalRig->pose()[6][1],physicalRig->pose()[6][2],physicalRig->pose()[6][3]);
    }
    if(GetConfiguration()->GetBool("training_telemetry",false) && physicalRigTime%20==0 && physicalRig->metrics().situation.weight>.001f){
      const auto &d=physicalRig->metrics();const auto &s=d.situation;
      printf("PHYSICAL_SITUATION t=%lu actor=%d action=%d profile=%u source=%s frame=%d difficulty=%.6f phase=%.6f weight=%.6f trunk=%.6f arms=%.6f foot_error=%.8f root_error=%.8f rate=%.6f pressure=%.6f support=%d style=%u\n",physicalRigTime,player->GetID(),int(s.kind),physicalSituationProfile,currentAnim->anim->GetName().c_str(),currentAnim->frameNum,s.difficulty,s.phase,s.weight,d.situationTrunk,d.situationArms,d.situationFootError,d.situationRootError,s.angularRate,input.situation.pressure,input.situation.supportSide,unsigned(input.situation.style));
    }
  } else physicalRig->evaluate(input);
  if(!physicalRig || !physicalRig->initialized())return;
  physicalRootDelta=vector(football_physics::subtractPoint(physicalRig->points()[0],input.pelvis));
  for(unsigned i=0;i<13;++i){contactLocal[i]=quaternion(physicalRig->pose()[i]);contactGlobal[i]=quaternion(physicalRig->worldRotations()[i]);contactPositions[i]=vector(physicalRig->points()[i]);}
}

void HumanoidBase::PhysicalHeaderTouch(Vector3 &outgoing,const Vector3 &incoming,bool shot){
  if(!PhysicalRigEnabled()||currentAnim->anim->GetVariable("touch_bodypart")!="head")return;
  Vector3 surface;const Vector3 ball=match->GetBall()->Predict(0);
  ContactSurface(ball,"head",contactGlobal,contactPositions,&surface);
  Vector3 velocity=spatialState.movement;
  if(contactPreviousBallValid){
    Quaternion local[13],global[13];Vector3 p[13];
    std::copy(contactPreviousSkinLocal,contactPreviousSkinLocal+13,local);p[0]=contactPreviousSkinRoot;
    ContactForwardKinematics(local,global,p);
    const Vector3 offset=contactGlobal[2].GetInverse()*(surface-contactPositions[2]);
    velocity=(surface-p[2]-global[2]*offset)*100.f;velocity.NormalizeMax(8.f);
  }
  const Vector3 aim=outgoing.GetNormalized(spatialState.bodyDirectionVec);
  float power=currentAnim->originatingCommand.touchInfo.inputPower;
  if(!player->GetExternalController())power=currentAnim->originatingCommand.touchInfo.desiredPower;
  if(player->GetExternalController()&&currentAnim->originatingCommand.touchInfo.charge_ms)
    power=clamp(currentAnim->originatingCommand.touchInfo.charge_ms/650.f,0.f,1.f);
  const float speed=football_header::speed(power,incoming.GetLength(),velocity.GetDotProduct(aim),shot);
  outgoing=aim*speed;
  if(GetConfiguration()->GetBool("training_telemetry",false))printf("HEADER_CONTACT_POWER t=%lu actor=%d shot=%d power=%.5f incoming=%.5f drive=%.5f speed=%.5f loaded=%d\n",match->GetActualTime_ms(),player->GetID(),shot?1:0,power,incoming.GetLength(),velocity.GetDotProduct(aim),speed,currentAnim->anim->GetVariable("physical_header_load")=="true"?1:0);
}

void HumanoidBase::PhysicalReceptionContact(const Vector3 &incoming,const Vector3 &outgoing,const std::string &part){
  if(!PhysicalRigEnabled()||incoming.GetLength()<1.8f)return;
  if(match->GetLastTouchPlayer()==player&&static_cast<Player*>(player)->GetLastTouchType()!=e_TouchType_Accidental)return;
  physicalBallImpactTime=match->GetActualTime_ms();physicalBallImpactVelocity=incoming-spatialState.movement;
  physicalBallImpactPosition=match->GetBall()->Predict(0);physicalBallImpactPart=part;
  if(physicalBallImpactPosition.coords[2]>.28f){
    if(!physicalReceptionContactAt||match->GetActualTime_ms()-physicalReceptionContactAt>250)physicalReceptionEpisodeAt=match->GetActualTime_ms();
    physicalReceptionContactAt=match->GetActualTime_ms();physicalReceptionPart=part;
  }
  AddPhysicalImpulse((incoming-outgoing)*.43f,physicalBallImpactPosition-contactPositions[0]);
  if(GetConfiguration()->GetBool("training_telemetry",false))printf("RECEPTION_BODY_LOAD t=%lu actor=%d part=%s incoming=%.5f\n",match->GetActualTime_ms(),player->GetID(),part.c_str(),incoming.GetLength());
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
  std::vector<Player*> opponents;match->GetTeam(1-static_cast<Player*>(player)->GetTeamID())->GetActivePlayers(opponents);
  float pressure=0;for(auto *opponent:opponents)pressure=std::max(pressure,clamp((1.5f-(opponent->GetPosition()-spatialState.position).GetLength())/1.5f,0.f,1.f));
  const float demand=(pass?.62f:1.f)*football_strike::followThroughLoad(power,speed,turn,pressure,header);
  const Vector3 direction=outgoing.Get2D().GetNormalized(spatialState.bodyDirectionVec);
  AddPhysicalImpulse(recoil-direction*demand,Vector3(0,0,header?.35f:.22f));
  if(demand>72.f)physicalPendingCut=recoil-direction*demand;
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
  auto observeVisible=[&](){
    const unsigned long snapshot=fetchedbuf_animApplyBuffer.snapshotTime_ms;
    if(!GetConfiguration()->GetBool("training_telemetry",false)||
       (physicalVisibleTelemetryTime!=~0ul&&snapshot>=physicalVisibleTelemetryTime&&snapshot-physicalVisibleTelemetryTime<40))return;
    physicalVisibleTelemetryTime=snapshot;
    humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
    const Vector3 origin=humanoidNode->GetPosition().Get2D();
    const Vector3 left=origin+(nodeMap.at("left_ankle")->GetDerivedPosition()-origin)*zMultiplier;
    const Vector3 right=origin+(nodeMap.at("right_ankle")->GetDerivedPosition()-origin)*zMultiplier;
    const Vector3 pelvis=origin+(nodeMap.at("body")->GetDerivedPosition()-origin)*zMultiplier;
    const Vector3 torso=nodeMap.at("middle")->GetDerivedRotation()*Vector3(0,0,1);
    Vector3 limbs[4];unsigned limb=0;
    for(const char *name:{"left_knee","right_knee","left_elbow","right_elbow"})limbs[limb++]=origin+(nodeMap.at(name)->GetDerivedPosition()-origin)*zMultiplier;
    printf("VISIBLE_LIMBS {\"t\":%lu,\"actor\":%d,\"left_knee\":[%.5f,%.5f,%.5f],\"right_knee\":[%.5f,%.5f,%.5f],\"left_elbow\":[%.5f,%.5f,%.5f],\"right_elbow\":[%.5f,%.5f,%.5f]}\n",snapshot,player->GetID(),limbs[0].coords[0],limbs[0].coords[1],limbs[0].coords[2],limbs[1].coords[0],limbs[1].coords[1],limbs[1].coords[2],limbs[2].coords[0],limbs[2].coords[1],limbs[2].coords[2],limbs[3].coords[0],limbs[3].coords[1],limbs[3].coords[2]);
    printf("VISIBLE_PHYSICS {\"t\":%lu,\"actor\":%d,\"human\":%d,\"walk\":%.5f,\"phase\":%.5f,\"slow\":%d,\"kind\":\"%s\",\"blend\":%.5f,\"pelvis\":[%.5f,%.5f,%.5f],\"left\":[%.5f,%.5f,%.5f],\"right\":[%.5f,%.5f,%.5f],\"torso\":[%.5f,%.5f,%.5f],\"root_delta\":%.6f}\n",fetchedbuf_animApplyBuffer.snapshotTime_ms,player->GetID(),player->GetExternalController()?1:0,fetchedVisibleWalking.coords[0],fetchedVisibleWalking.coords[1],fetchedVisibleWalking.coords[2]>.5f?1:0,fetchedbuf_animApplyBuffer.anim->GetAnimType().c_str(),fetchedContactBlend,pelvis.coords[0],pelvis.coords[1],pelvis.coords[2],left.coords[0],left.coords[1],left.coords[2],right.coords[0],right.coords[1],right.coords[2],torso.coords[0],torso.coords[1],torso.coords[2],fetchedPhysicalRootDelta.coords[2]);
  };
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
    const bool observeSituation=fetchedSituationState.coords[0]>.001f &&
      GetConfiguration()->GetBool("training_telemetry",false);
    Quaternion nativeUpper[7];
    if(observeSituation)for(unsigned i=1;i<7;++i)nativeUpper[i]=nodeMap.at(pes3::nativeBoneNames[i])->GetRotation();
    PutTrainingContactPose();
    humanoidNode->SetPosition(humanoidNode->GetPosition()+fetchedPhysicalRootDelta*((1-fetchedContactBlend)/zMultiplier),false);
    const Quaternion rootDelta=Quaternion(QUATERNION_IDENTITY).GetSlerped(1-fetchedContactBlend,fetchedPhysicalAdditive[0]);
    nodeMap.at("body")->SetRotation((rootDelta*nodeMap.at("body")->GetRotation()).GetNormalized(),false);
    humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
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
      node->SetRotation((delta*node->GetRotation()).GetNormalized(),false);
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
      node->SetRotation((delta*node->GetRotation()).GetNormalized(),false);
    }
    limitRenderedArms();
    humanoidNode->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
    PutTrainingHeadLook();
    if(observeSituation){
      float trunk=0,arms=0;
      for(unsigned i:{1u,3u,4u,5u,6u}){
        const auto current=rotation(nodeMap.at(pes3::nativeBoneNames[i])->GetRotation());
        const float delta=football_physics::length(football_physics::logarithm(football_physics::productRotation(current,football_physics::inverseRotation(rotation(nativeUpper[i])))));
        if(i==1)trunk=delta;else arms=std::max(arms,delta);
      }
      printf("PHYSICAL_SITUATION_RENDER t=%lu actor=%d action=%d source=%s frame=%d weight=%.6f difficulty=%.6f trunk=%.6f arms=%.6f foot_error=%.8f root_error=%.8f\n",fetchedbuf_animApplyBuffer.snapshotTime_ms,player->GetID(),int(std::round(fetchedSituationState.coords[2])),fetchedbuf_animApplyBuffer.anim->GetName().c_str(),fetchedbuf_animApplyBuffer.frameNum,fetchedSituationState.coords[0],fetchedSituationState.coords[1],trunk,arms,situationFootError,situationRootError);
    }
    observeVisible();return;
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
  observeVisible();
}
