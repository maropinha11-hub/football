// Football Training: solo practice using the original Gameplay Football simulation.
#include "match.hpp"
#include "../main.hpp"
#include "managers/usereventmanager.hpp"
#include <cmath>
#include <cstdio>

void Match::ResetTraining(int exercise, bool ballAtPlayer) {
  trainingExercise = exercise;
  Player *player = designatedPossessionPlayer;
  Vector3 position = ballAtPlayer ? player->GetPosition().Get2D() : Vector3(0, 0, 0);
  if (!ballAtPlayer && exercise == 2) position = Vector3(30, 0, 0);
  const Vector3 direction = ballAtPlayer ? player->GetDirectionVec() : Vector3(1, 0, 0);
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
  const char *names[] = {"Livre", "Conducao", "Finalizacao", "Bola aerea"};
  SpamMessage(std::string("Treino: ") + names[exercise] + " | View/R: reiniciar | F2: trazer bola", 4000);
  printf("TRAINING_RESET exercise=%d\n", exercise);
  fflush(stdout);
}

void Match::ProcessTraining() {
  auto &events = UserEventManager::GetInstance();
  auto keyOnce = [&events](SDL_Keycode key) {
    return events.ConsumeKeyPress(key);
  };

  if (keyOnce(SDLK_ESCAPE)) EnvironmentManager::GetInstance().SignalQuit();
  if (keyOnce(SDLK_p)) pause = !pause;
  if (keyOnce(SDLK_TAB)) trainingCloseCamera = !trainingCloseCamera;
  if (keyOnce(SDLK_r)) ResetTraining(trainingExercise);
  if (keyOnce(SDLK_F2)) ResetTraining(trainingExercise, true);
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
        if (i == 4) trainingCloseCamera = !trainingCloseCamera;
        else ResetTraining(i);
      }
    }
  }
  trainingPreviousButtons = buttons;

  if (!pause) {
    if (trainingResetAt_ms && actualTime_ms >= trainingResetAt_ms) ResetTraining(trainingExercise);
    if (actualTime_ms > 0) CheckBallCollisions();
    previousBallPos = ball->Predict(0);
    ball->Process();

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
      printf("TRAINING_FRAME {\"t\":%lu,\"exercise\":%d,\"player\":[%.4f,%.4f,%.4f],"
             "\"speed\":%.4f,\"ball\":[%.4f,%.4f,%.4f],\"ball_speed\":%.4f,"
             "\"function\":%d,\"frame\":%d,\"controller\":%d,\"goals\":%u}\n",
             actualTime_ms, trainingExercise, p.coords[0], p.coords[1], p.coords[2],
             movement.GetLength(), position.coords[0], position.coords[1], position.coords[2],
             ballMovement.GetLength(), (int)designatedPossessionPlayer->GetCurrentFunctionType(),
             designatedPossessionPlayer->GetFrameNum(), trainingController, trainingGoals);
      fflush(stdout);
    }
  }

  if (trainingCloseCamera) {
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
