#include "match.hpp"
#include "../main.hpp"
#include "managers/usereventmanager.hpp"
#include <cmath>
#include <cstdio>

void Match::ProcessTrainingContact(){
  if(!trainingPartner)return;
  auto &events=UserEventManager::GetInstance();
  auto *human=trainingPlayer->GetHumanoid();auto *partner=trainingPartner->GetHumanoid();
  if(events.ConsumeKeyPress(SDLK_F10)){
    trainingContactExercise=(trainingContactExercise+1)%3;ResetTraining(0,true);
    SpamMessage(trainingContactExercise==0?"Contato: parceiro fora | F10: ativar":trainingContactExercise==1?
      "Contato: parceiro ao lado | LT: proteger/agarrar | H: camisa | N: proteger | M: disputa | F10: pressao":
      "Contato: parceiro pressiona | LT: proteger/agarrar | H: camisa | N: proteger | M: disputa | F10: desligar",7000);
    printf("PHYSICAL_LAB exercise=%d actor=%d partner=%d\n",trainingContactExercise,trainingPlayer->GetID(),trainingPartner->GetID());
  }
  if(events.ConsumeKeyPress(SDLK_F11) && trainingContactExercise){
    trainingPartnerBall=!trainingPartnerBall;
    SetBallRetainer(0);ball->SetMomentum(Vector3(0));
    const Player *owner=trainingPartnerBall?trainingPartner:trainingPlayer;
    const Vector3 offset=trainingPartnerBall?(owner->GetPosition()-trainingPlayer->GetPosition()).Get2D().GetNormalized(owner->GetBodyDirectionVec())*.7f:owner->GetBodyDirectionVec()*.4f;
    ball->SetPosition(owner->GetPosition()+offset+Vector3(0,0,.11f));
    SpamMessage(trainingPartnerBall?"Bola no parceiro: LT tenta agarrar":"Bola no jogador: LT protege",4000);
    printf("PHYSICAL_LAB_POSSESSION t=%lu partner=%d\n",actualTime_ms,trainingPartnerBall?1:0);
  }
  trainingPartnerVelocity=Vector3(0);human->SetPhysicalShield(false);human->SetPhysicalHandTarget(Vector3(0),false);partner->SetPhysicalGrip(Vector3(0),Vector3(0));
  if(!human->PhysicalRigEnabled()){trainingGrip=false;return;}
  if(!trainingContactExercise){trainingGrip=false;return;}
  const Vector3 separation=trainingPartner->GetPosition()-trainingPlayer->GetPosition();
  const float distance=separation.Get2D().GetLength();
  const Vector3 normal=separation.Get2D().GetNormalized(Vector3(0,1,0));
  const Vector3 ballPosition=ball->Predict(0);
  const float myBallDistance=(ballPosition-trainingPlayer->GetPosition()).Get2D().GetLength();
  const float theirBallDistance=(ballPosition-trainingPartner->GetPosition()).Get2D().GetLength();
  const bool withBall=!trainingPartnerBall && TrainingHasBall() && myBallDistance<1.5f && myBallDistance<theirBallDistance+.12f;
  bool trigger=false,gripKey=events.GetKeyboardState(SDLK_h),shield=events.GetKeyboardState(SDLK_n);
  if(trainingController>0){
    const int slot=static_cast<HIDGamepad*>(controllers[trainingController])->GetGamepadID();
    trigger=events.GetControllerAxis(slot,SDL_CONTROLLER_AXIS_TRIGGERLEFT)>.35f;
  }
  gripKey=gripKey || (trigger && !withBall);
  shield=shield || (trigger && withBall);
  if(!gripKey)trainingGripBlocked=false;
  human->SetPhysicalShield(shield || gripKey);
  const float partnerYaw=std::atan2(trainingPartner->GetBodyDirectionVec().coords[0],-trainingPartner->GetBodyDirectionVec().coords[1]);
  const Vector3 shirtPoint=trainingGrip?trainingPartner->GetPosition()+trainingGripAnchor.GetRotated2D(partnerYaw):partner->GetPhysicalShirtPoint();
  const float handDistance=human->PhysicalHandDistance(shirtPoint);
  if((gripKey || shield) && distance<.9f)human->SetPhysicalHandTarget(shirtPoint,true);
  const bool busy=human->PhysicalRigBusy() || partner->PhysicalRigBusy();
  if(!busy && trainingContactExercise==2 && distance>.50f){
    trainingPartnerVelocity=-normal*std::min(2.2f,(distance-.48f)*4.f);
    partner->OffsetPosition(trainingPartnerVelocity*.01f);
  }
  if(trainingGrip && !busy){
    const float age=(actualTime_ms-trainingGripStarted)*.001f;
    const Vector3 escapeDirection=normal.GetRotated2D(.35f*std::sin(age*2.f));
    // The partner steps and turns out of the hold instead of remaining an
    // inert target. The attachment still needs a real reachable hand.
    trainingPartnerVelocity=escapeDirection*(.35f+.55f*std::min(1.f,age));
    trainingPartnerVelocity+=partner->PhysicalBalanceVelocity();
    partner->OffsetPosition(trainingPartnerVelocity*.01f);
  }else if(!busy){
    const Vector3 step=partner->PhysicalBalanceVelocity();
    trainingPartnerVelocity+=step;partner->OffsetPosition(step*.01f);
  }
  // Horizontal capsule contact feeds equal and opposite impulses into the
  // two articulated actors. Root correction is bounded and cannot add a kick
  // to the ball; native weighted-skin contacts still own ball interactions.
  if(!busy && distance<.52f){
    const float penetration=.52f-distance;
    const Vector3 correction=normal*std::min(.025f,penetration*.5f);
    human->OffsetPosition(-correction);partner->OffsetPosition(correction);
    if(actualTime_ms>=trainingContactUntil){
      const float closing=std::max(.4f,(trainingPlayer->GetMovement()-trainingPartnerVelocity).GetDotProduct(normal));
      const Vector3 impulse=normal*clamp(closing*41.25f,20.f,190.f);
      human->AddPhysicalImpulse(-impulse,Vector3(0,0,.18f));partner->AddPhysicalImpulse(impulse,Vector3(0,0,.18f));
      trainingContactUntil=actualTime_ms+280;
      printf("PHYSICAL_PAIR_CONTACT t=%lu distance=%.5f impulse=%.4f\n",actualTime_ms,distance,impulse.GetLength());
    }
  }
  if(events.ConsumeKeyPress(SDLK_m) && !busy && distance<.56f && actualTime_ms>=trainingTackleUntil){
    const float speed=trainingPlayer->GetMovement().GetLength();
    const Vector3 impulse=normal*(speed>4?175.f:95.f);
    partner->AddPhysicalImpulse(impulse,Vector3(0,0,.18f));human->AddPhysicalImpulse(-impulse*.45f,Vector3(0,0,.18f));
    trainingTackleUntil=actualTime_ms+850;
    // This button is a deliberate body-contact test; it does not teleport or
    // award the ball. Existing tackles remain available in the full match.
    printf("PHYSICAL_CONTEST t=%lu distance=%.4f impulse=%.4f\n",actualTime_ms,distance,impulse.GetLength());
  }
  if(gripKey && !trainingGrip && !trainingGripBlocked && !busy && distance<.9f && handDistance<.10f){
    trainingGrip=true;trainingGripOffset=separation;trainingGripStarted=actualTime_ms;trainingGripEscape=0;
    trainingGripAnchor=(shirtPoint-trainingPartner->GetPosition()).GetRotated2D(-partnerYaw);
    printf("PHYSICAL_GRIP t=%lu state=begin distance=%.4f hand_gap=%.5f\n",actualTime_ms,distance,handDistance);
  }
  if(trainingGrip && (!gripKey || busy || distance>1.08f || handDistance>.23f || trainingGripEscape>=1.f)){
    trainingGrip=false;trainingGripBlocked=gripKey;
    printf("PHYSICAL_GRIP t=%lu state=release distance=%.4f reason=%s\n",actualTime_ms,distance,trigger && withBall?"possession":!gripKey?"button":busy?"fall":trainingGripEscape>=1?"escaped":"reach");
  }
  if(trainingGrip){
    const Vector3 relative=trainingPartnerVelocity-trainingPlayer->GetMovement();
    Vector3 force=(separation-trainingGripOffset)*900.f+relative*65.f;
    if(force.GetLength()>260)force=force.GetNormalized(0)*260;
    const float age=(actualTime_ms-trainingGripStarted)*.001f;
    if(age>.6f)trainingGripEscape+=.01f*(.25f+.35f*std::min(1.f,force.GetLength()/200.f));
    partner->SetPhysicalGrip(shirtPoint,-force);
    // A force integrated for 10 ms, with an equal reaction; never an impulse
    // repeated at its full force magnitude every simulation step.
    human->AddPhysicalImpulse(force*.01f,Vector3(0,0,.24f));partner->AddPhysicalImpulse(-force*.01f,Vector3(0,0,.24f));
    human->OffsetPosition(force*(.01f/(84.f*6.f)));partner->OffsetPosition(-force*(.01f/(84.f*6.f)));
    if(actualTime_ms%100==0)printf("PHYSICAL_GRIP_FORCE t=%lu force=%.5f reaction=%.5f distance=%.5f escape=%.5f\n",actualTime_ms,force.GetLength(),force.GetLength(),distance,trainingGripEscape);
  }
  if(actualTime_ms%100==0 && GetConfiguration()->GetBool("training_telemetry",false))
    printf("PHYSICAL_PARTNER t=%lu exercise=%d distance=%.5f speed=%.4f grip=%d shield=%d hand_gap=%.5f reaching=%d with_ball=%d trigger=%d\n",actualTime_ms,trainingContactExercise,distance,trainingPartnerVelocity.GetLength(),trainingGrip?1:0,shield?1:0,handDistance,gripKey?1:0,withBall?1:0,trigger?1:0);
}
