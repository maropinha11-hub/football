#include "onthepitch/player/humanoid/motion_matching.hpp"
#include "onthepitch/player/humanoid/pose_inertia.hpp"
#include "onthepitch/reception_prediction.hpp"
#include "onthepitch/physical_match_rules.hpp"
#include <iostream>
#include <random>

using namespace football_physics;
int main(){
  unsigned checks=0,failures=0;
  auto check=[&](bool ok,const char *name){++checks;if(!ok){++failures;std::cerr<<name<<'\n';}};
  std::mt19937 random(971);std::uniform_real_distribution<float> value(-2.f,2.f);
  MotionClipIndex index;MotionMetric metric;
  for(unsigned row=0;row<147;++row){MotionFrame f;f.frame=int(row*2);for(float &x:f.feature)x=value(random);index.frames.push_back(f);}index.build();
  bool exact=true,restricted=true,entryOnly=true;unsigned tested=0;
  for(unsigned sample=0;sample<300;++sample){
    MotionVector query;for(float &x:query)x=value(random);
    for(float &x:metric.scale)x=.05f+std::fabs(value(random));
    auto found=index.search(query,metric,true);tested+=found.tested;
    float best=std::numeric_limits<float>::infinity();int frame=-1;
    for(auto candidate:index.frames){const float cost=motionCost(query,candidate.feature,metric);if(cost<best){best=cost;frame=candidate.frame;}}
    exact&=found.frame==frame&&std::fabs(found.cost-best)<1e-4f;
    const auto limited=index.search(query,metric,true,150);restricted&=limited.frame>=150&&std::isfinite(limited.cost);
    const auto first=index.search(query,metric,false);entryOnly&=first.frame==0&&std::fabs(first.cost-motionCost(query,index.frames.front().feature,metric))<1e-4f;
  }
  check(exact,"blocked feature search differs from exhaustive nearest neighbours");
  check(restricted,"continuations may not rewind an unfinished gait");
  const auto bounded=index.search(index.frames[145].feature,MotionMetric{},true,80,120);
  check(bounded.frame>=80&&bounded.frame<=120,"search may not enter the exhausted tail of a locomotion cycle");
  check(entryOnly,"contact actions must retain their authored entry frame");
  check(index.search(index.frames[71].feature,MotionMetric{},true).frame==142,"matching fails to select an interior frame");
  MotionFeature pose,other;other.contacts[0]=1;
  check(motionCost(pose,pose)<motionCost(pose,other),"support contact phase must influence the result");
  MotionVector invalid{};invalid[3]=std::numeric_limits<float>::quiet_NaN();
  check(!std::isfinite(motionCost(invalid,index.frames[0].feature,metric)),"invalid queries must not become winning poses");
  std::vector<Vec> root{{{0,.02f,0}},{{0,.05f,0}},{{0,.09f,0}},{{0,.14f,0}},{{0,.20f,0}}};
  phaseRootTrajectory(root,2);
  check(std::fabs(root[2][1]-.02f)<1e-7f&&std::fabs(root[3][1]-.05f)<1e-7f&&std::fabs(root[4][1]-.09f)<1e-7f,
    "interior poses must preserve the physics clock's first step and acceleration");

  PoseInertia inertia;Pose a,b,out;for(auto &q:a)q={{0,0,0,1}};b=a;
  b[1]=exponential({{.45f,0,.12f}});b[8]=exponential({{.65f,0,0}});b[11]=exponential({{.25f,0,0}});
  std::array<Vec,13> velocity{};std::array<float,13> mask;mask.fill(1);mask[0]=0;
  inertia.observe(a,velocity,0);inertia.apply(a,velocity,mask,out);
  inertia.observe(b,velocity,1);inertia.apply(b,velocity,mask,out);
  float discontinuity=0;for(unsigned i=0;i<13;++i)discontinuity=std::max(discontinuity,length(logarithm(productRotation(out[i],inverseRotation(a[i])))));
  check(discontinuity<1e-5f,"an inertial transition must preserve its outgoing pose");
  Pose repeat;inertia.apply(b,velocity,mask,repeat);
  check(repeat==out,"repeated evaluation within a physics tick must be idempotent");
  mask[8]=0;inertia.apply(b,velocity,mask,out);
  check(length(logarithm(productRotation(out[8],inverseRotation(b[8]))))<1e-6f,"ball contact masks must restore the authored joint");
  float largestStep=0;mask.fill(1);mask[0]=0;
  inertia.apply(b,velocity,mask,out);
  for(unsigned i=0;i<100;++i){const Pose old=out;inertia.advance(.01f);inertia.apply(b,velocity,mask,out);
    for(unsigned bone=1;bone<13;++bone)largestStep=std::max(largestStep,length(logarithm(productRotation(out[bone],inverseRotation(old[bone])))));
  }
  check(inertia.maximumOffset()<1e-5f,"inertial pose offsets must converge instead of leaving a frozen blend");
  check(std::isfinite(largestStep)&&largestStep<.08f,"inertial transition must remain finite and bounded");
  check(out[0]==b[0],"inertial limb smoothing may not change world heading or root motion");
  inertia.observe(a,velocity,2,false);inertia.apply(a,velocity,mask,out);
  check(inertia.maximumOffset()<1e-6f,"a continuously advancing source mixer must not restart a frozen pose offset");
  check(football_rules::userBackheel(-.9f,1.f,160)&&!football_rules::userBackheel(-.9f,1.f,161),
    "rear short-pass charge must distinguish a light heel from a body-turning pass");
  check(!football_rules::userBackheel(.9f,1.f,80)&&!football_rules::userBackheel(-.9f,4.f,80)&&
    !football_rules::userBackheel(std::numeric_limits<float>::quiet_NaN(),1.f,80),
    "heel preference must not apply to forward, running or invalid commands");
  PoseInertia tracking;tracking.observe(a,velocity,0);tracking.apply(a,velocity,mask,out);
  float rawNoise=0,filteredNoise=0;Pose lastFiltered=out,lastRaw=a;
  for(unsigned tick=0;tick<100;++tick){
    Pose noisy=a;noisy[8]=exponential({{tick%2?.10f:-.10f,0,0}});
    tracking.advance(.01f);tracking.apply(noisy,velocity,mask,out);
    rawNoise+=length(logarithm(productRotation(noisy[8],inverseRotation(lastRaw[8]))));
    filteredNoise+=length(logarithm(productRotation(out[8],inverseRotation(lastFiltered[8]))));
    lastRaw=noisy;lastFiltered=out;
  }
  check(filteredNoise<rawNoise*.4f,"tracking must attenuate rapid alternating leg noise");
  mask[8]=0;tracking.apply(b,velocity,mask,out);
  check(length(logarithm(productRotation(out[8],inverseRotation(b[8]))))<1e-6f,"tracking must not delay the authored ball contact");
  auto incoming=[](unsigned ms){const float t=ms*.001f;return football_reception::Vec{{5-10*t,0,1.8f-.4f*t}};};
  const auto reception=football_reception::predict(incoming,{{0,0,0}},{{0,0,0}},{{-10,0,-.4f}},true);
  check(reception.valid&&reception.gap<.01f&&reception.height>1.5f&&reception.time>.45f,
    "a chest-height incoming pass must produce a reachable native receiving plan");
  check(!football_reception::predict(incoming,{{0,2,0}},{{0,0,0}},{{-10,0,-.4f}},true).valid,
    "a pass outside the body's receiving corridor cannot trigger a phantom reception");
  check(!football_reception::predict(incoming,{{0,0,0}},{{0,0,0}},{{-10,0,-.4f}},false).valid,
    "a controlled ball must not trigger another player's free-ball receiving plan");
  auto descending=[](unsigned ms){return football_reception::Vec{{.2f,0,3-4*ms*.001f}};};
  auto toBrakingRunner=[](unsigned ms){return football_reception::Vec{{5-6*ms*.001f,0,1.2f}};};
  const auto braking=football_reception::predict(toBrakingRunner,{{0,0,0}},{{4,0,0}},{{-6,0,0}},true);
  check(braking.valid&&braking.time>.6f&&braking.gap<.12f,
    "receiving prediction includes braking instead of extrapolating the old running velocity");
  check(football_reception::predict(descending,{{0,0,0}},{{0,0,0}},{{0,0,-4}},true).valid,
    "a vertically descending ball must be anticipated despite zero horizontal approach speed");
  auto receding=[](unsigned ms){return football_reception::Vec{{3+ms*.004f,0,.12f}};};
  check(!football_reception::predict(receding,{{0,0,0}},{{0,0,0}},{{4,0,0}},true).valid,
    "receding balls must not glue a receiver to an impossible future contact");
  std::cout<<"{\"result\":\""<<(failures?"failed":"passed")<<"\",\"checks\":"<<checks<<",\"failures\":"<<failures<<",\"search_queries\":300,\"candidates_tested\":"<<tested<<",\"transition_discontinuity_rad\":"<<discontinuity<<"}\n";
  return failures?1:0;
}
