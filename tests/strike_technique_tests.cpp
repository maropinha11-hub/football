#include "onthepitch/player/humanoid/strike_technique.hpp"
#include <iostream>
int main(){
  using namespace football_strike;int failures=0;
  auto check=[&](bool ok,const char *name){std::cout<<(ok?"PASS ":"FAIL ")<<name<<'\n';if(!ok)++failures;};
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
  std::cout<<"{\"result\":\""<<(failures?"failed":"passed")<<"\",\"checks\":9,\"failures\":"<<failures<<"}\n";return failures?1:0;
}
