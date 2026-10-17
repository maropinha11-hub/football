#include "humanoidbase.hpp"
#include "motion_matching.hpp"
#include "../../../main.hpp"
#include "../../match.hpp"
#include <map>

void HumanoidBase::RankMotionMatches(DataSet &candidates,const PlayerCommand &command){
  if(!PhysicalRigEnabled() || candidates.empty())return;
  using namespace football_physics;
  const unsigned joints[5]={9,12,2,4,6};
  auto extract=[&](Animation *clip,int frame,float yaw){
    auto rootAt=[&](int f){Quaternion q;Vector3 p;const int end=clip->GetEffectiveFrameCount();
      clip->GetKeyFrame("player",std::min(f,end),q,p);
      if(f>end)p+=Vector3(0,-clip->GetOutgoingVelocity(),0).GetRotated2D(clip->GetOutgoingAngle())*((f-end)*.01f);
      return p;
    };
    auto sample=[&](int f,Quaternion *global,Vector3 *positions){
      Quaternion local[13];Vector3 unused;positions[0]=rootAt(f).GetRotated2D(yaw);
      Quaternion turn;turn.SetAngleAxis(yaw,Vector3(0,0,1));
      for(unsigned i=0;i<13;++i)clip->GetKeyFrame(pes3::nativeBoneNames[i],std::min(f,clip->GetEffectiveFrameCount()),local[i],unused);
      local[0]=turn*local[0];ContactForwardKinematics(local,global,positions);
    };
    MotionFeature result;Quaternion q[13],nextQ[13];Vector3 p[13],next[13];
    sample(frame,q,p);sample(frame+1,nextQ,next);
    for(unsigned i=0;i<5;++i){
      Vector3 position=p[joints[i]]-p[0];Vector3 velocity=(next[joints[i]]-p[joints[i]])*100;
      result.positions[i]={{position.coords[0],position.coords[1],position.coords[2]}};
      result.velocities[i]={{velocity.coords[0],velocity.coords[1],velocity.coords[2]}};
    }
    const Vector3 origin=rootAt(frame);
    for(unsigned i=0;i<3;++i){const int future=frame+int(i+1)*15;sample(future,q,p);
      Vector3 trajectory=(rootAt(future)-origin).Get2D().GetRotated2D(yaw);
      Vector3 facing=q[0]*Vector3(0,-1,0);
      result.trajectory[i]={{trajectory.coords[0],trajectory.coords[1],0}};
      result.facing[i]={{facing.coords[0],facing.coords[1],0}};
    }
    return result;
  };
  MotionFeature query=extract(currentAnim->anim,currentAnim->frameNum,startAngle-spatialState.angle);
  const Vector3 desired=(command.useDesiredMovement?command.desiredDirection*command.desiredVelocityFloat:spatialState.movement).GetRotated2D(-spatialState.angle);
  const Vector3 facing=(command.useDesiredLookAt?command.desiredLookAt-spatialState.position:spatialState.bodyDirectionVec).Get2D().GetRotated2D(-spatialState.angle).GetNormalized(Vector3(0,-1,0));
  for(unsigned i=0;i<3;++i){const float time=(i+1)*.15f;
    query.trajectory[i]={{desired.coords[0]*time,desired.coords[1]*time,0}};
    query.facing[i]={{facing.coords[0],facing.coords[1],0}};
  }
  // Contact clips enter at their authored beginning. This is a constrained
  // motion-matching search: native reach/timing feasibility still follows it.
  // Jumping to arbitrary kick frames would discard the ball-contact marker.
  static std::map<const Animation*,MotionFeature> database;
  std::map<int,float> costs;
  const bool preferRight=command.desiredFunctionType==e_FunctionType_BallControl;
  for(int id:candidates){auto *clip=anims->GetAnim(id);
    auto found=database.find(clip);if(found==database.end())found=database.emplace(clip,extract(clip,0,0)).first;
    costs[id]=motionCost(query,found->second);
    if(command.useDesiredTripDirection){
      // Pose continuity is a secondary preference for impacts. A front brace
      // may resemble idle more closely than a side step, but cannot recover
      // a lateral blow. Preserve the native incident-direction constraint.
      const Vector3 incident=command.desiredTripDirection.GetRotated2D(-spatialState.angle).Get2D().GetNormalized(Vector3(0,-1,0));
      const Vector3 authored=GetVectorFromString(clip->GetVariable("bumpdirection")).Get2D().GetNormalized(incident);
      costs[id]+=80.f*(1.f-incident.GetDotProduct(authored));
    }
    if(preferRight && clip->GetVariable("touch_bodypart")!="right_foot")costs[id]+=10.f;
  }
  std::stable_sort(candidates.begin(),candidates.end(),[&](int a,int b){return costs[a]<costs[b];});
  if(GetConfiguration()->GetBool("training_telemetry",false))
    printf("MOTION_MATCH t=%lu candidates=%zu indexed=%zu choice=%d cost=%.6f function=%d\n",match->GetActualTime_ms(),candidates.size(),database.size(),candidates.front(),costs[candidates.front()],int(command.desiredFunctionType));
}
