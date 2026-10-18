#include "onthepitch/player/humanoid/situational_action.hpp"

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <new>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

// Verify the hot path itself, not just a claim about its containers.
namespace { bool observeAllocation=false;unsigned allocations=0; }
void *operator new(std::size_t size) {
  if(observeAllocation)++allocations;
  if(void *p=std::malloc(size))return p;
  throw std::bad_alloc();
}
void *operator new[](std::size_t size) { return ::operator new(size); }
void operator delete(void *p) noexcept { std::free(p); }
void operator delete[](void *p) noexcept { std::free(p); }
#if __cplusplus>=201402L
void operator delete(void *p,std::size_t) noexcept { std::free(p); }
void operator delete[](void *p,std::size_t) noexcept { std::free(p); }
#endif

using namespace football_situations;
namespace {
unsigned failures=0,checks=0;
void check(bool ok,const char *name) { ++checks;if(!ok) {++failures;std::cerr<<"FAILED: "<<name<<'\n';} }
pes3::NativeBind nativeBind() {
  pes3::NativeBind b;
  b.offsets={{{{0,0,.96f}},{{0,0,.15f}},{{0,-.03f,.5f}},{{.16f,-.01f,.48f}},{{-.01f,0,-.33f}},{{-.16f,-.01f,.48f}},{{.01f,0,-.33f}},{{.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}},{{-.087f,0,-.01f}},{{0,0,-.42f}},{{0,-.04f,-.44f}}}};
  for(auto &q:b.rotations)q={{0,0,0,1}};
  return b;
}
float qdistance(pes3::Rotation a,pes3::Rotation b) {
  float dot=0;for(unsigned i=0;i<4;++i)dot+=a[i]*b[i];
  return 2*std::acos(std::max(-1.f,std::min(1.f,std::fabs(dot))));
}
pes3::NativePoints points(const pes3::NativeBind &bind,const pes3::NativeRotations &pose) {
  pes3::NativeRotations global;pes3::NativePoints result{};
  for(unsigned i=0;i<13;++i) {
    const int parent=pes3::nativeParents[i];
    global[i]=parent<0?pose[i]:pes3::productRotation(global[parent],pose[i]);
    result[i]=parent<0?pes3::Point{{0,0,.96f}}:pes3::addPoint(result[parent],pes3::rotatePoint(global[parent],bind.offsets[i]));
  }
  return result;
}
float pointDistance(pes3::Point a,pes3::Point b) {
  const auto d=pes3::subtractPoint(a,b);return std::sqrt(pes3::dotPoint(d,d));
}
void settle(ActionLayer &layer,const Context &c) { for(unsigned i=0;i<100;++i)layer.step(c); }
pes3::NativeRotations nativeSample(const std::string &path) {
  auto pose=nativeBind().rotations;std::ifstream stream(path);
  check(bool(stream),"native action source is readable");std::string line;
  while(std::getline(stream,line)) {
    const auto comma=line.find(',');if(comma==std::string::npos)continue;
    const auto name=line.substr(0,comma);
    for(unsigned i=0;i<13;++i)if(name==pes3::nativeBoneNames[i]) {
      std::vector<float> values;std::stringstream tokens(line.substr(comma+1));std::string token;
      while(std::getline(tokens,token,','))values.push_back(std::stof(token));
      if(values.size()>=5) {
        const unsigned frame=(values.size()/5)/2;
        for(unsigned j=0;j<4;++j)pose[i][j]=values[frame*5+j+1];
        pes3::unitRotation(pose[i],pose[i]);
      }
    }
  }
  return pose;
}
}

int main(int argc,char **argv) {
  const auto bind=nativeBind();const auto base=bind.rotations;
  ActionLayer layer;Context c;c.kind=ActionKind::Pass;c.phase=.23f;
  settle(layer,c);auto pose=base;layer.evaluate(c,bind,1,pose,{{0,0,.96f}});
  const auto easy=layer.metrics();
  check(easy.torsoBend>.002f && easy.shoulderAmplitude>.002f,"an ordinary pass uses a modest connected torso and arm response");
  Context hard=c;hard.speed=6;hard.power=1;hard.pressure=1;hard.signedTurn=2.5f;hard.difficulty=1;hard.ball={{.6f,-.5f,.1f}};
  layer.reset();settle(layer,hard);auto difficult=base;layer.evaluate(hard,bind,1,difficult,{{0,0,.96f}});
  check(layer.metrics().torsoBend>easy.torsoBend*2 && layer.metrics().shoulderAmplitude>easy.shoulderAmplitude*2,"difficult passes recruit substantially more torso and arms");
  check(layer.metrics().torsoBend<.42f && layer.metrics().torsoTwist<.49f && layer.metrics().shoulderAmplitude<.49f,"whole upper-body adaptation respects conservative angular limits");
  bool exact=true;for(unsigned i:{0u,7u,8u,9u,10u,11u,12u})exact&=std::memcmp(base[i].data(),difficult[i].data(),sizeof(pes3::Rotation))==0;
  const auto oldPoints=points(bind,base),newPoints=points(bind,difficult);
  check(exact && pointDistance(oldPoints[9],newPoints[9])==0 && pointDistance(oldPoints[12],newPoints[12])==0,"pelvis, legs and both contact foot endpoints remain exactly native");
  const auto oldHead=pes3::productRotation(base[1],base[2]);
  const auto newHead=pes3::productRotation(difficult[1],difficult[2]);
  check(qdistance(oldHead,newHead)<.001f,"torso preparation preserves the requested head orientation");
  const auto fixedMetrics=layer.metrics();bool idempotent=true;
  for(unsigned i=0;i<100;++i) {
    auto candidate=base;layer.evaluate(hard,bind,1,candidate,{{0,0,.96f}});
    idempotent&=std::memcmp(candidate.data(),difficult.data(),sizeof(candidate))==0;
  }
  check(idempotent && std::memcmp(&fixedMetrics,&layer.metrics(),sizeof(fixedMetrics))==0,"repeated same-tick candidate evaluation is deterministic and does not advance filters");
  layer.reset();Context left=hard;left.rightFoot=false;left.supportSide=1;left.signedTurn=-hard.signedTurn;left.ball[0]=-hard.ball[0];
  settle(layer,left);auto leftPose=base;layer.evaluate(left,bind,1,leftPose,{{0,0,.96f}});
  check(leftPose[1][2]*difficult[1][2]<0 && layer.metrics().shoulderAmplitude>.05f,"left-foot adaptation reverses trunk counter-rotation while retaining arm support");
  // Abrupt contextual changes must not kick a shoulder or chest in one frame.
  float peakRate=0,peakPoseRate=0;auto previous=leftPose;
  for(unsigned i=0;i<240;++i) {
    Context current=(i/30)%2?left:hard;current.phase=i<120?.23f:.73f;
    layer.step(current);auto now=base;layer.evaluate(current,bind,1,now,{{0,0,.96f}});
    for(unsigned b:{1u,3u,4u,5u,6u})peakPoseRate=std::max(peakPoseRate,qdistance(previous[b],now[b])/.01f);
    peakRate=std::max(peakRate,layer.metrics().angularRate);previous=now;
  }
  check(peakRate<=2.101f && peakPoseRate<2.2f,"a changed side or follow-through is bounded in angular speed");
  for(ActionKind kind:{ActionKind::Pass,ActionKind::Shot,ActionKind::Cross,ActionKind::Control}) {
    layer.reset();Context act=hard;act.kind=kind;settle(layer,act);
    auto now=base;layer.evaluate(act,bind,1,now,{{0,0,.96f}});
    check(qdistance(now[1],base[1])>.02f && qdistance(now[3],base[3])>.02f,"each supported action adapts the torso and arms together");
  }
  layer.reset();Context header=hard;header.kind=ActionKind::Header;settle(layer,header);
  auto headPose=base;layer.evaluate(header,bind,1,headPose,{{0,0,.96f}});
  const auto headed=points(bind,headPose);
  check(std::memcmp(base[1].data(),headPose[1].data(),sizeof(pes3::Rotation))==0 &&
    std::memcmp(base[2].data(),headPose[2].data(),sizeof(pes3::Rotation))==0 &&
    pointDistance(oldPoints[2],headed[2])==0 && qdistance(headPose[3],base[3])>.01f,
    "a header changes its arms while preserving exact head contact position and orientation");
  Context disabled=hard;disabled.enabled=false;auto neutral=base;layer.evaluate(disabled,bind,1,neutral,{{0,0,.96f}});
  check(std::memcmp(base.data(),neutral.data(),sizeof(base))==0,"a disabled or cancelled action never alters the supplied pose");
  layer.step(disabled);neutral=base;layer.evaluate(hard,bind,1,neutral,{{0,0,.96f}});
  check(std::memcmp(base.data(),neutral.data(),sizeof(base))==0 && layer.metrics().weight==0,"cancellation clears residual action filters");
  layer.reset();Context endpoint=hard;endpoint.phase=0;settle(layer,endpoint);neutral=base;layer.evaluate(endpoint,bind,1,neutral,{{0,0,.96f}});
  check(std::memcmp(base.data(),neutral.data(),sizeof(base))==0,"action preparation begins at the unmodified native pose");
  layer.reset();endpoint.phase=1;settle(layer,endpoint);neutral=base;layer.evaluate(endpoint,bind,1,neutral,{{0,0,.96f}});
  check(std::memcmp(base.data(),neutral.data(),sizeof(base))==0,"completed follow-through ends at the unmodified native pose");
  layer.reset();Context lowGain=c;lowGain.difficulty=.5f;lowGain.pressure=.3f;
  lowGain.trunkGain=.75f;lowGain.armGain=.75f;settle(layer,lowGain);
  const float lowTorso=layer.metrics().torsoAngle,lowArm=layer.metrics().armsAngle;
  layer.reset();Context highGain=lowGain;highGain.trunkGain=1.2f;highGain.armGain=1.2f;settle(layer,highGain);
  check(layer.metrics().torsoAngle>lowTorso*1.4f && layer.metrics().armsAngle>lowArm*1.4f,
    "catalog gains change the actual torso and arm movement rather than a label alone");
  layer.reset();Context follow=lowGain;follow.phase=.73f;follow.followThroughGain=.75f;settle(layer,follow);
  const float lowFollow=layer.metrics().torsoAngle;
  layer.reset();follow.followThroughGain=1.2f;settle(layer,follow);
  check(layer.metrics().torsoAngle>lowFollow*1.15f,"the follow-through profile gain affects the post-contact trunk motion");
  layer.reset();Context interrupted=hard;interrupted.phase=.65f;settle(layer,interrupted);
  auto beforeFade=base;layer.evaluate(interrupted,bind,1,beforeFade,{{0,0,.96f}});
  Context locomotion;float fadePeak=0;bool fadeHead=true;
  for(unsigned tick=0;tick<200;++tick) {
    layer.step(locomotion);auto fading=base;layer.evaluate(locomotion,bind,1,fading,{{0,0,.96f}});
    for(unsigned bone:{1u,3u,4u,5u,6u})fadePeak=std::max(fadePeak,qdistance(beforeFade[bone],fading[bone])/.01f);
    const auto globalHead=pes3::productRotation(fading[1],fading[2]);fadeHead&=qdistance(oldHead,globalHead)<.001f;
    beforeFade=fading;
  }
  check(fadePeak<2.2f && fadeHead,"returning to locomotion fades the whole upper body without an end-of-clip snap or head kick");
  check(std::memcmp(beforeFade.data(),base.data(),sizeof(base))==0 && layer.metrics().weight==0 &&
    layer.metrics().kind==ActionKind::None,"a completed fade settles to exactly neutral within two seconds");
  layer.reset();settle(layer,interrupted);auto beforeRequeue=base;layer.evaluate(interrupted,bind,1,beforeRequeue,{{0,0,.96f}});
  interrupted.phase=.01f;layer.step(interrupted);auto requeued=base;layer.evaluate(interrupted,bind,1,requeued,{{0,0,.96f}});
  check(qdistance(beforeRequeue[1],requeued[1])<.0215f && qdistance(requeued[1],base[1])>.02f,
    "a native same-kind phase requeue preserves the filter instead of restarting the torso abruptly");
  const std::string root=argc>1?argv[1]:"data/media/animations";
  std::array<pes3::NativeRotations,3> native{{nativeSample(root+"/pass/idle/000.anim"),
    nativeSample(root+"/shot/idle/020.anim"),nativeSample(root+"/ballcontrol/walk/000.anim")}};
  // Native authored rotations must be treated as the base, never replaced by
  // an invented neutral action. An exhaustive parameter matrix is inexpensive
  // here and keeps profile counts separate from genuinely checked poses.
  unsigned matrix=0;bool matrixSafe=true;float maximumBend=0,maximumShoulder=0;
  for(unsigned type=1;type<=5;++type)for(float turn:{-2.6f,0.f,2.6f})
    for(float speed:{0.f,3.f,7.f})for(float phase:{.15f,.36f,.70f,.91f})for(float gain:{.75f,1.2f})for(unsigned pattern=0;pattern<15;++pattern) {
      Context variant=hard;variant.kind=ActionKind(type);variant.signedTurn=turn;variant.speed=speed;
      variant.pattern=pattern;variant.phase=phase;variant.trunkGain=variant.armGain=variant.followThroughGain=gain;
      variant.rightFoot=matrix%2==0;variant.supportSide=variant.rightFoot?-1:1;
      layer.reset();for(unsigned tick=0;tick<60;++tick)layer.step(variant,.02f);
      const auto source=native[matrix%native.size()];auto adjusted=source;
      layer.evaluate(variant,bind,1,adjusted,{{0,0,.96f}});
      const auto sourcePoints=points(bind,source),adjustedPoints=points(bind,adjusted);
      for(unsigned bone:{0u,7u,8u,9u,10u,11u,12u})
        matrixSafe&=std::memcmp(source[bone].data(),adjusted[bone].data(),sizeof(pes3::Rotation))==0;
      matrixSafe&=pointDistance(sourcePoints[9],adjustedPoints[9])==0 && pointDistance(sourcePoints[12],adjustedPoints[12])==0;
      for(const auto &q:adjusted) { float norm=0;for(float value:q) { matrixSafe&=std::isfinite(value);norm+=value*value; }matrixSafe&=std::fabs(norm-1)<1e-5f; }
      maximumBend=std::max(maximumBend,layer.metrics().torsoBend);
      maximumShoulder=std::max(maximumShoulder,layer.metrics().shoulderAmplitude);++matrix;
    }
  check(matrix==5400 && matrixSafe && maximumBend<.42f && maximumShoulder<.49f,
    "5400 native-source action contexts preserve exact lower-body contact and bounded finite upper-body poses");
  layer.reset();Context open=hard;open.pattern=0;open.signedTurn=1.3f;settle(layer,open);
  auto compact=base;layer.evaluate(open,bind,1,compact,{{0,0,.96f}});
  layer.reset();open.pattern=1;settle(layer,open);auto lateralPose=base;layer.evaluate(open,bind,1,lateralPose,{{0,0,.96f}});
  layer.reset();open.pattern=2;open.ball[2]=-.05f;settle(layer,open);auto aerialPose=base;layer.evaluate(open,bind,1,aerialPose,{{0,0,.96f}});
  check(qdistance(compact[1],lateralPose[1])>.025f && qdistance(lateralPose[1],aerialPose[1])>.04f,
    "compact, lateral opening and airborne patterns change actual torso axes instead of cloning a label");
  // Every family must change the pose itself at the same contextual input,
  // rather than supplying additional names for the compact response.
  std::array<pes3::NativeRotations,15> families;
  Context family=c;family.speed=3;family.power=.5f;family.pressure=.4f;
  family.signedTurn=1;family.ball={{.3f,-.4f,-.25f}};family.difficulty=.6f;
  family.trunkGain=family.armGain=.85f;family.incoming={{4,7,-2}};
  for(unsigned pattern=0;pattern<15;++pattern) {
    family.pattern=pattern;layer.reset();settle(layer,family);families[pattern]=base;
    layer.evaluate(family,bind,1,families[pattern],{{0,0,.96f}});
  }
  bool distinct=true;float minimumFamilyDistance=10;
  for(unsigned a=0;a<15;++a)for(unsigned b=a+1;b<15;++b) {
    float separation=0;for(unsigned bone:{1u,3u,4u,5u,6u})
      separation=std::max(separation,qdistance(families[a][bone],families[b][bone]));
    minimumFamilyDistance=std::min(minimumFamilyDistance,separation);distinct&=separation>.005f;
  }
  check(distinct,"all fifteen situational families produce different connected body poses at identical input");
  Context impact=family;impact.pattern=0;impact.phase=impact.contactPhase;
  layer.reset();settle(layer,impact);
  check(layer.metrics().torsoAngle>.07f && layer.metrics().armsAngle>.10f,
    "upper-body preparation remains visible at the exact contact phase instead of collapsing to neutral");
  header.contactMade=true;header.phase=.85f;layer.reset();settle(layer,header);
  auto recovery=base;layer.evaluate(header,bind,1,recovery,{{0,0,.96f}});
  check(qdistance(recovery[1],base[1])>.03f,
    "a header can recruit the torso only after its real contact is complete");
  std::array<pes3::Rotation,7> chest;
  for(unsigned i=0;i<7;++i)chest[i]=base[i];
  const auto chestBase=chest;adaptChestArms(chest,20,20,90,3,5);
  bool chestContactFixed=true;for(unsigned i=0;i<3;++i)chestContactFixed&=std::memcmp(chest[i].data(),chestBase[i].data(),sizeof(pes3::Rotation))==0;
  check(chestContactFixed && qdistance(chest[3],chestBase[3])>.03f && qdistance(chest[5],chestBase[5])>.03f,
    "additional chest reception shapes change arms while preserving the exact contacting torso and head chain");
  float chestRate=0;auto chestPrevious=chestBase;
  for(unsigned frame=0;frame<=90;++frame){
    auto current=chestBase;adaptChestArms(current,frame,20,90,3,5);
    for(unsigned bone:{3u,4u,5u,6u})chestRate=std::max(chestRate,qdistance(current[bone],chestPrevious[bone])/.01f);
    chestPrevious=current;
  }
  check(chestRate<1.5f,"chest arm variations evolve continuously and keep natural bounded speed");
  layer.reset();Context corrupt=hard;corrupt.phase=std::nanf("");corrupt.ball[0]=std::nanf("");
  corrupt.power=std::nanf("");corrupt.signedTurn=std::nanf("");layer.step(corrupt);
  auto safe=base;layer.evaluate(corrupt,bind,1,safe,{{0,0,.96f}});bool finitePose=true;
  for(const auto &q:safe)for(float value:q)finitePose&=std::isfinite(value);
  check(finitePose,"nonfinite contextual sensor values cannot poison the native skeleton");
  observeAllocation=true;
  for(unsigned i=0;i<1000;++i) { layer.step(hard);auto p=base;layer.evaluate(hard,bind,1,p,{{0,0,.96f}}); }
  observeAllocation=false;
  check(allocations==0,"one thousand simulation ticks and evaluations allocate no heap memory");
  std::cout<<"{\"result\":\""<<(failures?"failed":"passed")<<"\",\"checks\":"<<checks<<",\"failures\":"<<failures
    <<",\"peak_angular_rate_rad_s\":"<<peakRate<<",\"peak_pose_rate_rad_s\":"<<peakPoseRate<<",\"parameter_contexts\":"<<matrix
    <<",\"maximum_torso_bend_rad\":"<<maximumBend<<",\"maximum_shoulder_offset_rad\":"<<maximumShoulder
    <<",\"maximum_locomotion_fade_rate_rad_s\":"<<fadePeak<<",\"allocations\":"<<allocations<<"}\n";
  return failures?1:0;
}
