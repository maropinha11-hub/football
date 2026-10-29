#include "onthepitch/player/humanoid/physical_rig.hpp"
#include <iostream>
using namespace football_physics;
int main(){
  pes3::NativeBind b;b.offsets={{{{0,0,.96f}},{{0,0,.15f}},{{0,-.03f,.5f}},{{.16f,-.01f,.48f}},{{-.01f,0,-.33f}},{{-.16f,-.01f,.48f}},{{.01f,0,-.33f}},{{.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}},{{-.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}}}};
  for(auto &q:b.rotations)q={{0,0,0,1}};
  unsigned checks=0,failures=0;auto check=[&](bool ok,const char *name){++checks;if(!ok){++failures;std::cerr<<name<<'\n';}};
  for(unsigned requested:{0u,1u,2u}){
    PhysicalRig body;body.configure(b,1);Input input;input.animationOnly=true;input.controller=requested;input.pose=b.rotations;
    bool animated=true,lengths=true;float response=0;
    for(unsigned tick=0;tick<500;++tick){
      if(tick==20)body.impulse({{360,0,0}},{{0,0,.4f}},true);
      body.step(input);const auto &m=body.metrics();
      animated&=body.mode()==Mode::Active&&!body.fullyDynamic()&&m.dynamicSegments==0&&m.physicalWorldBuilds==0;
      response=std::max(response,m.lean);
      for(unsigned bone=1;bone<13;++bone)lengths&=std::fabs(length(subtractPoint(body.points()[bone],body.points()[pes3::nativeParents[bone]]))-length(b.offsets[bone]))<1e-5f;
    }
    check(animated,"animation gameplay never enters free-body dynamics, even with a forced-fall request and legacy controller setting");
    check(lengths,"situational balance preserves all native bone lengths");
    check(response>.03f&&body.metrics().lean<.01f,"an impact visibly recruits balance and then returns to the authored pose");
  }
  for(auto kind:{football_situations::ActionKind::Pass,football_situations::ActionKind::Shot,football_situations::ActionKind::Cross,football_situations::ActionKind::Control}){
    PhysicalRig body;body.configure(b,1);Input input;input.animationOnly=true;input.pose=b.rotations;
    input.situation.enabled=true;input.situation.kind=kind;input.situation.power=.7f;input.situation.difficulty=.6f;
    input.situation.ball={{.15f,-.3f,-.8f}};input.situation.direction={{.7f,-.7f,0}};input.situation.contactPhase=.5f;
    float trunk=0,arms=0;bool fixedFeet=true;
    for(unsigned tick=0;tick<100;++tick){
      input.situation.phase=tick/99.f;input.situation.contactMade=tick>=50;body.step(input);
      trunk=std::max(trunk,body.metrics().situationTrunk);arms=std::max(arms,body.metrics().situationArms);
      fixedFeet&=body.metrics().situationFootError<1e-5f&&body.metrics().dynamicSegments==0;
    }
    check(trunk>.015f&&arms>.015f&&fixedFeet,"passes, shots, crosses and controls move the upper body without displacing the contacting feet or running a ragdoll");
  }
  {
    PhysicalRig body;body.configure(b,1);Input input;input.pose=b.rotations;input.animationOnly=true;
    input.pose[7]=input.pose[10]=exponential({{-.20f,0,0}});input.pose[8]=input.pose[11]=exponential({{.45f,0,0}});
    input.pose[9]=input.pose[12]=exponential({{-.25f,0,0}});
    input.reachBone=12;input.reachWeight=1;input.reach={{0,-.10f,.025f}};body.step(input);const Vec initial=body.points()[12];
    float maximumStep=0;Vec previous=initial;
    for(unsigned tick=0;tick<30;++tick){body.step(input);maximumStep=std::max(maximumStep,length(subtractPoint(body.points()[12],previous)));previous=body.points()[12];}
    const float displacement=length(subtractPoint(body.points()[12],initial));
    if(!(maximumStep<.008f&&displacement>.04f))std::cerr<<"reach step="<<maximumStep<<" displacement="<<displacement<<" request="<<body.metrics().reach<<" initial="<<initial[0]<<","<<initial[1]<<","<<initial[2]<<" final="<<body.points()[12][0]<<","<<body.points()[12][1]<<","<<body.points()[12][2]<<'\n';
    check(maximumStep<.008f&&displacement>.04f,"a situational leg reach develops gradually instead of snapping a foot to the ball");
  }
  std::cout<<"{\"checks\":"<<checks<<",\"failures\":"<<failures<<"}\n";return failures?1:0;
}
