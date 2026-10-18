#include "match.hpp"
#include "physical_match_rules.hpp"
#include <set>
#include "../main.hpp"
#include "managers/usereventmanager.hpp"
#include <cmath>
#include <cstdio>

void Match::ProcessPlayerMatchContact(){
  if(!PlayerMatchEnabled() || !trainingPlayer)return;
  auto *human=trainingPlayer->GetHumanoid();
  std::vector<Player*> actors;teams[0]->GetActivePlayers(actors);teams[1]->GetActivePlayers(actors);
  for(auto *actor:actors){auto *body=actor->GetHumanoid();body->SetPhysicalTraction(Vector3(0));body->SetPhysicalGrip(Vector3(0),Vector3(0));body->SetPhysicalShield(false);body->SetPhysicalHandTarget(Vector3(0),false);}
  if(!human->PhysicalRigEnabled()){trainingGrip=false;physicalGripOpponent=nullptr;return;}
  if(!IsInPlay() || IsInSetPiece()){trainingGrip=false;physicalGripOpponent=nullptr;physicalAIHolds.clear();return;}

  auto &events=UserEventManager::GetInstance();
  Player *opponent=nullptr;float nearest=1000;
  for(auto *actor:actors)if(actor->GetTeamID()!=trainingPlayer->GetTeamID() && actor->GetFormationEntry().role!=e_PlayerRole_GK){
    const float distance=(actor->GetPosition()-trainingPlayer->GetPosition()).Get2D().GetLength();
    if(distance<nearest){nearest=distance;opponent=actor;}
  }
  if(!opponent)return;
  // Explicit optional laboratory setup, never part of ordinary match AI.
  if(GetConfiguration()->GetBool("training_physical_lab",false) && events.ConsumeKeyPress(SDLK_F2)){
    const Vector3 root=trainingPlayer->GetPosition(),forward=trainingPlayer->GetBodyDirectionVec();
    const bool tackle=events.GetKeyboardState(SDLK_LCTRL);
    opponent->ResetPosition(tackle?root+forward*.60f:root+forward*.15f+forward.GetRotated2D(pi*.5f)*.68f,root+forward*3.f);
    SpamMessage("Ensaio de contato: adversario aproximado | M: disputa | LT: proteger/agarrar",4000);
    printf("PHYSICAL_MATCH_SETUP t=%lu actor=%d opponent=%d\n",actualTime_ms,trainingPlayer->GetID(),opponent->GetID());
  }
  if(trainingGrip && physicalGripOpponent)opponent=physicalGripOpponent;
  auto *other=opponent->GetHumanoid();
  const Vector3 separation=opponent->GetPosition()-trainingPlayer->GetPosition();
  const float distance=separation.Get2D().GetLength();
  const Vector3 normal=separation.Get2D().GetNormalized(trainingPlayer->GetBodyDirectionVec());
  if(GetConfiguration()->GetBool("training_physical_lab",false) && events.ConsumeKeyPress(SDLK_F11)){
    SetBallRetainer(0);ball->SetMomentum(Vector3(0));
    Player *receiver=events.GetKeyboardState(SDLK_LSHIFT)?trainingPlayer:opponent;
    ball->SetPosition(receiver->GetPosition()+receiver->GetBodyDirectionVec()*.55f+Vector3(0,0,.11f));
    receiver->GetTeam()->SetLastTouchPlayer(receiver,e_TouchType_Intentional_Nonkicked);
    receiver->UpdatePossessionStats(false);UpdateLatestMentalImageBallPredictions();
    SpamMessage("Ensaio: bola no adversario | LT: tentar segurar",3000);
  }
  const bool withBall=trainingPlayer->HasPossession() && (ball->Predict(0)-trainingPlayer->GetPosition()).Get2D().GetLength()<1.5f;
  bool trigger=false;
  if(trainingController>0){const int slot=static_cast<HIDGamepad*>(controllers[trainingController])->GetGamepadID();trigger=events.GetControllerAxis(slot,SDL_CONTROLLER_AXIS_TRIGGERLEFT)>.35f;}
  const bool gripKey=events.GetKeyboardState(SDLK_h) || (trigger && !withBall);
  const bool shield=events.GetKeyboardState(SDLK_n) || (trigger && withBall);
  if(!gripKey)trainingGripBlocked=false;
  human->SetPhysicalShield(shield || gripKey);
  // Possession-side AI keeps its native decisions but can brace in a contest.
  if(distance<.9f && opponent->HasPossession())other->SetPhysicalShield(true);
  const float yaw=std::atan2(opponent->GetBodyDirectionVec().coords[0],-opponent->GetBodyDirectionVec().coords[1]);
  const Vector3 shirt=trainingGrip?opponent->GetPosition()+trainingGripAnchor.GetRotated2D(yaw):other->GetPhysicalShirtPoint(trainingPlayer->GetPosition());
  const float gap=human->PhysicalHandDistance(shirt);
  if((shield || gripKey) && distance<.9f)human->SetPhysicalHandTarget(shirt,true);
  const bool busy=human->PhysicalRigBusy() || other->PhysicalRigBusy();
  if(events.ConsumeKeyPress(SDLK_m) && !busy && distance<.85f && actualTime_ms>=trainingTackleUntil){
    const float strength=trainingPlayer->GetMovement().GetLength()>4?175.f:95.f;
    other->AddPhysicalImpulse(normal*strength,Vector3(0,0,.18f));human->AddPhysicalImpulse(-normal*strength*.45f,Vector3(0,0,.18f));
    trainingTackleUntil=actualTime_ms+850;
    printf("PHYSICAL_MATCH_CONTEST t=%lu actor=%d opponent=%d impulse=%.3f distance=%.4f\n",actualTime_ms,trainingPlayer->GetID(),opponent->GetID(),strength,distance);
  }
  if(gripKey && !trainingGrip && !trainingGripBlocked && !busy && distance<.9f && gap<.10f){
    trainingGrip=true;physicalGripOpponent=opponent;trainingGripOffset=separation;trainingGripStarted=actualTime_ms;trainingGripEscape=0;
    trainingGripAnchor=(shirt-opponent->GetPosition()).GetRotated2D(-yaw);
    printf("PHYSICAL_MATCH_GRIP t=%lu state=begin actor=%d opponent=%d hand_gap=%.5f\n",actualTime_ms,trainingPlayer->GetID(),opponent->GetID(),gap);
  }
  if(trainingGrip && football_rules::excessiveHold((actualTime_ms-trainingGripStarted)*.001f,
      std::min(260.f,((separation-trainingGripOffset)*900.f+(opponent->GetMovement()-trainingPlayer->GetMovement())*65.f).GetLength()),other->PhysicalRigBusy())){
    referee->PhysicalFoul(opponent,trainingPlayer,other->PhysicalRigBusy()?1.7f:1.1f);
    trainingGrip=false;trainingGripBlocked=true;physicalGripOpponent=nullptr;return;
  }
  if(trainingGrip && (!gripKey || busy || distance>1.08f || gap>.23f || trainingGripEscape>=1.f)){
    trainingGrip=false;trainingGripBlocked=gripKey;physicalGripOpponent=nullptr;
    printf("PHYSICAL_MATCH_GRIP t=%lu state=release reason=%s\n",actualTime_ms,!gripKey?"button":busy?"fall":trainingGripEscape>=1?"escaped":"reach");
  }
  if(trainingGrip){
    const Vector3 relative=opponent->GetMovement()-trainingPlayer->GetMovement();
    Vector3 force=(separation-trainingGripOffset)*900.f+relative*65.f;
    if(force.GetLength()>260)force=force.GetNormalized(0)*260;
    const float age=(actualTime_ms-trainingGripStarted)*.001f;
    if(age>.6f)trainingGripEscape+=.01f*(.25f+.35f*std::min(1.f,force.GetLength()/200.f));
    other->SetPhysicalGrip(shirt,-force);human->SetPhysicalTraction(force);other->SetPhysicalTraction(-force);
    human->AddPhysicalImpulse(force*.01f,Vector3(0,0,.24f));other->AddPhysicalImpulse(-force*.01f,Vector3(0,0,.24f));
    if(actualTime_ms%100==0)printf("PHYSICAL_MATCH_GRIP_FORCE t=%lu force=%.5f reaction=%.5f distance=%.5f escape=%.5f\n",actualTime_ms,force.GetLength(),force.GetLength(),distance,trainingGripEscape);
  }
  // The CPU uses the same reach-limited hands, shirt force, reciprocal
  // traction, protection and referee as the controlled player.
  std::set<int> occupied;
  if(trainingGrip){occupied.insert(trainingPlayer->GetID());occupied.insert(opponent->GetID());}
  for(auto *actor:actors){
    if(actor==trainingPlayer || actor->GetFormationEntry().role==e_PlayerRole_GK || occupied.count(actor->GetID()))continue;
    auto *body=actor->GetHumanoid();if(body->PhysicalRigBusy())continue;
    auto &hold=physicalAIHolds[actor->GetID()];Player *victim=hold.victim;
    if(!victim){
      float closest=.95f;
      for(auto *candidate:actors)if(candidate->GetTeamID()!=actor->GetTeamID() && !occupied.count(candidate->GetID())){
        const float gap=(candidate->GetPosition()-actor->GetPosition()).Get2D().GetLength();
        if(gap<closest){closest=gap;victim=candidate;}
      }
    }
    if(!victim)continue;
    auto *target=victim->GetHumanoid();const Vector3 delta=victim->GetPosition()-actor->GetPosition();
    const float d=delta.Get2D().GetLength();
    const bool possession=actor->HasPossession() && (ball->Predict(0)-actor->GetPosition()).Get2D().GetLength()<1.4f;
    const bool carrier=victim->HasPossession() && (ball->Predict(0)-victim->GetPosition()).Get2D().GetLength()<1.4f;
    if(possession && d<.95f)body->SetPhysicalShield(true);
    const bool laboratory=GetConfiguration()->GetBool("training_physical_lab",false)&&events.GetKeyboardState(SDLK_b)&&victim==trainingPlayer;
    const bool reaching=carrier && ((actualTime_ms/1000+actor->GetID()*7)%17==0 || laboratory);
    if(reaching || hold.victim)body->SetPhysicalShield(true);
    const Vector3 shirt=target->GetPhysicalShirtPoint(actor->GetPosition());
    if((possession || reaching || hold.victim) && d<.95f)body->SetPhysicalHandTarget(shirt,true);
    const float hand=body->PhysicalHandDistance(shirt);
    if(laboratory && actualTime_ms%100==0)
      printf("PHYSICAL_AI_REACH t=%lu actor=%d victim=%d distance=%.5f carrier=%d hand_gap=%.5f function=%d\n",actualTime_ms,actor->GetID(),victim->GetID(),d,carrier,hand,int(actor->GetCurrentFunctionType()));
    if(!hold.victim && reaching && actualTime_ms>=hold.cooldown && d<.85f && hand<.10f && !target->PhysicalRigBusy()){
      hold.victim=victim;hold.offset=delta;hold.started=actualTime_ms;
      printf("PHYSICAL_AI_GRIP t=%lu actor=%d victim=%d state=begin gap=%.5f\n",actualTime_ms,actor->GetID(),victim->GetID(),hand);
    }
    if(!hold.victim)continue;
    const float age=(actualTime_ms-hold.started)*.001f;
    Vector3 force=(delta-hold.offset)*900.f+(victim->GetMovement()-actor->GetMovement())*65.f;
    if(force.GetLength()>180)force=force.GetNormalized(0)*180;
    if(football_rules::excessiveHold(age,force.GetLength(),target->PhysicalRigBusy())){
      referee->PhysicalFoul(victim,actor,target->PhysicalRigBusy()?1.7f:1.1f);
      hold.victim=nullptr;hold.cooldown=actualTime_ms+7000;return;
    }
    if(d>1.08f || hand>.23f || target->PhysicalRigBusy() || age>1.4f || (!reaching && age>.7f)){
      printf("PHYSICAL_AI_GRIP t=%lu actor=%d victim=%d state=release age=%.4f\n",actualTime_ms,actor->GetID(),victim->GetID(),age);
      hold.victim=nullptr;hold.cooldown=actualTime_ms+5000;continue;
    }
    body->SetPhysicalTraction(force);target->SetPhysicalGrip(shirt,-force);target->SetPhysicalTraction(-force);
    body->AddPhysicalImpulse(force*.01f,Vector3(0,0,.24f));target->AddPhysicalImpulse(-force*.01f,Vector3(0,0,.24f));
    occupied.insert(actor->GetID());occupied.insert(victim->GetID());
    if(actualTime_ms%100==0 || (laboratory && actualTime_ms%20==0))printf("PHYSICAL_AI_GRIP_FORCE t=%lu actor=%d victim=%d force=%.4f age=%.4f gap=%.5f\n",actualTime_ms,actor->GetID(),victim->GetID(),force.GetLength(),age,hand);
  }
  if(actualTime_ms%100==0 && GetConfiguration()->GetBool("training_telemetry",false))
    printf("PHYSICAL_MATCH_CONTACT t=%lu opponent=%d distance=%.4f shield=%d reaching=%d grip=%d hand_gap=%.5f\n",actualTime_ms,opponent->GetID(),distance,shield?1:0,gripKey?1:0,trainingGrip?1:0,gap);
}

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
  trainingPartnerVelocity=Vector3(0);human->SetPhysicalTraction(Vector3(0));partner->SetPhysicalTraction(Vector3(0));human->SetPhysicalShield(false);human->SetPhysicalHandTarget(Vector3(0),false);partner->SetPhysicalGrip(Vector3(0),Vector3(0));
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
    const Vector3 correction=normal*std::min(.05f,penetration);
    // A planted shield directs more separation into the pressuring actor.
    // The residual comes from the ground, not an extra opposing ball impulse.
    human->OffsetPosition(-correction*(shield?.20f:.50f));partner->OffsetPosition(correction*(shield?.80f:.50f));
    human->SetPhysicalTraction(-normal*(80.f+65.f*trainingPartnerVelocity.GetLength()));
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
    human->SetPhysicalTraction(force);partner->SetPhysicalTraction(-force);
    const Vector3 intended=trainingPartnerVelocity;
    trainingPartnerVelocity=partner->PhysicalContactVelocity(intended);
    partner->OffsetPosition((trainingPartnerVelocity-intended)*.01f);
    // A force integrated for 10 ms, with an equal reaction; never an impulse
    // repeated at its full force magnitude every simulation step.
    human->AddPhysicalImpulse(force*.01f,Vector3(0,0,.24f));partner->AddPhysicalImpulse(-force*.01f,Vector3(0,0,.24f));
    if(actualTime_ms%100==0)printf("PHYSICAL_GRIP_FORCE t=%lu force=%.5f reaction=%.5f distance=%.5f escape=%.5f intended_speed=%.5f actual_speed=%.5f\n",actualTime_ms,force.GetLength(),force.GetLength(),distance,trainingGripEscape,intended.GetLength(),trainingPartnerVelocity.GetLength());
  }
  if(actualTime_ms%100==0 && GetConfiguration()->GetBool("training_telemetry",false))
    printf("PHYSICAL_PARTNER t=%lu exercise=%d distance=%.5f speed=%.4f grip=%d shield=%d hand_gap=%.5f reaching=%d with_ball=%d trigger=%d\n",actualTime_ms,trainingContactExercise,distance,trainingPartnerVelocity.GetLength(),trainingGrip?1:0,shield?1:0,handDistance,gripKey?1:0,withBall?1:0,trigger?1:0);
}
