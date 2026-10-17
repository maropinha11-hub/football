#include "humanoidbase.hpp"
#include "../../../main.hpp"
#include "../../match.hpp"
#include "../player.hpp"
#include "../controller/humancontroller.hpp"
#include "hid/gamepad.hpp"
#include "managers/usereventmanager.hpp"

namespace {
float easeFoot(float x){x=clamp(x,0.f,1.f);return x*x*(3-2*x);}
Vector3 limitedFoot(Vector3 v,float limit){return v.GetLength()>limit?v.GetNormalized(0)*limit:v;}
}

void HumanoidBase::ResetFootwork(){
  footworkPhase=-1;footworkWaitRelease=false;footworkContacts=0;footworkVelocity=Vector3(0);
}

bool HumanoidBase::ProcessFootwork(){
  if(!PhysicalRigEnabled() || !player->GetExternalController())return false;
  auto *controller=static_cast<HumanController*>(player->GetExternalController());
  auto *hid=controller->GetHIDevice();auto &events=UserEventManager::GetInstance();
  bool trigger=false;
  if(hid->GetDeviceType()==e_HIDeviceType_Gamepad)
    trigger=events.GetControllerAxis(static_cast<HIDGamepad*>(hid)->GetGamepadID(),SDL_CONTROLLER_AXIS_TRIGGERRIGHT)>.35f;
  if(!trigger)footworkWaitRelease=false;
  const Vector3 sphere=match->GetBall()->Predict(0);
  const float range=(sphere-spatialState.position).Get2D().GetLength();
  const bool safe=!UpperReceptionActive() && !PhysicalStaggering() && controller->GetActionMode()==0 &&
    !hid->GetButton(e_ButtonFunction_Sprint) && sphere.coords[2]<.18f &&
    match->GetBall()->GetMovement().GetLength()<1.8f && range>.25f && range<.84f;
  const bool locomotion=currentAnim->functionType==e_FunctionType_Movement || currentAnim->functionType==e_FunctionType_BallControl;
  if(footworkPhase<0 && footworkWaitRelease && trigger && safe && locomotion){
    currentMentalImage=match->GetMentalImage(0);Animation *idle=anims->GetAnim(GetIdleMovementAnimID());
    spatialState.movement=Vector3(0);spatialState.floatVelocity=0;
    SampleContactAnimation(idle,0,spatialState.position,spatialState.angle,false,contactLocal,contactGlobal,contactPositions);
    UpdatePhysicalRigPose();contactPoseBlend=1;
    animApplyBuffer.anim=idle;animApplyBuffer.frameNum=0;animApplyBuffer.position=spatialState.position;
    animApplyBuffer.orientation=spatialState.angle;animApplyBuffer.smooth=true;animApplyBuffer.noPos=false;
    return true;
  }
  if(footworkPhase<0 && (!trigger || footworkWaitRelease || !safe || spatialState.floatVelocity>1.1f))return false;
  if(footworkPhase<0){
    currentMentalImage=match->GetMentalImage(0);
    footworkFacing=spatialState.angle;footworkBall=sphere;
    Animation *idle=anims->GetAnim(GetIdleMovementAnimID());
    SampleContactAnimation(idle,0,spatialState.position,footworkFacing,false,contactLocal,contactGlobal,contactPositions);
    footworkHome=contactPositions[12];footworkGoal=footworkHome;footworkVelocity=Vector3(0);
    Vector3 sole;ContactSurface(footworkHome+Vector3(0,0,-.35f),"right_foot",contactGlobal,contactPositions,&sole);
    footworkSole=sole-footworkHome;
    const Vector3 stick=hid->GetDirection();footworkKind=stick.GetLength()>.25f?1:0;
    footworkDirection=match->GetTrainingMovement(stick).Get2D().GetNormalized(spatialState.bodyDirectionVec);
    footworkPhase=0;footworkContacts=0;currentAnim->touchMade=true;
    printf("PHYSICAL_FOOTWORK_BEGIN t=%lu kind=%u range=%.5f\n",match->GetActualTime_ms(),footworkKind,range);
  }
  currentMentalImage=match->GetMentalImage(0);
  if(!trigger || !safe)footworkPhase=std::max(.80f,footworkPhase);
  footworkPhase+=.01f/(footworkKind?2.0f:1.8f);
  // Finish reaching the sole before scheduling its traction phase. A fixed
  // playback clock could otherwise drag the target away before contact.
  if(footworkKind && !footworkContacts && trigger && safe && footworkPhase>=.44f && footworkPhase<.80f)footworkPhase=.44f;
  const float returnPhase=footworkKind?.92f:.85f;
  if(footworkKind && footworkPhase>=.82f && footworkPhase<.92f &&
      footworkGoal.coords[2]<footworkBall.coords[2]+.24f-footworkSole.coords[2])footworkPhase=.82f;
  if(footworkPhase>=returnPhase && footworkPhase<1 &&
      (footworkGoal-footworkHome).Get2D().GetLength()>.08f)footworkPhase=returnPhase;
  const float phase=clamp(footworkPhase,0.f,1.f);
  const Vector3 previousFoot=contactPositions[12];
  Animation *idle=anims->GetAnim(GetIdleMovementAnimID());
  SampleContactAnimation(idle,0,spatialState.position,footworkFacing,false,contactLocal,contactGlobal,contactPositions);
  const Vector3 side=spatialState.bodyDirectionVec.GetRotated2D(-.5f*pi);
  Vector3 top=footworkBall+Vector3(0,0,.112f)-footworkSole;
  Vector3 wanted;
  if(!footworkKind){
    const Vector3 outside=top+side*.23f+Vector3(0,0,.10f);
    const Vector3 inside=top-side*.23f+Vector3(0,0,.10f);
    if(phase<.35f)wanted=footworkHome*(1-easeFoot(phase/.35f))+outside*easeFoot(phase/.35f);
    else if(phase<.70f)wanted=outside*(1-easeFoot((phase-.35f)/.35f))+inside*easeFoot((phase-.35f)/.35f);
    else if(phase<.85f)wanted=inside*(1-easeFoot((phase-.70f)/.15f))+(footworkHome+Vector3(0,0,.30f))*easeFoot((phase-.70f)/.15f);
    else wanted=footworkHome+Vector3(0,0,.30f*(1-easeFoot((phase-.85f)/.15f)));
  }else{
    const Vector3 lifted=top+Vector3(0,0,.12f);
    const Vector3 drag=footworkDirection*(.22f*easeFoot((phase-.48f)/.24f));
    if(phase<.28f)wanted=footworkHome*(1-easeFoot(phase/.28f))+lifted*easeFoot(phase/.28f);
    else if(phase<.44f)wanted=lifted*(1-easeFoot((phase-.28f)/.16f))+top*easeFoot((phase-.28f)/.16f);
    else if(phase<.75f)wanted=top+drag;
    else if(phase<.82f)wanted=top+footworkDirection*.22f+Vector3(0,0,.15f*easeFoot((phase-.75f)/.07f));
    else if(phase<.92f){const float release=easeFoot((phase-.82f)/.10f);wanted=(top+footworkDirection*.22f+Vector3(0,0,.15f))*(1-release)+(footworkHome+Vector3(0,0,.30f))*release;}
    else wanted=footworkHome+Vector3(0,0,.30f*(1-easeFoot((phase-.92f)/.08f)));
  }
  const Vector3 desired=limitedFoot((wanted-footworkGoal)*8.f,.95f);
  footworkVelocity+=limitedFoot(desired-footworkVelocity,.04f);
  footworkGoal+=footworkVelocity*.01f;
  const float envelope=easeFoot((footworkGoal.coords[2]-footworkHome.coords[2])/.32f);Quaternion lean,open;
  lean.SetAngleAxis(.13f*envelope,Vector3(1,0,0));
  const Quaternion head=contactGlobal[2];contactLocal[1]=(lean*contactLocal[1]).GetNormalized();
  open.SetAngleAxis(.13f*envelope,Vector3(0,1,0));contactLocal[5]=(open*contactLocal[5]).GetNormalized();
  open.SetAngleAxis(-.10f*envelope,Vector3(0,1,0));contactLocal[3]=(open*contactLocal[3]).GetNormalized();
  ContactForwardKinematics(contactLocal,contactGlobal,contactPositions);
  contactLocal[2]=(contactGlobal[1].GetInverse()*head).GetNormalized();
  ContactForwardKinematics(contactLocal,contactGlobal,contactPositions);
  FitContactLeg(1,footworkGoal-contactPositions[12],contactLocal,contactGlobal,contactPositions);
  spatialState.movement=Vector3(0);spatialState.floatVelocity=0;
  UpdatePhysicalRigPose();
  // A planted sole can transfer traction, but a stepover never supplies a
  // ball impulse. The same weighted skin and 2.5 mm gate as native kicks is
  // authoritative; no ball repositioning or enlarged contact proxy is used.
  Vector3 skin;float gap=ContactSurface(sphere,"right_foot",contactGlobal,contactPositions,&skin);
  // Solve a unilateral shoe/sphere constraint on the pose, never on the ball.
  // This also protects withdrawal, when a heel could otherwise cut back
  // through the ball despite the earlier sole impulse being legitimate.
  for(unsigned iteration=0;iteration<6 && gap<.0008f && !PhysicalRigBusy();++iteration){
    const Vector3 away=(skin-sphere).GetNormalized(Vector3(0,0,1));
    FitContactLeg(1,away*(.001f-gap),contactLocal,contactGlobal,contactPositions);
    gap=ContactSurface(sphere,"right_foot",contactGlobal,contactPositions,&skin);
  }
  if(footworkKind && !footworkContacts && phase==.44f){
    if((footworkGoal-contactPositions[12]).GetLength()>.05f)footworkPhase=.80f;
    else if((footworkGoal-top).GetLength()<.06f)
      footworkBall+=limitedFoot(sphere+Vector3(0,0,.111f)-skin,.003f);
  }
  const bool contact=footworkKind && phase>=.40f && phase<=.76f && trigger && safe && !PhysicalRigBusy() &&
    gap<=.0025f && gap>=-.001f && skin.coords[2]>sphere.coords[2]+.055f;
  if(contact){
    Vector3 velocity=(contactPositions[12]-previousFoot)*70.f;velocity.coords[2]=std::min(0.f,match->GetBall()->GetMovement().coords[2]);
    velocity=limitedFoot(velocity,.85f);match->GetBall()->Touch(velocity);
    auto *actor=static_cast<Player*>(player);actor->GetTeam()->SetLastTouchPlayer(actor,e_TouchType_Intentional_Kicked);actor->UpdatePossessionStats(false);
    match->NotifyTrainingTouch(e_FunctionType_BallControl,false);++footworkContacts;
    printf("PHYSICAL_FOOTWORK_CONTACT t=%lu gap=%.7f speed=%.5f\n",match->GetActualTime_ms(),gap,velocity.GetLength());
  }
  // Manual footwork still participates in incoming upper-body collisions;
  // update the sweep history even while its ball remains on the ground.
  ProcessTrainingBodyContact();
  contactPoseBlend=1;
  animApplyBuffer.anim=idle;animApplyBuffer.frameNum=0;animApplyBuffer.position=spatialState.position;
  animApplyBuffer.orientation=footworkFacing;animApplyBuffer.smooth=true;animApplyBuffer.noPos=false;
  if(GetConfiguration()->GetBool("training_telemetry",false) && match->GetActualTime_ms()%20==0)
    printf("PHYSICAL_FOOTWORK t=%lu kind=%u phase=%.5f gap=%.6f speed=%.5f contacts=%u ankle=[%.5f,%.5f,%.5f] support=[%.5f,%.5f,%.5f]\n",match->GetActualTime_ms(),footworkKind,phase,gap,footworkVelocity.GetLength(),footworkContacts,contactPositions[12].coords[0],contactPositions[12].coords[1],contactPositions[12].coords[2],contactPositions[9].coords[0],contactPositions[9].coords[1],contactPositions[9].coords[2]);
  if(footworkPhase>=1 && (footworkGoal-footworkHome).GetLength()<.012f && footworkVelocity.GetLength()<.1f){
    const unsigned contacts=footworkContacts;const Vector3 position=spatialState.position,focus=position+spatialState.bodyDirectionVec;
    ResetPosition(position,focus);footworkWaitRelease=trigger;
    printf("PHYSICAL_FOOTWORK_END t=%lu contacts=%u\n",match->GetActualTime_ms(),contacts);
  }
  return true;
}
