// written by bastiaan konings schuiling 2008 - 2015
// this work is public domain. the code is undocumented, scruffy, untested, and should generally not be used for anything important.
// i do not offer support, so don't ask. to be used for inspiration :)

#include "player.hpp"

#include "../match.hpp"

#include "controller/elizacontroller.hpp"
#include "controller/humancontroller.hpp"
#include "analog_locomotion.hpp"
#include "../reception_prediction.hpp"
#include "controller/strategies/strategy.hpp"

#include "../../main.hpp"
#include "../../utils.hpp"

#include "base/geometry/triangle.hpp"

int PlayerBase::playerCount = 0;

PlayerBase::PlayerBase(Match *match, PlayerData *playerData) : match(match), playerData(playerData), id(playerCount++), humanoid(0), controller(0), externalController(0), isActive(false) {
  debug = false;
  lastTouchTime_ms = 0;
  lastTouchType = e_TouchType_None;
  fatigueFactorInv = 1.0;
  confidenceFactor = 1.0;

  averageStat = GetStat("physical_balance") +
                GetStat("physical_reaction") +
                GetStat("physical_acceleration") +
                GetStat("physical_velocity") +
                GetStat("physical_stamina") +
                GetStat("physical_agility") +
                GetStat("physical_shotpower") +
                GetStat("technical_standingtackle") +
                GetStat("technical_slidingtackle") +
                GetStat("technical_ballcontrol") +
                GetStat("technical_dribble") +
                GetStat("technical_shortpass") +
                GetStat("technical_highpass") +
                GetStat("technical_header") +
                GetStat("technical_shot") +
                GetStat("technical_volley") +
                GetStat("mental_calmness") +
                GetStat("mental_workrate") +
                GetStat("mental_resilience") +
                GetStat("mental_defensivepositioning") +
                GetStat("mental_offensivepositioning") +
                GetStat("mental_vision");
  averageStat /= 22.0;

  //if (Verbose()) printf("player '%s' has an average stat of %f\n", playerData->GetLastName().c_str(), averageStat);
  Log(e_Notice, "PlayerBase", "PlayerBase", "player '" + playerData->GetLastName() + "' has an average stat of " + real_to_str(averageStat));

}

PlayerBase::~PlayerBase() {
  if (Verbose()) printf("exiting playerbase.. ");
  if (isActive) Deactivate();
  if (Verbose()) printf("deleting humanoid.. ");
  if (humanoid) delete humanoid;
  if (Verbose()) printf("done\n");
}

void PlayerBase::Deactivate() {
  ResetSituation(GetPosition());

  isActive = false;

  if (humanoid) humanoid->Hide();

  if (externalController) externalController = 0;
  delete controller;
}

IController *PlayerBase::GetController() {
  if (externalController) return externalController;
                     else return controller;
}

void PlayerBase::RequestCommand(PlayerCommandQueue &commandQueue) {
  if (externalController) externalController->RequestCommand(commandQueue);
                     else controller->RequestCommand(commandQueue);
  if(TrainingEnabled()){
    auto *fieldPlayer=dynamic_cast<Player*>(this);
    sprintRequested=false;
    for(auto &command:commandQueue)if(command.useDesiredMovement){
      sprintRequested|=command.desiredVelocityFloat>4.5f;
      command.desiredVelocityFloat=std::min(command.desiredVelocityFloat,GetMaxVelocity());
    }
    if(externalController){
      auto *human=static_cast<HumanController*>(externalController);
      sprintRequested=human->SprintButtonDown();
      const float strength=human->GetHIDevice()->GetDirection().GetLength();
      if(!sprintRequested&&human->GetActionMode()==0&&strength>.01f&&strength<=football_input::walkingStickLimit&&!match->TrainingReceivingBall()){
        const float manual=human->GetFloatVelocity();
        for(auto &command:commandQueue)if(command.useDesiredMovement&&
            (command.desiredFunctionType==e_FunctionType_Movement||command.desiredFunctionType==e_FunctionType_BallControl))
          command.desiredVelocityFloat=std::min(command.desiredVelocityFloat,manual);
      }
    }else if(fieldPlayer&&PlayerMatchEnabled()&&fieldPlayer->GetFormationEntry().role!=e_PlayerRole_GK&&
             !match->GetBallRetainer()&&(match->GetLastTouchPlayer()!=this||
               (match->GetBall()->Predict(0).coords[2]>.35f&&GetLastTouchType()!=e_TouchType_Intentional_Kicked))){
      auto point=[](const Vector3 &p)->football_reception::Vec{return {{p.coords[0],p.coords[1],p.coords[2]}};};
      Player *last=match->GetLastTouchPlayer();
      const bool free=!last||last->GetTeamID()==fieldPlayer->GetTeamID()||(last->GetPosition()-match->GetBall()->Predict(0)).Get2D().GetLength()>1.15f;
      const auto plan=football_reception::predict([&](unsigned ms){return point(match->GetBall()->Predict(ms));},point(GetPosition()),point(GetMovement()),point(match->GetBall()->GetMovement()),free);
      if(GetConfiguration()->GetBool("training_telemetry",false)&&match->GetActualTime_ms()%100==0&&
         (match->GetBall()->Predict(1000).Get2D()-GetPosition()).GetLength()<2.f&&match->GetBall()->Predict(0).coords[2]>2.5f)
        printf("CPU_AIR_FORECAST t=%lu actor=%d valid=%d free=%d speed=%.4f future_height=%.4f\n",match->GetActualTime_ms(),GetID(),plan.valid?1:0,free?1:0,GetMovement().GetLength(),match->GetBall()->Predict(1000).coords[2]);
      if(plan.valid){
        bool receiving=fieldPlayer->GetTeam()->GetDesignatedTeamPossessionPlayer()==fieldPlayer;
        // Possession designation can lag an arrival beside another player.
        // Let the best nearby reachable receiver respond instead of watching
        // the ball pass while a more distant teammate remains designated.
        if(!receiving&&plan.time<1.10f&&plan.gap<1.10f){
          const Vector3 arrival(plan.point[0],plan.point[1],0);
          float own=(arrival-GetPosition().Get2D()).GetLength();bool better=false;
          std::vector<Player*> mates;fieldPlayer->GetTeam()->GetActivePlayers(mates);
          for(auto *mate:mates)if(mate!=fieldPlayer&&mate->GetFormationEntry().role!=e_PlayerRole_GK){
            const Vector3 next=mate->GetPosition().Get2D()+mate->GetMovement().Get2D()*std::min(.18f,plan.time);
            if((arrival-next).GetLength()+.18f<own){better=true;break;}
          }
          receiving=!better;
        }
        const Vector3 facing=(match->GetBall()->Predict(0)-GetPosition()).Get2D().GetNormalized(GetDirectionVec());
        const Vector3 meeting=Vector3(plan.point[0],plan.point[1],0)-facing*.34f;
        const Vector3 step=meeting-GetPosition().Get2D();
        const float approach=clamp(step.GetLength()/std::max(.25f,plan.time),0.f,2.2f);
        for(auto &command:commandQueue)if(command.desiredFunctionType==e_FunctionType_Movement||command.desiredFunctionType==e_FunctionType_BallControl||command.desiredFunctionType==e_FunctionType_Trap){
          command.useDesiredLookAt=true;command.desiredLookAt=match->GetBall()->Predict(0).Get2D();
          if(receiving){command.useDesiredMovement=true;command.desiredDirection=step.GetNormalized(facing);command.desiredVelocityFloat=approach;}
        }
        const bool action=std::any_of(commandQueue.begin(),commandQueue.end(),[](const PlayerCommand &c){return c.desiredFunctionType!=e_FunctionType_Movement&&c.desiredFunctionType!=e_FunctionType_BallControl&&c.desiredFunctionType!=e_FunctionType_Trap;});
        if(receiving&&!action&&!fieldPlayer->TouchPending()&&plan.time<1.10f&&plan.height<2.65f){
          PlayerCommand trap;trap.desiredFunctionType=e_FunctionType_Trap;trap.useDesiredMovement=trap.useDesiredLookAt=true;
          trap.desiredDirection=step.GetNormalized(facing);trap.desiredVelocityFloat=approach;trap.desiredLookAt=match->GetBall()->Predict(0).Get2D();
          commandQueue.erase(std::remove_if(commandQueue.begin(),commandQueue.end(),[](const PlayerCommand &c){return c.desiredFunctionType==e_FunctionType_Trap;}),commandQueue.end());
          commandQueue.insert(commandQueue.begin(),trap);
        }
        if(GetConfiguration()->GetBool("training_telemetry",false)&&match->GetActualTime_ms()%100==0)
          printf("CPU_RECEIVE_ORIENT t=%lu actor=%d arrival=%.4f height=%.4f step=%.5f approach=%.5f active=%d\n",match->GetActualTime_ms(),GetID(),plan.time,plan.height,step.GetLength(),approach,receiving?1:0);
      }
    }
  }
  auto *referee=match->GetReferee();
  if(referee->WaitingForRestart()){
    // Authorization blocks a ball action, not the other twenty-one players.
    // Preserve legal off-ball movement instead of wiping the controller's
    // runs along with the taker's premature kick.
    if(!referee->IsRestartTaker(this)){
      commandQueue.erase(std::remove_if(commandQueue.begin(),commandQueue.end(),[](const PlayerCommand &command){return command.desiredFunctionType!=e_FunctionType_Movement;}),commandQueue.end());
      if(!commandQueue.empty())return;
    }
    commandQueue.clear();PlayerCommand wait;
    wait.desiredFunctionType=e_FunctionType_Movement;
    wait.useDesiredMovement=wait.useDesiredLookAt=true;
    wait.desiredDirection=GetDirectionVec();wait.desiredVelocityFloat=idleVelocity;
    wait.desiredLookAt=GetPosition()+GetDirectionVec()*10.f;commandQueue.push_back(wait);
  }else if(referee->KeepThrowerOutside(this)){
    for(auto &command:commandQueue)if(command.desiredFunctionType==e_FunctionType_Movement){
      command.useDesiredMovement=true;command.desiredVelocityFloat=idleVelocity;
    }
  }
}

void PlayerBase::SetExternalController(IController *externalController) {
  this->externalController = externalController;
  if (this->externalController) {
    this->externalController->Reset();
    this->externalController->SetPlayer(this);
    this->externalController->SetFallbackController(controller);
    //debug = true;
  } else {
    controller->Reset();
    //debug = false;
  }
}

void PlayerBase::SetDebug(bool state) {
  debug = state;
}

bool PlayerBase::GetDebug() const {
  if (IsReleaseVersion()) return false; else return debug;
}

void PlayerBase::Process() {
  if (isActive) {
    if (externalController) externalController->Process(); else controller->Process();
    humanoid->Process();
  } else {
    if (humanoid) humanoid->Hide();
  }
  //if (debug) printf("::%f velo\n", GetMovement().GetLength());
}

void PlayerBase::PreparePutBuffers(unsigned long snapshotTime_ms) {
  humanoid->PreparePutBuffers(snapshotTime_ms);
}

void PlayerBase::FetchPutBuffers(unsigned long putTime_ms) {
  humanoid->FetchPutBuffers(putTime_ms);
}

void PlayerBase::Put() {
  humanoid->Put();
}

float PlayerBase::GetStat(const char *name) const {
  return playerData->GetStat(name);
}

float PlayerBase::GetMaxVelocity() const {
  // see humanoidbase's physics function
  const float maximum=sprintVelocity * GetVelocityMultiplier();
  return TrainingEnabled()?sprintEnergy.speedLimit(maximum):maximum;
}

float PlayerBase::GetVelocityMultiplier() const {
  // see humanoid_utils' physics function
  return 0.9f + GetStat("physical_velocity") * 0.1f;
}

float PlayerBase::GetLastTouchBias(int decay_ms, unsigned long time_ms) {
  unsigned long adaptedTime_ms = time_ms;
  if (time_ms == 0) adaptedTime_ms = match->GetActualTime_ms();
  if (decay_ms > 0) return 1.0f - clamp((adaptedTime_ms - GetLastTouchTime_ms()) / (float)decay_ms, 0.0f, 1.0f);
  return 0.0f;
}

void PlayerBase::ResetSituation(const Vector3 &focusPos) {
  positionHistoryPerSecond.clear();
  lastTouchTime_ms = 0;
  lastTouchType = e_TouchType_None;
  if (IsActive()) humanoid->ResetSituation(focusPos);
  if (GetController()) GetController()->Reset();
}
