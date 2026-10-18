// written by bastiaan konings schuiling 2008 - 2015
// this work is public domain. the code is undocumented, scruffy, untested, and should generally not be used for anything important.
// i do not offer support, so don't ask. to be used for inspiration :)

#include "goalie_default.hpp"
#include "../../../../keeper_trajectory.hpp"

#include "base/geometry/triangle.hpp"

#include "../../../../../main.hpp"

GoalieDefaultStrategy::GoalieDefaultStrategy(ElizaController *controller) : Strategy(controller) {
  name = "goalie default";

  ballBoundForGoal_ycoord = 0.0f;
}

GoalieDefaultStrategy::~GoalieDefaultStrategy() {
}

Vector3 CalculateBestAchievableTarget(Player *player, const Vector3 &pos1, float time1_sec, const Vector3 &pos2, float time2_sec) {

  float stepsPerMeter = 4.0f;
  float stepSize = 1.0f / clamp(pos1.GetDistance(pos2) * stepsPerMeter, 1.0f, 20.0f);

  for (float percentage = 0.0f; percentage <= 1.0f; percentage += stepSize) {

    Vector3 checkPos = pos1 + (pos2 - pos1) * percentage;
    float checkTime_sec = time1_sec + (time2_sec - time1_sec) * percentage;

    int maxTime_ms = -1;
    unsigned int timeNeeded_ms = AI_GetTimeNeededForDistance_ms(player->GetPosition(), player->GetMovement(), checkPos, player->GetMaxVelocity(), false/*precise*/, maxTime_ms, false/*debug*/).optimistic_ms;
    if (timeNeeded_ms * 0.001f <= checkTime_sec) {
      return checkPos;
      break;
    }
  }

  return pos2;
}

void GoalieDefaultStrategy::RequestInput(const MentalImage *mentalImage, Vector3 &direction, float &velocity) {

  // base position
  float lineDistance = PlayerMatchEnabled()?(controller->GetFadingTeamPossessionAmount()>1.2f?8.f:4.f):10.0f; // default distance keeper stays in front of goal line
  Vector3 ballPos = mentalImage->GetBallPrediction(600 + CastPlayer()->GetTimeNeededToGetToBall_ms() * 0.2f).Get2D(); // todo: not sure if we should keep this to 'now' or more predictive
  Vector3 targetPos = Vector3((pitchHalfW - lineDistance) * team->GetSide(), 0, 0);
  Vector3 goalPos = Vector3(pitchHalfW * team->GetSide(), 0, 0);

  float maxVelocity = sprintVelocity;

  if (ballPos.coords[0] * team->GetSide() > 0) { // optimization

    CalculateIfBallIsBoundForGoal(mentalImage);

    if (!IsBallBoundForGoal()) {

      // tactical position, make goal as small as possible

      // todo: maybe in some situations, we should prefer walking as max velo, because then the correct body directino can be applied (walking backwards, for example), which are better for deflect anims
      maxVelocity = sprintVelocity;//walkVelocity;

      // first, make line from ballPos to one post, then one to the other post, then calculate the line in between.
      // this line is the line we want our goalie to be on: it splits the goal in to equal halves (in the 'ball view projection', that is)
      Vector3 toPost1 = Vector3(pitchHalfW * team->GetSide(),  3.7f, 0) - ballPos;
      Vector3 toPost2 = Vector3(pitchHalfW * team->GetSide(), -3.7f, 0) - ballPos;
      radian angle = toPost2.GetAngle2D(toPost1);
      Vector3 middle = toPost1.GetRotated2D(angle * 0.5f).GetNormalized(Vector3(team->GetSide(), 0, 0));
      Line ballToGoal;
      ballToGoal.SetVertex(0, ballPos);
      ballToGoal.SetVertex(1, ballPos + middle);

      // this line is now arbitrary length - make it so long that v2 is on the backline
      // (or rather, near the backline - keeping ON the backline is dangerous; some anims may only touch the ball when it's already behind the line, which is pretty useless :p)
      Line backLine;
      backLine.SetVertex(0, Vector3((pitchHalfW - 0.7f) * team->GetSide(), -pitchHalfH, 0));
      backLine.SetVertex(1, Vector3((pitchHalfW - 0.7f) * team->GetSide(),  pitchHalfH, 0));
      Vector3 intersect = ballToGoal.GetIntersectionPoint(backLine).Get2D();
      intersect.coords[1] = clamp(intersect.coords[1], -3.7f, 3.7f);
      ballToGoal.SetVertex(1, intersect);

      float awayFromGoalOffset_m = 0.7f; // meters away from goal line (over the ballToGoal line, not straight forward)
      float awayFromGoalBias = 0.3f; // factor between goal and ball
      awayFromGoalBias *= NormalizedClamp(controller->GetFadingTeamPossessionAmount(), 1.0f, 1.5f);


      // when opponent comes rushing in and team mates are too far away to help, come out to 'reduce goal size'

      if (controller->GetFadingTeamPossessionAmount() < 1.0f) {

        Player *opp = controller->GetOppTeam()->GetDesignatedTeamPossessionPlayer();
        Vector3 oppPos = opp->GetPosition() + opp->GetMovement() * 0.32f;

        // if opp isn't in ball control, don't use ball pos but opp pos
        if (opp->HasPossession() == false) {
          ballToGoal.SetVertex(0, oppPos * 0.6f + ballPos * 0.4f);
        } else {
          ballToGoal.SetVertex(0, oppPos * 0.4f + ballPos * 0.6f);
        }

        // first, calculate how close the opponent on the ball is to the goal/shooting treshold
        float shootThreshold = 20.0f; // average/base value; this distance is dynamic
        float oppToGoalDistance = (goalPos - oppPos).GetLength();
        float oppToThresholdDistance = clamp(oppToGoalDistance - shootThreshold * NormalizedClamp(oppToGoalDistance, 0.0f, shootThreshold * 2.0f), 0.0f, pitchHalfW); // variable threshold distance
        Vector3 shootingPoint = oppPos + (goalPos - oppPos).GetNormalized(0) * oppToThresholdDistance;
        //SetGreenDebugPilon(shootingPoint);

        // now calculate the distance between this shooting point and our closest mate
        Player *mate = AI_GetClosestPlayer(team, shootingPoint, false, CastPlayer());
        float mateToThresholdDistance = 99999;
        if (mate) {
          Vector3 matePos = mate->GetPosition() + mate->GetMovement() * 0.24f;
          mateToThresholdDistance = (shootingPoint - matePos).GetLength();
        }

        if (mateToThresholdDistance > oppToThresholdDistance + 1.0f) { // come out, brave keeper!

          awayFromGoalBias = 1.0f;

          // the amount of 'come out bias' is related to how dangerous the opponent's closest mate is if they are to receive the ball.
          // basically, the same as the above code, but with the secondary opponent and mate
          Player *oppHelper = AI_GetClosestPlayer(controller->GetOppTeam(), goalPos, false, opp);
          if (oppHelper) {

            Vector3 oppHelperPosition = oppHelper->GetPosition() + oppHelper->GetMovement() * 0.32f;

            // first, calculate how close the opponent helper is to the goal/shooting treshold
            float helperShootThreshold = 24.0f; // average/base value; this distance is dynamic
            float oppHelperToGoalDistance = (goalPos - oppHelperPosition).GetLength();
            float oppHelperToThresholdDistance = clamp(oppHelperToGoalDistance - helperShootThreshold * NormalizedClamp(oppHelperToGoalDistance, 0.0f, helperShootThreshold * 2.0f), 0.0f, pitchHalfW); // variable threshold distance
            Vector3 helperShootingPoint = oppHelperPosition + (goalPos - oppHelperPosition).GetNormalized(0) * oppHelperToThresholdDistance;
            //SetYellowDebugPilon(helperShootingPoint);

            // now calculate the distance between this shooting point and our closest mate
            Player *mateHelper = AI_GetClosestPlayer(team, helperShootingPoint, false, CastPlayer());
            float mateHelperToThresholdDistance = 99999;
            if (mateHelper) mateHelperToThresholdDistance = (helperShootingPoint - (mateHelper->GetPosition() + mateHelper->GetMovement() * 0.24f)).GetLength();

            float secondaryDistanceDiff = 0.0f;
            // if this var is bigger, LESS likely to come out because of secondary danger
            if (mateHelperToThresholdDistance > oppHelperToThresholdDistance) secondaryDistanceDiff = NormalizedClamp(mateHelperToThresholdDistance - oppHelperToThresholdDistance, 0.0f, 2.0f);

            // also take into account the ratio between the primary opp to goal and the helper opp to goal distance
            // if this var is bigger, LESS likely to come out because of secondary danger
            float helperVSPrimaryDistanceRatio = 1.0f - NormalizedClamp(oppHelperToThresholdDistance / (oppToThresholdDistance + 0.0001f), 1.0f, 1.5f);
            helperVSPrimaryDistanceRatio *= 0.7f; // always allow some coming out despite opp mate danger

            awayFromGoalBias = clamp(1.0f - (secondaryDistanceDiff * helperVSPrimaryDistanceRatio), 0.0f, 1.0f);
          }

        }

      } // end keeper come out code

      bool applyRushOut = team->GetController()->GetEndApplyKeeperRush_ms() > match->GetActualTime_ms();
      if (applyRushOut) awayFromGoalBias = 1.0f;

      float distance = std::max(ballToGoal.GetLength() - 0.5f, 0.0f); // keep distance from target, we don't want to overshoot
      awayFromGoalOffset_m = clamp(distance * awayFromGoalBias, awayFromGoalOffset_m, pitchHalfW); // when ball is farther away, goalie stays farther away from goal (to make runs when necessary)

      // offset from goal line
      targetPos = ballToGoal.GetVertex(1) + (ballToGoal.GetVertex(0) - ballToGoal.GetVertex(1)).GetNormalized(0) * awayFromGoalOffset_m;
      //SetGreenDebugPilon(targetPos);

/* disabled: just rush to ball even if we probably can't make it there. this stuff doesn't work good enough (yet?)
      // time we assume it will take for the ball to arrive at some point (in other words: how fast the attacker gets the ball there)
      float time1_sec = (targetPos - ballToGoal.GetVertex(0)).GetLength() / sprintVelocity;
      float time2_sec = (ballToGoal.GetVertex(1) - ballToGoal.GetVertex(0)).GetLength() / sprintVelocity;

      //SetYellowDebugPilon(targetPos);
      targetPos = CalculateBestAchievableTarget(CastPlayer(), targetPos, time1_sec, ballToGoal.GetVertex(1), time2_sec);
      SetRedDebugPilon(targetPos + Vector3(0, 0, 0.1f));
*/

      // when going back to goal: go slower to allow for proper body direction
      float u = 0.0f;
      float distanceToBallToGoalLine = ballToGoal.GetDistanceToPoint(player->GetPosition(), u);
      if ((targetPos - goalPos).GetLength() < (player->GetPosition() - goalPos).GetLength() &&
          distanceToBallToGoalLine < 1.0f && u > 0.0f) maxVelocity = walkVelocity;

      targetPos.coords[0] = clamp(targetPos.coords[0], -pitchHalfW + 0.2f, pitchHalfW - 0.2f); // not very useful to stand behind backline

    } else {

      // intercept ball
      // todo: doesn't yet walk backwards if ball is too high

      maxVelocity = sprintVelocity;

      Line ballToGoal;
      ballToGoal.SetVertex(0, mentalImage->GetBallPrediction(10).Get2D());
      float minGoalLineDist = 0.4f;
      Vector3 ballOverGoalLinePos = Vector3(pitchHalfW * team->GetSide(), ballBoundForGoal_ycoord, 0);
      ballOverGoalLinePos += (ballToGoal.GetVertex(0) - ballOverGoalLinePos).GetNormalized(0) * minGoalLineDist;
      ballToGoal.SetVertex(1, ballOverGoalLinePos);
      float u = 0.0f;
      float distance = ballToGoal.GetDistanceToPoint(player->GetPosition() + player->GetMovement() * 0.05f, u);

      float u_at_1sec = 0.0f;
      float distance_at_1sec = ballToGoal.GetDistanceToPoint(mentalImage->GetBallPrediction(1010).Get2D(), u_at_1sec);

      bool should_gk_run_towards_the_goal = false;
      if (u_at_1sec > 1e-4) {
        float time_to_reach_gk = u / u_at_1sec;
        Vector3 ball_position_at_gk = mentalImage->GetBallPrediction(10 + 1000 * time_to_reach_gk);
        if (ball_position_at_gk.coords[2] > 2.5) {
          should_gk_run_towards_the_goal = true;
        }
      }

      u = clamp(u, 0.0f, 1.0f);

      if (should_gk_run_towards_the_goal) {
        targetPos = ballOverGoalLinePos;
      } else {
        targetPos = ballToGoal.GetVertex(0) + (ballToGoal.GetVertex(1) - ballToGoal.GetVertex(0)) * u;
        targetPos.coords[2] = 0.0;
        targetPos.coords[0] = clamp(targetPos.coords[0], -pitchHalfW + 0.2f,
                                    pitchHalfW - 0.2f); // not very useful to stand behind line
      }
    }
  }

  const char *mode=IsBallBoundForGoal()?"shot":"position";
  if(PlayerMatchEnabled()){
    // Read the same curved/bouncing forecast as the ball. Claim only an
    // attainable, descending arrival inside our area, before opponents.
    const float side=team->GetSide();
    if(!IsBallBoundForGoal()){
      const float danger=(mentalImage->GetBallPrediction(0).Get2D()-goalPos).GetLength();
      if(controller->GetFadingTeamPossessionAmount()<1.05f){
        const float depth=clamp(danger*.45f,2.f,9.f);
        targetPos.coords[0]=side*std::max(targetPos.coords[0]*side,pitchHalfW-depth);
      }
      std::vector<Player*> opponents;controller->GetOppTeam()->GetActivePlayers(opponents);
      for(unsigned ms=200;ms<=1200;ms+=100){
        const Vector3 arrival=mentalImage->GetBallPrediction(ms);
        if(arrival.coords[0]*side<pitchHalfW-12.f || arrival.coords[0]*side>pitchHalfW-.2f ||
           std::fabs(arrival.coords[1])>14.f || arrival.coords[2]<.5f || arrival.coords[2]>2.35f ||
           mentalImage->GetBallPrediction(ms+50).coords[2]>arrival.coords[2])continue;
        int maximum=-1;
        const unsigned reach=AI_GetTimeNeededForDistance_ms(player->GetPosition(),player->GetMovement(),arrival.Get2D(),player->GetMaxVelocity(),false,maximum,false).optimistic_ms;
        if(reach+120>ms)continue;
        bool crowded=false;for(auto *opp:opponents){
          const Vector3 predicted=opp->GetPosition()+opp->GetMovement()*(ms*.001f);
          if((predicted-arrival).Get2D().GetLength()<1.2f){crowded=true;break;}
        }
        if(crowded)continue;
        targetPos=arrival.Get2D();maxVelocity=sprintVelocity;mode="claim";break;
      }
      Player *attacker=controller->GetOppTeam()->GetDesignatedTeamPossessionPlayer();
      if(attacker&&attacker->HasPossession()&&mentalImage->GetBallPrediction(100).coords[2]<.8f){
        const Vector3 attack=attacker->GetPosition()+attacker->GetMovement()*.18f;
        float cover=100;std::vector<Player*> mates;team->GetActivePlayers(mates);
        for(auto *mate:mates)if(mate!=player)cover=std::min(cover,(mate->GetPosition()-attack).Get2D().GetLength());
        const float range=(attack-goalPos).Get2D().GetLength();
        const float depth=football_keeper::closeAngleDepth(range,(mentalImage->GetBallPrediction(0)-attacker->GetPosition()).Get2D().GetLength(),cover);
        if(depth>0){
          targetPos=goalPos+(attack-goalPos).Get2D().GetNormalized(Vector3(-side,0,0))*std::min(depth,std::max(.3f,range-.7f));
          maxVelocity=sprintVelocity;mode="close_angle";
          if(range<8.f&&(attack-player->GetPosition()).Get2D().GetLength()<3.f){targetPos=mentalImage->GetBallPrediction(180).Get2D();mode="smother";}
        }
      }
    }
    if(!std::isfinite(targetPos.coords[0])||!std::isfinite(targetPos.coords[1]))targetPos=goalPos-Vector3(side*.7f,0,0);
    if(GetConfiguration()->GetBool("training_telemetry",false))
      printf("KEEPER_DECISION t=%lu actor=%d mode=%s target=[%.4f,%.4f] bound=%d\n",match->GetActualTime_ms(),player->GetID(),mode,targetPos.coords[0],targetPos.coords[1],IsBallBoundForGoal()?1:0);
  }

  direction = targetPos - player->GetPosition();
  velocity = clamp(direction.GetLength() * distanceToVelocityMultiplier, idleVelocity, maxVelocity);
  direction.Normalize(player->GetDirectionVec());
}

void GoalieDefaultStrategy::CalculateIfBallIsBoundForGoal(const MentalImage *mentalImage) {
  ballBoundForGoal=false;ballBoundForGoal_ycoord=0;
  const float panic=1.02f+(1-(CastPlayer()->GetStat("mental_defensivepositioning")*.6f+CastPlayer()->GetStat("mental_vision")*.4f))*.5f;
  Vector3 previous=mentalImage->GetBallPrediction(0);
  for(unsigned ms=20;ms<4000 && ms<ballPredictionSize_ms;ms+=20){
    const Vector3 next=mentalImage->GetBallPrediction(ms);float y=0;
    if(football_keeper::goalCrossing({{previous.coords[0],previous.coords[1],previous.coords[2]}},
        {{next.coords[0],next.coords[1],next.coords[2]}},team->GetSide(),pitchHalfW,3.7f*panic,goalHeight+.11f,y)){
      ballBoundForGoal=true;ballBoundForGoal_ycoord=y;return;
    }
    previous=next;
  }
}
