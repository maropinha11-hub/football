// Football Training: solo practice using the original Gameplay Football simulation.
#include "match.hpp"
#include "../main.hpp"
#include "managers/usereventmanager.hpp"
#include <cmath>
#include <cstdio>

void Match::ResetTraining(int exercise, bool ballAtPlayer) {
  trainingExercise = clamp(exercise, 0, 4);
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
    ball->SetPosition(position + Vector3(8, 0, 3.5f));
    ball->SetMomentum(Vector3(-5.0f, 0, 3.0f));
  }
  bestPossessionTeamID = 0;
  inPlay = true;
  inSetPiece = false;
  goalScored = false;
  camPos.clear();
  resetNetting = true;
  trainingView.reset(std::atan2(direction.coords[1], direction.coords[0]));
  trainingEyeInitialized = false;
  const char *names[] = {"Livre", "Conducao", "Finalizacao", "Bola aerea", "Falta"};
  SpamMessage(std::string("Treino: ") + names[exercise] + " | View/R: reiniciar | F2: trazer bola", 4000);
  printf("TRAINING_RESET exercise=%d\n", exercise);
  fflush(stdout);
}

Vector3 Match::GetTrainingMovement(const Vector3 &stick) const {
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
  const float relativeSpeed = (ball->GetMovement() - designatedPossessionPlayer->GetMovement()).GetLength();
  // Hysteresis keeps the head/body mode from flickering between individual dribble touches.
  // A sprint is about 8 m/s: allow a small margin when approaching a still
  // ball, so the original reception assistance engages before body contact.
  const bool controlled = delta.Get2D().GetLength() < (trainingView.withBall ? 2.3f : 1.5f) &&
      delta.coords[2] < (trainingView.withBall ? 1.4f : 0.9f) && relativeSpeed < (trainingView.withBall ? 12.0f : 10.0f);
  const Vector3 body = designatedPossessionPlayer->GetBodyDirectionVec();
  trainingView.update(controlled, std::atan2(body.coords[1], body.coords[0]), input->GetDirection(), look, 0.01f,
                      clamp(GetConfiguration()->GetReal("firstperson_look_speed", 2.1f), 0.5f, 5.0f),
                      clamp(GetConfiguration()->GetReal("firstperson_recenter_speed", 1.3f), 0.2f, 4.0f));
}

void Match::ResolveTrainingBallContacts(const Vector3 &from) {
  Player *player = designatedPossessionPlayer;
  const Vector3 root = player->GetPosition();
  const Vector3 forward = player->GetBodyDirectionVec();
  const Vector3 right(forward.coords[1], -forward.coords[0], 0);
  const float height = player->GetPlayerData()->GetHeight();
  Vector3 a[4], b[4];
  float radii[4] = {0.19f, 0.19f, 0.31f, 0.23f};
  for (int leg = 0; leg < 2; ++leg) {
    const Vector3 side = right * (leg == 0 ? -0.10f : 0.10f);
    a[leg] = root + side + Vector3(0, 0, 0.15f);
    b[leg] = root + side + Vector3(0, 0, height * 0.46f);
  }
  a[2] = root + Vector3(0, 0, height * 0.49f);
  b[2] = root + Vector3(0, 0, height * 0.78f);
  a[3] = root + Vector3(0, 0, height * 0.88f);
  b[3] = root + Vector3(0, 0, height * 0.95f);
  if (player->GetCurrentFunctionType() == e_FunctionType_Sliding) {
    for (int i = 0; i < 4; ++i) {
      a[i] = root + forward * (i * 0.28f - 0.3f) + Vector3(0, 0, 0.23f);
      b[i] = a[i] + forward * 0.3f;
    }
  }
  const Vector3 movement = player->GetMovement();
  const Vector3 displacement = movement * 0.01f;
  const Vector3 to = ball->Predict(0);
  training::Contact earliest;
  for (int i = 0; i < 4; ++i) {
    const auto hit = training::sweep(from + displacement, to, a[i], b[i], radii[i]);
    if (hit.hit && (!earliest.hit || hit.time < earliest.time)) earliest = hit;
  }
  if (!earliest.hit) return;
  const Vector3 incoming = ball->GetMovement() - movement;
  // A just-kicked ball may start touching a foot: allow it to depart without a second impulse.
  if (incoming.GetDotProduct(earliest.normal) >= 0 && earliest.time == 0 &&
      (to - root).GetLength() > (from - root).GetLength()) return;
  Vector3 corrected = earliest.point + earliest.normal * 0.003f;
  const Vector3 velocity = training::rebound(incoming, earliest.normal, 0.42f) + movement;
  corrected += velocity * (0.01f * (1 - earliest.time));
  ball->ResolveContact(corrected, velocity);
  ++trainingContacts;
}

void Match::ProcessTraining() {
  auto &events = UserEventManager::GetInstance();
  auto keyOnce = [&events](SDL_Keycode key) {
    return events.ConsumeKeyPress(key);
  };

  if (keyOnce(SDLK_ESCAPE)) EnvironmentManager::GetInstance().SignalQuit();
  if (keyOnce(SDLK_p)) pause = !pause;
  if (keyOnce(SDLK_TAB)) trainingCameraMode = (trainingCameraMode + 1) % 3;
  if (keyOnce(SDLK_r)) ResetTraining(trainingExercise);
  if (keyOnce(SDLK_F2)) ResetTraining(trainingExercise, true);
  if (keyOnce(SDLK_F3) || keyOnce(SDLK_5)) ResetTraining(4);
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
        else ResetTraining(i == 2 && input->GetButton(e_ButtonFunction_Switch) ? 4 : i);
      }
    }
  }
  trainingPreviousButtons = buttons;

  if (!pause) {
    if (trainingResetAt_ms && actualTime_ms >= trainingResetAt_ms) ResetTraining(trainingExercise);
    UpdateTrainingView(input);
    previousBallPos = ball->Predict(0);
    ball->Process();
    ResolveTrainingBallContacts(previousBallPos);

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
          SDLK_r, SDLK_1, SDLK_2, SDLK_3, SDLK_4, SDLK_5, SDLK_TAB};
      for (unsigned int i = 0; i < 11; ++i)
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
             "\"look_active\":%d,\"move_active\":%d,\"shot_active\":%d,\"charge_ms\":%d,\"action_mode\":%d,\"move\":[%.4f,%.4f],\"keys\":%u}\n",
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
             inputMovement.coords[0], inputMovement.coords[1], keys);
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
    cameraNodePosition = designatedPossessionPlayer->GetPosition() + Vector3(0, -13, 9);
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
