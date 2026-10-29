#include "onthepitch/player/humanoid/physical_rig.hpp"
#include "onthepitch/player/humanoid/adaptive_reception.hpp"
#include "onthepitch/player/humanoid/shirt_cloth.hpp"
#include "onthepitch/player/humanoid/anatomical_arms.hpp"
#include "onthepitch/player/humanoid/contact_resistance.hpp"
#include "onthepitch/player/humanoid/body_ball_response.hpp"
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
 for(float height:{.3f,.6f,.9f,1.15f}){
  const auto bind=bindPose();auto pose=standing().pose;const Vec root{{0,0,.96f}};Pose world;Points points;
  football_reach::fk(bind,pose,root,world,points);const auto support=points[9];
  football_reach::leg(bind,pose,root,10,{{-.087f,-.35f,height}});
  football_reach::fk(bind,pose,root,world,points);
  check(length(subtractPoint(points[12],{{-.087f,-.35f,height}}))<.001f,"airborne reach actually reaches the requested ankle location");
  check(std::fabs(length(subtractPoint(points[11],points[10]))-length(bind.offsets[11]))<1e-5f&&std::fabs(length(subtractPoint(points[12],points[11]))-length(bind.offsets[12]))<1e-5f,"airborne reach preserves thigh and shin lengths");
  check(length(subtractPoint(points[9],support))<1e-6f,"reaching leg does not displace the opposite support shoe");
 }
 for(float height:{.16f,.32f,.64f}){
  const float apex=.12f+std::sqrt(2*height/9.81f),landing=.12f+2*std::sqrt(2*height/9.81f);
  check(football_reach::jump(0,height)==0&&std::fabs(football_reach::jump(apex,height)-height)<1e-5f&&football_reach::jump(landing+.01f,height)==0,"jump has grounded takeoff, physical apex and grounded landing");
 }
 for(bool cushion:{false,true}){
  const Vec grazing{{-.01f,0,-2.f}},normal{{1,0,0}};
  const Vec after=football_contacts::bodyResponse(grazing,normal,cushion);
  check(after[2]<-1.99f,"a nearly unloaded back contact preserves the ball's downward slide");
  check(after[0]>0&&length(after)<=length(grazing),"stationary skin friction cannot add energy");
  const Vec incoming{{-8,0,-3}},absorbed=football_contacts::bodyResponse(incoming,normal,cushion);
  check(length(absorbed)<length(incoming)&&absorbed[0]>0,"a real normal impulse can dissipate a driven ball");
  check(football_contacts::bodyResponse({{1,0,-2}},normal,cushion)==Vec{{1,0,-2}},"a separating ball is not pulled back onto the body");
 }
 {
  const Vec normal{{1,0,0}},incoming{{-2,7,0}};
  const auto deliberate=football_contacts::preparedControlResponse(incoming,normal);
  const auto passive=football_contacts::bodyResponse(incoming,normal,true);
  check(length(deliberate)<length(passive)*.3f&&deliberate[0]>=0,"a single prepared leg reception absorbs its measured incoming momentum without reversing into the surface");
  check(football_contacts::preparedControlResponse({{1,4,0}},normal)==Vec{{1,4,0}},"a prepared gesture cannot capture an already separating ball");
 }
 const std::string root=argc>1?argv[1]:"data/media/animations";
 const auto front=loadMotion(root+"/movement_special/idle/special/000_stand_up_from_front.anim");
 const auto back=loadMotion(root+"/movement_special/idle/special/000_stand_up_from_back.anim");
 check(front.size()>50 && back.size()>50,"front and back get-up retain their complete authored tracks");
 PhysicalRig rig;const auto bind=bindPose();Input in=standing();rig.configure(bind,1);rig.setRecoveryMotions(front,back);rig.step(in);rig.impulse({{165,0,0}},{{0,0,.18f}},true);
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
 check(rig.metrics().elbowAngle>=.14f && rig.metrics().elbowAngle<=2.41f && rig.metrics().armSpeed<=3.81f,"shirt reach respects elbow flexion and angular-speed limits");
 float maximumArmError=0,maximumArmOverlap=0,maximumElbowSwing=0;
 bool elbowForward=true;
 for(Vec target:std::vector<Vec>{{{.52f,0,1.30f}},{{-.52f,0,1.3f}},{{0,.6f,1.2f}},{{0,-.5f,1.8f}},{{0,0,.9f}}}){
  rig.configure(bind,1);in=standing();in.handTargetActive=in.protect=true;in.handTarget=target;
  for(unsigned tick=0;tick<180;++tick){
   if(tick==40)rig.impulse({{125,0,0}},{{0,0,.18f}});
   rig.step(in);
   for(unsigned bone:{3u,4u,5u,6u})maximumArmError=std::max(maximumArmError,armLimitError(bone,rig.pose()[bone]));
   for(unsigned bone:{4u,6u}){const auto q=rig.pose()[bone];const Quat hinge=normalized({{q[0],0,0,q[3]}});
    elbowForward &=2*std::atan2(hinge[0],hinge[3])<=-.024f;
    maximumElbowSwing=std::max(maximumElbowSwing,length(logarithm(productRotation(q,inverseRotation(hinge)))));
   }
   maximumArmOverlap=std::max(maximumArmOverlap,rig.metrics().armPenetration);
  }
 }
 check(maximumArmError<1e-5f,"final mixed shoulders and elbows respect swing/twist limits during impact and unreachable shirt targets");
 check(elbowForward && maximumElbowSwing<=.1001f,"final visible elbows never hyperextend or bend sideways like a broken arm");
 check(maximumArmOverlap<.001f,"final reaching forearms stay outside the torso proxy during cross-body and behind-back targets");
 bool projectionStable=true;
 for(unsigned bone:{3u,4u,5u,6u})for(unsigned i=0;i<100;++i){
  const auto q=anatomicalArm(bone,exponential({{std::sin(float(i))*3,std::cos(float(i))*3,std::sin(i*.7f)*3}}));
  projectionStable &=armLimitError(bone,q)<1e-5f;
 }
 check(projectionStable,"anatomical projection remains finite and idempotent over extreme rotations");
 const Vec freeVelocity=contactVelocity({{0,-1,0}},{{0,200,0}},false);
 const Vec protectedVelocity=contactVelocity({{0,-1,0}},{{0,200,0}},true);
 check(length(freeVelocity)<.10f && length(protectedVelocity)>.9f,"shirt traction slows intended locomotion while a planted shield resists ordinary pulling force");
 check(length(subtractPoint(contactVelocity({{0,-1,0}},{{0,-200,0}},false),{{0,-1,0}}))<1e-6f,"shirt resistance cannot accelerate a player when its force points along travel");
 bool stayedUp=true,usedStep=false;float peakRisk=0;
 for(unsigned direction=0;direction<8;++direction){
  rig.configure(bind,1);in=standing();rig.step(in);const float angle=direction*3.14159265f/4;
  rig.impulse({{190.f*std::cos(angle),190.f*std::sin(angle),0}},{{0,0,.18f}});
  for(unsigned tick=0;tick<200;++tick){rig.step(in);stayedUp&=rig.mode()==Mode::Active;usedStep|=length(rig.balanceVelocity())>.1f;peakRisk=std::max(peakRisk,rig.metrics().balanceRisk);}
 }
 check(stayedUp && usedStep,"ordinary running contact attempts corrective steps in eight directions without automatically falling");
 rig.configure(bind,1);in=standing();rig.step(in);rig.impulse({{190,0,0}},{{0,0,.18f}});
 float committedSpeed=0;
 for(unsigned tick=0;tick<36;++tick){rig.step(in);if(tick==34)committedSpeed=length(rig.balanceVelocity());}
 check(committedSpeed>.10f,"support step persists long enough to cross a native idle-animation transition");
 rig.configure(bind,1);in=standing();rig.step(in);rig.impulse({{350,0,0}},{{0,0,.28f}});
 unsigned fallTick=0;
 for(unsigned tick=1;tick<100;++tick){rig.step(in);if(rig.mode()==Mode::Falling){fallTick=tick;break;}}
 check(fallTick>=20 && fallTick<60,"an unrecoverable impulse causes a fall only after a recovery attempt");
 rig.configure(bind,1);in=standing();in.gripped=true;rig.step(in);bool pulledDown=false;
 for(unsigned tick=0;tick<500;++tick){rig.impulse({{2.6f,0,0}},{{0,0,.24f}});rig.step(in);if(rig.mode()==Mode::Falling){pulledDown=true;break;}}
 check(pulledDown,"sustained shirt traction can overcome the restricted support step");
 // Same-tick phase sampling must not accelerate the reaching arm.
 rig.configure(bind,1);in=standing();in.protect=true;in.handTargetActive=true;in.handTarget={{.52f,0,1.30f}};
 for(unsigned i=0;i<50;++i)rig.step(in);
 const Pose handPose=rig.pose();for(unsigned i=0;i<30;++i)rig.evaluate(in);
 check(length(logarithm(productRotation(handPose[3],inverseRotation(rig.pose()[3]))))<1e-6f,"repeated animation sampling cannot advance hand IK within one tick");
 rig.configure(bind,1);in=standing();in.velocity={{7,0,0}};float transportError=0;
 for(unsigned tick=0;tick<400;++tick){in.pelvis[0]=.07f*tick;rig.step(in);if(tick>50)transportError=std::max(transportError,rig.metrics().jointError);}
 check(transportError<.04f,"kinematic substeps keep sprinting upper-body joint anchors together without alternating double-speed transport");
 std::vector<BalanceMotion> choices(2);
 for(unsigned i=0;i<2;++i){choices[i].frames.resize(3);for(auto &key:choices[i].frames)key.pose=standing().pose;choices[i].push={{1,0,0}};choices[i].speed=i?5.f:3.f;choices[i].lateral=0;}
 rig.configure(bind,1);rig.setBalanceMotions(choices);in=standing();in.velocity={{5,0,0}};rig.step(in);rig.impulse({{65,0,0}});rig.step(in);
 check(rig.metrics().balanceChoice==1,"reference matching distinguishes the effective playback speed of motion variants");
 for(unsigned i=0;i<2;++i){choices[i].speed=0;choices[i].lateral=i?.035f:-.035f;}
 bool matchedSides=true;
 for(int direction:{-1,1}){rig.configure(bind,1);rig.setBalanceMotions(choices);in=standing();rig.step(in);rig.impulse({{65.f*direction,0,0}});rig.step(in);matchedSides&=rig.metrics().balanceChoice==(direction<0?0:1);}
 check(matchedSides,"left and right balance variants respond to the incident side rather than tying permanently");
 choices.resize(1);rig.setBalanceMotions(choices);rig.impulse({{65,0,0}});rig.step(in);
 check(rig.metrics().balanceChoice==0,"replacing the reference bank clears the previous selection safely");
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
 float peakRunningJitter=0,frameRateSpread=0,minimumOffset=100,maximumOffset=0;
 for(float frameDt:{.01f,1.f/60,1.f/30,1.f/15}){
  ShirtCloth moving;moving.configure(rest,triangles,mobility);std::vector<Vec> target=rest;float lastOffset=0;
  for(unsigned frame=0;frame<unsigned(5/frameDt);++frame){
   for(unsigned i=0;i<rest.size();++i)target[i]=addPoint(rest[i],{{7.f*frame*frameDt,0,0}});
   moving.step(target,normals,frameDt,{{0,0,0}},{{0,0,0}});
   if(frame*frameDt>3.f)peakRunningJitter=std::max(peakRunningJitter,std::fabs(moving.displacement()-lastOffset));
   lastOffset=moving.displacement();
  }
  minimumOffset=std::min(minimumOffset,moving.displacement());maximumOffset=std::max(maximumOffset,moving.displacement());
 }
 frameRateSpread=maximumOffset-minimumOffset;
 check(peakRunningJitter<.001f,"shirt at constant sprint speed settles without repeated frame-to-frame snapping");
 check(frameRateSpread<.003f,"shirt response remains close across 15, 30, 60 and 100 FPS");
 const float beforeZeroDt=cloth.displacement();for(auto &point:rest)point[0]+=.1f;
 cloth.step(rest,normals,0,{{0,0,0}},{{0,0,0}});
 check(std::fabs(cloth.displacement()-beforeZeroDt)<1e-5f,"interpolated render with no new simulation tick transports the shirt without injecting inertia");
 std::cout<<"{\"result\":\""<<(failures?"failed":"passed")<<"\",\"checks\":"<<checks<<",\"failures\":"<<failures<<",\"recovery_samples\":"<<recoverySamples<<",\"recovery_pelvis_step_m\":"<<peakStep<<",\"forearm_trunk_clearance_ratio\":"<<clearance<<",\"hand_gap_m\":"<<minimumGap<<",\"hand_step_m\":"<<peakHandStep<<",\"cloth_deformation_m\":"<<deformation<<",\"cloth_stretch_ratio\":"<<stretch<<",\"running_cloth_jitter_m\":"<<peakRunningJitter<<",\"cloth_fps_spread_m\":"<<frameRateSpread<<",\"ordinary_contact_peak_risk\":"<<peakRisk<<",\"unrecoverable_fall_tick\":"<<fallTick<<",\"sprint_joint_error_m\":"<<transportError<<",\"maximum_arm_limit_error_rad\":"<<maximumArmError<<",\"maximum_arm_overlap_m\":"<<maximumArmOverlap<<",\"maximum_elbow_side_bend_rad\":"<<maximumElbowSwing<<"}\n";
 return failures?1:0;
}
