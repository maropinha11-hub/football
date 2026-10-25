#include "onthepitch/player/humanoid/learned_muscle_policy.hpp"
#include "onthepitch/player/humanoid/learned_balance_policy.hpp"
#include "onthepitch/player/analog_locomotion.hpp"
#include <iostream>
int main(){
 int failures=0,checks=0;auto check=[&](bool ok,const char *name){++checks;if(!ok){++failures;std::cerr<<"FAIL "<<name<<'\n';}};
 using football_muscle::acceleration;
 bool supportPolicy=true;for(float speed:{-2.5f,-1.f,0.f,1.f,2.5f})for(float height:{.68f,.9f,1.2f}){
  float step,hip;football_balance_ml::predict(0,speed,height,.2f,false,step,hip);
  supportPolicy&=std::isfinite(step)&&std::isfinite(hip)&&std::fabs(step)<=.42f&&std::fabs(hip)<=.32f;
  if(std::fabs(speed)>1.f)supportPolicy&=step*speed>0;
 }
 check(supportPolicy,"trained balance inference proposes bounded reachable steps in the disturbance direction across body heights");
 bool symmetry=true,bounded=true;for(int e=-60;e<=60;++e)for(int v=-120;v<=120;v+=4){const float a=acceleration(e*.01f,v*.1f);bounded&=std::isfinite(a)&&std::fabs(a)<=140.001f;symmetry&=std::fabs(a+acceleration(-e*.01f,-v*.1f))<.0001f;}
 check(symmetry&&bounded,"learned motor is bounded and responds symmetrically to mirrored disturbances");
 check(acceleration(0,0)==0&&acceleration(.12f,0)>0&&acceleration(-.12f,0)<0,"resting muscles stay at rest and a displaced joint pulls toward its reference");
 bool recovery=true;float finalError=0;
 for(float disturbance:{-2.5f,-1.f,1.f,2.5f}){float position=.12f,velocity=disturbance;for(int i=0;i<300;++i){const float a=acceleration(-position,-velocity);velocity+=(a-2.5f*velocity)*.01f;position+=velocity*.01f;recovery&=std::isfinite(position)&&std::fabs(position)<.4f;}finalError=std::max(finalError,std::fabs(position));}
 check(recovery&&finalError<.005f,"a perturbed reduced angular link recovers its reference without divergent oscillation");
 float previous=0;bool monotonic=true;for(int i=0;i<=1000;++i){const float s=football_input::movementSpeed(i*.001f,false,3.6f,7.2f);monotonic&=s+1e-6f>=previous&&s-previous<.02f;previous=s;}
 check(monotonic&&football_input::movementSpeed(.55f,false,3.6f,7.2f)<1.5f,"ordinary light-to-medium stick has a continuous walking range without a jog-speed threshold jump");
 check(std::fabs(football_input::movementSpeed(1,false,3.6f,7.2f)-3.6f)<.001f&&std::fabs(football_input::movementSpeed(1,true,3.6f,7.2f)-7.2f)<.001f,"full-stick and RB retain their approved top speeds");
 std::cout<<"{\"result\":\""<<(failures?"failed":"passed")<<"\",\"checks\":"<<checks<<",\"failures\":"<<failures<<"}\n";return failures?1:0;
}
