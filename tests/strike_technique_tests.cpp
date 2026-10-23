#include "onthepitch/player/humanoid/strike_technique.hpp"
#include <iostream>
#include "onthepitch/keeper_trajectory.hpp"
#include "onthepitch/player/humanoid/native_contact_timing.hpp"
#include "onthepitch/reception_prediction.hpp"
int main(){
  using namespace football_strike;int failures=0,checks=0;
  auto check=[&](bool ok,const char *name){++checks;std::cout<<(ok?"PASS ":"FAIL ")<<name<<'\n';if(!ok)++failures;};
  check(shortPassSpeed(10)<4.f&&shortPassSpeed(130)<6.f,"a brief tap is a gentle pass");
  check(shortPassSpeed(650)>20.f&&shortPassSpeed(1000)==shortPassSpeed(650),"holding A supplies a bounded firm pass");
  bool increasing=true;for(unsigned n=11;n<650;++n)increasing&=shortPassSpeed(n)>shortPassSpeed(n-1);
  check(increasing,"charging produces a continuous monotonic pass response");
  check(choose(.4f,.5f,-.2f,3,true)==Technique::Outside,"right-foot strike across the body can use the outside");
  check(choose(.4f,-.5f,.2f,3,true,false)==Technique::Outside,"outside-foot mechanics mirror for the left foot");
  check(choose(.3f,0,.15f,5,true)==Technique::Toe,"a hurried close central strike can use the toe");
  check(choose(.9f,0,0,1,true)==Technique::Knuckle,"a powerful central strike permits a low-spin technique");
  check(followThroughLoad(.9f,7,3,.8f,false)>180&&followThroughLoad(.2f,0,0,0,false)<35,"awkward running releases demand substantially more support than an easy pass");
  check(followThroughLoad(.7f,6,.5f,.4f,true)>followThroughLoad(.7f,0,.5f,.4f,true),"running aerial contacts need a landing recovery");
  check(!football_keeper::saveWindow(-.4f,-6.f,18.f),"keeper waits rather than diving while the ball is still metres in front");
  check(football_keeper::saveWindow(-.4f,-.65f,18.f),"keeper commits when the reaching plane coincides with flight");
  check(!football_keeper::saveWindow(-.4f,2.f,18.f),"keeper cannot choose an animation that touches only after the ball passes");
  bool normalized=true;for(unsigned count=2;count<120;++count){float sum=0;for(unsigned f=0;f<count;++f)sum+=football_contact::approachWeight(f,count);normalized &=std::fabs(sum/count-1.f)<1e-5f;}
  check(normalized,"future contact prediction integrates exactly the same full native approach as playback");
  auto nearMiss=[](unsigned ms){return football_reception::Vec{{4-8*ms*.001f,1.25f,.15f}};};
  check(football_reception::predict(nearMiss,{{0,0,0}},{{0,0,0}},{{-8,0,0}},true).valid,"receiver takes a reachable adjustment step for an off-centre pass");
  check(!football_reception::predict(nearMiss,{{0,-1,0}},{{0,0,0}},{{-8,0,0}},true).valid,"receiver cannot invent a two-metre side contact");
  std::cout<<"{\"result\":\""<<(failures?"failed":"passed")<<"\",\"checks\":"<<checks<<",\"failures\":"<<failures<<"}\n";return failures?1:0;
}
