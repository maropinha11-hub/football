#include "onthepitch/player/humanoid/strike_technique.hpp"
#include <iostream>
#include "onthepitch/keeper_trajectory.hpp"
#include "onthepitch/player/humanoid/native_contact_timing.hpp"
#include "onthepitch/reception_prediction.hpp"
#include "onthepitch/player/sprint_energy.hpp"
#include "onthepitch/player/humanoid/contact_flight.hpp"
int main(){
  using namespace football_strike;int failures=0,checks=0;
  auto check=[&](bool ok,const char *name){++checks;std::cout<<(ok?"PASS ":"FAIL ")<<name<<'\n';if(!ok)++failures;};
  check(shortPassSpeed(10)>5.f&&shortPassSpeed(50)>5.5f&&shortPassSpeed(130)<8.f,"a brief tap reaches a nearby teammate without becoming a driven pass");
  check(shortPassSpeed(650)>20.f&&shortPassSpeed(1000)==shortPassSpeed(650),"holding A supplies a bounded firm pass");
  bool increasing=true;for(unsigned n=11;n<650;++n)increasing&=shortPassSpeed(n)>shortPassSpeed(n-1);
  check(increasing,"charging produces a continuous monotonic pass response");
  using football_condition::SprintEnergy;
  SprintEnergy energy;float exhaustedAt=0;
  for(int i=0;i<2400;++i){energy.step(.01f,energy.speedLimit(7.5f),true,.7f);if(energy.depleted){exhaustedAt=(i+1)*.01f;break;}}
  check(exhaustedAt>7&&exhaustedAt<24&&energy.speedLimit(7.5f)<=4.36f,"sustained sprint exhausts reserve and enforces a real speed cap");
  auto walking=energy,jogging=energy;for(int i=0;i<400;++i){walking.step(.01f,1.2f,false,.7f);jogging.step(.01f,4.4f,false,.7f);}
  check(walking.value>jogging.value+.08f&&walking.value<.8f&&!walking.depleted,"walking recovers faster and permits reusing a partial refill");
  auto reused=walking;for(int i=0;i<100;++i)reused.step(.01f,6.f,true,.7f);
  check(reused.value<walking.value,"a partial refill is spent by the next sprint");
  SprintEnergy slowStep,fastStep;for(int i=0;i<500;++i)slowStep.step(.02f,6.5f,true,.7f);for(int i=0;i<1000;++i)fastStep.step(.01f,6.5f,true,.7f);
  check(std::fabs(slowStep.value-fastStep.value)<.002f,"sprint reserve depends on simulated seconds rather than animation or render rate");
  bool boundedEnergy=true;for(int i=0;i<12000;++i){energy.step(.01f,energy.speedLimit(7.5f),true,.7f);boundedEnergy&=energy.value>=0&&energy.value<=1;}
  check(boundedEnergy,"held sprint remains bounded through exhaustion and recovery cycles");
  SprintEnergy ordinary;for(int i=0;i<3000;++i)ordinary.step(.01f,7.5f,false,.7f);
  check(ordinary.value==1.f&&!ordinary.depleted,"fast assisted movement cannot spend the human reserve when RB is released");
  auto central=football_flight::contactSpin({{0,-.11f,0}},{{0,25,0}});
  auto inside=football_flight::contactSpin({{.04f,-.10f,0}},{{0,25,0}});
  auto outside=football_flight::contactSpin({{-.04f,-.10f,0}},{{0,25,0}});
  auto top=football_flight::contactSpin({{0,-.10f,.04f}},{{0,25,0}});
  auto below=football_flight::contactSpin({{0,-.10f,-.04f}},{{0,25,0}});
  check(football_flight::length(central)<.001f&&inside[2]*outside[2]<0&&std::fabs(inside[2])>10,"real opposite sides of the ball produce opposite curve and a central strike stays low-spin");
  check(top[0]*below[0]<0&&std::fabs(top[0])>10,"high and low contact distinguish dip and backspin");
  check(football_flight::length(inside)<=52.01f&&football_flight::length(football_flight::contactSpin({{.04f,-.10f,0}},{{0,40,0}},true))<=22.01f,"shoe and head angular impulses respect separate friction and spin limits");
  check(choose(.4f,.5f,-.2f,3,true)==Technique::Outside,"right-foot strike across the body can use the outside");
  check(choose(.4f,-.5f,.2f,3,true,false)==Technique::Outside,"outside-foot mechanics mirror for the left foot");
  check(choose(.3f,0,.15f,5,true)==Technique::Toe,"a hurried close central strike can use the toe");
  check(choose(.9f,0,0,1,true)==Technique::Knuckle,"a powerful central strike permits a low-spin technique");
  check(followThroughLoad(.9f,7,3,.8f,false)>180&&followThroughLoad(.2f,0,0,0,false)<35,"awkward running releases demand substantially more support than an easy pass");
  check(followThroughLoad(.7f,6,.5f,.4f,true)>followThroughLoad(.7f,0,.5f,.4f,true),"running aerial contacts need a landing recovery");
  check(!football_keeper::saveWindow(-.4f,-6.f,18.f),"keeper waits rather than diving while the ball is still metres in front");
  check(football_keeper::saveWindow(-.4f,-.65f,18.f),"keeper commits when the reaching plane coincides with flight");
  check(!football_keeper::saveWindow(-.4f,2.f,18.f),"keeper cannot choose an animation that touches only after the ball passes");
  check(football_keeper::catchable(9.f,.8f)&&!football_keeper::catchable(28.f,.1f),"a feasible authored catch can hold a manageable arrival while a driven shot needs a parry");
  bool normalized=true;for(unsigned count=2;count<120;++count){float sum=0;for(unsigned f=0;f<count;++f)sum+=football_contact::approachWeight(f,count);normalized &=std::fabs(sum/count-1.f)<1e-5f;}
  check(normalized,"future contact prediction integrates exactly the same full native approach as playback");
  auto nearMiss=[](unsigned ms){return football_reception::Vec{{4-8*ms*.001f,1.25f,.15f}};};
  check(football_reception::predict(nearMiss,{{0,0,0}},{{0,0,0}},{{-8,0,0}},true).valid,"receiver takes a reachable adjustment step for an off-centre pass");
  check(!football_reception::predict(nearMiss,{{0,-1,0}},{{0,0,0}},{{-8,0,0}},true).valid,"receiver cannot invent a two-metre side contact");
  std::cout<<"{\"result\":\""<<(failures?"failed":"passed")<<"\",\"checks\":"<<checks<<",\"failures\":"<<failures<<"}\n";return failures?1:0;
}
