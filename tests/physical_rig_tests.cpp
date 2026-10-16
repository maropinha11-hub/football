// Numerical and behavioral checks for the native articulated-body experiment.
#include "onthepitch/player/humanoid/physical_rig.hpp"
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using namespace football_physics;
namespace {
unsigned failures=0,checks=0;
void check(bool ok,const char *name){++checks;if(!ok){++failures;std::cerr<<"FAILED: "<<name<<'\n';}}
pes3::NativeBind bindPose(){
  pes3::NativeBind b;
  b.offsets={{{{0,0,.96f}},{{0,0,.15f}},{{0,-.03f,.5f}},{{.16f,-.01f,.48f}},{{-.01f,0,-.33f}},{{-.16f,-.01f,.48f}},{{.01f,0,-.33f}},{{.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}},{{-.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}}}};
  for(auto &q:b.rotations)q={{0,0,0,1}};return b;
}
Input standing(){Input input;for(auto &q:input.pose)q={{0,0,0,1}};input.pose[4]=input.pose[6]=exponential({{-.7f,0,0}});input.pose[8]=input.pose[11]=exponential({{.3f,0,0}});return input;}
float boneError(const PhysicalRig &r,const pes3::NativeBind &b,float scale=1){float error=0;for(unsigned i=1;i<13;++i)error=std::max(error,std::fabs(length(subtractPoint(r.points()[i],r.points()[pes3::nativeParents[i]]))-length(b.offsets[i])*scale));return error;}
bool finite(const PhysicalRig &r){for(auto p:r.points())for(float x:p)if(!std::isfinite(x)||std::fabs(x)>10000)return false;for(auto q:r.pose()){float n=0;for(float x:q)n+=x*x;if(!std::isfinite(n)||std::fabs(n-1)>.001f)return false;}return true;}
Input sourcePose(const std::string &path){
  std::ifstream stream(path);check(bool(stream),"native source pose is readable");Input input=standing();std::string line;
  while(std::getline(stream,line)){
    const auto comma=line.find(',');if(comma==std::string::npos)continue;
    const auto name=line.substr(0,comma);std::vector<float> values;std::stringstream tokens(line.substr(comma+1));std::string token;
    if(name=="player"||name=="extension")continue;
    for(unsigned i=0;i<13;++i)if(name==pes3::nativeBoneNames[i]){
      while(std::getline(tokens,token,','))values.push_back(std::stof(token));
      if(values.size()>=5){const unsigned key=(values.size()/5)/2;for(unsigned c=0;c<4;++c)input.pose[i][c]=values[key*5+c+1];input.pose[i]=normalized(input.pose[i]);}
    }
  }
  return input;
}
}
int main(int argc,char **argv){
  const auto bind=bindPose();
  PhysicalRig rig;Input input=standing();rig.configure(bind,1);
  float maximumBoneError=0,peakLean=0;
  rig.step(input);const Vec initialLeft=rig.points()[9],initialRight=rig.points()[12];
  rig.impulse({{65,0,0}});
  for(unsigned step=0;step<300;++step){rig.step(input);peakLean=std::max(peakLean,rig.metrics().lean);maximumBoneError=std::max(maximumBoneError,boneError(rig,bind));}
  check(rig.mode()==Mode::Active && peakLean>.02f,"a light impulse disturbs balance without dropping the body");
  check(rig.metrics().lean<.003f,"damped balance returns to rest");
  check(length(subtractPoint(initialLeft,rig.points()[9]))<.012f && length(subtractPoint(initialRight,rig.points()[12]))<.012f,"stance feet remain anchored during a recoverable push");
  float minimumPelvis=10;unsigned fell=0,recovered=0;Mode previous=rig.mode();
  rig.impulse({{230,0,0}},{{0,0,.55f}});
  bool allFinite=true;
  for(unsigned step=0;step<800;++step){rig.step(input);allFinite&=finite(rig);minimumPelvis=std::min(minimumPelvis,rig.points()[0][2]);maximumBoneError=std::max(maximumBoneError,boneError(rig,bind));if(rig.mode()!=previous){fell+=rig.mode()==Mode::Falling;recovered+=rig.mode()==Mode::Recovering;previous=rig.mode();}}
  check(fell==1 && recovered==1 && rig.mode()==Mode::Active,"a strong impulse produces fall, get-up and active control in order");
  check(minimumPelvis<.6f && minimumPelvis>.12f,"physical pelvis falls onto the ground instead of playing an upright trip");
  check(allFinite && maximumBoneError<1e-5f,"articulation remains finite and bones do not stretch through a fall");
  for(float dt:{.005f,.01f,.02f}){
    rig.configure(bind,1);rig.step(input,dt);rig.impulse({{-190,0,0}},{{0,0,.5f}});
    for(unsigned i=0;i<unsigned(8/dt);++i)rig.step(input,dt);
    check(finite(rig) && rig.mode()==Mode::Active,"fall and recovery remain stable across supported timesteps");
  }
  rig.reset();rig.step(input);rig.impulse({{230,0,0}});rig.step(input);rig.reset();rig.step(input);
  check(rig.mode()==Mode::Active && std::fabs(rig.points()[0][2]-.96f)<.002f,"reset clears ragdoll momentum and pending impulses");
  // Reach targets move gradually, and unreachable targets cannot elongate a leg.
  rig.configure(bind,1);rig.step(input);input.reachBone=12;input.reach={{.14f,0,0}};input.reachWeight=1;
  Vec last=rig.points()[12];float maximumFootStep=0;
  for(unsigned step=0;step<70;++step){rig.step(input);maximumFootStep=std::max(maximumFootStep,length(subtractPoint(last,rig.points()[12])));last=rig.points()[12];}
  check(maximumFootStep<.007f && rig.metrics().reach>.10f,"contact reach approaches its target without a one-frame leg snap");
  check(boneError(rig,bind)<1e-5f,"two-bone reach preserves thigh and shin length");
  // Native selection samples multiple animation phases per 10 ms tick. Physics
  // must follow the newest phase without integrating its state a second time.
  rig.configure(bind,1);Input strike=standing();strike.action=true;rig.step(strike);
  const float age=rig.age();const Vec oldFoot=rig.points()[12];
  strike.pose[10]=exponential({{-.65f,0,0}});rig.evaluate(strike);
  check(length(subtractPoint(oldFoot,rig.points()[12]))>.2f && rig.age()==age,
    "same-tick source phase changes update the foot without advancing physics");
  const Vec freshFoot=rig.points()[12];for(unsigned i=0;i<20;++i)rig.evaluate(strike);
  check(length(subtractPoint(freshFoot,rig.points()[12]))<1e-6f && rig.age()==age,
    "repeated pose evaluation is idempotent within one physics tick");
  unsigned contexts=0,unsafeCuts=0;float matrixError=0;
  bool matrixFinite=true;
  const std::string root=argc>1?argv[1]:"data/media/animations";
  std::array<Input,3> bases{{sourcePose(root+"/ballcontrol/walk/000.anim"),sourcePose(root+"/shot/idle/020.anim"),sourcePose(root+"/trap/idle/000_IB000.anim")}};
  for(float speed:{0.f,3.8f,7.f})for(float turn:{-4.2f,-1.2f,0.f,1.2f,4.2f})for(float height:{0.f,.06f,.12f})for(float side:{-.08f,0.f,.08f})for(float pressure:{.7f,100.f}){
    Input v=bases[contexts%3];rig.configure(bind,1);v.reachBone=12;v.reach={{side,0,height}};v.reachWeight=1;v.opponentDistance=pressure;v.opponent={{1,0,0}};
    for(unsigned tick=0;tick<70;++tick){const float yaw=turn*tick*.01f;v.forward={{std::sin(yaw),-std::cos(yaw),0}};v.velocity=scalePoint(v.forward,speed);v.pelvis={{0,0,.96f}};rig.step(v);matrixFinite&=finite(rig);matrixError=std::max(matrixError,boneError(rig,bind));}
    unsafeCuts+=rig.mode()==Mode::Falling;++contexts;
  }
  check(contexts==270 && matrixFinite && matrixError<1e-5f,"270 combinations of speed, turn, reach and pressure preserve a finite articulated skeleton");
  check(unsafeCuts>0,"sustained high-speed unsafe cuts can lose balance without a scripted external hit");
  std::cout<<"{\"result\":\""<<(failures?"failed":"passed")<<"\",\"checks\":"<<checks<<",\"failures\":"<<failures<<",\"parameter_contexts\":"<<contexts<<",\"unsafe_cut_contexts\":"<<unsafeCuts<<",\"maximum_bone_error_m\":"<<std::max(matrixError,maximumBoneError)<<",\"minimum_pelvis_height_m\":"<<minimumPelvis<<",\"maximum_foot_step_m\":"<<maximumFootStep<<"}\n";
  return failures?1:0;
}
