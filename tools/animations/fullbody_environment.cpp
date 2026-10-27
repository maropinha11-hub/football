// Persistent PPO environment. Protocol is local little-endian float32 over
// pipes; no GUI, emulated physics or externally forced root is involved.
#include "onthepitch/player/humanoid/articulated_body.hpp"
#include "onthepitch/player/humanoid/procedural_reference.hpp"
#include "onthepitch/player/humanoid/body_reference.hpp"
#include <iostream>
#include <random>
#include <cstdint>
#include <cstring>
#include <cstdlib>
using namespace football_physics;
namespace {
constexpr unsigned actionCount=20;
constexpr unsigned channels[actionCount]={0,1,2,6,12,9,15,18,19,20,27,28,29,21,30,24,25,33,34,3};
pes3::NativeBind nativeBind(){pes3::NativeBind b;
  b.offsets={{{{0,0,.96f}},{{0,0,.15f}},{{0,-.03f,.5f}},{{.16f,-.01f,.48f}},{{-.01f,0,-.33f}},{{-.16f,-.01f,.48f}},{{.01f,0,-.33f}},{{.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}},{{-.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}}}};
  for(auto &q:b.rotations)q={{0,0,0,1}};return b;}
struct Environment {
  pes3::NativeBind bind=nativeBind();std::unique_ptr<ArticulatedBody> body;std::mt19937 rng;
  Pose reference{},pose{};Vec root{},command{},start{};Quat heading{};
  std::array<float,actionCount> filtered{},previous{};unsigned tick=0;float phase=0,level=0;bool flatSoles=false;
  Environment(unsigned seed,bool flat=false):rng(seed),flatSoles(flat){reset(0);}
  float uniform(float a,float b){return a+(b-a)*std::generate_canonical<float,24>(rng);}
  void reset(float difficulty){level=difficulty;tick=0;phase=0;filtered={};previous={};body.reset(new ArticulatedBody);
    root=start={{0,0,.935f}};heading=exponential({{0,0,uniform(-3.14159265f,3.14159265f)}});
    reference=BodyReference::standing(bind,heading);pose=reference;
    const float speed=level<.05f?0.f:uniform(.12f,.55f)*level;
    const float angle=uniform(-.25f,.25f);command=rotatePoint(heading,{{std::sin(angle)*speed,-std::cos(angle)*speed,0}});
    Metrics m;body->motor(bind,1,reference,root,{{0,0,0}},.01f,{{0,0,0}},pose,root,m);
  }
  void observation(float *out){body->fullObservation(reference,command,phase,filtered.data(),out);}
  float step(const float *actions,float difficulty,bool &done,float *diagnostics){
    previous=filtered;float change=0,effort=0;std::array<float,36> mapped{};
    for(unsigned i=0;i<actionCount;++i){filtered[i]+=(bounded(actions[i],-1,1)-filtered[i])*.4f;
      mapped[channels[i]]=filtered[i];change+=std::pow(filtered[i]-previous[i],2);effort+=filtered[i]*filtered[i];}
    Metrics metrics;
    for(unsigned sub=0;sub<2;++sub){
      reference=BodyReference::standing(bind,heading);
      // Mathematical gait is a weak style prior. The policy, not a carried
      // trajectory, must produce actual displacement and measured foot support.
      if(level>.01f&&length(command)>.01f){
        phase+=.01f*length(command)/(.24f/football_walk::stanceFraction);phase-=std::floor(phase);
        Pose gait=reference;Vec local=rotatePoint(inverseRotation(heading),command);
        football_walk::pose(bind,gait,{{0,0,.925f}},phase,.24f,local);football_walk::upperBody(bind,gait,phase);
        if(flatSoles){Points points;Pose global;BodyReference::fk(bind,1,gait,{{0,0,.925f}},points,global);
          // The old visual walking prior carried the pelvis pitch into the
          // sole. That is acceptable for a carried visual reference but not
          // for the finite physical support surface in this environment.
          for(unsigned foot:{9u,12u})gait[foot]=normalized(productRotation(inverseRotation(global[foot-1]),heading));}
        for(unsigned i=1;i<13;++i)reference[i]=blended(reference[i],gait[i],std::min(1.f,level));
      }
      Vec push{{0,0,0}};
      if(level>.05f&&tick>100&&tick%200==0){const float angle=uniform(-3.14f,3.14f),force=uniform(0,12)*level;push={{std::cos(angle)*force,std::sin(angle)*force,0}};}
      body->motor(bind,1,reference,root,command,.01f,push,pose,root,metrics,nullptr,true,mapped.data());++tick;
    }
    float observation[ArticulatedBody::fullFeatures];this->observation(observation);
    const Vec velocity{{observation[3]*3,observation[4]*3,observation[5]*3}},wanted{{observation[117]*2,observation[118]*2,0}};
    const float speedError=std::pow(velocity[0]-wanted[0],2)+std::pow(velocity[1]-wanted[1],2);
    const float poseCost=[&](){float cost=0;for(unsigned i=1;i<13;++i)cost+=std::pow(length(logarithm(productRotation(pose[i],inverseRotation(reference[i])))),2);return cost/12;}();
    float reward=1.f+5.f*std::exp(-speedError/.10f)+1.2f*std::exp(-15.f*std::pow(root[2]-.935f,2))+
      metrics.fullBodyUpright+.3f*std::exp(-poseCost*3)-.005f*effort-.08f*change-.04f*velocity[2]*velocity[2];
    const bool failed=root[2]<.72f||metrics.fullBodyUpright<.72f||!std::isfinite(metrics.kineticEnergy);
    if(failed)reward-=3.f;
    done=failed||tick>=1000;
    diagnostics[0]=root[2];diagnostics[1]=metrics.fullBodyUpright;diagnostics[2]=length(subtractPoint(root,start));
    diagnostics[3]=std::sqrt(speedError);diagnostics[4]=failed?1.f:0.f;diagnostics[5]=tick*.01f;
    diagnostics[6]=length(command)>.001f?dotPoint(subtractPoint(root,start),unit(command)):0.f;
    diagnostics[7]=length(command)*tick*.01f;diagnostics[8]=std::max(observation[125],observation[126]);
    if(done)reset(difficulty);
    return reward*.02f;
  }
};
}
int main(int argc,char **argv){
  const unsigned count=argc>1?std::strtoul(argv[1],nullptr,10):16,seed=argc>2?std::strtoul(argv[2],nullptr,10):11;
  if(count<1||count>256)return 2;
  std::ios::sync_with_stdio(false);std::cin.tie(nullptr);
  const uint32_t header[5]={0x46504233,ArticulatedBody::fullFeatures,actionCount,count,9};std::cout.write(reinterpret_cast<const char*>(header),sizeof(header));
  const bool flat=argc>3&&std::strcmp(argv[3],"flat-soles")==0;
  std::vector<Environment> envs;envs.reserve(count);for(unsigned i=0;i<count;++i)envs.emplace_back(seed+i*65537,flat);
  std::vector<float> observations(count*ArticulatedBody::fullFeatures),rewards(count),done(count),diagnostics(count*9),actions(count*actionCount);
  auto output=[&](){for(unsigned i=0;i<count;++i)envs[i].observation(observations.data()+i*ArticulatedBody::fullFeatures);
    for(auto *array:{&observations,&rewards,&done,&diagnostics})std::cout.write(reinterpret_cast<const char*>(array->data()),array->size()*sizeof(float));std::cout.flush();};
  output();uint32_t opcode=0;float difficulty=0;
  while(std::cin.read(reinterpret_cast<char*>(&opcode),sizeof(opcode))){
    if(opcode==2)break;
    if(!std::cin.read(reinterpret_cast<char*>(&difficulty),sizeof(difficulty))||!std::isfinite(difficulty)||difficulty<0||difficulty>1.5f)return 3;
    if(opcode==1){for(auto &env:envs)env.reset(difficulty);std::fill(rewards.begin(),rewards.end(),0);std::fill(done.begin(),done.end(),0);std::fill(diagnostics.begin(),diagnostics.end(),0);output();continue;}
    if(opcode!=0||!std::cin.read(reinterpret_cast<char*>(actions.data()),actions.size()*sizeof(float)))return 3;
    for(float a:actions)if(!std::isfinite(a))return 4;
    for(unsigned i=0;i<count;++i){bool terminal=false;rewards[i]=envs[i].step(actions.data()+i*actionCount,difficulty,terminal,diagnostics.data()+i*9);done[i]=terminal?1.f:0.f;}
    output();
  }
}
