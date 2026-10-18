#pragma once
#include "physical_rig.hpp"
#include <limits>

namespace football_physics {
constexpr unsigned motionDimensions=50;
struct MotionFeature {
  std::array<Vec,5> positions{},velocities{};
  std::array<Vec,3> trajectory{},facing{};
  std::array<float,2> contacts{};
};
using MotionVector=std::array<float,motionDimensions>;
inline MotionVector motionVector(const MotionFeature &feature){
  MotionVector result{};unsigned at=0;
  for(const auto &group:{feature.positions,feature.velocities})for(auto v:group)for(float x:v)result[at++]=x;
  for(const auto &group:{feature.trajectory,feature.facing})for(auto v:group)for(float x:v)result[at++]=x;
  for(float x:feature.contacts)result[at++]=x;
  return result;
}
struct MotionMetric {
  MotionVector scale{};
  MotionMetric(){for(unsigned i=0;i<motionDimensions;++i)scale[i]=i<15?1.f:i<30?.20f:i<39?1.2247449f:i<48?.4472136f:1.2f;}
};
inline float motionCost(const MotionVector &a,const MotionVector &b,const MotionMetric &metric){
  float cost=0;
  for(unsigned i=0;i<motionDimensions;++i){const float d=(a[i]-b[i])*metric.scale[i];cost+=d*d;}
  return std::isfinite(cost)?cost:std::numeric_limits<float>::infinity();
}
inline float motionCost(const MotionFeature &a,const MotionFeature &b){return motionCost(motionVector(a),motionVector(b),MotionMetric{});}

struct MotionFrame {int frame=0;MotionVector feature{};};
// Pose time and simulation time differ after an interior-frame entry. Keep
// the new physics trajectory's first displacement/acceleration instead of
// skipping its first steps or inserting a stationary simulation tick.
template<class Point> void phaseRootTrajectory(std::vector<Point> &path,int entry){
  if(entry<=0||entry>=int(path.size()))return;
  for(int i=int(path.size())-1;i>=entry;--i)path[i]=path[i-entry];
}
struct MotionResult {int frame=0;float cost=std::numeric_limits<float>::infinity();unsigned tested=0;};
// Exact blocked nearest-neighbour search. Bounds are independent of the
// metric, so learned positive scales preserve the full-search result.
class MotionClipIndex {
 public:
  std::vector<MotionFrame> frames;
  void build(){
    blocks.clear();
    for(unsigned start=0;start<frames.size();start+=16){
      Block block;block.start=start;block.end=std::min(start+16,unsigned(frames.size()));
      block.lo.fill(std::numeric_limits<float>::infinity());block.hi.fill(-std::numeric_limits<float>::infinity());
      for(unsigned row=start;row<block.end;++row)for(unsigned i=0;i<motionDimensions;++i){
        block.lo[i]=std::min(block.lo[i],frames[row].feature[i]);block.hi[i]=std::max(block.hi[i],frames[row].feature[i]);
      }
      blocks.push_back(block);
    }
  }
  MotionResult search(const MotionVector &query,const MotionMetric &metric,bool phases,int earliest=0)const{
    MotionResult best;
    for(const auto &block:blocks){
      float lower=0;
      for(unsigned i=0;i<motionDimensions;++i){const float d=std::max(block.lo[i]-query[i],std::max(0.f,query[i]-block.hi[i]))*metric.scale[i];lower+=d*d;}
      if(lower>best.cost)continue;
      for(unsigned row=block.start;row<block.end;++row){
        const auto &entry=frames[row];if((!phases&&entry.frame!=0)||entry.frame<earliest)continue;
        const float cost=motionCost(query,entry.feature,metric);++best.tested;
        if(cost<best.cost){best.frame=entry.frame;best.cost=cost;}
      }
    }
    return best;
  }
 private:
  struct Block {MotionVector lo,hi;unsigned start,end;};
  std::vector<Block> blocks;
};
}
