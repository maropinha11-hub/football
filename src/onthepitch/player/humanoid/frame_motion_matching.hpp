#pragma once
#include "motion_matching.hpp"
#include "pose_inertia.hpp"
#include <limits>

namespace football_physics {
struct ReferenceFrame {
  MotionFeature feature;
  Pose pose{};
  std::array<Vec,13> velocity{};
  float height=0;
  unsigned clip=0,frame=0,end=0;
  std::array<float,2> support{{0,0}};
};
struct ReferenceLibrary {
  std::vector<ReferenceFrame> frames;
  struct Match {unsigned index=0,tested=0;float cost=std::numeric_limits<float>::infinity();};
  Match search(const MotionFeature &query,std::array<float,2> support,unsigned continuation)const{
    Match result;
    for(unsigned index=0;index<frames.size();++index){const auto &candidate=frames[index];
      // A future pose must exist. A contact action is never in this library.
      if(candidate.frame+2>=candidate.end)continue;
      float cost=motionCost(query,candidate.feature);
      // Intent must outweigh an exact static stance when starting to walk.
      // The physical body's initial foot velocity is legitimately zero.
      for(unsigned t=0;t<3;++t){const Vec delta=subtractPoint(query.trajectory[t],candidate.feature.trajectory[t]);cost+=5.f*dotPoint(delta,delta);}
      for(unsigned side=0;side<2;++side)cost+=.12f*std::pow(support[side]-candidate.support[side],2.f);
      if(index!=continuation)cost+=.15f;
      ++result.tested;if(cost<result.cost){result.cost=cost;result.index=index;}
    }
    return result;
  }
};
class FrameMotionPlayer {
 public:
  std::shared_ptr<const ReferenceLibrary> library;
  ReferenceLibrary::Match lastSearch;
  void reset(){index=0;age=0;initialized=observed=false;inertia.reset();}
  void observeQuery(MotionFeature &query,float dt){
    for(unsigned i=0;i<5;++i){query.velocities[i]=observed?capped(scalePoint(subtractPoint(query.positions[i],previous[i]),1/std::max(.001f,dt)),10.f):Vec{{0,0,0}};previous[i]=query.positions[i];}
    observed=true;
  }
  bool step(const MotionFeature &query,std::array<float,2> support,float dt,Pose &pose,float &height){
    if(!library||library->frames.empty())return false;
    bool transition=false;
    if(initialized&&index+1<library->frames.size()&&library->frames[index+1].clip==library->frames[index].clip)++index;
    if(!initialized||age%8==0||library->frames[index].frame+3>=library->frames[index].end){
      lastSearch=library->search(query,support,initialized?index:~0u);
      if(!std::isfinite(lastSearch.cost))return false;
      transition=!initialized||lastSearch.index!=index;index=lastSearch.index;
    }
    const auto &frame=library->frames[index];
    if(transition)inertia.observe(frame.pose,frame.velocity,++epoch);
    inertia.advance(dt);std::array<float,13> mask;mask.fill(1);mask[0]=0;
    inertia.apply(frame.pose,frame.velocity,mask,pose);height=frame.height;
    initialized=true;++age;return true;
  }
  unsigned selectedIndex()const{return index;}
 private:
  unsigned index=0,age=0;unsigned long epoch=0;bool initialized=false,observed=false;PoseInertia inertia;
  std::array<Vec,5> previous{};
};
}
