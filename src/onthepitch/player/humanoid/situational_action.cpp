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

void adaptChestArms(std::array<Rotation,7> &pose,float phase,float contact,
                    float duration,float speed,float incomingSide) {
  if(!std::isfinite(phase)||!std::isfinite(duration)||duration<=0)return;
  const float t=clamp(phase/duration,0,1),at=clamp(contact/duration,.1f,.9f);
  const float envelope=smooth(t/.12f)*smooth((1-t)/.18f);
  const float prepare=t<=at?std::sin(.5f*pi*t/at):1-smooth((t-at)/(1-at));
  const float stride=clamp(speed/5,0,1),side=clamp(incomingSide/10,-1,1);
  const float spread=envelope*(.035f+.055f*prepare+.025f*stride);
  const float swing=envelope*(.055f*stride*std::sin(pi*t)+.035f*side*prepare);
  const Point offsets[4]={{{swing,-spread,.025f*side*envelope}},
    {{-envelope*(.03f+.04f*prepare),0,0}},
    {{-swing,spread,-.025f*side*envelope}},
    {{-envelope*(.04f+.03f*prepare),0,0}}};
  for(unsigned i=0;i<4;++i){
    Rotation q;if(pes3::unitRotation(pes3::productRotation(exponential(offsets[i]),pose[i+3]),q))pose[i+3]=q;
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
  const float hard=active?difficulty(c):metrics_.difficulty,load=.36f+.94f*hard;
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
  const float cushion=c.pattern==9?1.f:0.f,redirect=c.pattern==10?1.f:0.f;
  const float reactive=c.pattern==11?1.f:0.f,volley=c.pattern==12?1.f:0.f;
  const float outside=c.pattern==13?1.f:0.f,instep=c.pattern==14?1.f:0.f;
  const float incomingSide=clamp(c.incoming[0]/10.f,-1,1);
  const float incomingLoad=clamp(length(c.incoming)/15.f,0,1);
  float type=1;
  if(c.kind==ActionKind::Shot)type=1.18f;
  if(c.kind==ActionKind::Cross)type=1.10f;
  if(c.kind==ActionKind::Control)type=.72f;
  std::array<Point,7> target{};
  const float effort=load*type*envelope;
  const float trunk=effort*clamp(c.trunkGain,0,1.25f);
  const float headerRelease=c.kind==ActionKind::Header ?
    (c.contactMade?smooth(recovery/.18f):0.f):1.f;
  {
    target[1]={{trunk*((.22f+.17f*opening)*before+.29f*after-airPattern*.26f*height*before+
      lowDrive*.15f*plant-lofted*.18f*before+firstTime*.13f*(before-after)+braced*.10f*plant+
      cushion*(-.16f*before+.10f*after)+redirect*.10f*before-
      volley*.18f*height*before+instep*.16f*after+reactive*.13f*incomingLoad*after),
      trunk*(-foot*(.055f*before+.09f*after)+.06f*lateral-.045f*support*pressure+
             openPattern*.12f*std::sin(turn*pi)*before+airPattern*.08f*foot*before+
             insideSweep*.13f*foot*plant-lofted*.10f*foot*before+braced*.11f*support*plant+
      cushion*.08f*incomingSide*before+redirect*.11f*foot*plant-
      volley*.12f*foot*before-outside*.12f*foot*plant),
      trunk*(foot*(-.30f*before+.40f*after)+.18f*direction*plant+.14f*turn*plant+
             openPattern*.24f*std::sin(turn*pi)*(before-.5f*after)+
             insideSweep*.22f*foot*(after-.5f*before)+backTurn*.24f*turn*(before+after)+
             firstTime*.15f*foot*(before-after)+cushion*.08f*incomingSide*(before-after)+
      redirect*.20f*(incomingSide+.5f*foot)*plant-volley*.12f*foot*before+
      outside*foot*(.18f*before-.22f*after)+instep*foot*(-.16f*before+.20f*after)+
      .045f*incomingSide*incomingLoad*before)}};
    target[1]=pes3::scalePoint(target[1],headerRelease);
    target[1][0]=clamp(target[1][0],-.30f,.36f);
    target[1][1]=clamp(target[1][1],-.20f,.20f);
    target[1][2]=clamp(target[1][2],-.48f,.48f);
  }
  // Counterbalancing upper arms are intentionally modest. The native clip
  // supplies the gross action, and the anatomical constraint pass runs later.
  // Added abduction keeps the arms away from the torso instead of planting a
  // hand on an opponent or manufacturing a support force.
  const float span=effort*(.12f+.18f*pressure+(.30f+.09f*openPattern+.12f*airPattern+.10f*braced+.08f*backTurn+.12f*cushion+.08f*redirect+.14f*reactive*incomingLoad+.15f*volley+.08f*instep)*(before+after));
  const float counter=effort*foot*((.25f+.10f*insideSweep+.08f*firstTime)*before-(.29f+.10f*backTurn)*after)+effort*(redirect*.12f*foot*plant+reactive*.16f*incomingSide*before-outside*.13f*foot*before);
  target[3]={{effort*(-.09f*before+.08f*after)-.35f*counter,-span,counter}};
  target[5]={{effort*(.08f*before-.09f*after)+.35f*counter,span,-counter}};
  target[4]={{-effort*(.09f*before+.11f*after+.04f*pressure),0,0}};
  target[6]={{-effort*(.11f*before+.09f*after+.04f*pressure),0,0}};
  if(c.pattern>=15&&c.pattern<=31){
    const unsigned style=c.pattern-15;
    const float wave=std::sin(pi*phase*(1.f+.045f*style));
    const float counterWave=std::sin(pi*phase*(1.1f+.07f*(style%5)));
    const float side=style%2?1.f:-1.f;
    const float absorption=clamp(c.incoming[1]/18.f,-1.f,1.f);
    target[1][0]+=trunk*((.035f+.006f*style)*wave-.13f*absorption*before);
    target[1][1]+=trunk*(.025f+.008f*(style%4))*side*counterWave;
    target[1][2]+=trunk*(.065f+.006f*style)*(turn+.4f*incomingSide+.3f*foot)*wave;
    target[3][0]+=effort*(.08f+.009f*style)*counterWave;
    target[5][0]-=effort*(.10f+.007f*style)*wave;
    target[3][1]-=effort*(.035f+.005f*style)*wave;
    target[5][1]+=effort*(.045f+.004f*style)*counterWave;
    if(c.pattern==18&&c.contactMade&&incomingLoad>.85f)
      target[1][0]-=trunk*.40f*before;
  }
  if(c.pattern>=32&&c.pattern<48){
    // Preparation bend, recovery bend, counter-rotation, arm span. Each row
    // is a different support strategy; continuous load/direction still drive it.
    static constexpr float strategy[16][4]={
      {.08f,-.04f,.12f,.06f},{-.04f,.08f,-.16f,.10f},
      {-.08f,.16f,.08f,.08f},{-.18f,.04f,-.10f,.20f},
      {.19f,-.06f,.06f,.16f},{-.14f,-.08f,.04f,.14f},
      {.02f,.10f,.22f,.18f},{-.12f,.12f,-.04f,.09f},
      {-.06f,.04f,.16f,.22f},{.16f,.02f,-.12f,.12f},
      {-.20f,-.12f,.02f,.24f},{.10f,-.08f,.24f,.07f},
      {-.10f,.06f,-.24f,.11f},{-.16f,.18f,.14f,.19f},
      {.06f,.14f,.28f,.13f},{.14f,-.10f,-.18f,.23f}};
    const auto &plan=strategy[c.pattern-32];
    target[1][0]+=trunk*(plan[0]*before+plan[1]*after);
    target[1][2]+=trunk*plan[2]*(.6f*foot+.4f*turn)*(before-.6f*after);
    const float opening=effort*plan[3]*(before+after);
    target[3][1]-=opening;target[5][1]+=opening;
    target[3][0]+=opening*.45f*foot;target[5][0]-=opening*.45f*foot;
  }
  // Distinct load/cushion strategies around the existing clip, rather than
  // swapping locomotion or inventing a contact with another body part.
  const float recruit=trunk*.7f,brace=effort*.10f*(before+after);
  switch(c.style){
    case ContactStyle::Inside:
      target[1][2]+=recruit*foot*(.10f*before-.08f*after);break;
    case ContactStyle::Outside:
      target[1][1]-=recruit*foot*.09f*plant;
      target[1][2]-=recruit*foot*.14f*(before-after);break;
    case ContactStyle::Instep:
      target[1][0]+=recruit*.10f*(after-.4f*before);break;
    case ContactStyle::Volley:
      target[1][0]-=recruit*.15f*before;
      target[1][2]+=recruit*foot*.10f*(after-before);
      target[3][1]-=brace;target[5][1]+=brace;break;
    case ContactStyle::HalfVolley:
      target[1][0]+=recruit*.14f*plant;
      target[3][0]-=brace;target[5][0]+=brace;break;
    case ContactStyle::HeadCushion:
      target[1][0]-=recruit*.14f*headerRelease*after;
      target[3][1]-=brace*.7f;target[5][1]+=brace*.7f;break;
    case ContactStyle::HeadRedirect:
      target[1][2]+=recruit*.16f*turn*headerRelease*after;break;
    case ContactStyle::Chest:
      target[1][0]+=recruit*(-.11f*before+.08f*after);break;
    case ContactStyle::Thigh:
      target[1][1]-=recruit*foot*.10f*plant;
      target[1][0]-=recruit*.07f*before;
      target[3][1]-=brace;target[5][1]+=brace;break;
    case ContactStyle::Shin:
      target[1][0]+=recruit*.11f*plant;
      target[1][2]+=recruit*.08f*incomingSide*after;break;
    case ContactStyle::DrivenImpact:
      target[1][0]-=recruit*.18f*incomingLoad*after;
      target[3][1]-=brace;target[5][1]+=brace;break;
    default:break;
  }
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
    offset_[i]=bounded(offset_[i],i==1?.52f:.49f);
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
