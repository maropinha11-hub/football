// Football Training: solo practice using the original Gameplay Football simulation.
#include "match.hpp"
#include "../main.hpp"
#include "managers/usereventmanager.hpp"
#include <cmath>
#include <cstdio>

void Match::ResetTraining(int exercise, bool ballAtPlayer) {
  trainingExercise = clamp(exercise, 0, 5);
  Player *player = designatedPossessionPlayer;
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
  SpamMessage(std::string("Treino: ") + names[exercise] + " | View/R: reiniciar | F2: trazer bola", 4000);
  printf("TRAINING_RESET exercise=%d\n", exercise);
  fflush(stdout);
}

void Match::NotifyTrainingTouch(e_FunctionType function, bool knockOn) {
  if (!TrainingEnabled()) return;
  // Only a real knock-on contact starts recovery. Passing/shooting, an
  // ordinary control touch, and resets release it immediately.
  trainingKnockOnUntil_ms = knockOn &&
      (function == e_FunctionType_BallControl || function == e_FunctionType_Trap) ? actualTime_ms + 1600 : 0;
}

void Match::LaunchTrainingBall(int delivery) {
  Player *player=designatedPossessionPlayer;
  const Vector3 root=player->GetPosition().Get2D();
  const Vector3 forward=player->GetBodyDirectionVec().Get2D().GetNormalized(Vector3(1,0,0));
  // Reset only this attempt, retaining the player's current field position and facing.
  ResetTraining(0,true);
  const Vector3 chest=player->GetHumanoid()->GetStandingChestTarget();
  const float flight=delivery==0?1.0f:delivery==1?.85f:1.15f;
  const Vector3 target=delivery==0 ? root+forward*.55f+Vector3(0,0,.11f) :
    delivery==1 ? chest : root+forward*.18f+Vector3(0,0,1.92f);
  const Vector3 origin=root+forward*(delivery==0?8.0f:delivery==1?7.0f:10.0f)+
    Vector3(0,0,delivery==0?.11f:delivery==1?2.0f:3.6f);
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
  SpamMessage(delivery==0?"Passe rasteiro recebido | F4: repetir":
      delivery==1?"Dominio de peito parado | F5: repetir":"Cruzamento alto | F6: repetir",4500);
  printf("TRAINING_DELIVERY type=%d t=%lu arrival_ms=%u error=%.5f target=[%.4f,%.4f,%.4f]\n",
    delivery,actualTime_ms,time,(ball->Predict(time)-target).GetLength(),target.coords[0],target.coords[1],target.coords[2]);
  fflush(stdout);
}

Vector3 Match::GetTrainingMovement(const Vector3 &stick) const {
  if(IsFirstPerson() && trainingReceiving)
    return trainingReceptionFacing*stick.coords[1]+
      Vector3(-trainingReceptionFacing.coords[1],trainingReceptionFacing.coords[0],0)*stick.coords[0];
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
  const Vector3 delta = ball->Predict(0) - designatedPossessionPlayer->GetPosition();
  // Keep the original interception assistance for an approaching pass, but
  // do not turn every loose ball or the player's own shot into a reception.
  bool receiving=false;
  const Vector3 incoming=ball->GetMovement();
  if(delta.Get2D().GetLength()<14 && incoming.GetLength()>.5f &&
      (delta.Get2D().GetDotProduct(incoming.Get2D())<0 ||
       (delta.Get2D().GetLength()<.75f && delta.coords[2]>0 && incoming.coords[2]<-.2f)) &&
      designatedPossessionPlayer->GetLastTouchBias(350)<.01f) {
    for(unsigned ms=100;ms<=1400;ms+=50) {
      const Vector3 arrival=ball->Predict(ms)-designatedPossessionPlayer->GetPosition();
      if(arrival.Get2D().GetLength()<1.25f && arrival.coords[2]<2.5f) {receiving=true;break;}
    }
  }
  if(receiving && !trainingReceiving)trainingReceptionFacing=designatedPossessionPlayer->GetBodyDirectionVec().Get2D().GetNormalized(Vector3(1,0,0));
  trainingReceiving=receiving;
  const float relativeSpeed = (ball->GetMovement() - designatedPossessionPlayer->GetMovement()).GetLength();
  // Hysteresis keeps the head/body mode from flickering between individual dribble touches.
  // A sprint is about 8 m/s: allow a small margin when approaching a still
  // ball, so the original reception assistance engages before body contact.
  const bool closeControl = delta.Get2D().GetLength() < (trainingView.withBall ? 2.3f : 1.5f) &&
      delta.coords[2] < (trainingView.withBall ? 1.65f : 0.9f) && relativeSpeed < (trainingView.withBall ? 12.0f : 10.0f);
  const bool recoveringKnockOn = trainingKnockOnUntil_ms > actualTime_ms &&
      delta.Get2D().GetLength() < 5.0f && delta.coords[2] < 1.4f && relativeSpeed < 12.0f;
  const bool controlled = closeControl || recoveringKnockOn || trainingReceiving;
  // Locomotion heading reflects where the feet are actually travelling.
  // A torso can anticipate the next touch while the current step is still
  // moving elsewhere; using that pose here makes forward drift after a turn.
  const Vector3 body = designatedPossessionPlayer->GetDirectionVec();
  const Vector3 ballVelocity = ball->GetMovement().Get2D();
  const float ballSpeed = ballVelocity.GetLength();
  // A reversal must finish its real touch, not just reverse the player's
  // velocity while the ball is still departing in the old direction.
  const bool canRepeat = delta.Get2D().GetLength() < 0.95f && relativeSpeed < 4.0f &&
      (ballSpeed > 0.5f ? ballVelocity.GetNormalized(0).GetDotProduct(
          training::forward(trainingView.travelYaw)) > 0.8f :
          designatedPossessionPlayer->GetMovement().GetLength() < 0.5f);
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

  if (keyOnce(SDLK_ESCAPE)) EnvironmentManager::GetInstance().SignalQuit();
  if (keyOnce(SDLK_p)) pause = !pause;
  if (keyOnce(SDLK_TAB)) trainingCameraMode = (trainingCameraMode + 1) % 3;
  if (pes3Preview) {
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
    teams[0]->Process();
    designatedPossessionPlayer->RelaxFatigue(1.0f);
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

    if (GetConfiguration()->GetBool("training_telemetry", false) && actualTime_ms % 100 == 0) {
      const Vector3 p = designatedPossessionPlayer->GetPosition();
      const Vector3 movement = designatedPossessionPlayer->GetMovement();
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
          SDLK_r, SDLK_1, SDLK_2, SDLK_3, SDLK_4, SDLK_5, SDLK_TAB, SDLK_6, SDLK_t,SDLK_F4,SDLK_F5,SDLK_F6};
      for (unsigned int i = 0; i < 16; ++i)
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
             ballMovement.GetLength(), (int)designatedPossessionPlayer->GetCurrentFunctionType(),
             designatedPossessionPlayer->GetFrameNum(), trainingController, trainingGoals,
             trainingCameraMode.load(), trainingView.withBall ? 1 : 0, trainingView.yaw,
             trainingView.headYaw, trainingView.pitch, trainingContacts, lookActive ? 1 : 0,
             input->GetDirection().GetLength() > 0.001f ? 1 : 0,
             input->GetButton(e_ButtonFunction_Shot) ? 1 : 0,
             designatedPossessionPlayer->GetExternalController() ?
               static_cast<HumanController*>(designatedPossessionPlayer->GetExternalController())->GetCharge_ms() : 0,
             designatedPossessionPlayer->GetExternalController() ?
               static_cast<HumanController*>(designatedPossessionPlayer->GetExternalController())->GetActionMode() : 0,
             inputMovement.coords[0], inputMovement.coords[1], keys,
             std::atan2(designatedPossessionPlayer->GetBodyDirectionVec().coords[1],
                        designatedPossessionPlayer->GetBodyDirectionVec().coords[0]),
             EnvironmentManager::GetInstance().GetTime_ms());
      fflush(stdout);
    }
  }

  if (IsFirstPerson()) {
    Quaternion yaw;
    yaw.SetAngleAxis(trainingView.yaw - 0.5f * pi, Vector3(0, 0, 1));
    cameraNodeOrientation = yaw;
    cameraOrientation.SetAngleAxis(0.5f * pi + trainingView.pitch, Vector3(1, 0, 0));
    cameraNodePosition = designatedPossessionPlayer->GetPosition() +
        training::forward(trainingView.yaw) * 0.10f + Vector3(0, 0, designatedPossessionPlayer->GetPlayerData()->GetHeight() - 0.10f);
    cameraFOV = clamp(GetConfiguration()->GetReal("firstperson_fov", 78.0f), 55.0f, 100.0f);
    cameraNearCap = 0.055f;
    cameraFarCap = 250;
  } else if (trainingCameraMode == 1) {
    cameraOrientation.SetAngleAxis(0.34f * pi, Vector3(1, 0, 0));
    cameraNodeOrientation = QUATERNION_IDENTITY;
    const bool inspectingPose=pes3Preview && pes3Preview->studyingBody();
    cameraNodePosition = designatedPossessionPlayer->GetPosition() +
        (inspectingPose ? Vector3(0,-4.5f,3.6f) : Vector3(0,-4.5f,2.8f));
    cameraFOV = 48.0f;
    cameraNearCap = 0.3f;
    cameraFarCap = 250.0f;
  } else {
    UpdateIngameCamera();
  }
  iterations.Lock();
  iterations.data++;
  iterations.Unlock();
}
