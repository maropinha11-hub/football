#include "onthepitch/player/humanoid/physical_rig.hpp"
#include "onthepitch/player/humanoid/shirt_cloth.hpp"
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>

using namespace football_physics;
namespace {
unsigned checks=0,failures=0;
void check(bool ok,const char*name){++checks;if(!ok){++failures;std::cerr<<"FAILED: "<<name<<'\n';}}
pes3::NativeBind bindPose(){pes3::NativeBind b;
 b.offsets={{{{0,0,.96f}},{{0,0,.15f}},{{0,-.03f,.5f}},{{.16f,-.01f,.48f}},{{-.01f,0,-.33f}},{{-.16f,-.01f,.48f}},{{.01f,0,-.33f}},{{.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}},{{-.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}}}};
 for(auto&q:b.rotations)q={{0,0,0,1}};return b;}
Input standing(){Input in;for(auto&q:in.pose)q={{0,0,0,1}};in.pose[4]=in.pose[6]=exponential({{-.7f,0,0}});in.pose[8]=in.pose[11]=exponential({{.3f,0,0}});return in;}
RecoveryMotion loadMotion(const std::string &path){
 std::ifstream stream(path);check(bool(stream),"original get-up animation is readable");
 std::map<std::string,std::vector<float>> tracks;std::string line;
 while(std::getline(stream,line)){
  const auto comma=line.find(',');if(comma==std::string::npos)continue;
  const std::string name=line.substr(0,comma);if(name!="player" && name!="body" && name!="middle" && name!="neck" && name.find("left_")!=0 && name.find("right_")!=0)continue;
  std::stringstream tokens(line.substr(comma+1));std::string token;while(std::getline(tokens,token,','))tracks[name].push_back(std::stof(token));
 }
 const auto &root=tracks.at("player");RecoveryMotion result(unsigned(root[root.size()-4])+1);
 for(unsigned frame=0;frame<result.size();++frame){
  for(unsigned bone=0;bone<13;++bone){const auto &track=tracks.at(pes3::nativeBoneNames[bone]);unsigned a=0;
   while(a+5<track.size() && track[a+5]<=frame)a+=5;
   const unsigned b=std::min(a+5,unsigned(track.size()-5));const float t=b==a?0:bounded((frame-track[a])/(track[b]-track[a]),0,1);
   Quat qa,qb;for(unsigned c=0;c<4;++c){qa[c]=track[a+1+c];qb[c]=track[b+1+c];}result[frame].pose[bone]=blended(qa,qb,t);
  }
  unsigned a=0;while(a+4<root.size() && root[a+4]<=frame)a+=4;
  const unsigned b=std::min(a+4,unsigned(root.size()-4));const float t=b==a?0:bounded((frame-root[a])/(root[b]-root[a]),0,1);
  for(unsigned c=0;c<3;++c)result[frame].pelvis[c]=root[a+1+c]*(1-t)+root[b+1+c]*t;
 }
 return result;
}
float armClearance(const PhysicalRig&r){
 float minimum=10;
 for(unsigned elbow:{4u,6u})for(unsigned sample=0;sample<=6;++sample){
  Vec point=addPoint(r.points()[elbow],rotatePoint(r.worldRotations()[elbow],{{0,0,-.25f*sample/6}}));
  point=rotatePoint(inverseRotation(r.worldRotations()[1]),subtractPoint(point,r.points()[1]));
  if(point[2]<-.1f || point[2]>.45f)continue;
  minimum=std::min(minimum,std::sqrt(point[0]*point[0]/(.185f*.185f)+point[1]*point[1]/(.135f*.135f)));
 }
 return minimum;
}
}
int main(int argc,char **argv){
 const std::string root=argc>1?argv[1]:"data/media/animations";
 const auto front=loadMotion(root+"/movement_special/idle/special/000_stand_up_from_front.anim");
 const auto back=loadMotion(root+"/movement_special/idle/special/000_stand_up_from_back.anim");
 check(front.size()>50 && back.size()>50,"front and back get-up retain their complete authored tracks");
 PhysicalRig rig;const auto bind=bindPose();Input in=standing();rig.configure(bind,1);rig.setRecoveryMotions(front,back);rig.step(in);rig.impulse({{165,0,0}},{{0,0,.18f}});
 unsigned recoverySamples=0;bool finite=true,returned=false;float low=10,high=0,peakStep=0;Vec last=rig.points()[0];
 for(unsigned i=0;i<1000;++i){rig.step(in);for(auto point:rig.points())for(float v:point)finite&=std::isfinite(v);
  if(rig.mode()==Mode::Recovering){++recoverySamples;low=std::min(low,rig.points()[0][2]);high=std::max(high,rig.points()[0][2]);peakStep=std::max(peakStep,length(subtractPoint(last,rig.points()[0])));}
  if(recoverySamples && rig.mode()==Mode::Active)returned=true;last=rig.points()[0];
 }
 check(recoverySamples>100 && returned,"original get-up motion completes before control resumes");
 check(finite && low<.4f && high>.75f,"get-up spans ground to standing without invalid coordinates");
 check(peakStep<.07f,"supported recovery does not teleport the pelvis upwards");
 rig.configure(bind,1);in=standing();in.pose[3]=exponential({{0,.95f,0}});in.pose[5]=exponential({{0,-.95f,0}});
 for(unsigned i=0;i<100;++i)rig.step(in);
 const float clearance=armClearance(rig);check(clearance>.96f,"crossed forearms are separated from the trunk envelope");
 rig.configure(bind,1);in=standing();in.protect=true;in.handTargetActive=true;in.handTarget={{.52f,0,1.30f}};
 Vec handBefore;float minimumGap=10,peakHandStep=0;
 for(unsigned i=0;i<150;++i){rig.step(in);Vec hand=addPoint(rig.points()[4],rotatePoint(rig.worldRotations()[4],{{0,0,-.25f}}));
  minimumGap=std::min(minimumGap,length(subtractPoint(hand,in.handTarget)));if(i)peakHandStep=std::max(peakHandStep,length(subtractPoint(hand,handBefore)));handBefore=hand;}
 check(minimumGap<.10f,"protective hand can reach a shirt within anatomical arm length");
 check(peakHandStep<.05f,"protective arm reaches gradually rather than snapping to its target");
 std::vector<Vec> rest,normals;std::vector<float> mobility;std::vector<unsigned> triangles;
 for(unsigned y=0;y<7;++y)for(unsigned x=0;x<7;++x){rest.push_back({{(x-3.f)*.05f,0,1.f+y*.05f}});normals.push_back({{0,1,0}});mobility.push_back(x && y && x<6 && y<6?1.f:0.f);}
 for(unsigned y=0;y<6;++y)for(unsigned x=0;x<6;++x){unsigned a=y*7+x;triangles.insert(triangles.end(),{a,a+1,a+7,a+1,a+8,a+7});}
 ShirtCloth cloth;cloth.configure(rest,triangles,mobility);
 for(unsigned i=0;i<150;++i)cloth.step(rest,normals,.01f,{{0,0,1.15f}},{{0,120,0}});
 const float deformation=cloth.displacement(),stretch=cloth.stretch();bool pinned=true,outside=true;
 for(unsigned i=0;i<rest.size();++i){if(!mobility[i])pinned&=length(subtractPoint(rest[i],cloth.positions()[i]))<1e-6f;outside&=cloth.positions()[i][1]>=-.00001f;}
 check(pinned,"shirt attachment vertices remain fixed on the animated body");
 check(outside,"cloth does not move inward through its animated skin surface");
 check(deformation>.003f && deformation<=.121f && stretch<1.5f,"cloth grip produces bounded, coupled surface deformation");
 for(unsigned i=0;i<300;++i)cloth.step(rest,normals,.01f,{{0,0,1.15f}},{{0,0,0}});
 check(cloth.displacement()<deformation*.35f,"released shirt relaxes toward the body instead of retaining a stretched pose");
 for(auto &point:rest)point[0]+=10;
 cloth.step(rest,normals,.01f,{{0,0,0}},{{0,0,0}});
 check(cloth.displacement()<.01f,"teleport/reset clears cloth inertia instead of creating an explosive stretch");
 std::cout<<"{\"result\":\""<<(failures?"failed":"passed")<<"\",\"checks\":"<<checks<<",\"failures\":"<<failures<<",\"recovery_samples\":"<<recoverySamples<<",\"recovery_pelvis_step_m\":"<<peakStep<<",\"forearm_trunk_clearance_ratio\":"<<clearance<<",\"hand_gap_m\":"<<minimumGap<<",\"hand_step_m\":"<<peakHandStep<<",\"cloth_deformation_m\":"<<deformation<<",\"cloth_stretch_ratio\":"<<stretch<<"}\n";
 return failures?1:0;
}
