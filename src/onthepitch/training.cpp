// Football Training: solo practice using the original Gameplay Football simulation.
#include "match.hpp"
#include "ball_turf.hpp"
#include "../main.hpp"
#include "managers/usereventmanager.hpp"
#include <cmath>
#include <cstdio>

namespace {
void turfInput(Match *match){
  if(!UserEventManager::GetInstance().ConsumeKeyPress(SDLK_g))return;
  const bool enabled=!GetConfiguration()->GetBool("training_turf_enabled",true);
  GetConfiguration()->SetBool("training_turf_enabled",enabled);
  match->GetBall()->CalculatePrediction();match->UpdateLatestMentalImageBallPredictions();
  match->SpamMessage(enabled?"Gramado irregular ligado":"Gramado liso para comparar",3000);
  printf("TURF_TOGGLE t=%lu enabled=%d\n",match->GetActualTime_ms(),enabled?1:0);
}

void physicalLabInput(Match *match,Player *actor,unsigned long time) {
  auto &events=UserEventManager::GetInstance();auto *body=actor->GetHumanoid();
  static unsigned direction=0;
  if(events.ConsumeKeyPress(SDLK_F3)){
    direction=(direction+1)%4;
    const char *names[]={"direita","frente","esquerda","tras"};
    match->SpamMessage(std::string("Direcao do impacto: ")+names[direction],2500);
    printf("PHYSICAL_IMPACT_DIRECTION t=%lu direction=%u\n",time,direction);
  }
  if(events.ConsumeKeyPress(SDLK_F7))body->TogglePhysicalRig();
  if(events.ConsumeKeyPress(SDLK_F1)){
    const bool enabled=!GetConfiguration()->GetBool("training_situational_motion",true);
    GetConfiguration()->SetBool("training_situational_motion",enabled);
    match->SpamMessage(enabled?"Variacoes corporais: ligadas":"Variacoes corporais: desligadas",3000);
    printf("PHYSICAL_SITUATION_TOGGLE t=%lu enabled=%d\n",time,enabled?1:0);
  }
  const Vector3 side=actor->GetBodyDirectionVec().GetRotated2D((1-int(direction))*.5f*pi);
  if(events.ConsumeKeyPress(SDLK_F8)){
    const bool control=events.GetKeyboardState(SDLK_LCTRL)||events.GetKeyboardState(SDLK_RCTRL);
    const bool shift=events.GetKeyboardState(SDLK_LSHIFT)||events.GetKeyboardState(SDLK_RSHIFT);
    const float impulse=control?350.f:shift?190.f:125.f;
    body->AddPhysicalImpulse(side*impulse,Vector3(0,0,.18f));
    printf("PHYSICAL_IMPACT_TEST t=%lu impulse=%.1f level=%s forced=0 direction=%u\n",time,impulse,control?"overload":shift?"strong":"medium",direction);
  }
  if(events.ConsumeKeyPress(SDLK_F9))body->AddPhysicalImpulse(side*165.f,Vector3(0,0,.18f),true);
}
}

void Match::ResetTraining(int exercise, bool ballAtPlayer) {
  trainingExercise = clamp(exercise, 0, 5);
  Player *player = trainingPlayer;
  Vector3 position = ballAtPlayer ? player->GetPosition().Get2D() : Vector3(0, 0, 0);
  if (!ballAtPlayer && exercise == 2) position = Vector3(30, 0, 0);
  if (!ballAtPlayer && exercise == 4) position = Vector3(28, -8, 0);
  const Vector3 direction = ballAtPlayer ? player->GetDirectionVec() :
      (exercise == 4 ? (Vector3(pitchHalfW, 0, 0) - position).GetNormalized(0) : Vector3(1, 0, 0));
  const Vector3 ballPosition = position + direction * 0.65f;

  SetBallRetainer(0);
  SetGoalScored(false);
  ballIsInGoal = false;
  lastGoalScorer = 0;
  trainingResetAt_ms = 0;
  trainingKnockOnUntil_ms = 0;
  trainingReceiving=false;trainingReceptionFacing=direction;
  trainingGrip=false;trainingGripBlocked=false;trainingPartnerBall=false;trainingGripEscape=0;trainingContactUntil=trainingTackleUntil=0;
  if(trainingPartner){
    trainingPartnerVelocity=Vector3(0);
    const Vector3 partnerPosition=trainingContactExercise?position+direction*.15f+direction.GetRotated2D(.5f*pi)*.72f:Vector3(150,150,0);
    trainingPartner->ResetPosition(partnerPosition,position+direction*3);
    trainingPartner->GetHumanoid()->SetPhysicalGrip(Vector3(0),Vector3(0));
  }
  lastTouchTeamID = -1;
  for (unsigned int i = 0; i < e_TouchType_SIZE; ++i) lastTouchTeamIDs[i] = -1;
  teams[0]->ResetSituation(ballPosition);
  teams[1]->ResetSituation(ballPosition);
  player->ResetPosition(position, position + direction * 10);
  // Reset the controller as well as the animation: a charged/queued action
  // from the previous attempt must not fire after the ball is repositioned.
  if (player->GetExternalController()) player->GetExternalController()->Reset();
  player->RelaxFatigue(1.0f);
  ball->ResetSituation(ballPosition);
  if (exercise == 3) {
    // Arrive at heading height before the first bounce, within a real
    // standing/jumping header's reach rather than landing metres away.
    ball->SetPosition(position + Vector3(5.5f, 0, 3.5f));
    ball->SetMomentum(Vector3(-5.0f, 0, 3.0f));
  }
  if (exercise == 5) {
    ball->SetPosition(position + Vector3(8, 0, 0.11f));
    ball->SetMomentum(Vector3(-6.0f, 0, 0));
  }
  bestPossessionTeamID = 0;
  inPlay = true;
  inSetPiece = false;
  goalScored = false;
  camPos.clear();
  resetNetting = true;
  trainingView.reset(std::atan2(direction.coords[1], direction.coords[0]));
  trainingEyeInitialized = false;
  const char *names[] = {"Livre", "Conducao", "Finalizacao", "Bola aerea", "Falta", "Passe recebido"};
  SpamMessage(std::string("Treino: ") + names[exercise] + (GetConfiguration()->GetBool("training_physical_lab",false)?" | F7: comparar | F8: impacto | F9: queda | R: reiniciar":" | View/R: reiniciar | F2: trazer bola"), 5000);
  printf("TRAINING_RESET exercise=%d\n", exercise);
  fflush(stdout);
}

void Match::NotifyTrainingTouch(e_FunctionType function, bool knockOn) {
  if (!TrainingEnabled()) return;
  // F11 only seeds the partner's possession exercise. A real accepted touch
  // by the controlled player immediately restores contextual protection.
  trainingPartnerBall=false;
  // Only a real knock-on contact starts recovery. Passing/shooting, an
  // ordinary control touch, and resets release it immediately.
  trainingKnockOnUntil_ms = knockOn &&
      (function == e_FunctionType_BallControl || function == e_FunctionType_Trap) ? actualTime_ms + 1600 : 0;
}

void Match::LaunchTrainingBall(int delivery) {
  Player *player=trainingPlayer;
  auto &events=UserEventManager::GetInstance();
  const bool cpu=PlayerMatchEnabled()&&events.GetKeyboardState(SDLK_h);
  if(cpu){
    std::vector<Player*> mates;GetTeam(trainingPlayer->GetTeamID())->GetActivePlayers(mates);
    float closest=1e9f;
    for(auto *mate:mates)if(mate!=trainingPlayer&&mate->GetFormationEntry().role!=e_PlayerRole_GK){
      const float distance=(mate->GetPosition()-trainingPlayer->GetPosition()).Get2D().GetLength();
      if(distance<closest){closest=distance;player=mate;}
    }
    const Vector3 front=trainingPlayer->GetBodyDirectionVec().Get2D().GetNormalized(Vector3(1,0,0));
    const Vector3 spot=trainingPlayer->GetPosition().Get2D()+front.GetRotated2D(.5f*pi)*3.f;
    player->ResetPosition(spot,spot+front*10.f);
    std::vector<Player*> actors;GetTeam(0)->GetActivePlayers(actors);GetTeam(1)->GetActivePlayers(actors);
    for(auto *actor:actors)if(actor!=player&&actor!=trainingPlayer&&actor->GetFormationEntry().role!=e_PlayerRole_GK&&
       (actor->GetPosition()-spot).Get2D().GetLength()<13.f){
      const Vector3 away=actor->GetPosition().Get2D()+front.GetRotated2D(-.5f*pi)*18.f;
      actor->ResetPosition(away,away+actor->GetBodyDirectionVec());
    }
  }
  const Vector3 root=player->GetPosition().Get2D();
  const Vector3 forward=player->GetBodyDirectionVec().Get2D().GetNormalized(Vector3(1,0,0));
  // Reset only this attempt, retaining the player's current field position and facing.
  if(!PlayerMatchEnabled())ResetTraining(0,true);
  else {
    SetBallRetainer(0);trainingReceiving=false;trainingReceptionFacing=forward;
    lastTouchTeamID=-1;for(unsigned i=0;i<e_TouchType_SIZE;++i)lastTouchTeamIDs[i]=-1;
    player->ResetPosition(root,root+forward*10.f);
    if(player->GetExternalController())player->GetExternalController()->Reset();
    if(!cpu){trainingView.reset(std::atan2(forward.coords[1],forward.coords[0]));trainingEyeInitialized=false;}
  }
  if(cpu&&delivery==0&&events.GetKeyboardState(SDLK_LSHIFT)&&events.GetKeyboardState(SDLK_LCTRL)){
    ball->SetPosition(Vector3(0,trainingPlayer->GetPosition().coords[1]<0?20.f:-20.f,.112f));ball->SetMomentum(Vector3(0));
    UpdateLatestMentalImageBallPredictions();
    SpamMessage("Caminhada sem bola: use o analogico levemente",4000);
    printf("WALK_LAB_SETUP t=%lu human=%d\n",actualTime_ms,trainingPlayer->GetID());return;
  }
  const Vector3 chest=player->GetHumanoid()->GetStandingChestTarget();
  const int heightFixture=delivery==1?(events.GetKeyboardState(SDLK_7)?1:events.GetKeyboardState(SDLK_8)?2:
    events.GetKeyboardState(SDLK_9)?3:events.GetKeyboardState(SDLK_0)?4:0):0;
  const bool driven=delivery==1 && events.GetKeyboardState(SDLK_LSHIFT);
  const bool belly=delivery==1 && events.GetKeyboardState(SDLK_LCTRL);
  const bool impact=driven&&belly;
  const float flight=heightFixture==4?.30f:heightFixture==1||heightFixture==2?.42f:heightFixture?.60f:delivery==0?1.0f:delivery==1?(impact?.13f:driven?.23f:.45f):1.15f;
  const float offset=events.GetKeyboardState(SDLK_LSHIFT)?.65f:events.GetKeyboardState(SDLK_LCTRL)?-.65f:0.f;
  const Vector3 lateral=forward.GetRotated2D(-.5f*pi)*offset;
  Vector3 target=delivery==0 ? root+forward*.55f+lateral+Vector3(0,0,.11f) :
    delivery==1 ? chest+Vector3(0,0,impact?0.f:belly?-.35f:0.f) : root+forward*.18f+Vector3(0,0,1.92f);
  if(heightFixture)target=root+forward*(heightFixture==4?-.18f:.23f)+
    forward.GetRotated2D(.5f*pi)*(heightFixture<3?-.12f:0.f)+Vector3(0,0,heightFixture==1?.43f:heightFixture==2?.74f:1.43f);
  const float roughness=GetConfiguration()->GetBool("training_turf_enabled",true)?GetConfiguration()->GetReal("training_turf_roughness",.65f):0;
  if(delivery==0)target.coords[2]+=football_turf::sample(target.coords[0],target.coords[1],roughness).height;
  const Vector3 origin=heightFixture==4?root-forward*.18f+Vector3(0,0,2.45f):heightFixture?root+forward*4.f+Vector3(0,0,heightFixture==1?.25f:heightFixture==2?.68f:3.2f):
    root+(impact?Vector3(0):lateral)+forward*(delivery==0?8.0f:delivery==1?4.5f:10.0f)+Vector3(0,0,delivery==0?.11f:delivery==1?1.35f:3.6f);
  ball->SetPosition(origin);
  Vector3 velocity=(target-origin)/flight;
  if(delivery)velocity.coords[2]+=4.905f*flight;
  // Account for the game's drag, spin and turf using its own predictor.
  const unsigned time=unsigned(std::round(flight*1000/10))*10;
  for(unsigned i=0;i<8;++i) {
    ball->SetMomentum(velocity);
    const Vector3 error=target-ball->Predict(time);
    if(error.GetLength()<.001f)break;
    velocity+=error/flight;
  }
  ball->SetMomentum(velocity);
  UpdateLatestMentalImageBallPredictions();
  SpamMessage(heightFixture==1?"Recepcao na canela | 7 + F5: repetir":heightFixture==2?"Recepcao na coxa | 8 + F5: repetir":
      heightFixture==3?"Recepcao descendente | 9 + F5: repetir":heightFixture==4?"Bola por tras | 0 + F5: repetir":delivery==0?"Passe rasteiro recebido | F4: repetir":
      delivery==1?"Dominio de peito: parado ou avancando | F5: repetir":"Cruzamento alto | F6: repetir",4500);
  printf("TRAINING_DELIVERY type=%d t=%lu arrival_ms=%u error=%.5f target=[%.4f,%.4f,%.4f] offset=%.3f match=%d actor=%d\n",
    delivery,actualTime_ms,time,(ball->Predict(time)-target).GetLength(),target.coords[0],target.coords[1],target.coords[2],offset,PlayerMatchEnabled()?1:0,player->GetID());
  fflush(stdout);
}

Vector3 Match::GetTrainingAim(const Vector3 &stick) const {
  // Reception restricts locomotion, never the outgoing pass/header target.
  // Aim is relative to the current front, excluding independent head look
  // and the repeated-turn steering target used while dribbling.
  if(!IsFirstPerson())return stick;
  const Vector3 front=GetTrainingFacing();
  const Vector3 right(front.coords[1],-front.coords[0],0);
  return front*stick.coords[1]+right*stick.coords[0];
}

Vector3 Match::GetTrainingMovement(const Vector3 &stick) const {
  if(trainingReceiving || (trainingPlayer && trainingPlayer->GetHumanoid()->UpperReceptionActive() && ball->Predict(0).coords[2]>.45f)) {
    // Only approach/retreat is authored for these chest receptions. In third
    // person project world input onto that same reception axis; in first
    // person the vertical stick already represents approach/retreat.
    const float along=IsFirstPerson()?stick.coords[1]:stick.GetDotProduct(trainingReceptionFacing);
    return trainingReceptionFacing*along;
  }
  return IsFirstPerson() ? trainingView.movement(stick) : stick;
}

void Match::UpdateTrainingView(IHIDevice *input) {
  auto &events = UserEventManager::GetInstance();
  Vector3 look(0);
  if (trainingController > 0) {
    const int slot = static_cast<HIDGamepad*>(input)->GetGamepadID();
    look = training::radialStick(Vector3(events.GetControllerAxis(slot, SDL_CONTROLLER_AXIS_RIGHTX),
                                        events.GetControllerAxis(slot, SDL_CONTROLLER_AXIS_RIGHTY), 0), 0.12f);
  }
  look.coords[0] += (events.GetKeyboardState(SDLK_RIGHT) ? 1.0f : 0.0f) - (events.GetKeyboardState(SDLK_LEFT) ? 1.0f : 0.0f);
  look.coords[1] += (events.GetKeyboardState(SDLK_DOWN) ? 1.0f : 0.0f) - (events.GetKeyboardState(SDLK_UP) ? 1.0f : 0.0f);
  const Vector3 delta = ball->Predict(0) - trainingPlayer->GetPosition();
  // Keep the original interception assistance for an approaching pass, but
  // do not turn every loose ball or the player's own shot into a reception.
  bool receiving=false;
  const Vector3 incoming=ball->GetMovement();
  const bool ownDrop=GetLastTouchPlayer()==trainingPlayer&&delta.coords[2]>.35f&&delta.Get2D().GetLength()<1.15f&&trainingPlayer->GetLastTouchType()!=e_TouchType_Intentional_Kicked;
  if((GetLastTouchPlayer()!=trainingPlayer||ownDrop) && delta.Get2D().GetLength()<14 && incoming.GetLength()>.5f &&
      (delta.Get2D().GetDotProduct(incoming.Get2D())<0 ||
       (delta.Get2D().GetLength()<.75f && delta.coords[2]>0 && incoming.coords[2]<-.2f)) &&
      (ownDrop||trainingPlayer->GetLastTouchBias(350)<.01f)) {
    for(unsigned ms=100;ms<=1400;ms+=50) {
      const Vector3 arrival=ball->Predict(ms)-trainingPlayer->GetPosition();
      if(arrival.Get2D().GetLength()<1.25f && arrival.coords[2]<2.5f) {receiving=true;break;}
    }
  }
  if(receiving && !trainingReceiving)trainingReceptionFacing=trainingPlayer->GetBodyDirectionVec().Get2D().GetNormalized(Vector3(1,0,0));
  if(PlayerMatchEnabled() && GetLastTouchPlayer() && GetLastTouchPlayer()!=trainingPlayer &&
      GetLastTouchPlayer()->HasPossession() && delta.coords[2]<.45f &&
      ball->GetMovement().GetLength()<GetLastTouchPlayer()->GetMovement().GetLength()+2)
    receiving=false;
  trainingReceiving=receiving;
  const float relativeSpeed = (ball->GetMovement() - trainingPlayer->GetMovement()).GetLength();
  // Hysteresis keeps the head/body mode from flickering between individual dribble touches.
  // A sprint is about 8 m/s: allow a small margin when approaching a still
  // ball, so the original reception assistance engages before body contact.
  const bool closeControl = delta.Get2D().GetLength() < (trainingView.withBall ? 2.3f : 1.5f) &&
      delta.coords[2] < (trainingView.withBall ? 1.65f : 0.9f) && relativeSpeed < (trainingView.withBall ? 12.0f : 10.0f);
  const bool recoveringKnockOn = trainingKnockOnUntil_ms > actualTime_ms &&
      delta.Get2D().GetLength() < 5.0f && delta.coords[2] < 1.4f && relativeSpeed < 12.0f;
  const bool controlled = trainingReceiving || ((closeControl || recoveringKnockOn) &&
    (!PlayerMatchEnabled() || trainingPlayer->HasPossession() || GetLastTouchPlayer()==trainingPlayer));
  // Locomotion heading reflects where the feet are actually travelling.
  // A torso can anticipate the next touch while the current step is still
  // moving elsewhere; using that pose here makes forward drift after a turn.
  const Vector3 body = trainingPlayer->GetDirectionVec();
  const Vector3 ballVelocity = ball->GetMovement().Get2D();
  const float ballSpeed = ballVelocity.GetLength();
  // A reversal must finish its real touch, not just reverse the player's
  // velocity while the ball is still departing in the old direction.
  const bool preparingAction=trainingPlayer->GetExternalController()&&
    static_cast<HumanController*>(trainingPlayer->GetExternalController())->GetActionMode()==2;
  const bool canRepeat = !preparingAction && delta.Get2D().GetLength() < 0.95f && relativeSpeed < 4.0f &&
      (ballSpeed > 0.5f ? ballVelocity.GetNormalized(0).GetDotProduct(
          training::forward(trainingView.travelYaw)) > 0.8f :
          trainingPlayer->GetMovement().GetLength() < 0.5f);
  const bool continuing = controlled && trainingView.withBall && trainingView.moving;
  const float previousTarget = trainingView.travelYaw, previousSteer = trainingView.steeringAngle;
  trainingView.update(controlled, std::atan2(body.coords[1], body.coords[0]),
                      trainingReceiving?Vector3(0):input->GetDirection(), look, 0.01f,
                      clamp(GetConfiguration()->GetReal("firstperson_look_speed", 2.6f), 0.5f, 5.0f),
                      clamp(GetConfiguration()->GetReal("firstperson_recenter_speed", 1.3f), 0.2f, 4.0f), canRepeat);
  if (continuing && trainingView.moving &&
      std::fabs(training::angle(previousSteer - trainingView.steeringAngle)) < 0.02f &&
      std::fabs(training::angle(previousTarget - trainingView.travelYaw)) > 0.4f &&
      GetConfiguration()->GetBool("training_telemetry", false))
    printf("TRAINING_STEER_REPEAT t=%lu target=%.4f\n", actualTime_ms, trainingView.travelYaw);
}

void Match::ProcessTraining() {
  auto &events = UserEventManager::GetInstance();
  auto keyOnce = [&events](SDL_Keycode key) {
    return events.ConsumeKeyPress(key);
  };
  turfInput(this);

  if (keyOnce(SDLK_ESCAPE)) EnvironmentManager::GetInstance().SignalQuit();
  if (keyOnce(SDLK_p)) pause = !pause;
  if (keyOnce(SDLK_TAB)) trainingCameraMode = (trainingCameraMode + 1) % 3;
  if(GetConfiguration()->GetBool("training_physical_lab",false)) {
    physicalLabInput(this,trainingPlayer,actualTime_ms);
  }else if (pes3Preview) {
    if (keyOnce(SDLK_v)) SpamMessage(pes3Preview->toggleBody(),7000);
    if (keyOnce(SDLK_F7)) SpamMessage(pes3Preview->toggle(),7000);
    if (keyOnce(SDLK_F8)) SpamMessage(pes3Preview->select(1),7000);
    if (keyOnce(SDLK_F9)) SpamMessage(pes3Preview->select(-1),7000);
    if (keyOnce(SDLK_F10)) SpamMessage(pes3Preview->pause(),7000);
    if (keyOnce(SDLK_F11)) SpamMessage(pes3Preview->step(),7000);
    if (keyOnce(SDLK_c)) SpamMessage(pes3Preview->capturedClip(),7000);
  }
  if (keyOnce(SDLK_r)) ResetTraining(trainingExercise);
  if (keyOnce(SDLK_F2)) ResetTraining(trainingExercise, true);
  if (keyOnce(SDLK_F3) || keyOnce(SDLK_5)) ResetTraining(4);
  if (keyOnce(SDLK_6)) ResetTraining(5);
  if (keyOnce(SDLK_F4)) LaunchTrainingBall(0);
  if (keyOnce(SDLK_F5)) LaunchTrainingBall(1);
  if (keyOnce(SDLK_F6)) LaunchTrainingBall(2);
  for (int exercise = 0; exercise < 4; ++exercise) {
    if (keyOnce(SDLK_1 + exercise)) ResetTraining(exercise);
  }

  // Rebind the single player after hotplug. Prefer a connected pad; keyboard is fallback.
  int wantedController = 0;
  for (unsigned int i = 1; i < controllers.size(); ++i) {
    auto *pad = static_cast<HIDGamepad*>(controllers[i]);
    if (events.IsJoystickConnected(pad->GetGamepadID())) {
      wantedController = i;
      break;
    }
  }
  if (wantedController != trainingController) {
    trainingController = wantedController;
    teams[0]->DeleteHumanGamers();
    teams[0]->AddHumanGamer(controllers[trainingController], e_PlayerColor_Green);
    trainingPreviousButtons = 0;
  }
  IHIDevice *input = controllers[trainingController];
  unsigned int buttons = (input->GetButton(e_ButtonFunction_Start) ? 1u : 0u)
                       | (input->GetButton(e_ButtonFunction_Select) ? 2u : 0u);
  if(input->GetButton(e_ButtonFunction_Sprint))buttons|=128u;
  if(!(buttons&128u) && (trainingPreviousButtons&128u) && trainingView.withBall)
    trainingKnockOnUntil_ms=actualTime_ms+1600;
  if ((buttons & 1u) && !(trainingPreviousButtons & 1u)) pause = !pause;
  if ((buttons & 2u) && !(trainingPreviousButtons & 2u)) ResetTraining(trainingExercise);
  if (trainingController > 0) {
    int slot = static_cast<HIDGamepad*>(input)->GetGamepadID();
    const SDL_GameControllerButton shortcuts[] = {SDL_CONTROLLER_BUTTON_DPAD_UP,
        SDL_CONTROLLER_BUTTON_DPAD_RIGHT, SDL_CONTROLLER_BUTTON_DPAD_DOWN,
        SDL_CONTROLLER_BUTTON_DPAD_LEFT, SDL_CONTROLLER_BUTTON_RIGHTSTICK};
    for (int i = 0; i < 5; ++i) {
      unsigned int mask = 1u << (i + 2);
      if (events.GetControllerButton(slot, shortcuts[i])) buttons |= mask;
      if ((buttons & mask) && !(trainingPreviousButtons & mask)) {
        if (i == 4) trainingCameraMode = (trainingCameraMode + 1) % 3;
        else ResetTraining(input->GetButton(e_ButtonFunction_Switch) ?
                           (i == 2 ? 4 : (i == 1 ? 5 : i)) : i);
      }
    }
  }
  trainingPreviousButtons = buttons;

  if (pes3Preview && (input->GetDirection().GetLength()>0.1f ||
      input->GetButton(e_ButtonFunction_ShortPass) || input->GetButton(e_ButtonFunction_LongPass) ||
      input->GetButton(e_ButtonFunction_HighPass) || input->GetButton(e_ButtonFunction_Shot) ||
      input->GetButton(e_ButtonFunction_Sprint) || input->GetButton(e_ButtonFunction_Dribble)))
    pes3Preview->releaseBodyForGameplay();
  if (pes3Preview) pes3Preview->process(pause);
  if (pause) trainingPaceWall_ms = 0;

  if (!pause) {
    if (trainingResetAt_ms && actualTime_ms >= trainingResetAt_ms) ResetTraining(trainingExercise);
    UpdateTrainingView(input);
    previousBallPos = ball->Predict(0);
    CheckBallCollisions();
    ball->Process();
    // Contacts query the position after this physical step, not the previous prediction cache.
    ball->CalculatePrediction();

    auto *image = new MentalImage(this);
    image->TakeSnapshot();
    mentalImages.insert(mentalImages.begin(), image);
    if (mentalImages.size() > 30) {
      delete mentalImages.back();
      mentalImages.pop_back();
    }

    teams[1]->UpdatePossessionStats();
    teams[0]->UpdatePossessionStats();
    ProcessTrainingContact();
    teams[0]->Process();
    if(trainingPartner)trainingPartner->GetHumanoid()->ProcessPhysicalPartner();
    trainingPlayer->RelaxFatigue(1.0f);
    ProcessFieldAudio();
    actualTime_ms += 10;
    matchTime_ms = actualTime_ms;

    const unsigned long wall_ms = EnvironmentManager::GetInstance().GetTime_ms();
    if (!trainingPaceWall_ms) {
      trainingPaceWall_ms = wall_ms;
      trainingPaceSim_ms = actualTime_ms;
    } else if (wall_ms - trainingPaceWall_ms >= 5000) {
      const float pace = float(actualTime_ms - trainingPaceSim_ms) / (wall_ms - trainingPaceWall_ms);
      Log(e_Notice, "Training", "Timing", "Simulation/real time: " + real_to_str(pace) + " (1.0 = real time)");
      trainingPaceWall_ms = wall_ms;
      trainingPaceSim_ms = actualTime_ms;
    }

    const Vector3 position = ball->Predict(0);
    bool goal = CheckForGoal(-1) || CheckForGoal(1);
    if (goal && !ballIsInGoal) {
      ++trainingGoals;
      SpamMessage("GOL! View/R: reiniciar", 2200);
      printf("TRAINING_GOAL count=%u\n", trainingGoals);
    }
    // The original net physics needs this flag latched until the next reset.
    // A goal-line crossing is only true for one simulation tick.
    if (goal) ballIsInGoal = true;
    bool outside = std::fabs(position.coords[0]) > pitchHalfW + 4.0f ||
                   std::fabs(position.coords[1]) > pitchHalfH + 4.0f;
    if ((goal || outside) && !trainingResetAt_ms) trainingResetAt_ms = actualTime_ms + 2000;
    if (trainingExercise == 3 && actualTime_ms > 1000 &&
        position.coords[2] < 0.3f && ball->GetMovement().GetLength() < 0.5f && !trainingResetAt_ms)
      trainingResetAt_ms = actualTime_ms + 4000;

    if (GetConfiguration()->GetBool("training_telemetry",false) && actualTime_ms%100==0)
      WriteTrainingTelemetry(input);
  }

  UpdatePlayerMatchCamera();
  iterations.Lock();
  iterations.data++;
  iterations.Unlock();
}

void Match::UpdatePlayerMatchCamera() {
  if (IsFirstPerson()) {
    Quaternion yaw;
    yaw.SetAngleAxis(trainingView.yaw - 0.5f * pi, Vector3(0, 0, 1));
    cameraNodeOrientation = yaw;
    cameraOrientation.SetAngleAxis(0.5f * pi + trainingView.pitch, Vector3(1, 0, 0));
    cameraNodePosition = trainingPlayer->GetPosition() +
        training::forward(trainingView.yaw) * 0.10f + Vector3(0, 0, trainingPlayer->GetPlayerData()->GetHeight() - 0.10f);
    cameraFOV = clamp(GetConfiguration()->GetReal("firstperson_fov", 78.0f), 55.0f, 100.0f);
    cameraNearCap = training::eyeNearPlane;
    cameraFarCap = 250;
  } else if (trainingCameraMode == 1) {
    cameraOrientation.SetAngleAxis(0.34f * pi, Vector3(1, 0, 0));
    cameraNodeOrientation = QUATERNION_IDENTITY;
    const bool inspectingPose=pes3Preview && pes3Preview->studyingBody();
    cameraNodePosition = trainingPlayer->GetPosition() +
        (inspectingPose ? Vector3(0,-4.5f,3.6f) : Vector3(0,-4.5f,2.8f));
    cameraFOV = 48.0f;
    cameraNearCap = 0.3f;
    cameraFarCap = 250.0f;
  } else {
    UpdateIngameCamera();
  }
}

void Match::WriteTrainingTelemetry(IHIDevice *input) {
  auto &events=UserEventManager::GetInstance();
  const Vector3 position=ball->Predict(0);
      const Vector3 p = trainingPlayer->GetPosition();
      const Vector3 movement = trainingPlayer->GetMovement();
      const Vector3 ballMovement = ball->GetMovement();
      const Vector3 inputMovement = input->GetDirection();
      const e_ButtonFunction keyboardButtons[] = {e_ButtonFunction_Up, e_ButtonFunction_Down,
          e_ButtonFunction_Left, e_ButtonFunction_Right, e_ButtonFunction_ShortPass,
          e_ButtonFunction_LongPass, e_ButtonFunction_HighPass, e_ButtonFunction_Shot,
          e_ButtonFunction_Sprint, e_ButtonFunction_Dribble, e_ButtonFunction_Switch};
      unsigned int keys = 0;
      for (unsigned int i = 0; i < 11; ++i)
        if (controllers[0]->GetButton(keyboardButtons[i])) keys |= 1u << i;
      const SDL_Keycode directKeys[] = {SDLK_LEFT, SDLK_RIGHT, SDLK_UP, SDLK_DOWN,
          SDLK_r, SDLK_1, SDLK_2, SDLK_3, SDLK_4, SDLK_5, SDLK_TAB, SDLK_6, SDLK_t,SDLK_F4,SDLK_F5,SDLK_F6,SDLK_e,SDLK_F7,SDLK_F8,SDLK_F9};
      for (unsigned int i = 0; i < 20; ++i)
        if (events.GetKeyboardState(directKeys[i])) keys |= 1u << (i + 11);
      bool lookActive = events.GetKeyboardState(SDLK_RIGHT) || events.GetKeyboardState(SDLK_LEFT) ||
                        events.GetKeyboardState(SDLK_UP) || events.GetKeyboardState(SDLK_DOWN);
      if (trainingController > 0) {
        const int slot = static_cast<HIDGamepad*>(input)->GetGamepadID();
        const Vector3 stick(events.GetControllerAxis(slot, SDL_CONTROLLER_AXIS_RIGHTX),
                            events.GetControllerAxis(slot, SDL_CONTROLLER_AXIS_RIGHTY), 0);
        lookActive = lookActive || stick.GetLength() > 0.12f;
      }
      printf("TRAINING_FRAME {\"t\":%lu,\"exercise\":%d,\"player\":[%.4f,%.4f,%.4f],"
             "\"speed\":%.4f,\"ball\":[%.4f,%.4f,%.4f],\"ball_speed\":%.4f,"
             "\"function\":%d,\"frame\":%d,\"controller\":%d,\"goals\":%u,"
             "\"camera\":%d,\"with_ball\":%d,\"yaw\":%.4f,\"head_yaw\":%.4f,\"pitch\":%.4f,\"contacts\":%u,"
             "\"look_active\":%d,\"move_active\":%d,\"shot_active\":%d,\"charge_ms\":%d,\"action_mode\":%d,\"move\":[%.4f,%.4f],\"keys\":%u,\"player_yaw\":%.4f,\"wall_ms\":%lu}\n",
             actualTime_ms, trainingExercise, p.coords[0], p.coords[1], p.coords[2],
             movement.GetLength(), position.coords[0], position.coords[1], position.coords[2],
             ballMovement.GetLength(), (int)trainingPlayer->GetCurrentFunctionType(),
             trainingPlayer->GetFrameNum(), trainingController, trainingGoals,
             trainingCameraMode.load(), trainingView.withBall ? 1 : 0, trainingView.yaw,
             trainingView.headYaw, trainingView.pitch, trainingContacts, lookActive ? 1 : 0,
             input->GetDirection().GetLength() > 0.001f ? 1 : 0,
             input->GetButton(e_ButtonFunction_Shot) ? 1 : 0,
             trainingPlayer->GetExternalController() ?
               static_cast<HumanController*>(trainingPlayer->GetExternalController())->GetCharge_ms() : 0,
             trainingPlayer->GetExternalController() ?
               static_cast<HumanController*>(trainingPlayer->GetExternalController())->GetActionMode() : 0,
             inputMovement.coords[0], inputMovement.coords[1], keys,
             std::atan2(trainingPlayer->GetBodyDirectionVec().coords[1],
                        trainingPlayer->GetBodyDirectionVec().coords[0]),
             EnvironmentManager::GetInstance().GetTime_ms());
      fflush(stdout);
}

void Match::ProcessPlayerMatchInput() {
  auto &events=UserEventManager::GetInstance();
  turfInput(this);
  if(GetConfiguration()->GetBool("training_physical_lab",false) && events.ConsumeKeyPress(SDLK_F10)){
    static unsigned scenario=0;const e_SetPiece types[]={e_SetPiece_FreeKick,e_SetPiece_Penalty,e_SetPiece_Corner,e_SetPiece_ThrowIn,e_SetPiece_GoalKick};
    referee->PracticeSetPiece(types[scenario++%5],trainingPlayer->GetTeamID());
    SpamMessage("Bola parada de teste | cobre com A/B/X | F10: proxima",3500);
  }
  if(GetConfiguration()->GetBool("training_physical_lab",false) && IsInPlay() && !IsInSetPiece()){
    if(events.ConsumeKeyPress(SDLK_F4))LaunchTrainingBall(0);
    if(events.ConsumeKeyPress(SDLK_F5))LaunchTrainingBall(1);
    if(events.ConsumeKeyPress(SDLK_F6)){
      if(!events.GetKeyboardState(SDLK_LCTRL))LaunchTrainingBall(2);
      else if(events.GetKeyboardState(SDLK_LSHIFT)){
        // Initial conditions only: the native CPU must still acquire the
        // ball, evaluate the open lanes and execute its own pass/contact.
        std::vector<Player*> mates,opponents;
        teams[1-trainingPlayer->GetTeamID()]->GetActivePlayers(mates);
        teams[trainingPlayer->GetTeamID()]->GetActivePlayers(opponents);
        Player *carrier=nullptr;
        for(auto *actor:mates)if(actor->GetFormationEntry().role==e_PlayerRole_CB){carrier=actor;break;}
        if(carrier){
          const float side=carrier->GetTeam()->GetSide();const Vector3 origin(side*30,0,0),goal(-side*pitchHalfW,0,0);
          unsigned lane=0;
          for(auto *actor:mates){
            if(actor==carrier){actor->ResetPosition(origin,goal);continue;}
            if(actor->GetFormationEntry().role==e_PlayerRole_GK){actor->ResetPosition(Vector3(side*(pitchHalfW-2),0,0),origin);continue;}
            const float x=(lane%2?7.f:-8.f)+float(lane/4)*-4.f;
            const float y=(lane%4<2?1.f:-1.f)*(9.f+float(lane/4)*6.f);
            actor->ResetPosition(origin+Vector3(side*x,y,0),goal);++lane;
          }
          unsigned mark=0;
          for(auto *actor:opponents){actor->ResetPosition(Vector3(-side*15,float(int(mark++%5)-2)*6,0),origin);}
          SetBallRetainer(0);ball->SetPosition(origin+Vector3(-side*.45f,0,.11f));ball->SetMomentum(Vector3(0));
          carrier->GetTeam()->SetLastTouchPlayer(carrier,e_TouchType_Intentional_Kicked);
          printf("CIRCULATION_LAB_SETUP t=%lu actor=%d side=%.0f\n",actualTime_ms,carrier->GetID(),side);
          SpamMessage("Saida curta livre | CPU decide e executa | R: reiniciar",4000);
        }
      }
      else{
        static unsigned nextKeeperTrial=std::max(0,GetConfiguration()->GetInt("training_keeper_lab_start",0));const unsigned trial=nextKeeperTrial++%11;
        Player *keeper=nullptr,*defender=nullptr;std::vector<Player*> opponents;teams[1-trainingPlayer->GetTeamID()]->GetActivePlayers(opponents);
        for(auto *actor:opponents)if(actor->GetFormationEntry().role==e_PlayerRole_GK)keeper=actor;else defender=actor;
        if(keeper){
          const float side=keeper->GetTeam()->GetSide();const Vector3 goal(side*pitchHalfW,0,0),forward(side,0,0);
          for(auto *actor:opponents)if(actor!=keeper)actor->ResetPosition(Vector3(side*15,actor->GetID()%2?20:-20,0),goal);
          SetBallRetainer(0);ball->SetMomentum(Vector3(0));
          if(trial==0){
            trainingPlayer->ResetPosition(goal-forward*14,goal);keeper->ResetPosition(goal-forward*1.5f,goal-forward*20);
            ball->SetPosition(trainingPlayer->GetPosition()+forward*.45f+Vector3(0,0,.11f));
            trainingPlayer->GetTeam()->SetLastTouchPlayer(trainingPlayer,e_TouchType_Intentional_Kicked);
          }else if(trial==1){
            const Vector3 start=goal-forward*13+Vector3(0,-1.5f,.2f);
            keeper->ResetPosition(goal-forward*.8f+Vector3(0,-2.5f,0),start);
            trainingPlayer->ResetPosition(start.Get2D()-forward,goal);ball->SetPosition(start);
            ball->SetMomentum(Vector3(side*13/.42f,5.05f/.42f,(2.12f+.5f*9.81f*.42f*.42f)/.42f));
            trainingPlayer->GetTeam()->SetLastTouchPlayer(trainingPlayer,e_TouchType_Intentional_Kicked);
          }else if(trial==7||trial==8){
            const float flight=trial==7?.72f:.90f,aim=trial==7?0.f:1.2f,height=trial==7?.11f:1.05f;
            const Vector3 start=goal-forward*11+Vector3(0,0,.11f);
            keeper->ResetPosition(goal-forward*1.2f,start);trainingPlayer->ResetPosition(Vector3(0,-20,0),goal);
            ball->SetPosition(start);ball->SetMomentum(Vector3(side*11/flight,aim/flight,trial==7?0.f:(height-.11f+.5f*9.81f*flight*flight)/flight));
            trainingPlayer->GetTeam()->SetLastTouchPlayer(trainingPlayer,e_TouchType_Intentional_Kicked);
          }else if(trial==9||trial==10){
            const float flight=trial==9?1.05f:.80f,offset=trial==9?-1.8f:1.6f;
            const Vector3 start=goal-forward*14+Vector3(0,offset,.11f);
            keeper->ResetPosition(goal-forward*2+Vector3(0,trial==9?1.6f:-.9f,0),start);
            trainingPlayer->ResetPosition(Vector3(0,-20,0),goal);ball->SetPosition(start);
            ball->SetMomentum(Vector3(side*14/flight,-offset/flight,0));
            defender->GetTeam()->SetLastTouchPlayer(defender,e_TouchType_Intentional_Kicked);
          }else if(trial>=5){
            const float sideAim=trial==5?-1.f:1.f,flight=.65f,height=trial==5?1.15f:2.12f;
            const Vector3 start=goal-forward*12+Vector3(0,-sideAim*.8f,.20f);
            keeper->ResetPosition(goal-forward*.85f,start);trainingPlayer->ResetPosition(start.Get2D()-forward,goal);
            ball->SetPosition(start);ball->SetMomentum(Vector3(side*12/flight,sideAim*3.6f/flight,(height-.2f+.5f*9.81f*flight*flight)/flight));
            trainingPlayer->GetTeam()->SetLastTouchPlayer(trainingPlayer,e_TouchType_Intentional_Kicked);
          }else if(defender){
            const float offset=trial==2?.5f:trial==3?-1.2f:1.2f;
            const Vector3 start=goal-forward*8+Vector3(0,offset,.11f);
            keeper->ResetPosition(goal-forward*(trial==2?2.f:1.4f)+Vector3(0,trial==2?.5f:0.f,0),start);
            trainingPlayer->ResetPosition(Vector3(0,-20,0),goal);
            ball->SetPosition(start);ball->SetMomentum(forward*8+Vector3(0,trial==2?0:-offset,0));
            defender->GetTeam()->SetLastTouchPlayer(defender,e_TouchType_Intentional_Kicked);
          }
          printf("KEEPER_LAB_SETUP t=%lu mode=%u actor=%d side=%.0f\n",actualTime_ms,trial,keeper->GetID(),side);
          SpamMessage("Ensaio goleiro: cara a cara / angulo / recuo | Ctrl+F6: proximo",4000);
        }
      }
    }
  }
  if(GetConfiguration()->GetBool("training_physical_lab",false))physicalLabInput(this,trainingPlayer,actualTime_ms);
  if(events.ConsumeKeyPress(SDLK_ESCAPE))EnvironmentManager::GetInstance().SignalQuit();
  if(events.ConsumeKeyPress(SDLK_p))pause=!pause;
  if(events.ConsumeKeyPress(SDLK_TAB))trainingCameraMode=(trainingCameraMode+1)%3;
  const bool restart=events.ConsumeKeyPress(SDLK_r);
  const bool call=events.ConsumeKeyPress(SDLK_e);
  int wanted=0;
  for(unsigned i=1;i<controllers.size();++i)
    if(events.IsJoystickConnected(static_cast<HIDGamepad*>(controllers[i])->GetGamepadID())) {wanted=i;break;}
  if(wanted!=trainingController) {
    trainingController=wanted;teams[0]->DeleteHumanGamers();
    teams[0]->AddHumanGamer(controllers[wanted],e_PlayerColor_Green);trainingPreviousButtons=0;
    printf("PLAYER_MATCH_CONTROLLER t=%lu slot=%d locked_id=%d\n",actualTime_ms,wanted,trainingPlayer->GetID());
  }
  IHIDevice *input=controllers[trainingController];
  unsigned buttons=(input->GetButton(e_ButtonFunction_Start)?1u:0u)|(input->GetButton(e_ButtonFunction_Select)?2u:0u);
  if(trainingController>0) {
    const int slot=static_cast<HIDGamepad*>(input)->GetGamepadID();
    if(events.GetControllerButton(slot,SDL_CONTROLLER_BUTTON_RIGHTSTICK))buttons|=4u;
    if(events.GetControllerAxis(slot,SDL_CONTROLLER_AXIS_TRIGGERRIGHT)>.5f)buttons|=8u;
  }
  if((buttons&1u)&&!(trainingPreviousButtons&1u))pause=!pause;
  if((buttons&4u)&&!(trainingPreviousButtons&4u))trainingCameraMode=(trainingCameraMode+1)%3;
  if(restart || ((buttons&2u)&&!(trainingPreviousButtons&2u)))RestartPlayerMatch();
  if(call || ((buttons&8u)&&!(trainingPreviousButtons&8u)))RequestPlayerMatchPass();
  trainingPreviousButtons=buttons;
  ProcessPlayerMatchContact();
}

void Match::RequestPlayerMatchPass() {
  if(!PlayerMatchEnabled() || pause || gameOver || !IsInPlay() || IsInSetPiece() || trainingPlayer->HasPossession())return;
  playerMatchPassUntil_ms=actualTime_ms+4500;
  SpamMessage("Passe pedido! Procure uma linha de passe livre.",2500);
  printf("PLAYER_MATCH_PASS_REQUEST t=%lu target=%d until=%lu\n",actualTime_ms,trainingPlayer->GetID(),playerMatchPassUntil_ms);fflush(stdout);
}

Player *Match::RequestedPassTarget(Player *passer) const {
  if(!PlayerMatchEnabled() || gameOver || pause || playerMatchPassUntil_ms<=actualTime_ms ||
      !IsInPlay() || IsInSetPiece() || passer==trainingPlayer || passer->GetTeamID()!=0 ||
      !passer->HasPossession() || trainingPlayer->HasPossession() ||
      (ball->Predict(0)-passer->GetPosition()).Get2D().GetLength()>1.1f || ball->Predict(0).coords[2]>1.0f)return nullptr;
  const float range=(passer->GetPosition()-trainingPlayer->GetPosition()).Get2D().GetLength();
  return range>1.5f && range<45?trainingPlayer:nullptr;
}

void Match::RecordPlayerMatchAction(Player *actor,e_FunctionType action,Player *target) {
  if(!PlayerMatchEnabled())return;
  if(target && actor->GetTeamID()==target->GetTeamID() && action==e_FunctionType_ShortPass)
    actor->GetTeam()->GetController()->RecordCombination(actor,target,actualTime_ms);
  const bool requested=playerMatchPassUntil_ms>actualTime_ms && actor!=trainingPlayer && actor->GetTeamID()==0 &&
    target==trainingPlayer && (action==e_FunctionType_ShortPass || action==e_FunctionType_LongPass || action==e_FunctionType_HighPass);
  if(requested) {playerMatchPassUntil_ms=0;SpamMessage("Passe vindo para voce!",1800);}
  if(requested || GetConfiguration()->GetBool("training_telemetry",false)) {
    printf("PLAYER_MATCH_ACTION t=%lu team=%d actor=%d action=%d target=%d requested=%d\n",actualTime_ms,
      actor->GetTeamID(),actor->GetID(),int(action),target?target->GetID():-1,requested?1:0);fflush(stdout);
  }
}

void Match::AlignTrainingView(){
  const Vector3 forward=trainingPlayer->GetBodyDirectionVec();
  trainingView.reset(std::atan2(forward.coords[1],forward.coords[0]));
  trainingReceptionFacing=forward;trainingReceiving=false;trainingEyeInitialized=false;
}

void Match::RestartPlayerMatch() {
  physicalGripOpponent=nullptr;physicalAIHolds.clear();trainingGrip=trainingGripBlocked=false;trainingGripEscape=0;
  pause=false;gameOver=false;inPlay=false;inSetPiece=false;goalScoredTimer=0;playerMatchPassUntil_ms=0;trainingKnockOnUntil_ms=0;trainingReceiving=false;
  SetMatchPhase(e_MatchPhase_PreMatch);matchTime_ms=0;
  for(int side=0;side<2;++side)matchData->SetGoalCount(side,0);
  ResetSituation(Vector3(0));referee->ResetForKickoff();
  trainingView.reset(0);trainingReceptionFacing=Vector3(1,0,0);trainingEyeInitialized=false;
  if(trainingPlayer->GetExternalController())trainingPlayer->GetExternalController()->Reset();
  SpamMessage("Nova partida | RT/E: pedir passe | R3/Tab: camera",5000);
  printf("PLAYER_MATCH_RESTART t=%lu locked_id=%d\n",actualTime_ms,trainingPlayer->GetID());fflush(stdout);
}

void Match::WritePlayerMatchTelemetry() {
  const unsigned samplePeriod=referee->WaitingForRestart()?100:500;
  if(!GetConfiguration()->GetBool("training_telemetry",false) || (!gameOver && actualTime_ms%samplePeriod!=0))return;
  unsigned humanCount=0;std::vector<Player*> players;
  teams[0]->GetActivePlayers(players);teams[1]->GetActivePlayers(players);
  for(auto *actor:players)if(actor->GetExternalController())++humanCount;
  char chunk[2048];std::string row;
  std::snprintf(chunk,sizeof(chunk),"PLAYER_MATCH_FRAME {\"t\":%lu,\"clock\":%lu,\"phase\":%d,\"locked_id\":%d,\"selected_id\":%d,\"human_count\":%u,\"home\":%d,\"away\":%d,\"in_play\":%d,\"set_piece\":%d,\"over\":%d,\"last_touch_team\":%d,\"pass_pending\":%d,\"players\":[",
    actualTime_ms,matchTime_ms,int(matchPhase),trainingPlayer->GetID(),trainingPlayer->GetExternalController()?trainingPlayer->GetID():-1,
    humanCount,GetScore(0),GetScore(1),IsInPlay()?1:0,IsInSetPiece()?1:0,gameOver?1:0,GetLastTouchTeamID(),playerMatchPassUntil_ms>actualTime_ms?1:0);
  row+=chunk;
  bool first=true;
  for(auto *actor:players) {
    const Vector3 point=actor->GetPosition();
    std::snprintf(chunk,sizeof(chunk),"%s{\"id\":%d,\"team\":%d,\"human\":%d,\"p\":[%.3f,%.3f,%.3f],\"speed\":%.3f,\"action\":%d}",first?"":",",actor->GetID(),actor->GetTeamID(),actor->GetExternalController()?1:0,
      point.coords[0],point.coords[1],point.coords[2],actor->GetMovement().GetLength(),int(actor->GetCurrentFunctionType()));row+=chunk;first=false;
  }
  const Vector3 ballPoint=ball->Predict(0);
  std::snprintf(chunk,sizeof(chunk),"],\"difficulty\":%.2f,\"designated_id\":%d,\"ball\":[%.3f,%.3f,%.3f],\"ball_speed\":%.3f,\"restart_type\":%d,\"restart_team\":%d,\"taker\":%d}\n",
    matchDifficulty,GetDesignatedPossessionPlayer()->GetID(),ballPoint.coords[0],ballPoint.coords[1],ballPoint.coords[2],ball->GetMovement().GetLength(),int(referee->GetBuffer().desiredSetPiece),referee->GetBuffer().teamID,referee->GetBuffer().taker?referee->GetBuffer().taker->GetID():-1);row+=chunk;
  // One stdio call holds its stream lock for the whole JSON record.
  printf("%s",row.c_str());fflush(stdout);
}
