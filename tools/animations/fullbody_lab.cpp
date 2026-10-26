// Headless rollouts use exactly the same Bullet assembly and motors as the
// visible experiment. This is not a surrogate pendulum training environment.
#include "onthepitch/player/humanoid/articulated_body.hpp"
#include "onthepitch/player/humanoid/procedural_reference.hpp"
#include <fstream>
#include <iostream>
#include <random>
#include <string>
#include <cstdlib>
using namespace football_physics;
int main(int argc,char **argv){
  unsigned seed=7;float push=0,seconds=6,walk=0;bool trace=false,feedback=true;std::string policy;
  for(int i=1;i<argc;++i){const std::string arg=argv[i];
    if(arg=="--seed"&&i+1<argc)seed=std::strtoul(argv[++i],nullptr,10);
    else if(arg=="--push"&&i+1<argc)push=std::atof(argv[++i]);
    else if(arg=="--seconds"&&i+1<argc)seconds=std::atof(argv[++i]);
    else if(arg=="--walk"&&i+1<argc)walk=std::atof(argv[++i]);
    else if(arg=="--policy"&&i+1<argc)policy=argv[++i];
    else if(arg=="--trace")trace=true;else if(arg=="--legacy-v1")feedback=false;else return 2;
  }
  std::vector<float> weights(ArticulatedBody::motorFeatures*ArticulatedBody::motorActions,0);
  if(!policy.empty()){std::ifstream input(policy);for(auto &x:weights)if(!(input>>x)||!std::isfinite(x))return 2;float extra;if(input>>extra)return 2;}
  pes3::NativeBind b;
  b.offsets={{{{0,0,.96f}},{{0,0,.15f}},{{0,-.03f,.5f}},{{.16f,-.01f,.48f}},{{-.01f,0,-.33f}},{{-.16f,-.01f,.48f}},{{.01f,0,-.33f}},{{.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}},{{-.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}}}};
  for(auto &q:b.rotations)q={{0,0,0,1}};
  Pose target=b.rotations,pose=target;Vec pelvis{{0,0,.935f}};
  target[7]=target[10]=exponential({{-.10f,0,0}});
  target[8]=target[11]=exponential({{.20f,0,0}});
  target[9]=target[12]=exponential({{-.10f,0,0}});
  target[0]=exponential({{.10f,0,0}});
  target[9]=target[12]=exponential({{-.20f,0,0}});
  target[4]=target[6]=exponential({{-.35f,0,0}});
  std::mt19937 random(seed);std::uniform_real_distribution<float> uniform(-1.f,1.f);
  const float direction=uniform(random)*3.14159265f;
  target[1]=exponential({{uniform(random)*.025f,uniform(random)*.025f,0}});
  ArticulatedBody body;double reward=0;float minHeight=10,maxSpeed=0,maxJoint=0,maxPenetration=0,uprightMin=1,peakResidual=0,peakSupport=0;unsigned count=0,standing=0;
  ProceduralReference gait;Vec start=pelvis;
  for(unsigned tick=0;tick<unsigned(seconds*100);++tick){
    Metrics metrics;Vec impulse{{0,0,0}};
    Vec command{{0,0,0}};
    if(walk!=0){
      Input input;input.controller=2;input.pose=b.rotations;input.pelvis=pelvis;
      command[1]=-walk*bounded((float(tick)-150.f)/100.f,0,1);input.velocity=command;
      target=gait.compose(input,b,1,.01f).pose;
    }
    if(tick==150)impulse={{push*std::cos(direction),push*std::sin(direction),0}};
    body.motor(b,1,target,pelvis,command,.01f,impulse,pose,pelvis,metrics,weights.data(),feedback);
    maxSpeed=std::max(maxSpeed,metrics.fullBodySpeed);maxJoint=std::max(maxJoint,metrics.jointError);maxPenetration=std::max(maxPenetration,metrics.penetration);
    minHeight=std::min(minHeight,pelvis[2]);uprightMin=std::min(uprightMin,metrics.fullBodyUpright);
    peakResidual=std::max(peakResidual,metrics.fullBodyResidual);peakSupport=std::max(peakSupport,metrics.supportTorque);
    if(metrics.dynamicSegments!=13||!std::isfinite(metrics.kineticEnergy))return 3;
    float poseError=0;for(unsigned i=1;i<13;++i)poseError+=length(logarithm(productRotation(pose[i],inverseRotation(target[i]))));
    reward+=2.f*std::exp(-8.f*std::pow(pelvis[2]-.935f,2))+metrics.fullBodyUpright-.02f*poseError-.02f*metrics.fullBodySpeed;
    standing+=pelvis[2]>.72f&&metrics.fullBodyUpright>.8f;++count;
    if(trace&&tick%25==0)std::cerr<<tick<<" height="<<pelvis[2]<<" up="<<metrics.fullBodyUpright<<" speed="<<metrics.fullBodySpeed<<" joints="<<metrics.jointError<<" support="<<metrics.supportFeet<<" balance="<<metrics.supportTorque<<" x="<<pelvis[0]<<" y="<<pelvis[1]<<" hip="<<logarithm(pose[7])[0]<<" hip_y="<<logarithm(pose[7])[1]<<" knee="<<logarithm(pose[8])[0]<<" ankle="<<logarithm(pose[9])[0]<<" ankle_y="<<logarithm(pose[9])[1]<<" error="<<metrics.motorError<<'\n';
  }
  std::cout<<"{\"reward\":"<<reward/count<<",\"standing_fraction\":"<<float(standing)/count<<",\"minimum_height\":"<<minHeight<<",\"minimum_upright\":"<<uprightMin<<",\"maximum_speed\":"<<maxSpeed<<",\"joint_error\":"<<maxJoint<<",\"penetration\":"<<maxPenetration<<",\"peak_residual\":"<<peakResidual<<",\"peak_support\":"<<peakSupport<<",\"final_height\":"<<pelvis[2]<<",\"dynamic_segments\":13,\"seed\":"<<seed<<",\"push\":"<<push<<",\"walk_speed\":"<<walk<<",\"forward_travel\":"<<start[1]-pelvis[1]<<"}\n";
}
