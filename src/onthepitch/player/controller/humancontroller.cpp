// written by bastiaan konings schuiling 2008 - 2015
// this work is public domain. the code is undocumented, scruffy, untested, and should generally not be used for anything important.
// i do not offer support, so don't ask. to be used for inspiration :)

// Football Training: preserve ball actions, expose off-ball sliding in solo practice.
#include "humancontroller.hpp"
#include "../analog_locomotion.hpp"

#include "../../AIsupport/AIfunctions.hpp"
#include "../../physical_match_rules.hpp"
#include "../../reception_prediction.hpp"
#include "../../pass_flight.hpp"

#include "../../../main.hpp"
#include "../../../hid/gamepad.hpp"
#include "../../../managers/usereventmanager.hpp"

HumanController::HumanController(Match *match, IHIDevice *hid) : PlayerController(match), hid(hid) {
  Reset();
}

HumanController::~HumanController() {
}

void HumanController::SetPlayer(PlayerBase *player) {
  lastSwitchTime_ms = match->GetActualTime_ms();

  PlayerController::SetPlayer(player);
}

void HumanController::RequestCommand(PlayerCommandQueue &commandQueue) {

  CastPlayer()->SetDesiredTimeToBall_ms(0);

  _Preprocess(); // calculate some variables


  // human input

  Vector3 rawInputDirection;
  float rawInputVelocityFloat = 0;
  _GetHidInput(rawInputDirection, rawInputVelocityFloat);
  _SetInput(rawInputDirection, rawInputVelocityFloat);
  Player *holdTarget=nullptr;
  if(player->GetHumanoid()->PhysicalRigEnabled()&&actionMode!=2){
    auto &events=UserEventManager::GetInstance();
    bool hold=events.GetKeyboardState(SDLK_h);
    if(hid->GetDeviceType()==e_HIDeviceType_Gamepad){
      const int slot=static_cast<HIDGamepad*>(hid)->GetGamepadID();
      hold=hold||events.GetControllerAxis(slot,SDL_CONTROLLER_AXIS_TRIGGERLEFT)>.35f;
    }
    if(hold){
      std::vector<Player*> opponents;
      if(!PlayerMatchEnabled()&&match->GetTrainingPartner())opponents.push_back(match->GetTrainingPartner());
      else match->GetTeam(1-team->GetID())->GetActivePlayers(opponents);
      float nearest=1.2f;
      for(auto *other:opponents){
        const float distance=(other->GetPosition()-player->GetPosition()).Get2D().GetLength();
        if(distance<nearest){nearest=distance;holdTarget=other;}
      }
      if(holdTarget){
        // The first-person camera's with-ball flag intentionally has wide
        // hysteresis. Physical protection/holding needs the closer owner,
        // including when a laboratory pass was just given to the partner.
        const Vector3 ball=match->GetBall()->Predict(0);
        const float mine=(ball-player->GetPosition()).Get2D().GetLength();
        const float theirs=(ball-holdTarget->GetPosition()).Get2D().GetLength();
        if(match->TrainingHasBall()&&mine<1.5f&&mine<theirs+.12f)holdTarget=nullptr;
      }
    }
  }


  // clear buffer?

  e_FunctionType functionType = CastPlayer()->GetCurrentFunctionType();
  if (actionMode == 2 &&
      (functionType == e_FunctionType_ShortPass ||
       functionType == e_FunctionType_LongPass ||
       functionType == e_FunctionType_HighPass ||
       functionType == e_FunctionType_Shot) && !CastPlayer()->TouchPending()) {
    actionMode = 0;
    gauge_ms = 0;
    actionBufferTime_ms = 0;
  }

  if (actionMode == 1 &&
      (functionType == e_FunctionType_Sliding ||
       functionType == e_FunctionType_Interfere) && !CastPlayer()->TouchPending()) {
    actionMode = 0;
    gauge_ms = 0;
    actionBufferTime_ms = 0;
  }


  // cancels

  // shot cancel
  if (actionMode == 2 && actionButton == e_ButtonFunction_Shot && hid->GetButton(e_ButtonFunction_ShortPass) && !match->IsInSetPiece()) {
    actionMode = 0;
    gauge_ms = 0;
    actionBufferTime_ms = 0;
  }

  // high pass cancel
  if (actionMode == 2 && actionButton == e_ButtonFunction_HighPass && hid->GetButton(e_ButtonFunction_ShortPass) && !match->IsInSetPiece()) {
    actionMode = 0;
    gauge_ms = 0;
    actionBufferTime_ms = 0;
  }

  // cancel action buffer
  if (actionMode == 2 && !match->IsInSetPiece() &&
      (actionBufferTime_ms > 2000 ||
       CastPlayer()->GetTimeNeededToGetToBall_ms() > CastPlayer()->GetTimeNeededToGetToBall_previous_ms() + 700 ||
      (CastPlayer()->GetCurrentFunctionType() == e_FunctionType_Interfere))) {
    actionMode = 0;
    gauge_ms = 0;
    actionBufferTime_ms = 0;
  }

  // cancel pressure and such
  if (actionMode == 1 && actionBufferTime_ms > 1000) {
    actionMode = 0;
    gauge_ms = 0;
    actionBufferTime_ms = 0;
  }


  // execute buffer?

  if(actionMode!=2)actionCommitted=false;
  if (actionMode == 2) {

    if(!hid->GetButton(actionButton) ||
       (TrainingEnabled() && match->TrainingReceivingBall() && !CastPlayer()->HasPossession()))
      actionCommitted=true;

    if (actionCommitted || !hid->GetButton(actionButton) ||
        (hid->GetButton(actionButton) && gauge_ms >= (TrainingEnabled()?
          (actionButton==e_ButtonFunction_Shot?520:1000):500)) ||
        (!CastPlayer()->HasPossession() && !match->IsInSetPiece() && actionBufferTime_ms > 0)) {

      int baseTime_ms = 60; // substract a little because we can't really press a button shorter than this
      float gaugeFactor = (gauge_ms - baseTime_ms) * (1.0f / float(1000 - baseTime_ms));
      gaugeFactor = clamp(gaugeFactor, 0.0f, 1.0f);
      if(TrainingEnabled() && actionButton==e_ButtonFunction_Shot)
        gaugeFactor=training::shotCharge(gauge_ms);

      // action button released!

      // force set piece methods
      if (match->IsInSetPiece() && team->GetController()->GetPieceTaker() == player && team->GetController()->GetSetPieceType() == e_SetPiece_KickOff) {

        PlayerCommand command;

        command.desiredFunctionType = e_FunctionType_ShortPass;
        command.touchInfo.autoDirectionBias = 1.0f;
        command.touchInfo.autoPowerBias = 1.0f;
        command.touchInfo.inputDirection = player->GetDirectionVec(); // dud
        command.touchInfo.inputPower = 0.1f; // dud

        Vector3 desiredTargetPosition = player->GetPosition() + player->GetDirectionVec() * 1.0f;
        command.touchInfo.forcedTargetPlayer = AI_GetClosestPlayer(team, desiredTargetPosition, false, CastPlayer());

        AI_GetPass(CastPlayer(), command.desiredFunctionType, command.touchInfo.inputDirection, command.touchInfo.inputPower, command.touchInfo.autoDirectionBias, command.touchInfo.autoPowerBias, command.touchInfo.desiredDirection, command.touchInfo.desiredPower, command.touchInfo.targetPlayer, command.touchInfo.forcedTargetPlayer);

        commandQueue.push_back(command);


      } else if (actionButton == e_ButtonFunction_ShortPass) {

        PlayerCommand command;
        command.desiredFunctionType = e_FunctionType_ShortPass;
        command.useDesiredMovement = false;
        command.useDesiredLookAt = false;

        float inputPower = clamp(pow(gaugeFactor, 0.7f), 0.01f, 1.0f);
        command.touchInfo.inputDirection = TrainingEnabled() && match->TrainingReceivingBall() ? GetDirection() : inputDirection;
        command.touchInfo.inputPower = inputPower;
        command.touchInfo.charge_ms=std::max(10,gauge_ms);
        command.touchInfo.autoDirectionBias = GetConfiguration()->GetReal("gameplay_shortpass_autodirection", _default_ShortPass_AutoDirection);
        command.touchInfo.autoPowerBias = GetConfiguration()->GetReal("gameplay_shortpass_autopower", _default_ShortPass_AutoPower);
        AI_GetPass(CastPlayer(), command.desiredFunctionType, command.touchInfo.inputDirection, command.touchInfo.inputPower, command.touchInfo.autoDirectionBias, command.touchInfo.autoPowerBias, command.touchInfo.desiredDirection, command.touchInfo.desiredPower, command.touchInfo.targetPlayer);

        commandQueue.push_back(command);


      } else if (actionButton == e_ButtonFunction_LongPass) {

        PlayerCommand command;
        command.desiredFunctionType = e_FunctionType_LongPass;
        command.useDesiredMovement = false;
        command.useDesiredLookAt = false;

        float inputPower = player->GetHumanoid()->PhysicalRigEnabled()?football_pass::chargedRange(std::max(10,gauge_ms),false)/60.f:
          clamp(pow(gaugeFactor, 0.65f), 0.01f, 1.0f);
        command.touchInfo.charge_ms=std::max(10,gauge_ms);
        command.touchInfo.inputDirection = TrainingEnabled() && match->TrainingReceivingBall() ? GetDirection() : inputDirection;
        command.touchInfo.inputPower = inputPower;
        command.touchInfo.autoDirectionBias = GetConfiguration()->GetReal("gameplay_throughpass_autodirection", _default_ThroughPass_AutoDirection);
        command.touchInfo.autoPowerBias = GetConfiguration()->GetReal("gameplay_throughpass_autopower", _default_ThroughPass_AutoPower);
        AI_GetPass(CastPlayer(), command.desiredFunctionType, command.touchInfo.inputDirection, command.touchInfo.inputPower, command.touchInfo.autoDirectionBias, command.touchInfo.autoPowerBias, command.touchInfo.desiredDirection, command.touchInfo.desiredPower, command.touchInfo.targetPlayer);

        commandQueue.push_back(command);


      } else if (actionButton == e_ButtonFunction_HighPass) {

        PlayerCommand command;
        command.desiredFunctionType = e_FunctionType_HighPass;
        command.useDesiredMovement = false;
        command.useDesiredLookAt = false;

        float inputPower = player->GetHumanoid()->PhysicalRigEnabled()?football_pass::chargedRange(std::max(10,gauge_ms),true)/60.f:
          clamp(pow(gaugeFactor, 0.55f), 0.01f, 1.0f);
        command.touchInfo.charge_ms=std::max(10,gauge_ms);
        command.touchInfo.inputDirection = TrainingEnabled() && match->TrainingReceivingBall() ? GetDirection() : inputDirection;
        command.touchInfo.inputPower = inputPower;
        command.touchInfo.autoDirectionBias = GetConfiguration()->GetReal("gameplay_highpass_autodirection", _default_HighPass_AutoDirection);
        command.touchInfo.autoPowerBias = GetConfiguration()->GetReal("gameplay_highpass_autopower", _default_HighPass_AutoPower);
        AI_GetPass(CastPlayer(), command.desiredFunctionType, command.touchInfo.inputDirection, command.touchInfo.inputPower, command.touchInfo.autoDirectionBias, command.touchInfo.autoPowerBias, command.touchInfo.desiredDirection, command.touchInfo.desiredPower, command.touchInfo.targetPlayer);

        commandQueue.push_back(command);


      } else if (actionButton == e_ButtonFunction_Shot) {

        PlayerCommand command;
        command.desiredFunctionType = e_FunctionType_Shot;
        command.useDesiredMovement = false;
        command.useDesiredLookAt = false;
        command.desiredVelocityFloat = inputVelocityFloat; // this is so we can use sprint/dribble buttons as shot modifiers
        command.touchInfo.inputDirection = TrainingEnabled() && match->TrainingReceivingBall() ? GetDirection() : inputDirection;
        command.touchInfo.autoDirectionBias = GetConfiguration()->GetReal("gameplay_shot_autodirection", _default_Shot_AutoDirection);
        if (GetHIDevice()->GetDeviceType() == e_HIDeviceType_Keyboard) command.touchInfo.autoDirectionBias = 1.0f;
        command.touchInfo.desiredDirection = AI_GetShotDirection(CastPlayer(), command.touchInfo.inputDirection, command.touchInfo.autoDirectionBias);
        command.touchInfo.desiredPower = clamp(pow(gaugeFactor, 0.6f), 0.01f, 1.0f);
        if(TrainingEnabled()) {
          command.touchInfo.inputPower=gaugeFactor;
          if(shotChip || hid->GetButton(e_ButtonFunction_Switch))command.modifier|=e_PlayerCommandModifier_Chip;
        }

        commandQueue.push_back(command);

      }

    }


  } else if (actionMode == 1) {

    if (hid->GetButton(actionButton)) {

      if (actionButton == e_ButtonFunction_Sliding) {

        PlayerCommand command;
        command.desiredFunctionType = e_FunctionType_Sliding;
        command.useDesiredMovement = true;
        command.desiredDirection = inputDirection;
        command.desiredVelocityFloat = inputVelocityFloat;
        command.useDesiredLookAt = true;
        command.desiredLookAt = CastPlayer()->GetPosition() + CastPlayer()->GetMovement() * 0.1f + command.desiredDirection * 10.0f;
        commandQueue.push_back(command);

      }

      if (actionButton == e_ButtonFunction_TeamPressure) {

        if (!TrainingEnabled()) team->GetController()->ApplyTeamPressure();

      }

      if (actionButton == e_ButtonFunction_KeeperRush) {

        if (!TrainingEnabled()) team->GetController()->ApplyKeeperRush();

      }

    } else {

      // action button released!
      actionMode = 0;

    }
  }

  // set piece?
  if ((match->IsInSetPiece() && team->GetController()->GetPieceTaker() == player && (actionMode != 2 || (actionMode == 2 && hid->GetButton(actionButton)) || match->GetBallRetainer() == player)) ||
      (match->IsInSetPiece() && team->GetController()->GetPieceTaker() != player && match->GetBallRetainer() == 0)) {
    _SetPieceCommand(commandQueue);
    //if (team->GetController()->GetPieceTaker() == player) printf("waiting to take set piece!\n");
    //if (team->GetController()->GetPieceTaker() != player) printf("waiting for teammate to take set piece!\n");
    return;
  }

  // delay direction input until we have chosen a steady direction.
  // this is because humans can only move an analog stick so fast, and we don't want requeues to happen mid-analogstick-movement.
  Vector3 inputDirectionSaveNonsteady = inputDirection;
  // A stationary rear tap prepares a heel contact. Do not let the receiving
  // magnet first walk the planted player through the ball while A is held.
  // Longer charges and all moving/aerial passes retain their normal approach.
  const bool preparingRearTap=player->GetHumanoid()->PhysicalRigEnabled() &&
    actionMode==2 && actionButton==e_ButtonFunction_ShortPass && !actionCommitted &&
    hid->GetButton(actionButton) && gauge_ms<=140 && !match->IsInSetPiece() &&
    !match->TrainingReceivingBall() && player->GetMovement().GetLength()<1.3f &&
    inputDirectionSaveNonsteady.GetDotProduct(player->GetBodyDirectionVec())<-.55f &&
    (match->GetBall()->Predict(0)-player->GetPosition()).Get2D().GetLength()<.9f;
  //SetGreenDebugPilon(player->GetPosition() + inputDirection * (inputVelocityFloat * 0.5f + 0.5f));
  inputDirection = steadyDirection;
  //SetBlueDebugPilon(player->GetPosition() + inputDirection * (inputVelocityFloat * 0.5f + 0.6f));

  if (match->IsInPlay() && !match->IsInSetPiece()) {

    bool idleTurnToOpponentGoal = false;
    bool knockOn = false;
    // RT changes touch/speed, not the first-person player's heading. The
    // original idle goal-facing shortcut would otherwise fight a recent turn.
    if (hid->GetButton(e_ButtonFunction_Dribble) && !(TrainingEnabled() && match->IsFirstPerson())) idleTurnToOpponentGoal = true;
    if (hid->GetButton(e_ButtonFunction_Dribble) && hid->GetButton(e_ButtonFunction_Sprint)) knockOn = true;

    // special adapted input for ballcontrol and trap, when we have shoot/pass buffers
    Vector3 inputDirectionSave2 = inputDirection;
    float inputVelocitySave2 = inputVelocityFloat;
    if (actionMode == 2) {
      float dot = CastPlayer()->GetDirectionVec().GetDotProduct(inputDirection) * 0.5f + 0.5f; // todo: test
      if (CastPlayer()->GetEnumVelocity() != e_Velocity_Idle) {
        inputDirection = (CastPlayer()->GetDirectionVec() * 1.0f + inputDirection * 0.0f).GetNormalized(inputDirection); // want inputdirection to be biggest, so we won't stubbornly fail to do 180s
      }
      dot = pow(dot, 1.5f); // prefer braking, even on slight angles
      dot = dot * 0.8f + 0.2f;
      dot *= 0.9f; // else, <=walk-anims may never work (backheels and such)
      inputVelocityFloat = CastPlayer()->GetFloatVelocity() * dot;
    }

    // ball control?
    bool keepCurrentBodyDirection = false;
    // sidestep dribble disabled for now, too quirky: if (hid->GetButton(e_ButtonFunction_Dribble)) keepCurrentBodyDirection = true;
    if(actionMode!=1&&!holdTarget&&!preparingRearTap)_BallControlCommand(commandQueue, idleTurnToOpponentGoal, knockOn, true, keepCurrentBodyDirection);

    // trap?
    if(actionMode!=1&&!holdTarget)_TrapCommand(commandQueue, idleTurnToOpponentGoal, knockOn);

    // reload original input
    if (actionMode == 2) {
      inputDirection = inputDirectionSave2;
      inputVelocityFloat = inputVelocitySave2;
    }

    // interfere?
    bool byAnyMeans = false;
    if (hid->GetButton(e_ButtonFunction_Pressure)) byAnyMeans = true;
    if(actionMode!=2&&(!holdTarget||actionMode==1))_InterfereCommand(commandQueue, byAnyMeans);
  }

  // movement
  bool forceMagnet = false;
  bool extraHaste = false;
  if (actionMode != 2 && hid->GetButton(e_ButtonFunction_Pressure)) {
    forceMagnet = true;
    extraHaste = true;
  }
  if (actionMode == 2) {
    forceMagnet = true;
    extraHaste = true;
  }
  if(TrainingEnabled() && match->TrainingReceivingBall() && actionMode==0 &&
      !player->GetHumanoid()->UpperReceptionActive())forceMagnet=true;
  _MovementCommand(commandQueue, forceMagnet, extraHaste);
  if(preparingRearTap && !commandQueue.empty()){
    auto &movement=commandQueue.back();movement.desiredVelocityFloat=0;
    movement.useDesiredLookAt=true;movement.desiredLookAt=player->GetPosition()+player->GetBodyDirectionVec()*10.f;
  }

  if (commandQueue.size() > 0) {
    PlayerCommand &command = commandQueue.at(commandQueue.size() - 1);
    assert(command.desiredFunctionType == e_FunctionType_Movement); // make sure this is the movement command (is probably guaranteed, check out _MovementCommand)

    if (TrainingEnabled()) {
      if(actionMode==0 && match->TrainingHasBall() && !match->TrainingReceivingBall() &&
          !player->GetHumanoid()->UpperReceptionActive() && !hid->GetButton(e_ButtonFunction_Sprint) &&
          hid->GetDirection().GetLength()>.01f && hid->GetDirection().GetLength()<=football_input::walkingStickLimit &&
          (match->GetBall()->Predict(0)-player->GetPosition()).Get2D().GetLength()<1.05f){
        // The original ball-control magnet quantizes gentle walking as idle.
        // Keep its real contact commands, but retain continuous manual travel
        // inside the controlled-ball corridor instead of stopping the root.
        command.desiredDirection=inputDirection;
        command.desiredVelocityFloat=rawInputVelocityFloat;
        command.desiredLookAt=player->GetPosition()+inputDirection*10.f;
      }
      // Assistance may request a faster interception than the raw stick.
      // Keep small reception adjustments small, and do not let that fallback
      // sprint after every forward-loop touch while RB is released.
      const Vector3 stick=hid->GetDirection();
      if(actionMode==0 && match->TrainingReceivingBall() && !player->GetHumanoid()->UpperReceptionActive())
        command.desiredVelocityFloat=std::min(command.desiredVelocityFloat,
          walkVelocity*clamp(GetConfiguration()->GetReal("training_walk_speed_scale",.72f),.55f,1.f));
      else if(actionMode==0 && match->TrainingHasBall() && !hid->GetButton(e_ButtonFunction_Sprint) &&
          player->GetHumanoid()->GetCurrentAnim()->anim->GetVariable("training_dribble")=="true" &&
          (match->GetBall()->Predict(0)-player->GetPosition()).Get2D().GetLength()<1.1f &&
          (match->GetBall()->GetMovement()-player->GetMovement()).Get2D().GetLength()<3.0f &&
          stick.coords[1]>.72f && std::fabs(stick.coords[0])<.20f)
        command.desiredVelocityFloat=std::min(command.desiredVelocityFloat,inputVelocityFloat);
      // The incoming-ball axis stays fixed. Forward/backward can adjust the
      // meeting point, but sideways input cannot turn the torso mid-reception.
      // Once the ball touches, native assistance follows the controlled drop.
      if(actionMode==0 && player->GetHumanoid()->UpperReceptionActive() && match->GetBall()->Predict(0).coords[2]>.45f) {
        command.desiredDirection=inputDirection;
        command.desiredVelocityFloat=(inputVelocityFloat>.05f?idleDribbleSwitch+.05f:0);
        command.desiredLookAt=player->GetPosition()+match->GetTrainingReceptionFacing()*10;
      }
      if(actionMode==0 && match->TrainingReceivingBall() && !player->GetHumanoid()->UpperReceptionActive()) {
        if(stick.GetLength()>.05f){
          const Vector3 front=match->GetTrainingReceptionFacing();
          const Vector3 native=command.desiredDirection*command.desiredVelocityFloat;
          const Vector3 sideways=native-front*native.GetDotProduct(front);
          const Vector3 manual=inputDirection*inputVelocityFloat;
          const Vector3 velocity=sideways+front*manual.GetDotProduct(front);
          command.desiredVelocityFloat=std::min(walkVelocity,velocity.GetLength());
          command.desiredDirection=velocity.GetNormalized(front);
        }
        const Vector3 arrival=match->GetBall()->Predict(200)-player->GetPosition();
        const float lateral=std::fabs(arrival.Get2D().GetCrossProduct(match->GetTrainingReceptionFacing()).coords[2]);
        if(stick.GetLength()<.05f && lateral<.25f &&
            (match->GetBall()->Predict(0).coords[2]>.6f || match->GetBall()->Predict(200).coords[2]>.6f)){
          // A well-aimed chest ball needs a quiet receiving base. Offset
          // deliveries still retain the native lateral interception step.
          command.desiredVelocityFloat=0;command.desiredDirection=match->GetTrainingReceptionFacing();
        }
        if(player->GetHumanoid()->PhysicalRigEnabled()&&stick.GetLength()<.05f&&match->GetBall()->Predict(0).coords[2]>.30f){
          auto point=[](const Vector3 &p)->football_reception::Vec{return {{p.coords[0],p.coords[1],p.coords[2]}};};
          const auto plan=football_reception::predict([&](unsigned ms){return point(match->GetBall()->Predict(ms));},point(player->GetPosition()),point(player->GetMovement()),point(match->GetBall()->GetMovement()),!match->GetBallRetainer());
          if(plan.valid){
            const Vector3 front=match->GetTrainingReceptionFacing();
            const Vector3 meeting=Vector3(plan.point[0],plan.point[1],0)-front*.24f-player->GetPosition().Get2D();
            // Do not run toward a point the high ball will pass hundreds of
            // milliseconds before it reaches receiving height. Wait at its
            // actual meeting point, retaining manual forward/back adjustment.
            command.desiredVelocityFloat=meeting.GetLength()<.40f?0.f:std::min(1.5f,meeting.GetLength()/std::max(.25f,plan.time));
            command.desiredDirection=meeting.GetNormalized(front);
            command.desiredLookAt=player->GetPosition()+front*10.f;
          }
        }
        for(auto &receive:commandQueue)if(receive.desiredFunctionType==e_FunctionType_Trap ||
            receive.desiredFunctionType==e_FunctionType_BallControl){
          receive.desiredDirection=command.desiredDirection;
          receive.desiredVelocityFloat=command.desiredVelocityFloat;
          receive.desiredLookAt=command.desiredLookAt;
        }
        if(GetConfiguration()->GetBool("training_telemetry",false) && match->GetActualTime_ms()%100==0)
          printf("TRAINING_RECEIVE_ASSIST t=%lu speed=%.5f direction=[%.5f,%.5f] match=%d\n",match->GetActualTime_ms(),command.desiredVelocityFloat,command.desiredDirection.coords[0],command.desiredDirection.coords[1],PlayerMatchEnabled()?1:0);
      }
      // Dribbling still needs the original movement assistance between touches,
      // especially when a turn cannot immediately use a ball-control animation.
      // Solo training always designates this player, so disable the match AI's
      // interception magnet once the ball is actually out of control.
      if (!match->TrainingHasBall() && !match->TrainingReceivingBall() && actionMode != 2) {
        command.desiredDirection = inputDirection;
        command.desiredVelocityFloat = inputVelocityFloat;
      }
      if (match->TrainingHasBall() && actionMode != 2 && inputVelocityFloat < 0.05f &&
          (match->GetBall()->Predict(0) - player->GetPosition()).Get2D().GetLength() < 0.9f &&
          match->GetBall()->GetMovement().Get2D().GetLength() < 1.0f)
        command.desiredVelocityFloat = idleVelocity;
      if (match->IsFirstPerson() && !match->TrainingHasBall() && !match->TrainingReceivingBall() && actionMode != 2)
        command.desiredLookAt = player->GetPosition() + match->GetTrainingFacing() * 10;
    }

/*
    // no magnet
    command.desiredDirection = inputDirection;
    command.desiredVelocityFloat = inputVelocityFloat;
    if (command.desiredVelocityFloat < idleDribbleSwitch) command.desiredDirection = (_mentalImage->GetBallPrediction(500).Get2D() - player->GetPosition()).GetNormalized(inputDirection);
    //command.desiredLookAt = CastPlayer()->GetPosition() + inputDirection * 10;
    command.desiredLookAt = _mentalImage->GetBallPrediction(500).Get2D();
*/

    // super cancel
    if (hid->GetButton(e_ButtonFunction_Dribble) && hid->GetButton(e_ButtonFunction_Sprint)) {
      if (!hasBestPossession && !(TrainingEnabled() && match->TrainingHasBall())) {
        command.desiredDirection = inputDirection;
        command.desiredVelocityFloat = inputVelocityFloat;
      }
    }
  }

  if(player->GetHumanoid()->PhysicalRigEnabled()){
    if(holdTarget&&!commandQueue.empty()){
      auto &movement=commandQueue.back();
      if(movement.desiredFunctionType==e_FunctionType_Movement){
        // A deliberate hold must not chase a passing ball through the native
        // reception magnet. Manual stick movement and physical traction still
        // apply, while the torso follows the actual nearby shirt target.
        movement.desiredDirection=rawInputDirection.GetNormalized(player->GetBodyDirectionVec());
        movement.desiredVelocityFloat=rawInputVelocityFloat;
        movement.useDesiredLookAt=true;movement.desiredLookAt=holdTarget->GetPosition().Get2D();
        if(GetConfiguration()->GetBool("training_telemetry",false)&&match->GetActualTime_ms()%100==0)
          printf("PHYSICAL_HOLD_STANCE t=%lu actor=%d target=%d manual_speed=%.4f\n",match->GetActualTime_ms(),player->GetID(),holdTarget->GetID(),rawInputVelocityFloat);
      }
    }
    if(actionMode==2 && !commandQueue.empty() && match->TrainingReceivingBall() &&
       hid->GetDirection().GetLength()<.05f && player->GetMovement().GetLength()<1.5f &&
       (match->GetBall()->Predict(0).coords[2]>1.2f || match->GetBall()->Predict(200).coords[2]>1.2f)){
      auto &movement=commandQueue.back();
      if(movement.desiredFunctionType==e_FunctionType_Movement){
        // A stationary buffered aerial action waits on its reception axis.
        // Do not let a provisional interception gait walk backwards and
        // remove the standing header before its real contact window opens.
        movement.desiredVelocityFloat=0;movement.desiredDirection=match->GetTrainingReceptionFacing();
        movement.useDesiredLookAt=true;movement.desiredLookAt=player->GetPosition()+match->GetTrainingReceptionFacing()*10.f;
      }
    }
    if(actionMode==0 && !commandQueue.empty()){
      auto &movement=commandQueue.back();
      const Vector3 step=player->GetHumanoid()->PhysicalBalanceVelocity();
      if(step.GetLength()>.025f && movement.desiredFunctionType==e_FunctionType_Movement){
        const Vector3 velocity=movement.desiredDirection*movement.desiredVelocityFloat+step;
        movement.desiredDirection=velocity.GetNormalized(movement.desiredDirection);
        movement.desiredVelocityFloat=std::min(sprintVelocity,velocity.GetLength());
        // Visible support steps use the native full-body trip selector.
        // Never replace an impact reaction with a forced generic walk.
        if(GetConfiguration()->GetBool("training_telemetry",false) && match->GetActualTime_ms()%50==0)
          printf("PHYSICAL_STEP_COMMAND t=%lu demand=%.5f velocity=%.5f direction=[%.4f,%.4f] look=%d\n",match->GetActualTime_ms(),step.GetLength(),movement.desiredVelocityFloat,movement.desiredDirection.coords[0],movement.desiredDirection.coords[1],movement.useDesiredLookAt?1:0);
      }
    }
    if(!commandQueue.empty()){
      auto &movement=commandQueue.back();
      if(movement.desiredFunctionType==e_FunctionType_Movement){
        const Vector3 velocity=player->GetHumanoid()->PhysicalContactVelocity(movement.desiredDirection*movement.desiredVelocityFloat);
        movement.desiredVelocityFloat=velocity.GetLength();
        movement.desiredDirection=velocity.GetNormalized(movement.desiredDirection);
      }
    }
    if(actionMode!=2)turningPass=false;
    for(unsigned i=0;i+1<commandQueue.size();++i){
      auto &pass=commandQueue[i];
      if(pass.desiredFunctionType!=e_FunctionType_ShortPass && pass.desiredFunctionType!=e_FunctionType_LongPass)continue;
      const Vector3 direction=pass.touchInfo.desiredDirection.Get2D().GetNormalized(player->GetBodyDirectionVec());
      const bool close=(match->GetBall()->Predict(0)-player->GetPosition()).Get2D().GetLength()<1.25f && match->GetBall()->Predict(0).coords[2]<.45f;
      const float facing=direction.GetDotProduct(player->GetBodyDirectionVec());
      const bool lightHeel=pass.desiredFunctionType==e_FunctionType_ShortPass&&football_rules::userBackheel(facing,player->GetMovement().GetLength(),gauge_ms);
      if(!lightHeel&&close&&facing<.60f){
        // Keep the queued receiving/pivot stance looking toward its pass.
        // The normal ball magnet otherwise turns it back to the ball during
        // the handoff and starts a second unnecessary pivot.
        for(auto &movement:commandQueue)if(movement.desiredFunctionType==e_FunctionType_Movement||movement.desiredFunctionType==e_FunctionType_BallControl){
          movement.useDesiredLookAt=true;movement.desiredLookAt=player->GetPosition()+direction*10.f;
        }
      }
      if(lightHeel)turningPass=false;
      const bool slowPivot=player->GetMovement().GetLength()<1.8f;
      if(!turningPass && !lightHeel && close && facing<(slowPivot?.55f:-.20f)){
        turningPass=true;turningPassDirection=direction;turningPassUntil=match->GetActualTime_ms()+1400;
        if(GetConfiguration()->GetBool("training_telemetry",false))printf("PHYSICAL_PASS_TURN t=%lu state=begin\n",match->GetActualTime_ms());
      }
      if(turningPass){
        const bool aligned=turningPassDirection.GetDotProduct(player->GetBodyDirectionVec())>(slowPivot?.75f:.40f);
        if(!aligned && close && match->GetActualTime_ms()<turningPassUntil){
          for(auto &movement:commandQueue)if(movement.desiredFunctionType==e_FunctionType_Movement||movement.desiredFunctionType==e_FunctionType_BallControl){
            movement.useDesiredLookAt=true;movement.useDesiredMovement=true;
            movement.desiredLookAt=player->GetPosition()+turningPassDirection*10.f;
            movement.desiredDirection=turningPassDirection;
            movement.desiredVelocityFloat=movement.desiredFunctionType==e_FunctionType_BallControl?idleDribbleSwitch+.1f:.9f;
          }
          commandQueue.erase(commandQueue.begin()+i);
        }else{
          pass.touchInfo.desiredDirection=turningPassDirection;turningPass=false;
          if(GetConfiguration()->GetBool("training_telemetry",false))printf("PHYSICAL_PASS_TURN t=%lu state=release aligned=%d\n",match->GetActualTime_ms(),aligned?1:0);
        }
      }
      break;
    }
  }
  // reload original input
  inputDirection = inputDirectionSaveNonsteady;
}

void HumanController::Process() {

  // just doesn't work so well (fixes the 'humans can't change stick pos instantly' problem, but introduces too much lag). maybe revisit/update later
  bool enableSteadyDirectionSystem = false;

  PlayerController::Process();

  Vector3 currentDirection;
  float dud;
  _GetHidInput(currentDirection, dud);
  radian angle = fabs(currentDirection.GetAngle2D(previousDirection));
  previousDirection = currentDirection;

  // only set steadydirection if angle is small (= human probably reaching his intended direction)
  // or very large (= maybe the stick has been in deadzone space; humans can't move this fast)
  if (enableSteadyDirectionSystem) {
    if (angle < 0.01f * pi || angle > 0.65f * pi || (match->GetActualTime_ms() - lastSteadyDirectionSnapshotTime_ms) > 100) {
      steadyDirection = currentDirection;
      lastSteadyDirectionSnapshotTime_ms = match->GetActualTime_ms();
    }
  } else {
    steadyDirection = currentDirection;
    lastSteadyDirectionSnapshotTime_ms = match->GetActualTime_ms();
  }

  _CalculateSituation();

  // action?

  if (actionMode == 0 && (!match->IsInSetPiece() || team->GetController()->GetPieceTaker() == player)) {

    // todo: clean this up

    // what is the context: do we want defend buttons or pass/shot buttons?
    float possessionContext = possessionAmount - 1.0f;
    if (match->GetDesignatedPossessionPlayer() == player) {
      possessionContext = 1.0f; // new (keeper was allowed doing slidings before free kick sometimes lol, sign something was wrong)
    } else {
      // in situations where we aren't the designated player, we sometimes still want to do ball stuff, because we could try to extend our leg to pass, for example
      if (hid->GetButton(e_ButtonFunction_ShortPass)) possessionContext += 0.15f; // todo: bug: the logic of these weighings are based on the default 'pes' button settings.. need to take into account the defensive function of the buttons as well
      if (hid->GetButton(e_ButtonFunction_LongPass)) possessionContext += 0.15f;
      if (hid->GetButton(e_ButtonFunction_Shot)) possessionContext += 0.15f;

      if (hid->GetButton(e_ButtonFunction_Pressure)) possessionContext -= 0.15f;
      if (hid->GetButton(e_ButtonFunction_Sliding)) possessionContext -= 0.15f;
      if (hid->GetButton(e_ButtonFunction_TeamPressure)) possessionContext -= 0.15f;

      if (match->GetBall()->Predict(0).coords[2] > 1.5f) possessionContext += 0.2f;
    }

    if (TrainingEnabled()) {
      possessionContext = (match->TrainingHasBall() || match->TrainingReceivingBall() ||
          match->GetBall()->Predict(200).GetDistance(player->GetPosition()) < 2.5f) ? 1.0f : -1.0f;
      // A/X/Y have no useful defensive action in solo practice. Accept the
      // original two-second action buffer before an incoming ball is close,
      // so its first contact can be a pass, volley or header. B retains the
      // defensive slide when no reception is imminent.
      Player *owner=match->GetLastTouchPlayer();
      bool enemyCarrier=PlayerMatchEnabled() && owner && owner->GetTeamID()!=team->GetID() &&
        owner->HasPossession() && match->GetBall()->Predict(0).coords[2]<.8f;
      if(PlayerMatchEnabled() && match->GetBall()->Predict(0).coords[2]<.8f){
        std::vector<Player*> opponents;oppTeam->GetActivePlayers(opponents);
        const Vector3 ball=match->GetBall()->Predict(0);
        for(auto *opponent:opponents)if((ball-opponent->GetPosition()).Get2D().GetLength()<1.05f &&
            (ball-player->GetPosition()).Get2D().GetLength()>(ball-opponent->GetPosition()).Get2D().GetLength()+.15f &&
            match->GetBall()->GetMovement().GetLength()<opponent->GetMovement().GetLength()+3.f)enemyCarrier=true;
      }
      if (!enemyCarrier && (!PlayerMatchEnabled() || match->TrainingReceivingBall()) && (hid->GetButton(e_ButtonFunction_ShortPass) ||
          hid->GetButton(e_ButtonFunction_LongPass) || hid->GetButton(e_ButtonFunction_Shot))
        ) possessionContext = 1.0f;
      if(enemyCarrier)possessionContext=-1.f;
      const Vector3 incoming = match->GetBall()->Predict(500) - player->GetPosition();
      if (match->GetBall()->Predict(0).coords[2] > 1.2f && incoming.Get2D().GetLength() < 2.5f &&
          incoming.Get2D().GetLength() < (match->GetBall()->Predict(0) - player->GetPosition()).Get2D().GetLength())
        possessionContext = 1.0f;
    }
    if(match->IsInSetPiece() && team->GetController()->GetPieceTaker()==player)possessionContext=1.f;
    if (possessionContext < 0.0f) {
      bool allowPressure = true;
      bool allowSliding = true;
      bool allowTeamPressure = true;
      bool allowKeeperRush = true;

      if (match->IsInSetPiece()) {
        allowPressure = false;
        allowSliding = false;
        allowTeamPressure = false;
        allowKeeperRush = false;
      }

      if (hid->GetButton(e_ButtonFunction_Pressure) && !hid->GetPreviousButtonState(e_ButtonFunction_Pressure) && allowPressure) {
        actionMode = 1;
        actionButton = e_ButtonFunction_Pressure;
      }

      if (hid->GetButton(e_ButtonFunction_Sliding) && !hid->GetPreviousButtonState(e_ButtonFunction_Sliding) && allowSliding) { // we don't want high passes to turn into slidings
        actionMode = 1;
        actionButton = e_ButtonFunction_Sliding;
      }

      if (hid->GetButton(e_ButtonFunction_TeamPressure) && !hid->GetPreviousButtonState(e_ButtonFunction_TeamPressure) && allowTeamPressure) {
        actionMode = 1;
        actionButton = e_ButtonFunction_TeamPressure;
      }

      if (hid->GetButton(e_ButtonFunction_KeeperRush) && !hid->GetPreviousButtonState(e_ButtonFunction_KeeperRush) && allowKeeperRush) {
        actionMode = 1;
        actionButton = e_ButtonFunction_KeeperRush;
      }

    } else {

      bool allowShortPass = true;
      bool allowLongPass = true;
      bool allowHighPass = true;
      bool allowShot = true;

      if (team->GetController()->GetPieceTaker() == player && team->GetController()->GetSetPieceType() == e_SetPiece_ThrowIn) {
        allowHighPass = false;
        allowShot = false;
      }

      if (hid->GetButton(e_ButtonFunction_ShortPass) && !hid->GetPreviousButtonState(e_ButtonFunction_ShortPass) && allowShortPass) {
        actionMode = 2;
        actionButton = e_ButtonFunction_ShortPass;
      }

      if (hid->GetButton(e_ButtonFunction_LongPass) && !hid->GetPreviousButtonState(e_ButtonFunction_LongPass) && allowLongPass) {
        actionMode = 2;
        actionButton = e_ButtonFunction_LongPass;
      }

      if (hid->GetButton(e_ButtonFunction_HighPass) && !hid->GetPreviousButtonState(e_ButtonFunction_HighPass) && allowHighPass) {
        actionMode = 2;
        actionButton = e_ButtonFunction_HighPass;
      }

      if (hid->GetButton(e_ButtonFunction_Shot) && !hid->GetPreviousButtonState(e_ButtonFunction_Shot) && allowShot) {
        actionMode = 2;
        actionButton = e_ButtonFunction_Shot;
        shotChip=hid->GetButton(e_ButtonFunction_Switch);
      }

    }

  }

  if (actionMode == 2) {
    const Vector3 stick=hid->GetDirection();
    if(TrainingEnabled()) {
      // Seed even when the first tap precedes reception assistance. Later
      // taps must not reset a committed aim to an old exercise's direction.
      if(!actionCommitted && gauge_ms==0)actionAim=CastPlayer()->GetDirectionVec();
      if(match->TrainingReceivingBall() && stick.GetLength()>.001f)
        actionAim=match->GetTrainingAim(stick).GetNormalized(actionAim);
    }
    if (hid->GetButton(actionButton) && !actionCommitted) {
      if(actionButton==e_ButtonFunction_Shot && hid->GetButton(e_ButtonFunction_Switch))shotChip=true;
      gauge_ms += 10;
      gauge_ms = clamp(gauge_ms, 10, 1000);
      actionBufferTime_ms = 0;
    } else {
      // button released, stay in this actionMode until actionBufferTime_ms becomes too big
      actionBufferTime_ms += 10;
    }
  }

  if (!TrainingEnabled() && hid->GetButton(e_ButtonFunction_Switch) && hasPossession) team->GetController()->ApplyAttackingRun();

}

Vector3 HumanController::GetDirection() {
  Vector3 direction = CastPlayer()->GetDirectionVec();
  const Vector3 stick = hid->GetDirection();
  if(TrainingEnabled() && match->TrainingReceivingBall())
    return stick.GetLength()>.001f ? match->GetTrainingAim(stick).GetNormalized(direction) :
      (actionMode==2?actionAim:direction);
  return (TrainingEnabled() ? match->GetTrainingMovement(stick) : stick).GetNormalized(direction);
}

float HumanController::GetFloatVelocity() {
  Vector3 rawInputDirection;
  float rawInputVelocityFloat = 0;
  _GetHidInput(rawInputDirection, rawInputVelocityFloat);
  return rawInputVelocityFloat;
}

int HumanController::GetReactionTime_ms() {
  return IController::GetReactionTime_ms(); // already have human reaction time to contend with
}

void HumanController::Reset() {
  actionMode = 0;
  actionCommitted=false;
  turningPass=false;turningPassUntil=0;
  shotChip=false;
  gauge_ms = 0;
  actionButton = e_ButtonFunction_ShortPass;
  actionBufferTime_ms = 0;

  lastSwitchTime_ms = -10000;
  lastSwitchTimeDuration_ms = 300;

  lastSteadyDirectionSnapshotTime_ms = 0;
  steadyDirection = Vector3(0, -1, 0);
  previousDirection = Vector3(0, -1, 0);

  fadingTeamPossessionAmount = 1.0;
}

void HumanController::_GetHidInput(Vector3 &rawInputDirection, float &rawInputVelocityFloat) {
  rawInputDirection = hid->GetDirection();
  if (TrainingEnabled()) rawInputDirection = match->GetTrainingMovement(rawInputDirection);
  const float magnitude = rawInputDirection.GetLength();

  if (rawInputDirection.GetLength() < (TrainingEnabled() ? 0.001f : analogStickDeadzone)) {
    rawInputDirection = CastPlayer()->GetDirectionVec();
    rawInputVelocityFloat = idleVelocity;
  } else {
    if (hid->GetButton(e_ButtonFunction_Sprint)) rawInputVelocityFloat = sprintVelocity;
    else if (hid->GetButton(e_ButtonFunction_Dribble)) rawInputVelocityFloat = dribbleVelocity;
    else if (!TrainingEnabled() && hid->GetButton(e_ButtonFunction_Switch) && match->GetDesignatedPossessionPlayer() == CastPlayer()) rawInputVelocityFloat = idleVelocity;
    else rawInputVelocityFloat = walkVelocity;
    // Keep the imported gait linked to actual travel, rather than slowing
    // its pose clock independently and making planted shoes slide.
    if(TrainingEnabled())rawInputVelocityFloat*=clamp(GetConfiguration()->GetReal(
        hid->GetButton(e_ButtonFunction_Sprint)?"training_sprint_speed_scale":"training_walk_speed_scale",
        hid->GetButton(e_ButtonFunction_Sprint)?.90f:.72f),.55f,1.0f);
    if (TrainingEnabled()) rawInputVelocityFloat=football_input::movementSpeed(magnitude,hid->GetButton(e_ButtonFunction_Sprint),rawInputVelocityFloat,sprintVelocity*clamp(GetConfiguration()->GetReal("training_sprint_speed_scale",.90f),.55f,1.f));
    if(TrainingEnabled() && match->TrainingReceivingBall() && actionMode==0 && !player->GetHumanoid()->UpperReceptionActive())
      rawInputVelocityFloat=std::min(rawInputVelocityFloat,idleDribbleSwitch+.05f);
    // The native solver quantizes speeds below this boundary as idle. Keep
    // a light on-ball stick in its slow native gait instead of holding still.
    if(TrainingEnabled() && match->TrainingHasBall() && !match->TrainingReceivingBall() &&
        !hid->GetButton(e_ButtonFunction_Sprint) && rawInputVelocityFloat>.05f)
      rawInputVelocityFloat=std::max(rawInputVelocityFloat,.65f);
    assert(rawInputDirection.GetLength() > 0.001f);
    rawInputDirection.Normalize(); // hid should do this, but still
  }

  if (GetLastSwitchBias() > 0.0f) {
    float switchInfluence = 0.5f;
    float switchBias = pow(GetLastSwitchBias(), 0.7f);
    Vector3 currentMovement = player->GetDirectionVec() * player->GetFloatVelocity();
    Vector3 manualMovement = rawInputDirection * rawInputVelocityFloat;
    Vector3 resultMovement = currentMovement * switchBias * switchInfluence +
                             manualMovement * (1.0f - switchBias * switchInfluence);
    rawInputDirection = resultMovement.GetNormalized(rawInputDirection);
    rawInputVelocityFloat = resultMovement.GetLength();
  }

}
