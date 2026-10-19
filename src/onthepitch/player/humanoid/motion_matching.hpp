#pragma once
#include "physical_rig.hpp"

namespace football_physics {
struct MotionFeature {
  std::array<Vec,5> positions{},velocities{};
  std::array<Vec,3> trajectory{},facing{};
};
// Explicit metre and m/s scales keep velocity from overwhelming pose phase.
// Queries use source pose/velocity plus desired future root trajectory.
inline float motionCost(const MotionFeature &query,const MotionFeature &candidate){
  auto square=[](Vec v){return dotPoint(v,v);};float cost=0;
  for(unsigned i=0;i<5;++i){
    cost+=square(subtractPoint(query.positions[i],candidate.positions[i]));
    cost+=.015f*square(subtractPoint(query.velocities[i],candidate.velocities[i]));
  }
  for(unsigned i=0;i<3;++i){
    cost+=1.5f*square(subtractPoint(query.trajectory[i],candidate.trajectory[i]));
    cost+=.2f*square(subtractPoint(query.facing[i],candidate.facing[i]));
  }
  return cost;
}
}
