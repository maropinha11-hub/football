// Numerical and behavioral checks for the native articulated-body experiment.
#include "onthepitch/player/humanoid/physical_rig.hpp"
#include "onthepitch/player/humanoid/motion_matching.hpp"
#include "onthepitch/player/humanoid/walking_gait.hpp"
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
bool finite(const PhysicalRig &r){if(!std::isfinite(r.metrics().kineticEnergy))return false;for(auto p:r.points())for(float x:p)if(!std::isfinite(x)||std::fabs(x)>10000)return false;for(auto q:r.pose()){float n=0;for(float x:q)n+=x*x;if(!std::isfinite(n)||std::fabs(n-1)>.001f)return false;}return true;}
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
  {
    bool support=true,links=true;float maxLift=0;Pose start{},end{};
    for(int f=0;f<=200;++f){const float t=f/200.f;
      const auto a=football_walk::foot(t,.45f,.09f),b=football_walk::foot(t+.5f,.45f,-.09f);
      support&=std::min(a[2],b[2])<.00001f;maxLift=std::max(maxLift,std::max(a[2],b[2]));
      auto pose=bind.rotations;football_walk::pose(bind,pose,{{0,0,.92f}},t,.45f);
      if(f==0)start=pose;if(f==200)end=pose;
      for(const auto &q:pose){float n=0;for(float x:q)n+=x*x;links&=std::isfinite(n)&&std::fabs(n-1)<.001f;}
    }
    const float touchPhase=football_walk::stanceFraction*.5f+.5f;
    const auto contact=football_walk::foot(touchPhase,.52f,0);
    check(std::fabs(contact[1])<1e-6f&&contact[2]>.044f,"walking contact remains at mid-swing when the support duration changes");
    float seam=0;for(unsigned b=7;b<13;++b)seam=std::max(seam,length(logarithm(productRotation(start[b],inverseRotation(end[b])))));
    check(support&&maxLift>.04f&&maxLift<.05f,"walking has overlapping ground support with a low lifted swing rather than a jogging flight phase");
    check(links&&seam<.001f,"the derived walking leg cycle stays finite and loops continuously on the native skeleton");
  }
  {
    bool taller=true,extended=true,links=true;float minimum=10,maximum=0;
    for(unsigned frame=0;frame<240;++frame){
      const float phase=frame/240.f;Pose pose=standing().pose;
      Vec pelvis{{0,0,football_walk::pelvisHeight(bind,phase,.52f)}};
      minimum=std::min(minimum,pelvis[2]);maximum=std::max(maximum,pelvis[2]);
      football_walk::pose(bind,pose,pelvis,phase,.52f);
      taller&=pelvis[2]>.90f;extended&=std::min(length(logarithm(pose[8])),length(logarithm(pose[11])))<.40f;
      Input source=standing();source.pose=pose;source.pelvis=pelvis;PhysicalRig walk;walk.configure(bind,1);walk.step(source);
      links&=boneError(walk,bind)<1e-5f;
    }
    check(taller&&extended,"walking has an extended support leg instead of keeping both knees squatted");
    check(links&&maximum-minimum<.04f,"walking stance follows reachable leg geometry with bounded pelvic bob");
  }
  {
    PhysicalRig persistent;persistent.configure(bind,1);Input quiet=standing();quiet.passiveTracking=true;
    unsigned maximumBuilds=0;bool activeMuscles=true;
    for(unsigned tick=0;tick<600;++tick){quiet.passiveTracking=(tick/30)%2==0;persistent.step(quiet);
      maximumBuilds=std::max(maximumBuilds,persistent.metrics().physicalWorldBuilds);
      activeMuscles&=persistent.metrics().neuralMotorSamples>0;
    }
    check(activeMuscles&&maximumBuilds==1,"stopping and starting CPU tracking preserves one continuously controlled body world");
    persistent.impulse({{165,0,0}},{{0,0,.18f}},true);
    float protection=0,hand=10,torque=0;unsigned protectedFrames=0;
    for(unsigned tick=0;tick<850;++tick){persistent.step(quiet);maximumBuilds=std::max(maximumBuilds,persistent.metrics().physicalWorldBuilds);
      if(persistent.mode()==Mode::Falling){
        const auto &m=persistent.metrics();protection=std::max(protection,m.protectiveReach);torque=std::max(torque,m.fallControl);
        if(m.protectiveReach>.25f)++protectedFrames;
        for(unsigned elbow:{4u,6u}){
          const Vec tip=addPoint(persistent.points()[elbow],rotatePoint(persistent.worldRotations()[elbow],{{0,0,-.25f}}));
          if(m.protectiveReach>.25f)hand=std::min(hand,tip[2]);
        }
      }
    }
    check(protection>.5f&&protectedFrames>12&&hand<.15f&&torque>12.f,"a falling body actively places protective arms toward the ground with muscular effort");
    check(maximumBuilds==1&&persistent.mode()==Mode::Active,"fall and get-up reuse the physical assembly instead of reallocating it");
  }
  // Unauthored support steps must lift a shoe under a recoverable push,
  // keep the opposite support and return smoothly without a trip animation.
  for(float dt:{.005f,.01f,.02f})for(Vec push:{Vec{{125,0,0}},Vec{{-125,0,0}},Vec{{0,125,0}},Vec{{0,-125,0}}}){
    PhysicalRig recovery;recovery.configure(bind,1);Input standingInput=standing();recovery.step(standingInput,dt);
    recovery.impulse(push);float lift=0,actualLift=0,supportError=0,shoeSpeed=0,links=0;bool generated=false,stable=true;
    Vec prior[2]={recovery.points()[9],recovery.points()[12]};const Vec initialFeet[2]={prior[0],prior[1]};
    for(unsigned tick=0;tick<unsigned(2.f/dt);++tick){
      standingInput.velocity=recovery.balanceVelocity();standingInput.pelvis=addPoint(standingInput.pelvis,scalePoint(standingInput.velocity,dt));
      recovery.step(standingInput,dt);const auto &m=recovery.metrics();
      generated|=m.recoveryStep>.5f;lift=std::max(lift,m.recoveryLift);
      if(m.recoveryFoot>=0)actualLift=std::max(actualLift,recovery.points()[m.recoveryFoot?12:9][2]-initialFeet[m.recoveryFoot][2]);supportError=std::max(supportError,m.recoverySupportError);
      for(unsigned side=0;side<2;++side){const Vec now=recovery.points()[side?12:9];shoeSpeed=std::max(shoeSpeed,length(subtractPoint(now,prior[side]))/dt);prior[side]=now;}
      links=std::max(links,boneError(recovery,bind));stable&=finite(recovery)&&recovery.mode()==Mode::Active;
      const Vec before=recovery.points()[12];recovery.evaluate(standingInput);
      stable&=length(subtractPoint(before,recovery.points()[12]))<1e-6f;
    }
    check(generated&&lift>.045f&&actualLift>.025f,"capture-point load generates a lifted recovery step without a reference clip");
    check(stable&&links<1e-5f&&supportError<.05f&&shoeSpeed<2.3f,"generated step retains support, finite bone lengths and bounded shoe velocity at supported timesteps");
    check(recovery.metrics().recoveryStep<.001f&&recovery.metrics().balanceRisk<.03f,"generated step finishes and returns to ordinary active locomotion");
  }
  {
    PhysicalRig recovery;recovery.configure(bind,1);Input v=standing();recovery.step(v);recovery.impulse({{125,0,0}});
    for(unsigned i=0;i<15;++i)recovery.step(v);v.action=v.touchPending=true;
    for(unsigned i=0;i<30;++i)recovery.step(v);
    check(recovery.metrics().recoveryStep<.001f,"queued ball action releases the generated support before its contact");
  }
  {
    PhysicalRig recovery;recovery.configure(bind,1);Input v=standing();recovery.step(v);recovery.impulse({{125,0,0}});
    for(unsigned i=0;i<18;++i)recovery.step(v);
    check(recovery.metrics().recoveryStep>.5f,"fall interruption starts during an actual generated support step");
    recovery.impulse({{170,0,0}},{{0,0,.18f}},true);
    for(unsigned i=0;i<800;++i)recovery.step(v);
    check(recovery.mode()==Mode::Active&&recovery.metrics().recoveryStep==0&&finite(recovery),"fall and get-up discard the old procedural foot anchors");
    recovery.configure(bind,1);v=standing();v.velocity={{0,-7,0}};recovery.step(v);recovery.impulse({{125,0,0}});
    for(unsigned i=0;i<15;++i)recovery.step(v);
    check(recovery.metrics().recoveryStep==0,"fast sprint does not pin a recovery shoe to an obsolete world position");
  }
  for(bool reaching:{false,true}){
    PhysicalRig recovery;recovery.configure(bind,1);Input v=standing();
    v.handTargetActive=reaching;v.handTarget={{.25f,-.20f,1.25f}};v.opponentDistance=reaching?1.f:.30f;
    recovery.step(v);recovery.impulse({{125,0,0}});float stepWeight=0,counter=0;
    for(unsigned i=0;i<80;++i){recovery.step(v);stepWeight=std::max(stepWeight,recovery.metrics().recoveryStep);counter=std::max(counter,recovery.metrics().counterbalance);}
    check(stepWeight==0&&counter>.01f&&finite(recovery),"hand constraints and close bodies retain muscle balance without a conflicting free step");
  }
  {
    PhysicalRig recovery;recovery.configure(bind,1);Input v=standing();recovery.step(v);recovery.impulse({{125,0,0}});
    for(unsigned i=0;i<15;++i)recovery.step(v);v.action=true;recovery.step(v);v.action=false;
    for(unsigned i=0;i<40;++i)recovery.step(v);
    check(recovery.metrics().recoveryStep==0,"even a one-tick action interruption commits a smooth support release");
    recovery.configure(bind,1);v=standing();v.pose[10]=exponential({{-.5f,0,0}});v.pose[11]=exponential({{1.4f,0,0}});recovery.step(v);
    const unsigned freeSide=recovery.points()[9][2]>recovery.points()[12][2]?0:1;
    recovery.impulse({{125,0,0}});recovery.step(v);
    check(recovery.metrics().recoveryFoot==int(freeSide),"recovery swings the free shoe while the lower loaded shoe remains support");
  }
  {
    PhysicalRig recovery;recovery.configure(bind,1);Input v=standing();recovery.step(v);recovery.impulse({{125,0,0}});
    for(unsigned i=0;i<15;++i)recovery.step(v);v.pelvis[0]+=8.f;recovery.step(v);
    check(recovery.metrics().recoveryStep==0&&recovery.metrics().balanceRisk==0&&finite(recovery),"a restart relocation clears stale support anchors and momentum");
    recovery.configure(bind,1);v=standing();v.velocity={{1.8f,0,0}};recovery.step(v);recovery.impulse({{125,0,0}});
    float supportError=0;for(unsigned i=0;i<100;++i){v.pelvis[0]+=.018f;recovery.step(v);supportError=std::max(supportError,recovery.metrics().recoverySupportError);}
    check(supportError<.06f&&recovery.metrics().recoveryStep==0&&finite(recovery),"a travelling base releases an obsolete support instead of straining the planted leg");
  }
  {
    PhysicalRig hands;hands.configure(bind,1);Input v=standing();hands.step(v);
    const Vec rightHand=addPoint(hands.points()[6],rotatePoint(hands.worldRotations()[6],{{0,0,-.25f}}));
    const Pose before=hands.pose();const bool reached=hands.adoptContactHand(rightHand);float jump=0;
    for(unsigned i=0;i<13;++i)jump=std::max(jump,length(logarithm(productRotation(before[i],inverseRotation(hands.pose()[i])))));
    check(reached&&hands.activeHandBone()==6&&jump<1e-6f,"a real idle-hand contact becomes the tracked grip hand without changing its pose");
    check(!hands.adoptContactHand({{10,0,0}})&&hands.activeHandBone()==6,"an out-of-reach shirt cannot create or switch a grip hand");
    v.handTargetActive=true;v.handTarget=rightHand;
    float drift=0;for(unsigned i=0;i<60;++i){hands.step(v);const Vec actual=addPoint(hands.points()[6],rotatePoint(hands.worldRotations()[6],{{0,0,-.25f}}));drift=std::max(drift,length(subtractPoint(actual,rightHand)));}
    check(drift<.10f&&hands.metrics().armSpeed<3.81f&&boneError(hands,bind)<1e-5f,"the adopted hand follows its actual contact with bounded joints and no limb stretching");
  }
  {
    PhysicalRig hit,reference;hit.configure(bind,1);reference.configure(bind,1);Input v=standing();v.action=true;
    hit.step(v);reference.step(v);float visible=0,footError=0;
    for(unsigned tick=1;tick<80;++tick){
      Input withHit=v;withHit.ballImpact={{0,-12,0}};withHit.ballImpactAge=tick*.01f;hit.step(withHit);reference.step(v);
      visible=std::max(visible,length(logarithm(productRotation(hit.pose()[1],inverseRotation(reference.pose()[1])))));
      footError=std::max(footError,length(subtractPoint(hit.points()[12],reference.points()[12])));
    }
    check(visible>.05f&&footError<.001f&&boneError(hit,bind)<1e-5f,"a ball impact causes a visible bounded reflex even during another action, preserving the contact foot");
    check(hit.metrics().neuralMotorSamples>0,"impact reference reaches the actual learned muscular tracker");
    hit.configure(bind,1);reference.configure(bind,1);hit.step(v);reference.step(v);visible=0;
    for(unsigned tick=1;tick<70;++tick){
      Input vertical=v;vertical.ballImpact={{0,0,-5}};vertical.ballImpactLever={{0,.22f,.45f}};vertical.ballImpactAge=tick*.01f;
      hit.step(vertical);reference.step(v);visible=std::max(visible,length(logarithm(productRotation(hit.pose()[1],inverseRotation(reference.pose()[1])))));
    }
    check(visible>.07f&&boneError(hit,bind)<1e-5f,"a descending ball has a visible shoulder/back reflex through its actual moment arm");
  }
  PhysicalRig rig;Input input=standing();rig.configure(bind,1);
  {
    float sink[2]={0,0},knees[2]={0,0},feet=0;
    for(unsigned strength=0;strength<2;++strength){
      PhysicalRig strike;strike.configure(bind,1);Input action=standing();action.action=action.touchPending=true;
      action.situation.kind=football_situations::ActionKind::Shot;action.situation.contactPhase=.6f;
      action.situation.power=strength?.95f:.1f;action.situation.signedTurn=.7f;
      for(unsigned tick=0;tick<50;++tick){action.situation.phase=tick*.01f;strike.step(action);
        sink[strength]=std::max(sink[strength],strike.metrics().supportSink);
        knees[strength]=std::max(knees[strength],strike.metrics().supportKnee);
        feet=std::max(feet,strike.metrics().supportFootError);
      }
    }
    check(sink[1]>sink[0]*1.5f&&knees[1]>knees[0]*1.2f,"stronger shots recruit visibly more pelvis and knee preparation before contact");
    check(feet<.0035f,"whole-body shot preparation keeps both actual support shoes in place");
  }
  float maximumBoneError=0,peakLean=0,peakCounterbalance=0;
  rig.step(input);const Vec initialLeft=rig.points()[9],initialRight=rig.points()[12];
  rig.impulse({{65,0,0}});
  for(unsigned step=0;step<300;++step){rig.step(input);peakCounterbalance=std::max(peakCounterbalance,rig.metrics().counterbalance);peakLean=std::max(peakLean,rig.metrics().lean);maximumBoneError=std::max(maximumBoneError,boneError(rig,bind));}
  check(rig.mode()==Mode::Active && peakLean>.02f,"a light impulse disturbs balance without dropping the body");
  check(peakCounterbalance>.005f && rig.metrics().counterbalance<.001f,"external momentum recruits bounded upper-body counterbalance and settles");
  check(rig.metrics().lean<.003f,"damped balance returns to rest");
  check(length(subtractPoint(initialLeft,rig.points()[9]))<.012f && length(subtractPoint(initialRight,rig.points()[12]))<.012f,"stance feet remain anchored during a recoverable push");
  float minimumPelvis=10;unsigned fell=0,recovered=0;Mode previous=rig.mode();
  rig.impulse({{165,0,0}},{{0,0,.18f}},true);
  bool allFinite=true;float accumulatedRotation=0,peakAngular=0,peakJointError=0;Quat lastRoot=rig.pose()[0];
  float muscleWork=0;unsigned muscularFallSamples=0;
  for(unsigned step=0;step<800;++step){rig.step(input);if(rig.mode()==Mode::Falling){accumulatedRotation+=length(logarithm(productRotation(rig.pose()[0],inverseRotation(lastRoot))));peakAngular=std::max(peakAngular,rig.metrics().angularSpeed);peakJointError=std::max(peakJointError,rig.metrics().jointError);}lastRoot=rig.pose()[0];allFinite&=finite(rig);minimumPelvis=std::min(minimumPelvis,rig.points()[0][2]);maximumBoneError=std::max(maximumBoneError,boneError(rig,bind));if(rig.mode()!=previous){fell+=rig.mode()==Mode::Falling;recovered+=rig.mode()==Mode::Recovering;previous=rig.mode();}}
  // Repeat a short unsupported fall to observe actual dynamic joint motors.
  PhysicalRig falling;falling.configure(bind,1);falling.step(input);falling.impulse({{165,0,0}},{{0,0,.18f}},true);
  for(unsigned i=0;i<90;++i){falling.step(input);if(falling.mode()==Mode::Falling){muscleWork+=falling.metrics().muscleEffort;muscularFallSamples+=falling.metrics().muscleEffort>.001f;}}
  check(muscularFallSamples>50 && muscleWork>1.f,"dynamic fall retains bounded internal joint effort instead of going limp");
  check(fell==1 && recovered==1 && rig.mode()==Mode::Active,"the explicit lab fall produces fall, get-up and active control in order");
  check(minimumPelvis<.6f && minimumPelvis>.07f,"physical pelvis falls onto the ground instead of playing an upright trip");
  check(allFinite && maximumBoneError<1e-5f,"articulation remains finite and bones do not stretch through a fall");
  check(accumulatedRotation<5.0f && peakAngular<18.f,"a lateral fall does not spin the pelvis through a somersault");
  check(peakJointError<.08f,"Bullet constraints retain their anatomical joint anchors");
  for(float dt:{.005f,.01f,.02f}){
    rig.configure(bind,1);rig.step(input,dt);rig.impulse({{-190,0,0}},{{0,0,.5f}},true);
    for(unsigned i=0;i<unsigned(8/dt);++i)rig.step(input,dt);
    check(finite(rig) && rig.mode()==Mode::Active,"fall and recovery remain stable across supported timesteps");
  }
  rig.reset();rig.step(input);rig.impulse({{230,0,0}});rig.step(input);rig.reset();rig.step(input);
  check(rig.mode()==Mode::Active && std::fabs(rig.points()[0][2]-.96f)<.002f,"reset clears ragdoll momentum and pending impulses");
  // Reach targets move gradually, and unreachable targets cannot elongate a leg.
  rig.configure(bind,1);rig.step(input);input.reachBone=12;input.reach={{.14f,0,0}};input.reachWeight=1;
  Vec last=rig.points()[12];float maximumFootStep=0;
  for(unsigned step=0;step<70;++step){rig.step(input);maximumFootStep=std::max(maximumFootStep,length(subtractPoint(last,rig.points()[12])));last=rig.points()[12];}
  check(maximumFootStep<.007f && rig.metrics().reach>.07f,"contact reach approaches its target without a one-frame leg snap");
  check(boneError(rig,bind)<1e-5f,"two-bone reach preserves thigh and shin length");
  input.reachBone=-1;float maximumReturnStep=0;last=rig.points()[12];
  for(unsigned i=0;i<80;++i){rig.step(input);maximumReturnStep=std::max(maximumReturnStep,length(subtractPoint(last,rig.points()[12])));last=rig.points()[12];}
  check(maximumReturnStep<.006f && rig.metrics().reach<.001f,
    "the foot returns gradually after its contact marker disappears");
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
  PhysicalRig reachingSave;reachingSave.configure(bind,1);Input save=standing();save.action=true;reachingSave.step(save);
  const Vec oldElbow=reachingSave.points()[4];save.reachBone=4;save.reachWeight=1;save.reach={{.04f,-.03f,0}};
  float saveHandStep=0;Vec oldHand=reachingSave.points()[4];
  for(unsigned tick=0;tick<50;++tick){reachingSave.step(save);saveHandStep=std::max(saveHandStep,length(subtractPoint(reachingSave.points()[4],oldHand)));oldHand=reachingSave.points()[4];}
  check(length(subtractPoint(reachingSave.points()[4],oldElbow))>.002f&&saveHandStep<.01f&&boneError(reachingSave,bind)<1e-5f,
    "a save shoulder follows a small contact correction smoothly without stretching its arm");
  unsigned contexts=0,unsafeCuts=0;float matrixError=0;
  PhysicalRig supported;supported.configure(bind,1);Input planted=standing();planted.action=true;
  planted.situation.enabled=true;planted.situation.kind=football_situations::ActionKind::Pass;
  planted.situation.power=.8f;planted.situation.difficulty=.6f;planted.situation.contactPhase=.35f;
  planted.situation.contactMade=true;planted.situation.signedTurn=.8f;
  float supportSinkPeak=0,supportKneePeak=0,supportFootPeak=0,supportKneeStep=0;Vec priorKnee{};
  for(unsigned tick=0;tick<100;++tick){
    planted.situation.phase=.36f+.005f*tick;supported.step(planted);
    supportSinkPeak=std::max(supportSinkPeak,supported.metrics().supportSink);
    supportKneePeak=std::max(supportKneePeak,supported.metrics().supportKnee);
    supportFootPeak=std::max(supportFootPeak,supported.metrics().supportFootError);
    if(tick)supportKneeStep=std::max(supportKneeStep,length(subtractPoint(priorKnee,supported.points()[8])));
    priorKnee=supported.points()[8];
  }
  check(supportSinkPeak>.002f&&supportKneePeak>.003f,"a grounded release recruits the pelvis and knees instead of a rigid lower body");
  check(supportFootPeak<.0035f&&supportKneeStep<.008f&&boneError(supported,bind)<1e-5f,"support bends smoothly while preserving planted shoes and bone lengths");
  check(std::hypot(supported.points()[0][0],supported.points()[0][1])<1e-6f,"support compliance never replaces the commanded horizontal root travel");
  planted.touchPending=true;planted.situation.contactMade=false;planted.situation.phase=0;
  for(unsigned tick=0;tick<200;++tick)supported.step(planted);
  check(supported.metrics().supportSink<.0001f&&supported.metrics().supportTilt<.0001f,"preparing the next ball contact gradually restores the original support pose");
  supported.reset();supported.step(standing());check(supported.metrics().supportSink==0&&supported.metrics().supportTilt==0,"reset clears support compression and its velocities");
  PhysicalRig sourceSupport;sourceSupport.configure(bind,1);Input sourceInput=standing();sourceInput.action=true;sourceSupport.step(sourceInput);
  planted.touchPending=false;planted.situation.phase=.5f;
  for(unsigned tick=0;tick<80;++tick)supported.step(planted);
  check(length(subtractPoint(supported.points()[9],sourceSupport.points()[9]))<.0035f&&length(subtractPoint(supported.points()[12],sourceSupport.points()[12]))<.0035f,
    "final evaluated feet retain solved support after the upper-body layers, rather than restoring the old leg pose");
  PhysicalRig stepping;stepping.configure(bind,1);Input sideStep=standing();sideStep.grounding=true;sideStep.velocity={{.2f,0,0}};
  stepping.step(sideStep);const Vec stanceFoot=stepping.points()[9];float peakPlant=0;
  for(unsigned tick=1;tick<=30;++tick){sideStep.pelvis[0]=tick*.002f;stepping.step(sideStep);peakPlant=std::max(peakPlant,stepping.metrics().plantedCorrection);}
  check(peakPlant>.01f&&length(subtractPoint(stepping.points()[9],stanceFoot))<.055f,"side-step stance reduces shoe sliding while the pelvis advances");
  check(boneError(stepping,bind)<1e-5f&&peakPlant<=.0551f,"planted support preserves segment lengths and bounds foot adjustment");
  sideStep.touchPending=true;stepping.step(sideStep);
  check(stepping.metrics().plantedCorrection==0,"a queued ball action immediately regains its authored foot trajectory");
  bool matrixFinite=true;
  const std::string root=argc>1?argv[1]:"data/media/animations";
  std::array<Input,3> bases{{sourcePose(root+"/ballcontrol/walk/000.anim"),sourcePose(root+"/shot/idle/020.anim"),sourcePose(root+"/trap/idle/000_IB000.anim")}};
  for(float speed:{0.f,3.8f,7.f})for(float turn:{-4.2f,-1.2f,0.f,1.2f,4.2f})for(float height:{0.f,.06f,.12f})for(float side:{-.08f,0.f,.08f})for(float pressure:{.7f,100.f}){
    Input v=bases[contexts%3];rig.configure(bind,1);v.reachBone=12;v.reach={{side,0,height}};v.reachWeight=1;v.opponentDistance=pressure;v.opponent={{1,0,0}};
    for(unsigned tick=0;tick<70;++tick){const float yaw=turn*tick*.01f;v.forward={{std::sin(yaw),-std::cos(yaw),0}};v.velocity=scalePoint(v.forward,speed);v.pelvis={{0,0,.96f}};rig.step(v);matrixFinite&=finite(rig);matrixError=std::max(matrixError,boneError(rig,bind));}
    unsafeCuts+=rig.mode()==Mode::Falling;++contexts;
  }
  check(contexts==270 && matrixFinite && matrixError<1e-5f,"270 combinations of speed, turn, reach and pressure preserve a finite articulated skeleton");
  check(unsafeCuts==0,"animation turns alone do not synthesize an unphysical fall impulse");
  MotionFeature query,near,far;query.trajectory[2]={{0,-1,0}};near=query;far=query;far.trajectory[2]={{1,0,0}};
  check(motionCost(query,near)<motionCost(query,far),"motion matching prefers the requested future trajectory");
  far=query;far.positions[0]={{.4f,0,0}};check(motionCost(query,near)<motionCost(query,far),"motion matching preserves the current support-foot pose");
  far=query;far.velocities[0]={{0,5,0}};check(motionCost(query,near)<motionCost(query,far),"motion matching penalizes discontinuous limb velocity");
  std::cout<<"{\"result\":\""<<(failures?"failed":"passed")<<"\",\"checks\":"<<checks<<",\"failures\":"<<failures<<",\"parameter_contexts\":"<<contexts<<",\"unsafe_cut_contexts\":"<<unsafeCuts<<",\"maximum_bone_error_m\":"<<std::max(matrixError,maximumBoneError)<<",\"minimum_pelvis_height_m\":"<<minimumPelvis<<",\"pelvis_rotation_rad\":"<<accumulatedRotation<<",\"peak_angular_speed_rad_s\":"<<peakAngular<<",\"peak_joint_error_m\":"<<peakJointError<<",\"maximum_foot_step_m\":"<<maximumFootStep<<"}\n";
  return failures?1:0;
}
