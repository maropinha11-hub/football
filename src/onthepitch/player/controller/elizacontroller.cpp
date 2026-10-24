// Copyright 2019 Google LLC & Bastiaan Konings
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// written by bastiaan konings schuiling 2008 - 2015
// this work is public domain. the code is undocumented, scruffy, untested, and should generally not be used for anything important.
// i do not offer support, so don't ask. to be used for inspiration :)

#include "../../../main.hpp"

#include "elizacontroller.hpp"
#include "../../tactical_choices.hpp"
#include "../../physical_match_rules.hpp"

#include <cmath>

#include "../../AIsupport/mentalimage.hpp"
#include "../../AIsupport/AIfunctions.hpp"

#include "../humanoid/humanoid_utils.hpp"

#include "strategies/strategy.hpp"

#include "strategies/offtheball/default_def.hpp"
#include "strategies/offtheball/default_mid.hpp"
#include "strategies/offtheball/default_off.hpp"
#include "strategies/offtheball/goalie_default.hpp"
#include "../playerofficial.hpp"

ElizaController::ElizaController(Match *match) : PlayerController(match) {
  lastDesiredDirection = Vector3(0);
  lastDesiredVelocity = 0;
}

ElizaController::~ElizaController() {
  if (Verbose()) printf("exiting elizacontroller.. ");
  if (defenseStrategy) delete defenseStrategy;
  if (midfieldStrategy) delete midfieldStrategy;
  if (offenseStrategy) delete offenseStrategy;
  if (goalieStrategy) delete goalieStrategy;
  if (Verbose()) printf("done\n");
}

void ElizaController::RequestCommand(PlayerCommandQueue &commandQueue) {

  lastSwitchTimeDuration_ms = 0;
  lastSwitchTime_ms = 0;

  CastPlayer()->SetDesiredTimeToBall_ms(0);

  _CalculateSituation();

  _Preprocess(); // calculate some variables



  Player *carrier=match->GetLastTouchPlayer();
  if(PlayerMatchEnabled() && match->IsInPlay() && !match->IsInSetPiece() &&
     CastPlayer()->GetHumanoid()->PhysicalRigEnabled() && CastPlayer()->GetHumanoid()->PhysicalShielding() &&
     carrier && carrier->GetTeamID()!=team->GetID() && carrier->HasPossession() &&
     !carrier->GetHumanoid()->PhysicalRigBusy()){
    const Vector3 delta=(carrier->GetPosition()-player->GetPosition()).Get2D();
    if(delta.GetLength()<1.1f){
      // Remain beside the carrier and face the contest, instead of returning
      // to formation before the reaching hand can arrive.
      PlayerCommand brace;brace.desiredFunctionType=e_FunctionType_Movement;
      brace.useDesiredMovement=brace.useDesiredLookAt=true;
      brace.desiredDirection=delta.GetNormalized(player->GetBodyDirectionVec());
      brace.desiredVelocityFloat=clamp((delta.GetLength()-.70f)*4.f,0.f,walkVelocity);
      brace.desiredLookAt=carrier->GetPosition().Get2D();
      lastDesiredDirection=brace.desiredDirection;lastDesiredVelocity=brace.desiredVelocityFloat;
      _SetInput(lastDesiredDirection,lastDesiredVelocity);commandQueue.push_back(brace);return;
    }
  }

  if(PlayerMatchEnabled() && (match->IsInSetPiece() || match->GetReferee()->WaitingForRestart())){
    const auto &restart=match->GetRefereeBuffer();
    const bool movingRestart=restart.desiredSetPiece==e_SetPiece_Corner||restart.desiredSetPiece==e_SetPiece_FreeKick||restart.desiredSetPiece==e_SetPiece_ThrowIn||restart.desiredSetPiece==e_SetPiece_GoalKick;
    if(movingRestart && restart.active && match->GetActualTime_ms()>=restart.prepareTime &&
       !match->GetReferee()->IsRestartTaker(player)){
      if(restartMovementStamp!=restart.prepareTime){restartMovementStamp=restart.prepareTime;restartMovementAnchor=player->GetPosition();}
      const float phase=(match->GetActualTime_ms()-restart.prepareTime)*.001f+player->GetID()*.71f;
      const bool attacking=team->GetID()==restart.teamID;
      const bool keeper=CastPlayer()->GetFormationEntry().role==e_PlayerRole_GK;
      const float range=keeper?.18f:attacking?1.9f:1.1f;
      Vector3 target=restartMovementAnchor+Vector3(std::sin(phase*.9f)*range,std::sin(phase*.65f+.8f)*range,0);
      const Vector3 away=(target-restart.restartPos).Get2D();
      const float exclusion=attacking?1.8f:restart.desiredSetPiece==e_SetPiece_ThrowIn?2.1f:9.25f;
      if(away.GetLength()<exclusion)target=restart.restartPos+away.GetNormalized(player->GetDirectionVec())*exclusion;
      target.coords[0]=clamp(target.coords[0],-pitchHalfW+.3f,pitchHalfW-.3f);target.coords[1]=clamp(target.coords[1],-pitchHalfH+.3f,pitchHalfH-.3f);
      const Vector3 delta=(target-player->GetPosition()).Get2D();
      PlayerCommand move;move.desiredFunctionType=e_FunctionType_Movement;move.useDesiredMovement=move.useDesiredLookAt=true;
      move.desiredDirection=delta.GetNormalized(player->GetDirectionVec());move.desiredVelocityFloat=delta.GetLength()>.32f?std::min(2.25f,delta.GetLength()*2.f):0;
      move.desiredLookAt=restart.restartPos.Get2D();commandQueue.push_back(move);
      if(GetConfiguration()->GetBool("training_telemetry",false)&&(match->GetActualTime_ms()+player->GetID()*10)%300==0)
        printf("RESTART_RUN t=%lu actor=%d attacking=%d speed=%.5f ball_gap=%.5f\n",match->GetActualTime_ms(),player->GetID(),attacking?1:0,move.desiredVelocityFloat,(player->GetPosition()-restart.restartPos).Get2D().GetLength());
      return;
    }
  }
  FormationEntry entry = CastPlayer()->GetDynamicFormationEntry();
  float mindSet = AI_GetMindSet(entry.role);


  // input

  Vector3 rawInputDirection = player->GetDirectionVec();
  float rawInputVelocityFloat = idleVelocity;
  Vector3 manualMovementDirection = player->GetDirectionVec();
  float manualMovementVelocityFloat = idleVelocity;

  bool manualMovement = false;
  bool extraHaste = false;


  // celebrate good times come on!

  if (!match->IsInPlay() && match->IsGoalScored()) {
    _AddCelebration(commandQueue);
    return;
  }


  // look at referee

  else if (!match->IsInPlay() && match->GetReferee()->GetBuffer().active == true &&
           (match->GetReferee()->GetCurrentFoulType() == 2 || match->GetReferee()->GetCurrentFoulType() == 3) &&
           match->GetReferee()->GetBuffer().stopTime < match->GetActualTime_ms() - 1000 &&
           match->GetReferee()->GetBuffer().prepareTime > match->GetActualTime_ms()) {

    // look at referee
    PlayerCommand command;
    command.desiredFunctionType = e_FunctionType_Movement;
    command.useDesiredMovement = true;
    command.useDesiredLookAt = true;
    command.desiredDirection = CastPlayer()->GetDirectionVec();
    assert(command.desiredDirection.coords[2] == 0.0f);
    command.desiredVelocityFloat = idleVelocity;
    command.desiredLookAt = match->GetOfficials()->GetReferee()->GetPosition();
    commandQueue.push_back(command);

    return;
  }


  // stand still

  else if (!match->IsInPlay()) { // this whole if/then/else structure is ugly and unclear

    PlayerCommand command;
    command.desiredFunctionType = e_FunctionType_Movement;
    command.useDesiredMovement = true;
    if (match->GetBallRetainer() == player) {
      command.desiredDirection = (Vector3(0) - player->GetPosition()).GetNormalized(player->GetDirectionVec());
    } else {
      command.desiredDirection = player->GetDirectionVec();
    }
    command.desiredVelocityFloat = idleVelocity;
    if (!match->IsInSetPiece()) {
      command.desiredDirection = (player->GetDirectionVec() * 0.6f + (Vector3(0) - player->GetPosition()).GetNormalized(player->GetDirectionVec()) * 0.4f).GetNormalized(player->GetDirectionVec());
      command.desiredVelocityFloat = ClampVelocity(player->GetFloatVelocity() * 0.95f - random(0.0f, 3.2f));
    }
    command.useDesiredLookAt = true;
    command.desiredLookAt = player->GetPosition() + (match->GetBall()->Predict(0).Get2D() - player->GetPosition()).GetNormalized(command.desiredDirection) * 10.0f;
    commandQueue.push_back(command);

    return;
  }


  // set piece taking

  else if ((match->IsInSetPiece() && team->GetController()->GetPieceTaker() == player) || match->GetBallRetainer() == player) {

    PlayerCommand actionCommand;

    if (team->GetController()->GetSetPieceType() == e_SetPiece_Penalty) {

      actionCommand.desiredFunctionType = e_FunctionType_Shot;
      actionCommand.useDesiredMovement = false;
      actionCommand.useDesiredLookAt = false;
      actionCommand.touchInfo.desiredDirection = (Vector3(-team->GetSide() * pitchHalfW, random(-5, 5), 0) - CastPlayer()->GetPosition()).GetNormalized(Vector3(-team->GetSide(), 0, 0));
      actionCommand.touchInfo.desiredPower = random(0.4f, 1.0f);
      commandQueue.push_back(actionCommand);

    } else {

      actionCommand.desiredFunctionType = e_FunctionType_ShortPass;
      actionCommand.useDesiredMovement = false;
      actionCommand.useDesiredLookAt = false;
      actionCommand.touchInfo.inputDirection = player->GetDirectionVec();
      actionCommand.touchInfo.inputPower = 0.5f;
      actionCommand.touchInfo.autoDirectionBias = 1.0f;
      actionCommand.touchInfo.autoPowerBias = 1.0f;

      actionCommand.touchInfo.forcedTargetPlayer = 0;

      Vector3 desiredTargetPosition;
      bool doCommand = true;

      if (team->GetController()->GetSetPieceType() == e_SetPiece_GoalKick) {
        if (random(0.0f, 1.0f) > 0.4f && (team->GetHumanGamerCount() == 0 || PlayerMatchEnabled())) {
          actionCommand.desiredFunctionType = e_FunctionType_HighPass;
          desiredTargetPosition = Vector3((pitchHalfW * -team->GetSide()) * 0.2f, random(-pitchHalfH, pitchHalfH), 0.0f);
        } else {
          actionCommand.desiredFunctionType = e_FunctionType_ShortPass;
          desiredTargetPosition = Vector3(player->GetPosition().coords[0] * 0.9f, random(-pitchHalfH, pitchHalfH), 0.0f);
        }

      } else if (team->GetController()->GetSetPieceType() == e_SetPiece_KickOff) {
        actionCommand.desiredFunctionType = e_FunctionType_ShortPass;
        desiredTargetPosition = player->GetPosition() + player->GetDirectionVec() * 1.0f;

      } else if (team->GetController()->GetSetPieceType() == e_SetPiece_FreeKick) {
        if (random(0.0f, 1.0f) > 0.5f) {
          actionCommand.desiredFunctionType = e_FunctionType_HighPass;
          desiredTargetPosition = Vector3(pitchHalfW * -team->GetSide(), random(-10.0f, 10.0f), 0.0f);
        } else {
          actionCommand.desiredFunctionType = e_FunctionType_ShortPass;
          desiredTargetPosition = player->GetPosition() + Vector3(-team->GetSide() * 10.0f, random(-10.0f, 10.0f), 0.0f);
        }

      } else if (team->GetController()->GetSetPieceType() == e_SetPiece_Corner) {
        if (random(0.0f, 1.0f) > 0.3f) {
          actionCommand.desiredFunctionType = e_FunctionType_HighPass;
          desiredTargetPosition = Vector3((pitchHalfW * -team->GetSide()) * (0.99f - random(0.0f, 0.12f)), random(-10.0f, 10.0f), 0.0f);
        } else {
          actionCommand.desiredFunctionType = e_FunctionType_ShortPass;
          desiredTargetPosition = Vector3((pitchHalfW * -team->GetSide()) * 0.8f, player->GetPosition().coords[1] * 0.8f, 0.0f);
        }

      } else if (team->GetController()->GetSetPieceType() == e_SetPiece_ThrowIn) {
        actionCommand.desiredFunctionType = e_FunctionType_ShortPass;
        desiredTargetPosition = player->GetPosition(); // closest to player

      } else if (match->GetBallRetainer() == player) { // keeper fetched ball, probably
        actionCommand.desiredFunctionType = e_FunctionType_HighPass;
        desiredTargetPosition = Vector3(pitchHalfW * team->GetSide(), random(-pitchHalfH, pitchHalfH), 0.0f);
        Player *targetPlayer = AI_GetClosestPlayer(team, desiredTargetPosition, false, CastPlayer());

        if (targetPlayer) {
          // check if this player is away from opponents, before throwing ball to him
          Player *closestOpp = AI_GetClosestPlayer(match->GetTeam(abs(team->GetID() - 1)), targetPlayer->GetPosition(), false, 0);
          if (closestOpp) {
            if (((closestOpp->GetPosition() + closestOpp->GetMovement() * 0.1f) - targetPlayer->GetPosition()).GetLength() > 10.0f || CastPlayer()->GetPossessionDuration_ms() > 4000) { // last touch bias is maximum so he won't hold forever
              actionCommand.touchInfo.forcedTargetPlayer = targetPlayer;
            } else {
              doCommand = false;
            }
          }
        }
      }

      if (doCommand) {
        if (actionCommand.touchInfo.forcedTargetPlayer == 0) actionCommand.touchInfo.forcedTargetPlayer = AI_GetClosestPlayer(team, desiredTargetPosition, false, CastPlayer());
        AI_GetPass(CastPlayer(), actionCommand.desiredFunctionType, actionCommand.touchInfo.inputDirection, actionCommand.touchInfo.inputPower, actionCommand.touchInfo.autoDirectionBias, actionCommand.touchInfo.autoPowerBias, actionCommand.touchInfo.desiredDirection, actionCommand.touchInfo.desiredPower, actionCommand.touchInfo.targetPlayer, actionCommand.touchInfo.forcedTargetPlayer);
        commandQueue.push_back(actionCommand);
      }
    }

    // remember, we are still in the 'set piece / ballretainer' if{}

    if (match->GetBallRetainer() != player) { // must be set piece taker, then
      PlayerCommand command;
      command.desiredFunctionType = e_FunctionType_Movement;
      command.useDesiredMovement = true;
      command.useDesiredLookAt = true;

      AI_GetBallControlMovement(_mentalImage, CastPlayer(), player->GetDirectionVec(), walkVelocity, command.desiredDirection, command.desiredVelocityFloat, command.desiredLookAt);
      assert(command.desiredDirection.coords[2] == 0.0f);

      commandQueue.push_back(command);
      return;
    } else { // must be ball retainer
      PlayerCommand command;
      command.desiredFunctionType = e_FunctionType_Movement;
      command.useDesiredMovement = true;
      command.desiredDirection = (actionCommand.touchInfo.desiredDirection.GetLength() > 0.0f) ? actionCommand.touchInfo.desiredDirection.Get2D().GetNormalized(player->GetDirectionVec()) : (Vector3(0) - player->GetPosition()).GetNormalized(player->GetDirectionVec());
      command.desiredVelocityFloat = idleVelocity;
      command.useDesiredLookAt = true;
      command.desiredLookAt = player->GetPosition() + command.desiredDirection * 10.0f;
      commandQueue.push_back(command);
      if (team->GetController()->GetSetPieceType() == e_SetPiece_ThrowIn) {
        //printf("elizacontroller throw in doCommand (green pilon == target)\n");
        //SetGreenDebugPilon(command.desiredLookAt);
      }
      return;
    }

  }


  // default strategies for defensively, midfielders and offensively positioned players

  else if (match->IsInPlay() && !match->IsInSetPiece() && match->GetBallRetainer() != player && match->GetDesignatedPossessionPlayer() != player && CastPlayer()->GetFormationEntry().role != e_PlayerRole_GK) { //(match->GetDesignatedPossessionPlayer() != player || (CastPlayer()->GetFormationEntry().role == e_PlayerRole_GK && !CastPlayer()->HasPossession()))) {
    if      (CastPlayer()->GetFormationEntry().role == e_PlayerRole_LB ||
             CastPlayer()->GetFormationEntry().role == e_PlayerRole_CB ||
             CastPlayer()->GetFormationEntry().role == e_PlayerRole_RB) {
      defenseStrategy->RequestInput(_mentalImage, rawInputDirection, rawInputVelocityFloat);
    }
    else if (CastPlayer()->GetFormationEntry().role == e_PlayerRole_DM ||
             CastPlayer()->GetFormationEntry().role == e_PlayerRole_LM ||
             CastPlayer()->GetFormationEntry().role == e_PlayerRole_CM ||
             CastPlayer()->GetFormationEntry().role == e_PlayerRole_RM ||
             CastPlayer()->GetFormationEntry().role == e_PlayerRole_AM) {
      midfieldStrategy->RequestInput(_mentalImage, rawInputDirection, rawInputVelocityFloat);
    }
    else if (CastPlayer()->GetFormationEntry().role == e_PlayerRole_CF) {
      offenseStrategy->RequestInput(_mentalImage, rawInputDirection, rawInputVelocityFloat);
    }

  }

  // dribble, pass, etcetera
  // In fixed-player matches, possession no longer switches the human onto
  // the ball carrier. CPU teammates must make the same decisions as opponents.
  else if (match->IsInPlay() && !match->IsInSetPiece() && match->GetDesignatedPossessionPlayer() == player && (team->GetHumanGamerCount() == 0 || PlayerMatchEnabled()) && CastPlayer()->GetFormationEntry().role != e_PlayerRole_GK) {
    if (CastPlayer()->GetTimeNeededToGetToBall_ms() < 1000) {
      GetOnTheBallCommands(commandQueue, rawInputDirection, rawInputVelocityFloat);
    }
    extraHaste = false; // todo: extra haste when touch anim is queued?
  }

  else if (match->IsInPlay() && !match->IsInSetPiece() && CastPlayer()->GetFormationEntry().role == e_PlayerRole_GK) {
    // keeper's mental image for deflections is near-instant; let's just call it premonition ;)
    const MentalImage *keeperMentalImage = PlayerMatchEnabled()?match->GetMentalImage(0):_mentalImage;
    static_cast<GoalieDefaultStrategy*>(goalieStrategy)->CalculateIfBallIsBoundForGoal(keeperMentalImage);
    bool boundForGoal = static_cast<GoalieDefaultStrategy*>(goalieStrategy)->IsBallBoundForGoal();
    if (boundForGoal) manualMovement = true;
    if (CastPlayer() != match->GetDesignatedPossessionPlayer()) manualMovement = true;
    goalieStrategy->RequestInput(keeperMentalImage, manualMovementDirection, manualMovementVelocityFloat);
    if(PlayerMatchEnabled()){manualMovement=true;_SetInput(manualMovementDirection,manualMovementVelocityFloat);}
    Player *last=match->GetLastTouchPlayer();
    if(PlayerMatchEnabled()&&last&&last!=player&&last->GetTeamID()==team->GetID()&&last->GetLastTouchType()==e_TouchType_Intentional_Kicked){
      _TrapCommand(commandQueue,false,false);
      _BallControlCommand(commandQueue,false,false);
      if(boundForGoal&&(match->GetBall()->Predict(150)-player->GetPosition()).Get2D().GetLength()<2.3f&&match->GetBall()->Predict(150).coords[2]<.65f){
        PlayerCommand block;block.desiredFunctionType=e_FunctionType_Interfere;block.useDesiredMovement=block.useDesiredLookAt=false;
        commandQueue.push_back(block);
      }
    }

    //if (boundForGoal && hasUniquePossession) printf("has unique possession, so no deflect anims (poss: %f)\n", possessionAmount);
    if (!hasUniquePossession || possessionAmount < 3.4f) {
      bool onlyPickupAnims = false;
      if (!boundForGoal && possessionAmount > 1.3f) onlyPickupAnims = true;
      _KeeperDeflectCommand(commandQueue, onlyPickupAnims);
    }

    if (CastPlayer()->GetTimeNeededToGetToBall_ms() < 1000 && match->GetDesignatedPossessionPlayer() == player) {
      GetOnTheBallCommands(commandQueue, rawInputDirection, rawInputVelocityFloat);
    }
  }

  bool forceMagnet = false;

  // team pressure
  float ballDistance = _mentalImage->GetBallPrediction(0).Get2D().GetDistance(player->GetPosition());
  if (match->IsInPlay() && !match->IsInSetPiece() &&
      ((team->GetController()->GetEndApplyTeamPressure_ms() > match->GetActualTime_ms() && team->GetController()->GetTeamPressurePlayer() == player) /*|| (player == team->GetDesignatedTeamPossessionPlayer() && ballDistance < 8.0f && CastPlayer()->GetManMarkingID() == -1) */) &&
      !teamHasBestPossession && match->GetDesignatedPossessionPlayer() != player && CastPlayer()->GetFormationEntry().role != e_PlayerRole_GK) {
    forceMagnet = true;
  }

  _SetInput(rawInputDirection, rawInputVelocityFloat);
  if (rawInputDirection.GetLength() != 0) lastDesiredDirection = rawInputDirection; else
                                          lastDesiredDirection = player->GetDirectionVec();
  lastDesiredVelocity = rawInputVelocityFloat;

  if (match->IsInPlay() && !match->IsInSetPiece()) {

    _QueueAerialDuel(commandQueue);
    // ball control?
    _BallControlCommand(commandQueue, false, false, false); // last param true == enable sticky run direction.

    // trap?
    _TrapCommand(commandQueue);

    // interfere?
    bool byAnyMeans = false;
    _InterfereCommand(commandQueue, byAnyMeans);

    // sliding?
    _SlidingCommand(commandQueue);
  }

  // movement
  if (!manualMovement && match->IsInPlay() && !match->IsInSetPiece()) {

    Player *opp = match->GetTeam(abs(team->GetID() - 1))->GetDesignatedTeamPossessionPlayer();

    if (CastPlayer() != match->GetDesignatedPossessionPlayer()) {

      float mindSet = AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role);
      float huntDistanceThreshold = 10.0f + (1.0f - mindSet) * 10.0f; // 10 + .. * 10
      huntDistanceThreshold *= 0.5f * CastPlayer()->GetFatigueFactorInv() +
                               0.5f * (1.0f - NormalizedClamp(CastPlayer()->GetAverageVelocity(10), idleVelocity, sprintVelocity));
      huntDistanceThreshold *= 0.3f + GetMatch()->GetMatchDifficulty() * 0.7f;

      if (forceMagnet) {

        // make sure the movement command magnets get the best input (which is then used as 'hint' for the 'toball' functions)

        inputDirection = Vector3(team->GetSide() * pitchHalfW, 0, 0) - CastPlayer()->GetPosition();
        inputVelocityFloat = idleVelocity;
        inputDirection.Normalize(CastPlayer()->GetDirectionVec());

      } else if (!teamHasBestPossession && CastPlayer()->GetManMarkingID() == -1 && ((opp->GetPosition() + opp->GetMovement() * 0.12f) - (CastPlayer()->GetPosition() + CastPlayer()->GetMovement() * 0.04f)).GetLength() < huntDistanceThreshold) { // defend player

          if (player == team->GetDesignatedTeamPossessionPlayer() && possessionAmount > 0.8f) {
            forceMagnet = true; // don't give up battles too easily
            extraHaste = true;
          }

          // or, defend an opponent, if we don't have anything better to do anyway

          Player *opp = match->GetTeam(abs(team->GetID() - 1))->GetDesignatedTeamPossessionPlayer();

          int huntingPlayersNum = 2; // remember, this includes players with man marking id that are not controlled by this hunting code
          std::vector<Player*> closestPlayers;
          AI_GetClosestPlayers(team, opp->GetPosition() + opp->GetMovement() * 0.1f, false, closestPlayers, huntingPlayersNum);
          bool close = false;
          for (unsigned int i = 0; i < closestPlayers.size(); i++) {
            if (closestPlayers.at(i) == player) {
              close = true;
              break;
            }
          }

          if (close) {

            /*
            // 'easy off' method
            Vector3 defendPosition_easy = CastPlayer()->GetPosition();
            AddDefensiveComponent(defendPosition_easy, 1.0f, opp->GetID());
            inputDirection = (defendPosition - CastPlayer()->GetPosition()).GetNormalized(inputDirection);
            inputVelocityFloat = clamp((defendPosition - CastPlayer()->GetPosition()).GetLength() * distanceToVelocityMultiplier, 0.0f, sprintVelocity);
            //forceMagnet = true; // more aggressive!
            */

            // more 'hunting' method
            Vector3 defendPosition = GetDefendPosition(opp);
            if (NeedDefendingMovement(team->GetSide(), player->GetPosition(), defendPosition)) {
              inputDirection = (defendPosition - CastPlayer()->GetPosition()).GetNormalized(inputDirection);
              inputVelocityFloat = clamp((defendPosition - CastPlayer()->GetPosition()).GetLength() * distanceToVelocityMultiplier, 0.0f, sprintVelocity);
              forceMagnet = true; // more aggressive!
            }

          } // close

      } // else (!forceMagnet)

    } // !designated

    inputVelocityFloat = RangeVelocity(inputVelocityFloat); // emulate controller quantization

    _MovementCommand(commandQueue, forceMagnet, extraHaste);

  } else { // keeper?

    PlayerCommand command;
    command.desiredFunctionType = e_FunctionType_Movement;
    command.useDesiredMovement = true;
    command.desiredDirection = manualMovementDirection;
    assert(command.desiredDirection.coords[2] == 0.0f);
    command.desiredVelocityFloat = manualMovementVelocityFloat;
    command.useDesiredLookAt = true;
    command.desiredLookAt = player->GetPosition() + (_mentalImage->GetBallPrediction(40).Get2D() - player->GetPosition()).GetNormalized(0) * 10.0f;
    commandQueue.push_back(command);

  }
}

void ElizaController::Process() {
  PlayerController::Process();
}

Vector3 ElizaController::GetDirection() {
  return lastDesiredDirection;
}

float ElizaController::GetFloatVelocity() {
  return lastDesiredVelocity;
}

void ElizaController::LoadStrategies() {
  defenseStrategy = new DefaultDefenseStrategy(this);
  midfieldStrategy = new DefaultMidfieldStrategy(this);
  offenseStrategy = new DefaultOffenseStrategy(this);
  goalieStrategy = new GoalieDefaultStrategy(this);
}

bool PreRatingSortFunc(const PreRating &a, const PreRating &b) {
  return a.totalRating > b.totalRating;
}

bool SortPlayersDeepestFirst(Player *a, Player *b) {
  return a->GetPosition().coords[0] * a->GetTeam()->GetSide() < b->GetPosition().coords[0] * b->GetTeam()->GetSide();
}

float ElizaController::GetLazyVelocity(float desiredVelocityFloat) {

  // input is unclamped! use large values (less lazy, apparently we are more off-position)
  float adaptedDesiredVelocityFloat = desiredVelocityFloat;
  // don't use full overflow though
  if (adaptedDesiredVelocityFloat > sprintVelocity) adaptedDesiredVelocityFloat = sprintVelocity + (adaptedDesiredVelocityFloat - sprintVelocity) * 0.1f;

  float startLazinessDistance = 20.0f * (CastPlayer()->GetFatigueFactorInv() * 0.8f + 0.2f);
  float endLazinessDistance = 65.0f * (CastPlayer()->GetFatigueFactorInv() * 0.5f + 0.5f);

  Vector3 oppPos = match->GetTeam(abs(team->GetID() - 1))->GetDesignatedTeamPossessionPlayer()->GetPosition();
  float actionDistance = (player->GetPosition() - oppPos).GetLength();
  float teamPossession = clamp(GetFadingTeamPossessionAmount() - 0.5f, 0.0f, 1.0f);
  float mindSet = AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role);

  // if mindSet is high (offensive), be lazy when teamPossession is low. and the other way round for defenders.
  // (midfielders are always half-lazy by role this way; pow() them a bit if this is undesired; this will of course wear them out more than backs and strikers)
  float lazinessByRole = mindSet + teamPossession * (1.0f - mindSet * 2.0f);
  float lazinessByPosition = NormalizedClamp(actionDistance, startLazinessDistance, endLazinessDistance);

  float lazyFactor = lazinessByPosition * (0.5f + lazinessByRole * 0.5f);
  float resultingVelocityFloat = adaptedDesiredVelocityFloat * (1.0f - lazyFactor);

  bool clampToDribble = false;
  if (desiredVelocityFloat >= dribbleVelocity) clampToDribble = true; // no standing still when initially undesired; it would get us further and further away from our desired position *edit: no longer true with the unclamped input
  if (clampToDribble && resultingVelocityFloat < dribbleVelocity) resultingVelocityFloat = dribbleVelocity;

  // short term fatigue/work rate shortage ;)
  // does not heed dribble clamp above, as to simulate players having to stop to catch their breath
  float breathLeftFactor = 1.0f - NormalizedClamp(CastPlayer()->GetAverageVelocity(10), idleVelocity, sprintVelocity);
  float workRate = CastPlayer()->GetStat("mental_workrate");
  breathLeftFactor = std::pow(breathLeftFactor, 0.8f - workRate * 0.2f);
  breathLeftFactor = clamp(breathLeftFactor * 1.2f, 0.0f, 1.0f); // make sure beginning of sprint is full speed
  breathLeftFactor = breathLeftFactor * lazyFactor + 1.0f * (1.0f - lazyFactor); // sometimes, we really need to force it
  resultingVelocityFloat = std::min(resultingVelocityFloat, sprintVelocity * breathLeftFactor);
  if(PlayerMatchEnabled()){
    // Recover away from the immediate contest instead of sprinting every
    // support run. The current carrier still uses native tactical choices.
    const bool possession=team->HasPossession();
    const bool urgent=CastPlayer()->GetTimeNeededToGetToBall_ms()<700||actionDistance<8.f;
    if(!urgent&&player->GetSprintEnergy()<.55f)resultingVelocityFloat=std::min(resultingVelocityFloat,possession?3.4f:4.1f);
    resultingVelocityFloat=std::min(resultingVelocityFloat,player->GetMaxVelocity());
  }

  return resultingVelocityFloat;
}

Vector3 ElizaController::GetSupportPosition(const MentalImage *mentalImage, const Vector3 &basePosition) {

  float offenseWeight = 0.8f + (AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role)) * clamp((GetFadingTeamPossessionAmount() - 0.5f) * 2.0f, 0.0f, 1.0f);
  float distanceWeight = 1.0f;
  float passWeight = 0.8f;
  float movementWeight = 1.5f;
  float formationWeight = 1.6f + clamp((CastPlayer()->GetPosition() - mentalImage->GetBallPrediction(100).Get2D()).GetLength() / 30.0f, 0.0, 1.0f);
  float offsideWeight = 10.0f;

  Vector3 playerPos = player->GetPosition() + player->GetMovement() * 0.1f; // + physics slowness


  // get closest opponents

  std::vector<Player*> opponents;
  std::vector<PlayerImage> opponentImages;
  AI_GetClosestPlayers(match->GetTeam(abs(team->GetID() - 1)), playerPos, false, opponents, 4);
  for (unsigned int i = 0; i < opponents.size(); i++) {
    PlayerImage oppImage = mentalImage->GetPlayerImage(opponents.at(i)->GetID());
    oppImage.position += oppImage.movement * 0.15f;
    opponentImages.push_back(oppImage);
  }


  // add candidate positions

  std::vector<Vector3> candidatePositions;
  candidatePositions.push_back(playerPos);
  float step = (2 * pi) / 12.0f;
  Vector3 pos;
  for (float rad = 0; rad < 2 * pi; rad += step) {
    pos.coords[0] = cos(rad);
    pos.coords[1] = sin(rad);
    candidatePositions.push_back(playerPos + pos * dribbleVelocity);
    candidatePositions.push_back(playerPos + pos * walkVelocity);
    candidatePositions.push_back(playerPos + pos * sprintVelocity);
  }


  // rate candidates

  Vector3 goalPos = Vector3(-team->GetSide() * pitchHalfW, playerPos.coords[1] * 0.8f, 0); // y element is because goal is wider than 0
  float goalDistance = fabs((goalPos - playerPos).GetLength() - 5.0f); // and not all too close
  float ballDistance = (playerPos - mentalImage->GetBallPrediction(100).Get2D()).GetLength();
  float formationDistance = (basePosition - playerPos).GetLength();
  float offside = AI_GetOffsideLine(match, mentalImage, abs(team->GetID() - 1));

  float passRating; // are opponents blocking pass space to this position?

  float bestRating = 0;
  int bestCandidate = 0;

  std::vector<PreRating> preRatings;

  for (unsigned int i = 0; i < candidatePositions.size(); i++) {

    if (fabs(candidatePositions.at(i).coords[0]) < pitchHalfW && fabs(candidatePositions.at(i).coords[1]) < pitchHalfH) {
      PreRating preRating;
      preRating.candidateID = i;

      // offense rating
      preRating.offenseRating = clamp((goalDistance - fabs((goalPos - candidatePositions.at(i)).GetLength() - 5.0)) / sprintVelocity * 0.5 + 0.5, 0.0, 1.0);

      // distance rating
      float candidateBallDistance = (candidatePositions.at(i) - mentalImage->GetBallPrediction(100).Get2D()).GetLength();
      float desiredBallDistance = 10.0f;
      // too close is bad as well..
      if (candidateBallDistance < desiredBallDistance) candidateBallDistance = desiredBallDistance + fabs(candidateBallDistance - desiredBallDistance);
      float candidateBallVsBallDistance = (ballDistance - candidateBallDistance);

      preRating.distanceRating = clamp((candidateBallVsBallDistance / sprintVelocity) * 0.5f + 0.5f, 0.0f, 1.0f);

      // movement rating
      preRating.movementRating = 1.0 - clamp((player->GetMovement() - (candidatePositions.at(i) - playerPos)).GetLength() / (2 * sprintVelocity), 0.0, 1.0);

      // formation rating
      preRating.formationRating = clamp(((formationDistance - (basePosition - candidatePositions.at(i)).GetLength()) / sprintVelocity) * 0.5 + 0.5, 0.0, 1.0);

      // offside rating
      bool isOffside = false;
      if (candidatePositions.at(i).coords[0] * -team->GetSide() >= offside * -team->GetSide()) isOffside = true;
      preRating.offsideRating = isOffside ? 0.0 : 1.0;

      preRating.totalRating = preRating.offenseRating * offenseWeight + preRating.distanceRating * distanceWeight + preRating.movementRating * movementWeight + preRating.formationRating * formationWeight + preRating.offsideRating * offsideWeight;

      // small bonus for 'current position'
      if (i == 0) preRating.totalRating += 0.1f;

      preRatings.push_back(preRating);
    }
  }

  std::sort(preRatings.begin(), preRatings.end(), PreRatingSortFunc);

  for (unsigned int i = 0; i < preRatings.size() / 3; i++) {

    const PreRating &preRating = preRatings.at(i);
    int candidateID = preRating.candidateID;

    // pass rating
    passRating = 1.0;
    Vector3 checkPosition = candidatePositions.at(candidateID) + (mentalImage->GetBallPrediction(240).Get2D() - candidatePositions.at(candidateID)).GetNormalized(0) * 2.0f;
    for (unsigned int o = 0; o < opponentImages.size(); o++) {
      float oppDist = pow(clamp((opponentImages.at(o).position - checkPosition).GetLength() / 8.0f, 0.0f, 1.0f), 1.2f); // 0 .. 1 == worst, best
      if (oppDist < passRating) passRating = oppDist;
    }

    // total rating
    float totalRating = preRating.totalRating + passRating * passWeight;
    if (totalRating > bestRating) {
      bestRating = totalRating;
      bestCandidate = candidateID;
    }

  }

  Vector3 result = candidatePositions.at(bestCandidate);

  return result;
}

Vector3 ElizaController::GetSupportPosition_ForceField(const MentalImage *mentalImage, const Vector3 &basePosition, bool makeRun) {

  Player *designatedPlayer = team->GetDesignatedTeamPossessionPlayer();

  Vector3 currentPos = player->GetPosition() + CastPlayer()->GetMovement() * 0.1f; //basePosition;
  Vector3 mainManPos = designatedPlayer->GetPosition() + designatedPlayer->GetMovement() * 0.1f;

  std::vector<ForceSpot> forceField;


  // support position

  float dynamicMindSet = AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role);
  float ballDistance = (match->GetBall()->Predict(250).Get2D() - player->GetPosition()).GetLength();
  float ballDistanceX = fabs(match->GetBall()->Predict(250).coords[0] - player->GetPosition().coords[0]);

  bool forceNoOffside = true;

  float basePositionWeight = 0.7f;
  float overallWeight = 1.0f;
  float opponentRepelWeight = 0.3f * overallWeight;
  float teammateRepelWeight = 0.4f * overallWeight;
  float ballRepelWeight = 1.0f * overallWeight;
  float runWeight = 1.0f * overallWeight;
  float flockToPossessionPlayerWeight = 0.45f * overallWeight;

  float webScale = 0.75f;

  switch (CastPlayer()->GetDynamicFormationEntry().role) {
    case e_PlayerRole_CB:
    case e_PlayerRole_LB:
    case e_PlayerRole_RB:
      opponentRepelWeight *= 2.2f;
      break;
    case e_PlayerRole_DM:
      opponentRepelWeight *= 2.0f;
      break;
    case e_PlayerRole_CM:
    case e_PlayerRole_LM:
    case e_PlayerRole_RM:
      opponentRepelWeight *= 1.6f;
      break;
    case e_PlayerRole_AM:
      opponentRepelWeight *= 1.2f;
      break;
    case e_PlayerRole_CF:
      opponentRepelWeight *= 1.0f;
      break;
    default:
      break;
  }

  float offsideX = AI_GetOffsideLine(match, _mentalImage, abs(team->GetID() - 1), 240);
  float adaptedMakeRun = makeRun;

  // actual base position
  {
    ForceSpot spot;
    spot.origin = basePosition;

    // let left and right flank flow forwards and backwards every period_sec seconds, for some dynamics
    // except for one close player, who should always run forward for support
    Player *forwardSupportPlayer = team->GetController()->GetForwardSupportPlayer();
    if (player == forwardSupportPlayer) {
      spot.origin.coords[0] += -team->GetSide() * (0.3f + 0.7f * dynamicMindSet) * 12.0f;
    } else {
      /* sine version
      float amount = 8.0f;//14.0f;//8.0f;
      float period_sec = 7.0f;
      float phase_offset = NormalizedClamp(currentPos.coords[1], -pitchHalfH, pitchHalfH);
      amount *= sin(match->GetActualTime_ms() * 0.001f * ((1.0f / period_sec) * 2.0f * pi) + (phase_offset * 2.0f * pi)) * 0.5f + 0.5f;
      float delta = -team->GetSide() * curve(dynamicMindSet, 0.5f) * (1.0f - pow(NormalizedClamp(ballDistanceX, 1.0f, 30.0f), 1.5f)) * amount; // offensive crew
      spot.origin.coords[0] += delta;
      */
      // lane version
      float amount = 22.0f;
      float laneY = -signSide(mainManPos.coords[1]) * 8.0f;
      amount *= curve(1.0f - NormalizedClamp(fabs(laneY - currentPos.coords[1]), 0.0f, 30.0f), 1.0f);
      float delta = -team->GetSide() * std::pow(dynamicMindSet, 1.5f) * amount;
      spot.origin.coords[0] += delta;
    }

    spot.magnetType = e_MagnetType_Attract;
    spot.decayType = e_DecayType_Constant;
    spot.power = 1.0f * basePositionWeight;
    // the farther away from this position, the more we are attracted to it
    spot.power *= 0.3f + 0.7f * NormalizedClamp((spot.origin - currentPos).GetLength(), 0.0f, 20.0f);
    forceField.push_back(spot);
  }

  if (adaptedMakeRun) {
    ForceSpot spot;
    spot.origin = Vector3(-team->GetSide() * pitchHalfW, currentPos.coords[1] * 0.5f, 0.0f);//player->GetDirectionVec() * 100.0f;// / distanceToVelocityMultiplier;
    spot.magnetType = e_MagnetType_Attract;
    spot.decayType = e_DecayType_Constant;
    spot.power = 2.0f * runWeight;
    forceField.push_back(spot);
  }

  // stay away from opponents
  std::vector<Player*> opponents;
  AI_GetClosestPlayers(match->GetTeam(abs(team->GetID() - 1)), mainManPos * 0.3f + currentPos + 0.7f, false, opponents, 3);
  for (unsigned int i = 0; i < opponents.size(); i++) {
    const PlayerImage &oppImg = mentalImage->GetPlayerImage(opponents.at(i)->GetID());
    ForceSpot spot;
    Vector3 oppPos = oppImg.position + oppImg.movement * 0.1f;
    spot.origin = oppPos + (oppPos - mainManPos).GetNormalized(0) * 2.0f; // anti-magnet behind opponent, because the pass-way must be cleared
    spot.magnetType = e_MagnetType_Repel;
    spot.decayType = e_DecayType_Variable;
    spot.power = 1.0f * opponentRepelWeight;
    spot.scale = 5.0f;
    if (adaptedMakeRun) {
      spot.scale = 2.0f;
      spot.power *= 0.5f;
    }
    spot.exp = 0.7f;
    forceField.push_back(spot);
  }

  // stay away from teammates
  if (team->GetFadingTeamPossessionAmount() >= 1.02f) {
    std::vector<Player*> players;
    AI_GetClosestPlayers(team, currentPos, false, players, 6);
    for (unsigned int i = 0; i < players.size(); i++) {
      if (players.at(i) != CastPlayer()) {
        const PlayerImage &mateImg = mentalImage->GetPlayerImage(players.at(i)->GetID());
        ForceSpot spot;
        spot.origin = mateImg.position + mateImg.movement * 0.1f;
        spot.magnetType = e_MagnetType_Repel;
        spot.decayType = e_DecayType_Variable;
        spot.power = 1.0f * teammateRepelWeight;
        spot.scale = 14.0f * webScale;
        spot.exp = 1.0f;
        forceField.push_back(spot);
      }
    }
  }

  // stay away from ball (to not get in the way of passes and possessionplayer)
  if (CastPlayer() != designatedPlayer && team->GetFadingTeamPossessionAmount() >= 1.06f) {
    ForceSpot spot;
    spot.magnetType = e_MagnetType_Repel;
    spot.decayType = e_DecayType_Variable;
    spot.power = 1.0f * ballRepelWeight;
    spot.scale = 2.0f;
    spot.exp = 0.5f;
    spot.origin = mentalImage->GetBallPrediction(200).Get2D();
    forceField.push_back(spot);
    spot.origin = mentalImage->GetBallPrediction(350).Get2D();
    forceField.push_back(spot);
    spot.origin = mentalImage->GetBallPrediction(500).Get2D();
    forceField.push_back(spot);
    spot.origin = mentalImage->GetBallPrediction(650).Get2D();
    forceField.push_back(spot);
  }

  if (CastPlayer() != designatedPlayer) {

    // attract to teammate in possession
    {
      ForceSpot spot;
      spot.origin = mainManPos;
      spot.magnetType = e_MagnetType_Attract;
      spot.decayType = e_DecayType_Variable;
      spot.power = 1.0f * flockToPossessionPlayerWeight;
      spot.scale = 28.0f * webScale;
      spot.exp = 1.0f;
      forceField.push_back(spot);
    }

    // ..yet not too close
    {
      ForceSpot spot;
      spot.origin = mainManPos;
      spot.magnetType = e_MagnetType_Repel;
      spot.decayType = e_DecayType_Variable;
      spot.power = 1.0f * flockToPossessionPlayerWeight;
      spot.scale = 16.0f * webScale;
      spot.exp = 1.0f;
      forceField.push_back(spot);
    }
  }

  Vector3 forceFieldPosition = currentPos + AI_GetForceFieldMovement(forceField, currentPos, 7);//8);

  if(PlayerMatchEnabled()&&team->HasPossession()){
    const Vector3 ball=match->GetBall()->Predict(400);
    const auto role=CastPlayer()->GetDynamicFormationEntry().role;
    // A wide defender offers an outside lane to a winger instead of standing
    // behind the same marking line. Only the defender on the ball's flank
    // leaves the back line; the original offside/field constraints follow.
    const float side=-team->GetSide(),progress=(mainManPos.coords[0]-currentPos.coords[0])*side;
    if((role==e_PlayerRole_LB||role==e_PlayerRole_RB)&&std::fabs(mainManPos.coords[1])>14.f&&
       currentPos.coords[1]*mainManPos.coords[1]>0&&progress>-4.f&&progress<16.f&&
       designatedPlayer!=player&&designatedPlayer->HasPossession()){
      Vector3 overlap=mainManPos+Vector3(side*7.f,signSide(mainManPos.coords[1])*4.5f,0);
      overlap.coords[1]=clamp(overlap.coords[1],-pitchHalfH+2.f,pitchHalfH-2.f);
      forceFieldPosition=forceFieldPosition*.35f+overlap*.65f;
      if(GetConfiguration()->GetBool("training_telemetry",false)&&(match->GetActualTime_ms()+player->GetID()*10)%400==0)
        printf("TACTICAL_OVERLAP t=%lu actor=%d carrier=%d\n",match->GetActualTime_ms(),player->GetID(),designatedPlayer->GetID());
    }
    if(std::fabs(ball.coords[1])>16.f&&ball.coords[0]*(-team->GetSide())>pitchHalfW-30.f&&
       (role==e_PlayerRole_CF||role==e_PlayerRole_AM)){
      const float lane=(player->GetID()%2?1.f:-1.f)*(role==e_PlayerRole_CF?3.5f:7.f);
      const Vector3 run((-team->GetSide())*(pitchHalfW-(role==e_PlayerRole_CF?8.f:13.f)),lane,0);
      forceFieldPosition=forceFieldPosition*.45f+run*.55f;
    }
  }

  float margin = 0.08f;
  if (forceNoOffside) if (forceFieldPosition.coords[0] * -team->GetSide() > (offsideX * -team->GetSide()) - margin) forceFieldPosition.coords[0] = offsideX - (margin * -team->GetSide());

  forceFieldPosition.coords[0] = clamp(forceFieldPosition.coords[0], -pitchHalfW, pitchHalfW);
  forceFieldPosition.coords[1] = clamp(forceFieldPosition.coords[1], -pitchHalfH, pitchHalfH);

  return forceFieldPosition;
}

void ElizaController::Reset() {
  lastDesiredDirection = Vector3(0);
  lastDesiredVelocity = 0;
}

void ElizaController::GetOnTheBallCommands(std::vector<PlayerCommand> &commandQueue, Vector3 &rawInputDirection, float &rawInputVelocityFloat) {

  turnForPass=false;
  if(PlayerMatchEnabled()){
    const Vector3 delta=match->GetBall()->Predict(0)-player->GetPosition();
    const Vector3 relative=match->GetBall()->GetMovement()-player->GetMovement();
    const float finishRange=(player->GetPosition()-Vector3(-team->GetSide()*pitchHalfW,0,0)).Get2D().GetLength();
    const float finishHeight=match->GetBall()->Predict(150).coords[2];
    const bool aerialFinish=finishRange<18.f&&finishHeight>.8f&&finishHeight<2.6f;
    if((match->GetLastTouchPlayer()!=player||CastPlayer()->GetLastTouchType()==e_TouchType_Accidental)&&
       !aerialFinish&&relative.GetLength()>2.8f&&delta.Get2D().GetLength()<4.f&&
       (match->GetBall()->Predict(300)-player->GetPosition()-player->GetMovement()*.3f).Get2D().GetLength()<delta.Get2D().GetLength()){
      // Acquire the pass before distributing it. Proximity-based possession
      // statistics alone are not proof of a completed reception. A reachable
      // attacking aerial opportunity keeps the native first-time finish/pass
      // options instead of always being converted into a chest trap.
      _TrapCommand(commandQueue,false,false);return;
    }
  }
  float oneTouchIsHard = 0.0f;
  float movementDiff = NormalizedClamp((match->GetBall()->GetMovement() - CastPlayer()->GetMovement()).GetLength(), 0.0f, 10.0f);
  oneTouchIsHard = movementDiff - CastPlayer()->GetStat("technical_shortpass") * movementDiff * 0.8f;

  std::vector<PlayerImage> opponentPlayerImages;
  _mentalImage->GetTeamPlayerImages(abs(team->GetID() - 1), -1, opponentPlayerImages);

  // A call for the ball is a preferred option, subject to the native lane
  // evaluation. Keep playing normally while the receiver is marked/offside.
  Player *requestedReceiver=match->RequestedPassTarget(CastPlayer());
  float requestOdds=0;
  int requestedPass=-1;
  if(requestedReceiver) {
    const float attackingSide=-team->GetSide();
    const float offside=AI_GetOffsideLine(match,_mentalImage,abs(team->GetID()-1))*attackingSide;
    const bool onside=requestedReceiver->GetPosition().coords[0]*attackingSide<=std::max(0.0f,offside);
    e_FunctionType bestType=e_FunctionType_ShortPass;
    const float range=(requestedReceiver->GetPosition()-player->GetPosition()).Get2D().GetLength();
    const float running=requestedReceiver->GetMovement().Get2D().GetLength();
    const float forward=requestedReceiver->GetMovement().GetNormalized(0).GetDotProduct(Vector3(attackingSide,0,0));
    float space=100;for(const auto &opp:opponentPlayerImages)
      space=std::min(space,(opp.position-requestedReceiver->GetPosition()-requestedReceiver->GetMovement()*.4f).Get2D().GetLength());
    const float groundOdds=_GetPassingOdds(requestedReceiver,e_FunctionType_ShortPass,opponentPlayerImages);
    float bestScore=-1;int method=0;
    for(auto type:{e_FunctionType_ShortPass,e_FunctionType_LongPass,e_FunctionType_HighPass}) {
      const float odds=_GetPassingOdds(requestedReceiver,type,opponentPlayerImages);
      const float score=football_tactics::requestScore(method++,odds,running,forward,groundOdds,range,space);
      if(odds>=.50f && score>bestScore) {bestScore=score;requestOdds=odds;bestType=type;}
    }
    if(onside && requestOdds>=0.50f) {
      _AddPass(commandQueue,requestedReceiver,bestType);
      requestedPass=int(bestType);
      if(PlayerMatchEnabled() && GetConfiguration()->GetBool("training_telemetry",false))
        printf("PLAYER_MATCH_REQUEST_CHOICE t=%lu actor=%d type=%d odds=%.4f receiver_speed=%.4f space=%.4f ground_odds=%.4f\n",match->GetActualTime_ms(),player->GetID(),requestedPass,requestOdds,running,space,groundOdds);
    }
  }


  // DECIDE WHAT TO DO

  float longPossessionFactor = std::pow(NormalizedClamp(CastPlayer()->GetPossessionDuration_ms(), 0, 5000), 2.0f);

  // first selection
  float forwardSpaceWeight = 0.4f;
  float spaceWeight = 0.3f;
  float forwardWeight = 2.0f + AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role) * 6.0f;

  float totalWeight1 = forwardSpaceWeight + spaceWeight + forwardWeight;
  float tacticalImprovementThreshold = 0.06f * (1.0f - AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role)); // only go on with pass selection if recipient has this much tactical advantage over current player

  // second selection
  float tacticalDiffWeight =
      1.0f +
      std::pow(AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role),
               2.0f) *
          10.0f;
  float passWeight = 1.0f;
  float passMinimum = 0.2f * (1.0f - AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role)) - longPossessionFactor * 0.1f;

  float totalWeight2 = tacticalDiffWeight + passWeight;

  // name says it all
  float passThreshold = 0.1f - longPossessionFactor * 0.05f;

  // self rating
  const TacticalPlayerSituation &sit = CastPlayer()->GetTacticalSituation();
  float tacticalRating = sit.forwardSpaceRating * forwardSpaceWeight +
                         sit.spaceRating * spaceWeight +
                         sit.forwardRating * forwardWeight;

  tacticalRating /= totalWeight1;

  // collect pass target candidates
  std::vector<Player*> mates;
  team->GetActivePlayers(mates);

  struct MateRating {
    Player *player;
    float tacticalRating;
    float tacticalDiffRating;
    float passRating;
    float proximityRating;
    e_FunctionType passType;
  };

  float bestTotalRating = 0.0f;
  MateRating bestMateRating;
  TacticalPlayerSituation bestMateSit;
  bestMateRating.player = 0;
  bestMateRating.passRating = 0.0f;
  bestMateRating.passType = e_FunctionType_ShortPass;
  for (unsigned int i = 0; i < mates.size(); i++) {

    if (mates.at(i) != CastPlayer()) {

      const TacticalPlayerSituation &mateSit = mates.at(i)->GetTacticalSituation();

      float mateTacticalRating = mateSit.forwardSpaceRating * forwardSpaceWeight +
                                 mateSit.spaceRating * spaceWeight +
                                 mateSit.forwardRating * forwardWeight;

      mateTacticalRating /= totalWeight1;
      if (mates.at(i)->GetFormationEntry().role == e_PlayerRole_GK) mateTacticalRating *= 0.7f; // don't like playing back to goalie

      MateRating mateRating;
      mateRating.player = mates.at(i);
      mateRating.tacticalRating = mateTacticalRating;

      if (mateTacticalRating > tacticalRating + tacticalImprovementThreshold) {

        float tacticalDiffRating = mateRating.tacticalRating - tacticalRating;

        mateRating.tacticalDiffRating = tacticalDiffRating;
        float passingOddsShort = _GetPassingOdds(mates.at(i), e_FunctionType_ShortPass, opponentPlayerImages);
        float passingOddsLong  = _GetPassingOdds(mates.at(i), e_FunctionType_LongPass,  opponentPlayerImages);
        float passingOddsHigh  = _GetPassingOdds(mates.at(i), e_FunctionType_HighPass,  opponentPlayerImages);
        if (passingOddsShort >= passingOddsLong && passingOddsShort >= passingOddsHigh) {
          mateRating.passRating = passingOddsShort;
          mateRating.passType = e_FunctionType_ShortPass;
        } else if (passingOddsLong >= passingOddsHigh) {
          mateRating.passRating = passingOddsLong;
          mateRating.passType = e_FunctionType_LongPass;
        } else {
          mateRating.passRating = passingOddsHigh;
          mateRating.passType = e_FunctionType_HighPass;
        }

        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +
                            mateRating.passRating * passWeight -
                            oneTouchIsHard;

        totalRating /= totalWeight2;

        if (totalRating > bestTotalRating && totalRating > passThreshold && mateRating.passRating > passMinimum) {
          bestTotalRating = totalRating;
          bestMateRating = mateRating;
          bestMateSit = mateSit;
        }
      }

    } // !self
  }

  // A confirmed quick possession can already offer a safe defensive outlet.
  // Waiting 350ms skipped this selector whenever the native pass had started
  // sooner. Incoming fast balls are still acquired above; circulation retains
  // its own settled-possession requirement in choose().
  if(PlayerMatchEnabled() && hasPossession && match->GetBall()->Predict(0).coords[2]<.55f){
    using namespace football_tactics;
    Situation state;const Vector3 p=player->GetPosition(),goal(-team->GetSide()*pitchHalfW,0,0);
    state.ownGoal=(p-Vector3(team->GetSide()*pitchHalfW,0,0)).Get2D().GetLength();state.goal=(goal-p).Get2D().GetLength();state.width=std::fabs(p.coords[1]);
    state.defender=AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role)<.35f;state.settled=hasPossession;
    state.possessionSeconds=CastPlayer()->GetPossessionDuration_ms()*.001f;
    for(const auto &opp:opponentPlayerImages)state.pressureDistance=std::min(state.pressureDistance,(opp.position-p).Get2D().GetLength());
    Player *outlet=nullptr,*box=nullptr;
    float outletRating=-1;
    const float offside=AI_GetOffsideLine(match,_mentalImage,abs(team->GetID()-1))*(-team->GetSide());
    for(auto *mate:mates)if(mate!=player){
      const Vector3 d=(mate->GetPosition()-p).Get2D();const float range=d.GetLength();
      if(mate->GetPosition().coords[0]*(-team->GetSide())>std::max(0.f,offside))continue;
      const float odds=_GetPassingOdds(mate,e_FunctionType_ShortPass,opponentPlayerImages);
      if(range>4 && range<23){
        const float rating=odds+.08f*clamp(d.coords[0]*(-team->GetSide())/15.f,-1.f,1.f);
        if(rating>outletRating){outletRating=rating;outlet=mate;state.outletOdds=odds;}
      }
      if((mate->GetPosition()-goal).Get2D().GetLength()<18 && std::fabs(mate->GetPosition().coords[1])<13){
        const float oddsHigh=_GetPassingOdds(mate,e_FunctionType_HighPass,opponentPlayerImages);
        if(oddsHigh>state.crossOdds){state.crossOdds=oddsHigh;box=mate;state.boxReceiver=true;}
      }
    }
    Player *runner=team->GetController()->GetCombinationRunner(CastPlayer(),match->GetActualTime_ms());
    if(runner && runner!=player && runner->GetMovement().GetDotProduct(Vector3(-team->GetSide(),0,0))>.7f &&
       runner->GetPosition().coords[0]*(-team->GetSide())<=std::max(0.f,offside)){
      const float range=(runner->GetPosition()-p).Get2D().GetLength();
      state.returnRunner=range>4&&range<22;state.returnOdds=_GetPassingOdds(runner,e_FunctionType_ShortPass,opponentPlayerImages);
    }
    state.shotOdds=_GetPassingOdds(goal,e_FunctionType_Shot,opponentPlayerImages,3.f);
    const Choice choice=choose(state);PlayerCommandQueue preferred;
    if(choice==Choice::BuildOut && outlet)_AddPass(preferred,outlet,e_FunctionType_ShortPass);
    if(choice==Choice::Circulate && outlet)_AddPass(preferred,outlet,e_FunctionType_ShortPass);
    if(choice==Choice::Combination && runner)_AddPass(preferred,runner,e_FunctionType_ShortPass);
    if(choice==Choice::Clearance)_AddPanicPass(preferred);
    if(choice==Choice::Cross && box)_AddPass(preferred,box,e_FunctionType_HighPass);
    if(choice==Choice::LongShot){
      PlayerCommand shot;shot.desiredFunctionType=e_FunctionType_Shot;shot.useDesiredMovement=shot.useDesiredLookAt=false;
      shot.touchInfo.desiredDirection=(goal-p).GetNormalized(Vector3(-team->GetSide(),0,0));shot.touchInfo.inputDirection=shot.touchInfo.desiredDirection;
      shot.touchInfo.autoDirectionBias=.2f;shot.touchInfo.desiredPower=shot.touchInfo.inputPower=clamp(.72f+state.goal/100.f,.72f,1.f);
      preferred.push_back(shot);
    }
    // A safe explicit human request remains first. Other contextual options
    // precede the original alternatives, which remain available if reach fails.
    if(requestedPass<0)commandQueue.insert(commandQueue.begin(),preferred.begin(),preferred.end());
    if(GetConfiguration()->GetBool("training_telemetry",false) &&
       (choice!=Choice::Native||(match->GetActualTime_ms()+player->GetID()*10)%200==0))
      printf("PLAYER_MATCH_TACTIC t=%lu actor=%d choice=%s own_goal=%.3f goal=%.3f pressure=%.3f outlet=%.4f cross=%.4f shot=%.4f options=%zu\n",match->GetActualTime_ms(),player->GetID(),name(choice),state.ownGoal,state.goal,state.pressureDistance,state.outletOdds,state.crossOdds,state.shotOdds,preferred.size());
  }

  // panic
  float mindSet = AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role);
  if (mindSet < 0.25f) {
    float panicProneness = 1.0f - mindSet * 2.0f;
    float goalCloseness = 1.0f - NormalizedClamp((CastPlayer()->GetPosition() - Vector3(pitchHalfW * CastPlayer()->GetTeam()->GetSide(), 0, 0)).GetLength(), 2.0f, 16.0f);//8.0f, 32.0f);
    if (CastPlayer()->GetDynamicFormationEntry().role != e_PlayerRole_GK) {
      if ((bestMateRating.player == 0 || bestMateRating.passRating < panicProneness * goalCloseness) && possessionAmount < 0.9f + panicProneness * goalCloseness * 0.8f) {
        _AddPanicPass(commandQueue);
        if (Verbose()) printf("panic! %f, %f, %f\n", possessionAmount, panicProneness, goalCloseness);
      }
    } else { // keeper
      if (possessionAmount < 3.0f) {
        _AddPanicPass(commandQueue);
      }
    }
  }

  if (bestMateRating.player != 0) {
    _AddPass(commandQueue, bestMateRating.player, bestMateRating.passType);
  }

  // shoot?
  float goalDist = NormalizedClamp((Vector3(pitchHalfW * -team->GetSide(), 0, 0) - player->GetPosition()).GetLength(), 0.0f, 32.0f);
  float idealShotPosFactor = 1.0f - NormalizedClamp((Vector3((pitchHalfW - 7.0f) * -team->GetSide(), 0, 0) - player->GetPosition()).GetLength(), 0.0f, 16.0f);
  idealShotPosFactor = curve(idealShotPosFactor, 1.0f);
  if (idealShotPosFactor > 0.1f) {
    float odds1 = _GetPassingOdds(Vector3((pitchHalfW + 1.0f) * -team->GetSide(), -3.6f, 0), e_FunctionType_Shot, opponentPlayerImages, 3.0f);
    float odds2 = _GetPassingOdds(Vector3((pitchHalfW + 1.0f) * -team->GetSide(),  0.0f, 0), e_FunctionType_Shot, opponentPlayerImages, 3.0f);
    float odds3 = _GetPassingOdds(Vector3((pitchHalfW + 1.0f) * -team->GetSide(),  3.6f, 0), e_FunctionType_Shot, opponentPlayerImages, 3.0f);
    float odds = odds2; float y = 0.0f;
    if (odds1 > odds) { odds = odds1; y = -3.5f; }
    if (odds3 > odds) { odds = odds3; y =  3.5f; }

    odds = std::pow(odds, 0.5f);
    if (Verbose()) printf("ODDS: %f\n", odds);

    if (odds + random(0.0f, 0.5f) > 0.5f) {
      PlayerCommand command;
      command.desiredFunctionType = e_FunctionType_Shot;
      command.useDesiredMovement = false;
      command.useDesiredLookAt = false;
      command.desiredVelocityFloat = rawInputVelocityFloat; // this is so we can use sprint/dribble buttons as shot modifiers
      command.touchInfo.desiredDirection = (Vector3((pitchHalfW + 1.0f) * -team->GetSide(), y + random(-1.0f + player->GetStat("technical_shot"), 1.0f - player->GetStat("technical_shot")), 0) - (CastPlayer()->GetPosition() + CastPlayer()->GetMovement() * 0.2f)).GetNormalized(Vector3(-team->GetSide(), 0, 0));
      command.touchInfo.desiredDirection = (command.touchInfo.desiredDirection * 0.7f + -CastPlayer()->GetDirectionVec() * (CastPlayer()->GetFloatVelocity() / sprintVelocity) * 0.3f).GetNormalized();
      command.touchInfo.autoDirectionBias = 1.0f;
      command.touchInfo.desiredPower = random(0.7f * (0.6f + goalDist * 0.4f), 1.0f * (0.6f + goalDist * 0.4f));
      commandQueue.push_back(command);
    }
  }


  e_Velocity enumVelocity = e_Velocity_Idle;
  AI_GetBestDribbleMovement(match, player->GetID(), _mentalImage, rawInputDirection, rawInputVelocityFloat, team->GetTeamData()->GetTactics());
  if(PlayerMatchEnabled()&&hasPossession){
    float pressure=100;for(const auto &opponent:opponentPlayerImages)pressure=std::min(pressure,(opponent.position-player->GetPosition()).Get2D().GetLength());
    const float goalRange=(player->GetPosition()-Vector3(-team->GetSide()*pitchHalfW,0,0)).Get2D().GetLength();
    if(pressure>1.8f&&goalRange>24.f)rawInputVelocityFloat=std::min(rawInputVelocityFloat,dribbleVelocity+.3f);
  }
  if(turnForPass){rawInputDirection=passFacing;rawInputVelocityFloat=.8f;}
  if(PlayerMatchEnabled() && GetConfiguration()->GetBool("training_telemetry",false) &&
      (match->GetActualTime_ms()+player->GetID()*10)%100==0) {
    printf("PLAYER_MATCH_AI t=%lu actor=%d team=%d desired_speed=%.3f choices=%zu request_target=%d request_odds=%.3f request_pass=%d\n",
      match->GetActualTime_ms(),player->GetID(),team->GetID(),rawInputVelocityFloat,commandQueue.size(),
      requestedReceiver?requestedReceiver->GetID():-1,requestOdds,requestedPass);
  }
}

void ElizaController::_AddPass(std::vector<PlayerCommand> &commandQueue, Player *target, e_FunctionType passType) {
  if(PlayerMatchEnabled() && CastPlayer()->HasPossession() && (target->GetPosition()-player->GetPosition()).Get2D().GetNormalized(0).GetDotProduct(player->GetBodyDirectionVec())<-.25f){
    std::vector<Player*> opponents;match->GetTeam(abs(team->GetID()-1))->GetActivePlayers(opponents);
    float pressure=100;for(auto *opp:opponents)pressure=std::min(pressure,(opp->GetPosition()-player->GetPosition()).Get2D().GetLength());
    const float ownGoal=(player->GetPosition()-Vector3(team->GetSide()*pitchHalfW,0,0)).Get2D().GetLength();
    if(!football_rules::rareHeel(-1.f,player->GetMovement().GetLength(),.35f,pressure,ownGoal,match->GetActualTime_ms())){
      turnForPass=true;passFacing=(target->GetPosition()-player->GetPosition()).Get2D().GetNormalized(player->GetDirectionVec());
      if(GetConfiguration()->GetBool("training_telemetry",false) && match->GetActualTime_ms()%200==0)
        printf("PLAYER_MATCH_TURN_PASS t=%lu actor=%d target=%d pressure=%.4f\n",match->GetActualTime_ms(),player->GetID(),target->GetID(),pressure);
      return;
    }
  }
  PlayerCommand command;
  command.desiredFunctionType = passType;
  command.useDesiredMovement = false;
  command.useDesiredLookAt = false;
  command.touchInfo.targetPlayer = 0;
  command.touchInfo.forcedTargetPlayer = target;
  command.touchInfo.inputDirection = Vector3(0);
  command.touchInfo.inputPower = 0;
  command.touchInfo.autoDirectionBias = 1.0f;
  command.touchInfo.autoPowerBias = 1.0f;
  AI_GetPass(CastPlayer(), passType, command.touchInfo.inputDirection, command.touchInfo.inputPower, command.touchInfo.autoDirectionBias, command.touchInfo.autoPowerBias, command.touchInfo.desiredDirection, command.touchInfo.desiredPower, command.touchInfo.targetPlayer, command.touchInfo.forcedTargetPlayer);
  commandQueue.push_back(command);
}

void ElizaController::_AddPanicPass(std::vector<PlayerCommand> &commandQueue) {

  int yside = signSide(player->GetDirectionVec().coords[1]); // > 0 ? 1 : -1;
  Vector3 sensibleAwayDir = ((player->GetDirectionVec() * Vector3(0.8f, 1.0f, 0.0f)).GetNormalized() + Vector3(-team->GetSide() * 0.7f, yside * 0.5f, 0)).GetNormalized(0) + Vector3(0, 0, 0.3f);
  sensibleAwayDir.Normalize(player->GetDirectionVec());

  PlayerCommand command;
  command.useDesiredMovement = false;
  command.useDesiredLookAt = false;

  command.touchInfo.inputDirection = sensibleAwayDir;
  command.touchInfo.desiredDirection = sensibleAwayDir;
  command.touchInfo.autoDirectionBias = 0.0f;
  command.touchInfo.autoPowerBias = 0.0f;

  command.desiredFunctionType = e_FunctionType_HighPass;
  command.touchInfo.inputPower = 0.7f;
  command.touchInfo.desiredPower = 0.7f;
  commandQueue.push_back(command);

  command.desiredFunctionType = e_FunctionType_Shot;
  command.touchInfo.inputPower = 0.6f;
  command.touchInfo.desiredPower = 0.6f;
  commandQueue.push_back(command);

  command.desiredFunctionType = e_FunctionType_LongPass;
  command.touchInfo.inputPower = 0.8f;
  command.touchInfo.desiredPower = 0.8f;
  commandQueue.push_back(command);
}

float ElizaController::_GetPassingOdds(Player *targetPlayer, e_FunctionType passType, const std::vector<PlayerImage> &opponentPlayerImages, float ballVelocityMultiplier) {

  float initialTargetDistance = (targetPlayer->GetPosition() - player->GetPosition()).GetLength();
  if (passType == e_FunctionType_HighPass && initialTargetDistance < 10.0f) return 0.0f;
  float estimatedTime_sec = 0.7f + initialTargetDistance * 0.03f;

  Vector3 target = targetPlayer->GetPosition() + targetPlayer->GetMovement() * clamp(estimatedTime_sec, 0.0f, 0.5f); // time needed to brake
  if (passType == e_FunctionType_LongPass) target += Vector3(-team->GetSide() * initialTargetDistance * 0.2f, 0, 0);

  return _GetPassingOdds(target, passType, opponentPlayerImages, ballVelocityMultiplier);
}

float ElizaController::_GetPassingOdds(const Vector3 &target, e_FunctionType passType, const std::vector<PlayerImage> &opponentPlayerImages, float ballVelocityMultiplier) {

  float secondScale = 1.0f; // how many seconds of range to measure danger in

  Vector3 origin = player->GetPosition() + player->GetMovement() * 0.12f;

  // draw imaginary line between this and target player
  Line line(origin, target);

  float danger = 0.0f;
  for (unsigned int opp = 0; opp < opponentPlayerImages.size(); opp++) {
    Vector3 oppPos = opponentPlayerImages.at(opp).position + opponentPlayerImages.at(opp).movement * 0.2f; // + time needed to brake
    float u; // % of line opp is closest to (0 .. 1)
    float oppDistance;
    oppDistance = line.GetDistanceToPoint(oppPos, u);

    if (u >= 0.0f && u <= 1.0f + 0.2f) { // opp is dangerous in the first place
      if ((passType == e_FunctionType_HighPass && (u < 0.2f || u > 0.65f)) ||
           passType != e_FunctionType_HighPass) {
        float clampedU = clamp(u, 0.0f, 1.0f);
        Vector3 intersect = origin * (1.0f - clampedU) + target * clampedU; // where opp is most likely to intercept ball

        float oppToIntersect_sec = (oppDistance + 1.0f) / sprintVelocity; // add some distance to correct for acceleration

        Vector3 originToBallPos = (intersect - origin);
        float penaltyTime = (passType == e_FunctionType_HighPass && u > 0.5f) ? 2.5f : 0.0f; // trapping high balls takes time
        float ballToIntersect_sec = 0.7f + originToBallPos.GetLength() * u * 0.03f + penaltyTime;
        ballToIntersect_sec *= 1.0f / ballVelocityMultiplier;

        danger += clamp(ballToIntersect_sec - oppToIntersect_sec + (secondScale * 0.5f), 0.0f, secondScale); // add some seconds because 0 seconds doesn't mean 0 danger
      }
    }
  }

  if (passType == e_FunctionType_HighPass){
    const bool crossing=PlayerMatchEnabled()&&std::fabs(player->GetPosition().coords[1])>14.f&&
      (player->GetPosition()-Vector3(-team->GetSide()*pitchHalfW,0,0)).Get2D().GetLength()<35.f;
    danger+=crossing?.22f:.4f;
  }

  danger = NormalizedClamp(danger, 0.0f, secondScale); // 1 super dangerous dude is basically the same as 100% danger
  float odds = 1.0f - danger;

  return odds;
}

void ElizaController::_QueueAerialDuel(PlayerCommandQueue &queue){
  if(!PlayerMatchEnabled()||!player->GetHumanoid()->PhysicalRigEnabled()||
     CastPlayer()->GetFormationEntry().role==e_PlayerRole_GK)return;
  if(std::any_of(queue.begin(),queue.end(),[](const PlayerCommand &c){return c.desiredFunctionType==e_FunctionType_ShortPass||c.desiredFunctionType==e_FunctionType_LongPass||c.desiredFunctionType==e_FunctionType_HighPass||c.desiredFunctionType==e_FunctionType_Shot;}))return;
  if(match->GetLastTouchPlayer()==player&&CastPlayer()->GetLastTouchType()!=e_TouchType_Accidental)return;
  const Vector3 position=player->GetPosition(),goal(-team->GetSide()*pitchHalfW,0,0);
  // Native finishing commands above keep priority; a defender or receiver
  // inside the box must still be allowed to compete for a high ball.
  std::vector<PlayerImage> opponents;_mentalImage->GetTeamPlayerImages(1-team->GetID(),-1,opponents);
  float pressure=100;for(const auto &opponent:opponents)pressure=std::min(pressure,(opponent.position-position).Get2D().GetLength());
  if(pressure>2.1f&&(goal-position).Get2D().GetLength()>24.f)return;
  float arrival=0,height=0,best=100;
  for(unsigned ms=80;ms<=800;ms+=20){const Vector3 ball=match->GetBall()->Predict(ms);
    const float gap=(ball-position-player->GetMovement()*(ms*.001f)).Get2D().GetLength();
    if(ball.coords[2]<1.25f||ball.coords[2]>2.65f||gap>1.05f)continue;
    const float score=gap+.18f*std::fabs(ball.coords[2]-1.75f)+ms*.0001f;
    if(score<best){best=score;arrival=ms*.001f;height=ball.coords[2];}
  }
  if(arrival==0)return;
  if(team->GetDesignatedTeamPossessionPlayer()!=player){
    const Vector3 landing=match->GetBall()->Predict(unsigned(arrival*1000));
    const float own=(landing-position).Get2D().GetLength();std::vector<Player*> mates;team->GetActivePlayers(mates);
    for(auto *mate:mates)if(mate!=player&&(landing-mate->GetPosition()).Get2D().GetLength()+.35f<own)return;
  }
  Player *target=nullptr;float rating=.68f;
  const float offside=std::max(0.f,AI_GetOffsideLine(match,_mentalImage,1-team->GetID())*(-team->GetSide()));
  std::vector<Player*> mates;team->GetActivePlayers(mates);
  for(auto *mate:mates)if(mate!=player){const Vector3 delta=mate->GetPosition()-position;const float range=delta.Get2D().GetLength();
    if(range<4||range>20||delta.coords[0]*(-team->GetSide())<0||mate->GetPosition().coords[0]*(-team->GetSide())>offside)continue;
    const float odds=_GetPassingOdds(mate,e_FunctionType_ShortPass,opponents);
    if(odds>rating){rating=odds;target=mate;}
  }
  PlayerCommand header;header.desiredFunctionType=e_FunctionType_ShortPass;
  header.useDesiredMovement=header.useDesiredLookAt=false;
  header.touchInfo.desiredDirection=((target?target->GetPosition()+target->GetMovement()*.25f:goal)-position).GetNormalized(Vector3(-team->GetSide(),0,0));
  header.touchInfo.inputDirection=header.touchInfo.desiredDirection;header.touchInfo.targetPlayer=target;
  header.touchInfo.desiredPower=header.touchInfo.inputPower=target?.45f:.62f;header.touchInfo.autoDirectionBias=.1f;
  queue.insert(queue.begin(),header);
  if(GetConfiguration()->GetBool("training_telemetry",false)&&match->GetActualTime_ms()%100==0)
    printf("CPU_AERIAL_DUEL t=%lu actor=%d arrival=%.4f height=%.4f pressure=%.4f target=%d\n",match->GetActualTime_ms(),player->GetID(),arrival,height,pressure,target?target->GetID():-1);
}

void ElizaController::_AddCelebration(std::vector<PlayerCommand> &commandQueue) {

  signed int xSide = (match->GetBall()->Predict(0).Get2D().coords[0] > 0) ? 1 : -1;
  signed int ySide = team->GetSide();
  if (team->GetLastTouchPlayer()) ySide = (team->GetLastTouchPlayer()->GetPosition().coords[1] > 0) ? 1 : -1;
  Vector3 celebrationPosition = Vector3(pitchHalfW * xSide, pitchHalfH * ySide, 0);

  Vector3 desiredDirection = (celebrationPosition - player->GetPosition()).GetNormalized();
  float desiredVelocityFloat = ClampVelocity((celebrationPosition - player->GetPosition()).GetLength() / 4.0f);
  Vector3 desiredLookAt = player->GetPosition() + player->GetDirectionVec() * 1000;

  int celebrationType = 1;
  if (match->GetLastGoalTeamID() != team->GetID()) {
    celebrationType = 2;
    desiredVelocityFloat = idleVelocity;
  } else {
    celebrationType = 1;
  }

  int madeGoal = 1;
  if (celebrationType == 1) {
    if (team->GetLastTouchPlayer() == player) {
      madeGoal = 2;
      desiredVelocityFloat = sprintVelocity;
    } else {
      madeGoal = 1;
      if (team->GetLastTouchPlayer() != 0) {
        if ((team->GetLastTouchPlayer()->GetPosition() - player->GetPosition()).GetLength() < 20) {
          celebrationPosition = team->GetLastTouchPlayer()->GetPosition();
          desiredDirection = ((team->GetLastTouchPlayer()->GetPosition() * 0.5 + celebrationPosition * 0.5) - player->GetPosition()).GetNormalized();
          desiredVelocityFloat = ClampVelocity((team->GetLastTouchPlayer()->GetPosition() - player->GetPosition()).GetLength() / 2.0);
        } else {
          desiredVelocityFloat = idleVelocity;
        }
        desiredLookAt = player->GetPosition() + team->GetLastTouchPlayer()->GetDirectionVec() * 100;
      }
    }
  }


  // celebration

  if (match->GetActualTime_ms() - match->GetReferee()->GetBuffer().stopTime > 2000 && match->GetActualTime_ms() - match->GetReferee()->GetBuffer().stopTime < 4000) {
    PlayerCommand command;
    command.desiredFunctionType = e_FunctionType_Special;
    command.useSpecialVar1 = true;
    command.specialVar1 = celebrationType;
    command.useSpecialVar2 = true;
    command.specialVar2 = madeGoal;
    command.useDesiredMovement = false;
    command.useDesiredLookAt = false;
    commandQueue.push_back(command);
  }


  // movement

  {
    PlayerCommand command;
    command.desiredFunctionType = e_FunctionType_Movement;
    command.useDesiredMovement = true;
    command.desiredDirection = desiredDirection;
    command.desiredVelocityFloat = desiredVelocityFloat;
    command.useDesiredLookAt = true;
    command.desiredLookAt = desiredLookAt;
    commandQueue.push_back(command);
  }

}
