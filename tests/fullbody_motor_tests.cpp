#include "onthepitch/player/humanoid/articulated_body.hpp"
#include "onthepitch/player/humanoid/procedural_reference.hpp"
#include "onthepitch/player/humanoid/frame_motion_matching.hpp"
#include <fstream>
#include <iostream>
using namespace football_physics;
namespace{
pes3::NativeBind bind(){pes3::NativeBind b;
 b.offsets={{{{0,0,.96f}},{{0,0,.15f}},{{0,-.03f,.5f}},{{.16f,-.01f,.48f}},{{-.01f,0,-.33f}},{{-.16f,-.01f,.48f}},{{.01f,0,-.33f}},{{.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}},{{-.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}}}};
 for(auto &q:b.rotations)q={{0,0,0,1}};return b;}
}
int main(){unsigned checks=0,failures=0;auto check=[&](bool ok,const char *name){++checks;if(!ok){++failures;std::cerr<<name<<'\n';}};
 const auto b=bind();
 for(float scale:{.85f,.9f,1.f,1.1f})for(float yaw:{0.f,1.57079633f,3.14159265f,4.71238898f})for(Vec push:{Vec{{0,0,0}},Vec{{15,0,0}},Vec{{-15,0,0}},Vec{{0,15,0}},Vec{{0,-15,0}}}){
  Input input;input.controller=2;input.pose=b.rotations;ProceduralReference generator;
  input.pose[0]=exponential({{0,0,yaw}});
  input=generator.compose(input,b,scale,.01f);Pose pose;Vec root=input.pelvis;ArticulatedBody body;
  bool dynamic=true,finite=true;float minHeight=10,minUp=1,jointError=0;unsigned worlds=0;
  for(unsigned tick=0;tick<600;++tick){Metrics m;body.motor(b,scale,input.pose,root,{{0,0,0}},.01f,tick==150?push:Vec{{0,0,0}},pose,root,m);
   dynamic&=m.dynamicSegments==13;finite&=std::isfinite(m.kineticEnergy);worlds=std::max(worlds,m.physicalWorldBuilds);
   minHeight=std::min(minHeight,root[2]/scale);minUp=std::min(minUp,m.fullBodyUpright);jointError=std::max(jointError,m.jointError);
  }
  check(dynamic&&finite&&worlds==1,"every segment stays dynamic in a persistent world");
  if(!(minHeight>.72f&&minUp>.8f&&jointError<.05f))std::cerr<<"context scale="<<scale<<" yaw="<<yaw<<" push="<<push[0]<<","<<push[1]<<" height="<<minHeight<<" upright="<<minUp<<" joint_error="<<jointError<<'\n';
  check(minHeight>.72f&&minUp>.8f&&jointError<.05f,"finite sole support maintains standing and small unforced push recovery");
 }
 {
  PhysicalRig rig;rig.configure(b,1);Input input;input.pose=b.rotations;
  for(unsigned mode:{0u,1u,2u,0u}){input.controller=mode;for(unsigned tick=0;tick<50;++tick)rig.step(input);
   check(rig.initialized()&&rig.fullyDynamic()==(mode==2),"controller switches initialize the requested physical mode");}
 }
 {
  ProceduralReference p;Input source;source.pose=b.rotations;source.controller=2;source.velocity={{0,-1,0}};
  Input moving;for(unsigned tick=0;tick<100;++tick)moving=p.compose(source,b,1,.01f);
  bool differs=false;for(unsigned i=1;i<13;++i)differs|=length(logarithm(productRotation(moving.pose[i],inverseRotation(source.pose[i]))))>.05f;
  check(differs,"procedural reference generates a new articulated pose");
  source.action=source.touchPending=true;
  const Input action=p.compose(source,b,1,.01f);check(action.pose==source.pose,"native football action contact is not replaced by an unrelated generated gait");
 }
 {
  ProceduralReference p;Input source;source.controller=1;source.pose=b.rotations;source.velocity={{0,-2,0}};
  bool phase=true,repeat=true;
  for(unsigned tick=0;tick<100;++tick){source.pose[7]=exponential({{.2f*std::sin(tick*.1f),0,0}});
   const auto output=p.compose(source,b,1,.01f);phase&=length(logarithm(productRotation(output.pose[7],inverseRotation(source.pose[7]))))<1e-5f;
   const auto again=p.evaluate(source);repeat&=length(logarithm(productRotation(output.pose[7],inverseRotation(again.pose[7]))))<1e-5f;}
  check(phase&&repeat,"native reference preserves the authored foot phase and repeated queries do not advance its clock");
  source.pose[7]=exponential({{.85f,0,0}});const auto jump=p.compose(source,b,1,.01f);
  check(length(logarithm(productRotation(jump.pose[7],inverseRotation(source.pose[7]))))>.3f,"a discontinuous native reference is inertialized instead of snapping a limb");
  for(unsigned tick=0;tick<80;++tick)p.compose(source,b,1,.01f);
  check(length(logarithm(productRotation(p.evaluate(source).pose[7],inverseRotation(source.pose[7]))))<.01f,"transition offsets decay back to the actual native pose");
  source.action=source.touchPending=true;
  check(p.compose(source,b,1,.01f).pose==source.pose&&p.evaluate(source).pose==source.pose,"authored football contacts bypass continuity offsets without changing their contact frame");
  PhysicalRig rig;rig.configure(b,1);source.action=source.touchPending=false;source.pose=b.rotations;rig.step(source);
  source.pose[7]=exponential({{.85f,0,0}});rig.step(source);bool aligned=true;
  for(unsigned bone=0;bone<13;++bone){const Quat rendered=productRotation(rig.additivePose()[bone],source.pose[bone]);
   aligned&=length(logarithm(productRotation(rendered,inverseRotation(rig.pose()[bone]))))<1e-5f;}
  check(aligned,"native render offsets and physical contact poses agree through a reference discontinuity");
 }
 for(float yaw:{0.f,1.57079633f,3.14159265f,4.71238898f}){
  PhysicalRig entry;entry.configure(b,1);Input source;source.pose=b.rotations;source.controller=2;source.action=source.touchPending=true;
  source.pose[0]=exponential({{0,0,yaw}});source.pose[8]=source.pose[11]=exponential({{1.7f,0,0}});source.velocity={{2,-3,0}};
  float minHeight=10,minUp=1;bool dynamic=true;
  for(unsigned tick=0;tick<70;++tick){entry.step(source);const auto &m=entry.metrics();minHeight=std::min(minHeight,entry.points()[0][2]);minUp=std::min(minUp,m.fullBodyUpright);dynamic&=m.dynamicSegments==13;}
  check(dynamic&&minHeight>.8f&&minUp>.9f,"entering the free body from an airborne native pose establishes sole support before locomotion");
 }
 for(unsigned bone:{0u,1u,4u,7u,8u,9u,10u})for(unsigned axis=0;axis<3;++axis){
  const auto model=ArticulatedBody::validateDynamics(b,bone,axis,1.f);
  check(model[0]<.05f&&model[1]>0&&std::fabs(model[2]+9.81f)<.2f,"tangent-space mass and bias agree with isolated Bullet gravity and internal-torque accelerations");
 }
 {
  auto library=std::make_shared<ReferenceLibrary>();
  for(unsigned frame=0;frame<10;++frame){ReferenceFrame f;f.frame=frame;f.end=10;f.height=.935f;f.pose=b.rotations;
   f.feature.trajectory[0]={{float(frame),0,0}};library->frames.push_back(f);}
  auto query=library->frames[5].feature;
  const auto nearest=library->search(query,{{0,0}},~0u);
  check(nearest.index==5&&nearest.tested==8,"nearest-neighbour search considers interior reference frames while excluding exhausted tails");
  FrameMotionPlayer player;player.library=library;Pose pose;float height;
  check(player.step(query,{{0,0}},.01f,pose,height)&&player.selectedIndex()==5,"the runtime can enter the selected interior locomotion phase");
  player.observeQuery(query,.01f);query.positions[0][0]+=.01f;player.observeQuery(query,.01f);
  check(std::fabs(query.velocities[0][0]-1.f)<1e-5f,"query velocities come from measured body movement, not from a guessed candidate");
 }
 std::cout<<"{\"result\":\""<<(failures?"failed":"passed")<<"\",\"checks\":"<<checks<<",\"failures\":"<<failures<<"}\n";return failures?1:0;
}
