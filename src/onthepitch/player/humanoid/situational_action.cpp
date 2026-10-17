#include "situational_action.hpp"

#include <algorithm>

namespace football_situations {
namespace {
constexpr float pi=3.14159265358979323846f;
using pes3::Point;
using pes3::Rotation;

float finite(float value,float fallback=0) { return std::isfinite(value)?value:fallback; }
float clamp(float value,float lo,float hi) { return std::max(lo,std::min(hi,finite(value,lo))); }
float length(Point p) { return std::sqrt(pes3::dotPoint(p,p)); }
Point bounded(Point p,float maximum) {
  const float magnitude=length(p);
  return magnitude>maximum?pes3::scalePoint(p,maximum/magnitude):p;
}
Rotation exponential(Point p) {
  const float angle=length(p);
  if(angle<1e-7f)return {{p[0]*.5f,p[1]*.5f,p[2]*.5f,1}};
  const float factor=std::sin(angle*.5f)/angle;
  return {{p[0]*factor,p[1]*factor,p[2]*factor,std::cos(angle*.5f)}};
}
bool valid(const Context &c) {
  return c.enabled && c.kind!=ActionKind::None &&
    unsigned(c.kind)<=unsigned(ActionKind::Control);
}
float smooth(float value) { value=clamp(value,0,1);return value*value*(3-2*value); }
float difficulty(const Context &c) {
  const float turn=std::fabs(clamp(c.signedTurn,-pi,pi))/pi;
  const float lateral=clamp(std::fabs(finite(c.ball[0]))/.7f,0,1);
  const float height=clamp((finite(c.ball[2],-.85f)+.85f)/1.1f,0,1);
  const float derived=.18f*clamp(c.speed/7,0,1)+.18f*clamp(c.power,0,1)+
    .18f*clamp(c.pressure,0,1)+.28f*turn+.12f*lateral+.06f*height;
  return clamp(std::max(finite(c.difficulty),derived),0,1);
}
}

void ActionLayer::reset() {
  offset_={};velocity_={};kind_=ActionKind::None;metrics_={};
}

void ActionLayer::step(const Context &c,float dt) {
  if(!c.enabled||unsigned(c.kind)>unsigned(ActionKind::Control)) { reset();return; }
  const bool active=valid(c);
  if(!active&&kind_==ActionKind::None) { reset();return; }
  dt=clamp(dt,.001f,.025f);
  const float phase=clamp(c.phase,0,1),contact=clamp(c.contactPhase,.12f,.88f);
  const float recovery=clamp((phase-contact)/(1-contact),0,1);
  // Keep a loaded upper body THROUGH impact. The previous two half-sines
  // both reached zero at contact, leaving the native straight torso exposed.
  const float before=phase<=contact?std::sin(.75f*pi*phase/contact):
    .70710678f*(1-smooth(recovery/.38f));
  const float after=smooth((phase-contact+.10f)/.30f)*smooth((1-phase)/.22f)*clamp(c.followThroughGain,0,1.25f);
  const float plant=smooth(phase/(contact*.65f))*smooth((1-phase)/(1-contact));
  // Preparation peaks before contact and unwinds into the follow-through. A
  // smooth start/end leaves the native clip responsible for its own timing.
  const float envelope=active?smooth(phase/.10f)*smooth((1-phase)/.15f):0;
  const float hard=active?difficulty(c):metrics_.difficulty,load=.30f+.90f*hard;
  const float foot=c.rightFoot?1.f:-1.f;
  const float support=c.supportSide<0?-1.f:1.f;
  const float pressure=clamp(c.pressure,0,1);
  const float direction=clamp(std::atan2(finite(c.direction[0]),-finite(c.direction[1],-1)),-pi,pi)/pi;
  const float turn=clamp(c.signedTurn/pi,-1,1);
  const float lateral=clamp(c.ball[0]/.7f,-1,1);
  const float opening=std::fabs(std::sin(clamp(c.signedTurn,-pi,pi)));
  const float height=clamp((finite(c.ball[2],-.85f)+.85f)/1.1f,0,1);
  const float openPattern=c.pattern==1?1.f:0.f,airPattern=c.pattern==2?1.f:0.f;
  const float lowDrive=c.pattern==3?1.f:0.f,insideSweep=c.pattern==4?1.f:0.f;
  const float lofted=c.pattern==5?1.f:0.f,backTurn=c.pattern==6?1.f:0.f;
  const float firstTime=c.pattern==7?1.f:0.f,braced=c.pattern==8?1.f:0.f;
  float type=1;
  if(c.kind==ActionKind::Shot)type=1.18f;
  if(c.kind==ActionKind::Cross)type=1.10f;
  if(c.kind==ActionKind::Control)type=.55f;
  std::array<Point,7> target{};
  const float effort=load*type*envelope;
  const float trunk=effort*clamp(c.trunkGain,0,1.25f);
  const float headerRelease=c.kind==ActionKind::Header ?
    (c.contactMade?smooth(recovery/.18f):0.f):1.f;
  {
    target[1]={{trunk*((.22f+.17f*opening)*before+.29f*after-airPattern*.26f*height*before+
      lowDrive*.15f*plant-lofted*.18f*before+firstTime*.13f*(before-after)+braced*.10f*plant),
      trunk*(-foot*(.055f*before+.09f*after)+.06f*lateral-.045f*support*pressure+
             openPattern*.12f*std::sin(turn*pi)*before+airPattern*.08f*foot*before+
             insideSweep*.13f*foot*plant-lofted*.10f*foot*before+braced*.11f*support*plant),
      trunk*(foot*(-.30f*before+.40f*after)+.18f*direction*plant+.14f*turn*plant+
             openPattern*.24f*std::sin(turn*pi)*(before-.5f*after)+
             insideSweep*.22f*foot*(after-.5f*before)+backTurn*.24f*turn*(before+after)+
             firstTime*.15f*foot*(before-after))}};
    target[1]=pes3::scalePoint(target[1],headerRelease);
    target[1][0]=clamp(target[1][0],-.30f,.36f);
    target[1][1]=clamp(target[1][1],-.20f,.20f);
    target[1][2]=clamp(target[1][2],-.48f,.48f);
  }
  // Counterbalancing upper arms are intentionally modest. The native clip
  // supplies the gross action, and the anatomical constraint pass runs later.
  // Added abduction keeps the arms away from the torso instead of planting a
  // hand on an opponent or manufacturing a support force.
  const float span=effort*(.10f+.17f*pressure+(.24f+.09f*openPattern+.12f*airPattern+.10f*braced+.08f*backTurn)*(before+after));
  const float counter=effort*foot*((.25f+.10f*insideSweep+.08f*firstTime)*before-(.29f+.10f*backTurn)*after);
  target[3]={{effort*(-.09f*before+.08f*after)-.35f*counter,-span,counter}};
  target[5]={{effort*(.08f*before-.09f*after)+.35f*counter,span,-counter}};
  target[4]={{-effort*(.09f*before+.11f*after+.04f*pressure),0,0}};
  target[6]={{-effort*(.11f*before+.09f*after+.04f*pressure),0,0}};
  for(unsigned i:{3u,4u,5u,6u})target[i]=bounded(pes3::scalePoint(target[i],clamp(c.armGain,0,1.25f)),.48f);

  // Critically damped, acceleration- and speed-bounded filters. Unlike a
  // per-evaluation lerp, the result cannot depend on how many candidate poses
  // the animation selector inspects during one simulation tick.
  float maximumRate=0;
  for(unsigned i=1;i<7;++i) {
    const Point old=offset_[i];
    Point acceleration=pes3::subtractPoint(pes3::scalePoint(pes3::subtractPoint(target[i],offset_[i]),324.f),
                                           pes3::scalePoint(velocity_[i],36.f));
    acceleration=bounded(acceleration,36.f);
    velocity_[i]=bounded(pes3::addPoint(velocity_[i],pes3::scalePoint(acceleration,dt)),2.1f);
    offset_[i]=pes3::addPoint(offset_[i],pes3::scalePoint(velocity_[i],dt));
    offset_[i]=bounded(offset_[i],i==1?.58f:.49f);
    if(i==1) {
      offset_[i][0]=clamp(offset_[i][0],-.30f,.36f);
      offset_[i][1]=clamp(offset_[i][1],-.20f,.20f);
      offset_[i][2]=clamp(offset_[i][2],-.48f,.48f);
    }
    maximumRate=std::max(maximumRate,length(pes3::subtractPoint(offset_[i],old))/dt);
  }
  if(active)kind_=c.kind;
  metrics_.kind=kind_;
  metrics_.torsoBend=headerRelease==0?0:std::sqrt(offset_[1][0]*offset_[1][0]+offset_[1][1]*offset_[1][1]);
  metrics_.torsoTwist=headerRelease==0?0:std::fabs(offset_[1][2]);
  metrics_.shoulderAmplitude=std::max(length(offset_[3]),length(offset_[5]));
  metrics_.torsoAngle=headerRelease==0?0:length(offset_[1]);
  metrics_.armsAngle=std::max(metrics_.shoulderAmplitude,std::max(length(offset_[4]),length(offset_[6])));
  metrics_.angularRate=maximumRate;metrics_.difficulty=hard;metrics_.phase=active?phase:1;
  metrics_.weight=clamp(std::max(metrics_.torsoAngle,metrics_.armsAngle)/.35f,0,1);
  if(!active) {
    float remaining=0,momentum=0;
    for(unsigned i=1;i<7;++i) {remaining=std::max(remaining,length(offset_[i]));momentum=std::max(momentum,length(velocity_[i]));}
    if(remaining<1e-6f&&momentum<1e-5f)reset();
  }
}

void ActionLayer::evaluate(const Context &c,const pes3::NativeBind &bind,float scale,
                           pes3::NativeRotations &pose,Point pelvis) const {
  if(!c.enabled||unsigned(c.kind)>unsigned(ActionKind::Control)||kind_==ActionKind::None||!std::isfinite(scale)||scale<=0)return;
  const ActionKind kind=c.kind==ActionKind::None?kind_:c.kind;
  for(float value:pelvis)if(!std::isfinite(value))return;
  for(unsigned i=1;i<7;++i)for(float value:bind.offsets[i])if(!std::isfinite(value))return;
  auto result=pose;
  // Changing middle rotates all of the upper skin, not a leg or its endpoint.
  // Headers skip it until contact so their contacting point is invariant.
  if(kind!=ActionKind::Header || (c.contactMade && c.phase>c.contactPhase)) {
    if(!pes3::unitRotation(pes3::productRotation(exponential(offset_[1]),pose[1]),result[1]))return;
    if(c.preserveHead) {
      // In parent-local coordinates: qMiddle' * qNeck' = qMiddle * qNeck.
      const auto oldHead=pes3::productRotation(pose[1],pose[2]);
      if(!pes3::unitRotation(pes3::productRotation(pes3::inverseRotation(result[1]),oldHead),result[2]))return;
    }
  }
  for(unsigned i:{3u,4u,5u,6u})
    if(!pes3::unitRotation(pes3::productRotation(exponential(offset_[i]),pose[i]),result[i]))return;
  pose=result;
}

} // namespace football_situations
