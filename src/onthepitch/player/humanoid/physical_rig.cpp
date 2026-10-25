#include "physical_rig.hpp"
#include "articulated_body.hpp"
#include "balance_controller.hpp"
#include "anatomical_arms.hpp"

namespace football_physics {
namespace {
// Segment fractions use de Leva's male reference. Splitting the trunk into
// pelvis/spine and combining forearm+hand are explicit game approximations.
constexpr float fractions[13]={.12f,.3146f,.0694f,.0271f,.0223f,.0271f,.0223f,.1416f,.0433f,.0137f,.1416f,.0433f,.0137f};
constexpr float radii[13]={.135f,.145f,.10f,.055f,.045f,.055f,.045f,.075f,.055f,.045f,.075f,.055f,.045f};
Vec tip(unsigned i){if(i==2)return {{0,0,.17f}};if(i==4||i==6)return {{0,0,-.27f}};if(i==9||i==12)return {{0,-.16f,-.02f}};return {{0,0,0}};}
}

void PhysicalRig::configure(const pes3::NativeBind &bind,float heightScale){reference=bind;scale=bounded(heightScale,.7f,1.3f);reset();}
void PhysicalRig::setRecoveryMotions(RecoveryMotion front,RecoveryMotion back){recoveryFront=std::move(front);recoveryBack=std::move(back);}
void PhysicalRig::setBalanceMotions(std::vector<BalanceMotion> motions){setSharedBalanceMotions(std::make_shared<const std::vector<BalanceMotion>>(std::move(motions)));}
void PhysicalRig::setSharedBalanceMotions(std::shared_ptr<const std::vector<BalanceMotion>> motions){balanceMotions=std::move(motions);balanceChoice=-1;balanceMotionTime=0;}
Vec PhysicalRig::balanceVelocity()const{return state==Mode::Active && balance?balance->velocity():Vec{{0,0,0}};}
void PhysicalRig::reset(){deliberateFall=false;arrestTime=0;impactReflex=impactReflexVelocity={{0,0,0}};recoveryFoot=-1;stepTime=stepCooldown=stepRelease=0;stepOffset[0]=stepOffset[1]={{0,0,0}};sourceFeetReady=false;for(unsigned i=0;i<2;++i){plantAge[i]=0;plantOffset[i]={{0,0,0}};}situationLayer.reset();supportTilt=supportTiltVelocity={{0,0,0}};supportSink=supportSinkVelocity=0;counterTilt=counterTiltVelocity={{0,0,0}};ready=false;state=Mode::Active;stateAge=settled=filteredTurn=unstableTime=protection=0;pendingImpulse=pendingTorque=reachOffset=sway=swayVelocity=filteredAcceleration=previousVelocity={{0,0,0}};angularVelocity={};articulated.reset();balance.reset(new BalanceController);balanceChoice=-1;balanceMotionTime=handEnvelope=0;forcedFall=handInitialized=handUpdatePending=false;handVelocity[0]=handVelocity[1]={{0,0,0}};physicalUpperValid=false;recoveryMotion=nullptr;reachOffsets={};for(auto &q:additive)q={{0,0,0,1}};debug={};}
void PhysicalRig::impulse(Vec value,Vec lever,bool forceFall){value=capped(value,360);pendingImpulse=addPoint(pendingImpulse,value);pendingTorque=addPoint(pendingTorque,crossPoint(lever,value));forcedFall=forcedFall || forceFall;}

bool PhysicalRig::adoptContactHand(Vec target){
  if(!ready||state!=Mode::Active)return false;
  unsigned selected=4;float gap=100;
  for(unsigned elbow:{4u,6u}){
    const Vec hand=addPoint(positions[elbow],rotatePoint(world[elbow],{{0,0,-.25f*scale}}));
    const float distance=length(subtractPoint(hand,target));if(distance<gap){gap=distance;selected=elbow;}
  }
  if(gap>=.10f)return false;
  // Adopt the hand which actually touched, starting from its current final
  // anatomical pose. This changes controller ownership, never its transform.
  handShoulder=int(selected)-1;handPose[0]=local[handShoulder];handPose[1]=local[handShoulder+1];
  handVelocity[0]=handVelocity[1]={{0,0,0}};handInitialized=true;handEnvelope=1;lastHandTarget=target;
  return true;
}
void PhysicalRig::forwardKinematics(){
  positions[0]=root;
  for(unsigned i=0;i<13;++i){
    const int parent=pes3::nativeParents[i];
    world[i]=parent<0?local[i]:normalized(productRotation(world[parent],local[i]));
    if(parent>=0)positions[i]=addPoint(positions[parent],rotatePoint(world[parent],scalePoint(reference.offsets[i],scale)));
  }
}

void PhysicalRig::solveLeg(unsigned hip,Vec target,float edgeMargin){
  const unsigned knee=hip+1,ankle=hip+2;
  const Vec upper=subtractPoint(positions[knee],positions[hip]),lower=subtractPoint(positions[ankle],positions[knee]);
  const float a=length(upper),b=length(lower);
  if(a<.05f||b<.05f)return;
  Vec direction=unit(subtractPoint(target,positions[hip]));
  const float distance=bounded(length(subtractPoint(target,positions[hip])),std::fabs(a-b)+edgeMargin,a+b-edgeMargin);
  target=addPoint(positions[hip],scalePoint(direction,distance));
  Vec pole=unit(subtractPoint(upper,scalePoint(direction,dotPoint(upper,direction))),rotatePoint(world[0],{{0,-1,0}}));
  const float along=(a*a-b*b+distance*distance)/(2*distance);
  const Vec bend=addPoint(addPoint(positions[hip],scalePoint(direction,along)),scalePoint(pole,std::sqrt(std::max(0.f,a*a-along*along))));
  const Quat thigh=normalized(productRotation(pes3::swingRotation(unit(upper),unit(subtractPoint(bend,positions[hip]))),world[hip]));
  const Quat shin=normalized(productRotation(pes3::swingRotation(unit(lower),unit(subtractPoint(target,bend))),world[knee]));
  const Quat shoe=world[ankle];
  local[hip]=normalized(productRotation(inverseRotation(world[0]),thigh));
  local[knee]=normalized(productRotation(inverseRotation(thigh),shin));
  local[ankle]=normalized(productRotation(inverseRotation(shin),shoe));
  forwardKinematics();
}

PhysicalRig::PhysicalRig():balance(new BalanceController){}
PhysicalRig::~PhysicalRig()=default;
void PhysicalRig::step(const Input &input,float dt){
  dt=bounded(dt,.001f,.02f);
  // Restarts and explicit laboratory placements can relocate the native
  // root. Neither a support anchor nor accumulated momentum survives that.
  if(ready&&state==Mode::Active&&length(subtractPoint(input.pelvis,root))>.45f+length(input.velocity)*dt)reset();
  protection+=(float(input.protect)-protection)*(1-std::exp(-7*dt));
  if(!ready){local=input.pose;root=input.pelvis;previousVelocity=input.velocity;lastForward=input.forward;ready=true;forwardKinematics();}
  debug={};
  if(state!=Mode::Active){recoveryFoot=-1;stepTime=stepCooldown=stepRelease=0;stepOffset[0]=stepOffset[1]={{0,0,0}};supportTilt=supportTiltVelocity={{0,0,0}};supportSink=supportSinkVelocity=0;}
  auto situation=input.situation;
  if(input.upperReception || input.staggering || state!=Mode::Active)situation.enabled=false;
  situationLayer.step(situation,dt);
  handDt=dt;handUpdatePending=true;
  if(input.handTargetActive)lastHandTarget=input.handTarget;
  handEnvelope+=(float(input.handTargetActive && !input.action && !input.upperReception)-handEnvelope)*(1-std::exp(-8*dt));
  Vec acceleration=scalePoint(subtractPoint(input.velocity,previousVelocity),1/dt);
  filteredAcceleration=addPoint(filteredAcceleration,scalePoint(subtractPoint(capped(acceleration,10),filteredAcceleration),1-std::exp(-6*dt)));
  const float turn=std::atan2(crossPoint(lastForward,input.forward)[2],bounded(dotPoint(lastForward,input.forward),-1,1))/dt;
  filteredTurn+=(bounded(turn,-6,6)-filteredTurn)*(1-std::exp(-6*dt));
  previousVelocity=input.velocity;lastForward=input.forward;
  Vec impactWanted{{0,0,0}};
  if(input.ballImpactAge>=0&&input.ballImpactAge<.60f){
    const float sustain=1-smooth((input.ballImpactAge-.12f)/.48f);
    // A vertical ball also bends a back/shoulder: its actual offset from
    // the pelvis supplies the moment arm. Z cross velocity was exactly zero
    // for these hits, leaving the receiving body rigid under the ball.
    Vec axis=crossPoint(input.ballImpactLever,input.ballImpact);
    if(length(axis)>.01f){
      const float speed=length(input.ballImpact);
      const float response=speed>2.f?bounded(.10f+speed*.009f,.10f,.27f):speed*.025f;
      impactWanted=scalePoint(unit(axis),response*sustain);
    }
  }
  const Vec impactAcceleration=capped(subtractPoint(scalePoint(subtractPoint(impactWanted,impactReflex),196.f),scalePoint(impactReflexVelocity,28.f)),18.f);
  impactReflexVelocity=capped(addPoint(impactReflexVelocity,scalePoint(impactAcceleration,dt)),1.4f);
  impactReflex=capped(addPoint(impactReflex,scalePoint(impactReflexVelocity,dt)),.23f);
  debug.turnRate=filteredTurn;debug.effort=bounded(length(filteredAcceleration)/12+std::fabs(filteredTurn)*length(input.velocity)/55,0,1);
  // Plant one support shoe during native sideways/backward steps. The
  // anchor is a ground contact, never a target ball position. Release before
  // swing, excessive stretch or a queued action; bound the correction so a
  // different gait cannot drag a planted limb across the pitch.
  Points source;Pose sourceWorld;
  source[0]=input.pelvis;
  for(unsigned bone=0;bone<13;++bone){const int parent=pes3::nativeParents[bone];
    sourceWorld[bone]=parent<0?input.pose[bone]:normalized(productRotation(sourceWorld[parent],input.pose[bone]));
    if(parent>=0)source[bone]=addPoint(source[parent],rotatePoint(sourceWorld[parent],scalePoint(reference.offsets[bone],scale)));
  }
  for(unsigned side=0;side<2;++side){
    const unsigned ankle=side?12:9;const Vec foot=source[ankle];
    const Vec footVelocity=sourceFeetReady?scalePoint(subtractPoint(foot,sourceFeet[side]),1/dt):Vec{{0,0,0}};
    const bool allowed=input.grounding&&!input.action&&!input.touchPending&&!input.upperReception&&!input.staggering&&state==Mode::Active;
    if(!allowed||foot[2]>plantHeight[side]+.045f||length(subtractPoint(foot,plantAnchor[side]))>.07f||plantAge[side]>.24f)plantAge[side]=0;
    if(allowed&&plantAge[side]==0&&sourceFeetReady&&foot[2]<.18f&&foot[2]<=source[side?9:12][2]+.015f&&
       std::fabs(footVelocity[2])<.20f&&length(footVelocity)<3.f){
      plantAnchor[side]=addPoint(foot,plantOffset[side]);plantHeight[side]=foot[2];plantAge[side]=dt;
    }
    Vec wanted{{0,0,0}};
    if(allowed&&plantAge[side]>0){plantAge[side]+=dt;wanted=capped(subtractPoint(plantAnchor[side],foot),.055f);wanted[2]=0;}
    plantOffset[side]=addPoint(plantOffset[side],capped(subtractPoint(wanted,plantOffset[side]),.7f*dt));
    sourceFeet[side]=foot;
  }
  sourceFeetReady=true;
  const float impulseSize=length(pendingImpulse);
  if(state==Mode::Falling&&articulated&&impulseSize>0){
    const Vec lever=scalePoint(crossPoint(pendingImpulse,pendingTorque),1/std::max(.001f,impulseSize*impulseSize));
    articulated->impulse(pendingImpulse,lever);
  }
  bool lostBalance=false;
  if(state==Mode::Active){
    balance->addImpulse(pendingImpulse,pendingTorque);
    if(!input.action&&!input.upperReception&&!input.staggering&&length(input.velocity)>1.5f){
      // Acceleration and a hard change of direction load the support even
      // without an external collision. Integrated forces, not random falls.
      balance->addImpulse(scalePoint(filteredAcceleration,mass*.12f*dt),{{0,0,0}});
    }
    const float stance=length(subtractPoint(positions[9],positions[12]));
    lostBalance=balance->step(dt,input.pelvis[2],stance,length(input.velocity),input.protect,input.gripped);
    updateSupportStep(input,source,dt,impulseSize);
    debug.balanceRisk=balance->risk;debug.balancePhase=balance->phase;debug.stepDemand=balance->stepDemand;debug.supportMargin=balance->margin;
    const float accumulatedLoad=std::max(impulseSize,length(balance->remainingImpulse()));
    if(accumulatedLoad>20 && !balanceMotions->empty() && (balanceChoice<0 || balanceMotionTime>.55f)){
      // Match incident direction, native entry pose and movement speed. The
      // selected reference remains additive; it never moves a foot to a ball.
      const Vec incident=rotatePoint(inverseRotation(input.pose[0]),unit(impulseSize>15?pendingImpulse:balance->remainingImpulse()));
      float best=1e9f;
      for(unsigned m=0;m<balanceMotions->size();++m){const auto &candidate=(*balanceMotions)[m];if(candidate.frames.empty())continue;
        float cost=2.f*(1-dotPoint(incident,candidate.push))+.08f*std::fabs(length(input.velocity)-candidate.speed);
        for(unsigned bone:{1u,3u,5u})cost+=.10f*length(logarithm(productRotation(candidate.frames.front().pose[bone],inverseRotation(input.pose[bone]))));
        cost+=.18f*std::fabs(candidate.gain-bounded(accumulatedLoad/100.f,.5f,1.25f));
        cost+=3.f*std::fabs(candidate.lateral-.035f*incident[0]);
        if(cost<best){best=cost;balanceChoice=int(m);balanceMotionTime=0;}
      }
    }
    balanceMotionTime+=dt;
    // Recruit the torso/arms for difficult cuts and external disturbances.
    // The approved root trajectory, lower-body pose and cadence are untouched.
    Vec wanted{{0,0,0}};
    if(!input.action&&!input.upperReception&&!input.staggering){
      const float cut=length(input.velocity)>1.5f?bounded((std::fabs(filteredTurn)-.8f)/3.f,0,1):0;
      wanted=addPoint(scalePoint(crossPoint({{0,0,1}},filteredAcceleration),cut*.022f),scalePoint(balance->lean(),.60f));
      wanted=capped(wanted,.16f);
    }
    const Vec response=capped(subtractPoint(scalePoint(subtractPoint(wanted,counterTilt),100.f),scalePoint(counterTiltVelocity,20.f)),12.f);
    counterTiltVelocity=capped(addPoint(counterTiltVelocity,scalePoint(response,dt)),.9f);
    counterTilt=capped(addPoint(counterTilt,scalePoint(counterTiltVelocity,dt)),.19f);
    // Muscular support compresses the stance under load. The animation still
    // owns travel and timing; this response is integrated once per physics
    // tick, then both animated shoes are pinned by two-bone IK in evaluate().
    const auto &c=input.situation;
    const float phase=bounded(c.phase,0,1),at=bounded(c.contactPhase,.12f,.88f);
    const float release=c.enabled&&c.kind!=football_situations::ActionKind::None&&c.contactMade?
      smooth((phase-at+.08f)/.20f)*smooth((1-phase)/.30f):0;
    const bool groundStrike=c.enabled&&(c.kind==football_situations::ActionKind::Pass||c.kind==football_situations::ActionKind::Shot||c.kind==football_situations::ActionKind::Cross)&&c.ball[2]<-.50f;
    const float preparation=groundStrike?smooth(phase/std::max(.08f,at*.75f))*(1-smooth((phase-at)/.35f)):0;
    const float load=std::max(release,preparation)*(.25f+.75f*bounded(std::max(c.power,c.difficulty),0,1));
    const float plant=1-smooth((std::min(positions[9][2],positions[12][2])-.14f)/.12f);
    const float freedom=input.upperReception||input.staggering||(input.touchPending&&!groundStrike)?0.f:plant;
    Vec wantedSupport=addPoint(scalePoint(balance->lean(),.72f),scalePoint(crossPoint({{0,0,1}},filteredAcceleration),.012f));
    const Vec localRelease{{-(.015f+.035f*preparation)*load,.035f*load*bounded(c.signedTurn,-1,1),.065f*load*bounded(c.signedTurn,-1,1)}};
    wantedSupport=capped(scalePoint(addPoint(wantedSupport,rotatePoint(input.pose[0],localRelease)),freedom),.12f);
    const Vec supportAcceleration=capped(subtractPoint(scalePoint(subtractPoint(wantedSupport,supportTilt),81),scalePoint(supportTiltVelocity,18)),3.f);
    supportTiltVelocity=capped(addPoint(supportTiltVelocity,scalePoint(supportAcceleration,dt)),.55f);
    supportTilt=capped(addPoint(supportTilt,scalePoint(supportTiltVelocity,dt)),.12f);
    const float wantedSink=freedom*std::min(.038f,.014f*load+.032f*debug.balanceRisk+.002f*debug.effort);
    const float sinkAcceleration=bounded(100*(wantedSink-supportSink)-20*supportSinkVelocity,-.5f,.5f);
    supportSinkVelocity=bounded(supportSinkVelocity+sinkAcceleration*dt,-.055f,.055f);
    supportSink=bounded(supportSink+supportSinkVelocity*dt,0,.038f);
  }
  if(state==Mode::Active && (forcedFall || lostBalance)){
    state=Mode::Falling;stateAge=settled=0;
    deliberateFall=forcedFall;fallStandingHeight=root[2];arrestTime=0;
    if(!articulated)articulated.reset(new ArticulatedBody);
    // Torque is converted to a whole-body angular velocity using the actual
    // assembly inertia, instead of spinning a single pelvis with arbitrary I.
    const Vec lever=impulseSize>0?scalePoint(crossPoint(pendingImpulse,pendingTorque),1/(impulseSize*impulseSize)):Vec{{0,0,0}};
    const Vec fallImpulse=forcedFall?pendingImpulse:balance->remainingImpulse();
    articulated->release(reference,scale,local,root,input.velocity,fallImpulse,forcedFall?lever:Vec{{0,0,.28f}});
  }else if(state==Mode::Active && impulseSize>0){
    swayVelocity=addPoint(swayVelocity,scalePoint(pendingTorque,1/14.f));
  }
  const Vec activeImpulse=state==Mode::Active?pendingImpulse:Vec{{0,0,0}};
  pendingImpulse=pendingTorque={{0,0,0}};
  forcedFall=false;
  stateAge+=dt;
  if(state==Mode::Active){
    for(unsigned sub=0;sub<2;++sub){
      const float h=dt*.5f;
      swayVelocity=addPoint(swayVelocity,scalePoint(subtractPoint(scalePoint(sway,-80),scalePoint(swayVelocity,18)),h));
      sway=capped(addPoint(sway,scalePoint(swayVelocity,h)),.38f);
      for(unsigned i=0;i<13;++i){
        const Vec wanted=int(i)==input.reachBone?capped(scalePoint(input.reach,input.reachWeight),.08f):Vec{{0,0,0}};
        reachOffsets[i]=addPoint(reachOffsets[i],capped(subtractPoint(wanted,reachOffsets[i]),.28f*h));
      }
    }
    physicalUpperValid=false;evaluate(input);
    // Retain the physical state when a CPU stops. Destroying and rebuilding
    // thirteen bodies repeatedly both loses muscle state and causes hitches.
    if(!articulated)articulated.reset(new ArticulatedBody);
    articulated->track(reference,scale,local,root,dt,activeImpulse,physicalUpper,debug);
    physicalUpperValid=true;evaluate(input);
  }else if(state==Mode::Falling){
    const Vec previous=root;
    for(unsigned sub=0;sub<2;++sub)articulated->step(dt*.5f,local,root,debug);
    forwardKinematics();separateArms();
    // A dynamically arrested stumble can return to standing control. A
    // recovered upright body must not play a lying get-up or wait on a timer.
    const float upright=rotatePoint(world[0],{{0,0,1}})[2];
    const float speed=length(subtractPoint(root,previous))/dt;
    if(!deliberateFall&&stateAge>.4f&&debug.supportFeet>0&&upright>.97f&&
       std::fabs(root[2]-fallStandingHeight)<.02f*scale&&speed<.45f)arrestTime+=dt;
    else arrestTime=0;
    if(arrestTime>.16f){
      state=Mode::Active;stateAge=settled=0;balance.reset(new BalanceController);
      reachOffsets={};sway=swayVelocity={{0,0,0}};physicalUpperValid=false;
      debug.arrestedFall=true;return;
    }
    // Rest is measured from kinetic energy, not from a root whose velocity
    // was zeroed by a penetration correction.
    if(stateAge>1.2f && debug.kineticEnergy<8.f)settled+=dt;else settled=0;
    if(settled>.65f || stateAge>4.2f){
      state=Mode::Recovering;stateAge=0;recoveryStart=root;recoveryPose=local;
      recoveryMotion=rotatePoint(world[0],{{0,-1,0}})[2]<0?&recoveryFront:&recoveryBack;
      if(recoveryMotion->empty())recoveryMotion=nullptr;
      recoveryDuration=recoveryMotion?.45f+(recoveryMotion->size()-1)*.016f+.25f:2.f;
      // Align the authored get-up to the fallen body's long axis, rather
      // than rotating the lying actor back to the pre-fall world heading.
      const Vec fallen=subtractPoint(positions[2],positions[0]);
      Vec authored{{0,-1,0}};
      if(recoveryMotion){const Pose &pose=(*recoveryMotion)[0].pose;authored=rotatePoint(pose[0],addPoint(reference.offsets[1],rotatePoint(pose[1],reference.offsets[2])));}
      recoveryYaw=exponential({{0,0,std::atan2(crossPoint(authored,fallen)[2],authored[0]*fallen[0]+authored[1]*fallen[1])}});
    }
  }else{
    recover(input);
    if(stateAge>=recoveryDuration){state=Mode::Active;stateAge=0;reachOffset=sway=swayVelocity={{0,0,0}};reachOffsets={};balance.reset(new BalanceController);handInitialized=false;}
  }
  forwardKinematics();
  const Vec midpoint=scalePoint(addPoint(positions[9],positions[12]),.5f);
  Vec xcom=addPoint(root,scalePoint(input.velocity,1/std::sqrt(9.81f/std::max(.4f,root[2]))));xcom[2]=midpoint[2];
  if(state!=Mode::Active)debug.supportMargin=.22f-length(subtractPoint(xcom,midpoint));
  debug.balanceChoice=balanceChoice;
}
void PhysicalRig::updateSupportStep(const Input &input,const Points &source,float dt,float impulseSize){
  stepCooldown=std::max(0.f,stepCooldown-dt);
  const bool available=!input.action&&!input.touchPending&&!input.upperReception&&!input.staggering&&!input.gripped&&!input.handTargetActive&&input.opponentDistance>.35f&&length(input.velocity)<4.8f;
  // A free support step must not compete with an anchored hand or step
  // through a close body. Those constraints retain upper-body balance.
  // A fresh external impulse or a sustained capture-point deficit can require
  // a new support. Neither the animation bank nor the ball supplies this target.
  if(recoveryFoot<0&&stepCooldown<=0&&available&&balance->stepDemand>.045f&&
     (impulseSize>45.f||balance->risk>.30f)&&std::min(source[9][2],source[12][2])<.22f){
    Vec direction=unit(balance->remainingImpulse(),input.forward);
    if(input.opponentDistance<.80f){
      const Vec toward=unit(input.opponent,input.forward);
      if(dotPoint(direction,toward)>0)direction=unit(subtractPoint(direction,scalePoint(toward,dotPoint(direction,toward)+.25f)),scalePoint(toward,-1));
    }
    const Vec lateral=rotatePoint(input.pose[0],{{1,0,0}});
    const float side=dotPoint(direction,lateral);
    recoveryFoot=std::fabs(side)>.25f?(side>0?0:1):
      (dotPoint(source[9],direction)<dotPoint(source[12],direction)?0:1);
    // Keep the lower, loaded shoe as support if the preferred outside
    // shoe is still the only grounded one in the current native gait.
    if(source[recoveryFoot?9:12][2]>source[recoveryFoot?12:9][2]+.035f)recoveryFoot=1-recoveryFoot;
    const unsigned moving=recoveryFoot?12:9,other=recoveryFoot?9:12;
    stepStart=source[moving];stepSupport=source[other];
    stepTarget=addPoint(stepStart,scalePoint(direction,bounded(.12f+balance->stepDemand*.55f,.14f,.34f)*scale));
    // An outside recovery step cannot cross through the standing shin.
    const float separation=dotPoint(subtractPoint(stepTarget,stepSupport),lateral)*(recoveryFoot? -1.f:1.f);
    if(separation<.14f*scale)stepTarget=addPoint(stepTarget,scalePoint(lateral,(.14f*scale-separation)*(recoveryFoot?-1.f:1.f)));
    stepTarget[2]=std::min(stepStart[2],stepSupport[2]);stepTime=0;stepRelease=0;stepCooldown=.85f;
  }
  if(recoveryFoot>=0){
    stepTime+=dt;
    const unsigned support=recoveryFoot?9:12;
    Vec drift=subtractPoint(source[support],stepSupport);drift[2]=0;
    const bool leavingSupport=length(drift)>.18f*scale||source[support][2]>stepSupport[2]+.10f*scale;
    if(!available||leavingSupport||stepRelease>0)stepRelease=std::min(1.f,stepRelease+dt/.12f);
    const float progress=bounded(stepTime/stepDuration,0,1);
    const float weight=smooth(stepTime/.08f)*(1-smooth(std::max(0.f,stepTime-stepDuration-.10f)/.22f))*(1-smooth(stepRelease));
    Vec swing=addPoint(stepStart,scalePoint(subtractPoint(stepTarget,stepStart),smooth(progress)));
    swing[2]+=.065f*scale*std::pow(std::sin(3.14159265f*progress),2.f);
    for(unsigned side=0;side<2;++side){
      const unsigned ankle=side?12:9;
      const Vec target=side==unsigned(recoveryFoot)?swing:stepSupport;
      const Vec wanted=scalePoint(capped(subtractPoint(target,source[ankle]),.40f*scale),weight);
      // Bounded speed prevents a changing base clip or an interrupted action
      // from snapping a shoe to its calculated support point.
      stepOffset[side]=addPoint(stepOffset[side],capped(subtractPoint(wanted,stepOffset[side]),1.45f*dt));
    }
    debug.recoveryStep=weight;debug.recoveryFoot=recoveryFoot;
    debug.recoveryLift=std::max(0.f,swing[2]-stepStart[2])*weight;
    if((stepTime>stepDuration+.33f||stepRelease>=1)&&length(stepOffset[0])+length(stepOffset[1])<.003f){
      recoveryFoot=-1;stepOffset[0]=stepOffset[1]={{0,0,0}};
    }
  }
}
void PhysicalRig::applySupportStep(const Input &input){
  if(recoveryFoot<0)return;
  for(unsigned side=0;side<2;++side){
    const unsigned ankle=side?12:9;
    const Vec target=addPoint(positions[ankle],stepOffset[side]);
    solveLeg(ankle-2,target,.001f);
    if(side==unsigned(recoveryFoot))debug.recoveryLift=std::max(0.f,positions[ankle][2]-stepStart[2]);
    if(side!=unsigned(recoveryFoot)&&debug.recoveryStep>.95f)debug.recoverySupportError=length(subtractPoint(positions[ankle],stepSupport));
  }
}
void PhysicalRig::evaluate(const Input &input){
  if(!ready || state!=Mode::Active)return;
  root=input.pelvis;
  local=input.pose;forwardKinematics();const Vec left=positions[9],right=positions[12];
  if(!input.upperReception&&!input.staggering&&(supportSink>1e-6f||length(supportTilt)>1e-6f)){
    const Vec leftKnee=positions[8],rightKnee=positions[11];
    const Quat leftShoe=world[9],rightShoe=world[12];
    root[2]-=supportSink;
    local[0]=normalized(productRotation(exponential(supportTilt),local[0]));forwardKinematics();
    solveLeg(7,left,1e-5f);solveLeg(10,right,1e-5f);
    local[9]=normalized(productRotation(inverseRotation(world[8]),leftShoe));
    local[12]=normalized(productRotation(inverseRotation(world[11]),rightShoe));forwardKinematics();
    debug.supportSink=supportSink;debug.supportTilt=length(supportTilt);
    debug.supportKnee=std::max(length(subtractPoint(leftKnee,positions[8])),length(subtractPoint(rightKnee,positions[11])));
    debug.supportFootError=std::max(length(subtractPoint(left,positions[9])),length(subtractPoint(right,positions[12])));
  }
  if(input.grounding&&recoveryFoot<0&&!input.action&&!input.touchPending&&!input.upperReception&&!input.staggering){
    for(unsigned side=0;side<2;++side)if(length(plantOffset[side])>1e-6f){
      const unsigned ankle=side?12:9;
      solveLeg(ankle-2,addPoint(positions[ankle],plantOffset[side]),1e-5f);
      debug.plantedCorrection=std::max(debug.plantedCorrection,length(plantOffset[side]));
    }
  }
  applySupportStep(input);
  if(input.receptionSupportBone==9||input.receptionSupportBone==12)
    solveLeg(input.receptionSupportBone-2,input.receptionSupport,.001f);
  Vec horizontal=capped(filteredAcceleration,5);
  Vec leanAxis=crossPoint({{0,0,1}},scalePoint(horizontal,1/9.81f));
  leanAxis=capped(addPoint(addPoint(addPoint(scalePoint(leanAxis,.68f),sway),balance->lean()),counterTilt),.44f);
  const float actionBias=input.upperReception || input.situation.kind==football_situations::ActionKind::Header?0.f:input.action?.35f:1.f;
  leanAxis=scalePoint(leanAxis,actionBias);
  // Retain the solved support chain. Reinitializing from input.pose here
  // discarded knee/foot planting before the final pose reached rendering.
  Pose target=local;
  debug.counterbalance=length(counterTilt);
  if(balanceChoice>=0 && !input.staggering && !input.action && !input.upperReception){
    const auto &motion=(*balanceMotions)[balanceChoice];
    const float frame=balanceMotionTime/.016f;
    if(frame<float(motion.frames.size()-1)){
      const unsigned a=unsigned(frame),b=std::min(a+1,unsigned(motion.frames.size()-1));
      const float envelope=smooth(balanceMotionTime/.16f)*smooth((motion.frames.size()-1-frame)/12.f)*.44f*motion.gain;
      for(unsigned bone:{1u,3u,4u,5u,6u}){
        const Quat q=blended(motion.frames[a].pose[bone],motion.frames[b].pose[bone],frame-a);
        const Vec delta=capped(logarithm(productRotation(q,inverseRotation(motion.frames[0].pose[bone]))),.65f);
        target[bone]=normalized(productRotation(exponential(scalePoint(delta,envelope)),target[bone]));
      }
    }
  }
  // Active movement stays on its native smoothed lower-body animation.
  // Only additive upper-body balance is applied; no absolute-pose overwrite.
  const Quat head=world[2];
  target[1]=normalized(productRotation(exponential(rotatePoint(inverseRotation(world[0]),leanAxis)),target[1]));
  if(!input.upperReception){
    const float shield=input.opponentDistance<1.15f?(.45f+.8f*protection)*(1-input.opponentDistance/1.15f):0;
    const bool opponentRight=dotPoint(input.opponent,crossPoint(input.forward,{{0,0,1}}))>0;
    for(unsigned i:{3u,5u}){
      const float armShield=shield*((i==5)==opponentRight?1.f:.1f);
      const float counterbalance=bounded(length(sway)*.75f+length(counterTilt)*.65f,0,.20f);
      target[i]=normalized(productRotation(exponential({{-.4f*length(sway),-filteredTurn*.012f+(i==5?armShield+counterbalance:-armShield-counterbalance),0}}),target[i]));
    }
  }
  local=target;forwardKinematics();
  local[2]=normalized(productRotation(inverseRotation(world[1]),head));forwardKinematics();
  // An action has its own bounded preparation/follow-through layer. It must
  // not inherit the old 'action disables all balance' behavior. Its upper
  // chain cannot reposition the root, support feet, or the ball-contact foot.
  const Vec situationRoot=root,situationLeft=positions[9],situationRight=positions[12];
  const Pose situationBase=local;
  auto situation=input.situation;
  if(input.upperReception || input.staggering)situation.enabled=false;
  situationLayer.evaluate(situation,reference,scale,local,root);
  forwardKinematics();
  debug.situation=situationLayer.metrics();
  debug.situationTrunk=length(logarithm(productRotation(local[1],inverseRotation(situationBase[1]))));
  debug.situationArms=0;
  for(unsigned bone:{3u,4u,5u,6u})debug.situationArms=std::max(debug.situationArms,length(logarithm(productRotation(local[bone],inverseRotation(situationBase[bone])))));
  debug.situationRootError=length(subtractPoint(root,situationRoot));
  debug.situationFootError=std::max(length(subtractPoint(positions[9],situationLeft)),length(subtractPoint(positions[12],situationRight)));
  for(unsigned ankle:{9u,12u})if(length(reachOffsets[ankle])>1e-6f)
    solveLeg(ankle-2,addPoint(positions[ankle],reachOffsets[ankle]));
  {
    const bool heading=input.reachBone==2;
    Vec upperReach=rotatePoint(inverseRotation(world[0]),capped(addPoint(reachOffsets[1],reachOffsets[2]),heading?.06f:.03f));
    const Vec bend=capped(crossPoint({{0,0,1}},scalePoint(upperReach,1/.45f)),heading?.14f:.10f);
    local[1]=normalized(productRotation(exponential(bend),local[1]));
    forwardKinematics();
  }
  // A measured ball hit has a short whole-upper-body reflex even while a
  // different football action is active. It never moves a contacting foot.
  // The learned muscle tracker follows this reference on the next substep.
  if(length(impactReflex)>.0001f){
    const float gain=input.upperReception?.35f:1.f;
    const float strength=bounded(length(impactReflex)/.216f,0,1);
    if(!(input.touchPending&&input.situation.kind==football_situations::ActionKind::Header))
      local[1]=normalized(productRotation(exponential(scalePoint(rotatePoint(inverseRotation(world[0]),impactReflex),gain)),local[1]));
    for(unsigned shoulder:{3u,5u})local[shoulder]=normalized(productRotation(exponential({{-.08f*strength,(shoulder==3?-.13f:.13f)*strength,0}}),local[shoulder]));
    forwardKinematics();
  }
  // Small anticipatory save corrections rotate the real shoulder chain.
  // The same damped reach envelope used by feet limits approach and release;
  // no limb is stretched and the ball still needs a measured skin contact.
  for(unsigned elbow:{4u,6u})if(length(reachOffsets[elbow])>1e-6f){
    const unsigned shoulder=elbow-1;
    const Vec tip=addPoint(positions[elbow],rotatePoint(world[elbow],{{0,0,-.25f*scale}}));
    const Vec lever=subtractPoint(tip,positions[shoulder]);
    const Quat turn=pes3::swingRotation(unit(lever),unit(addPoint(lever,reachOffsets[elbow])));
    const Quat goal=normalized(productRotation(exponential(capped(logarithm(turn),.16f)),world[shoulder]));
    local[shoulder]=normalized(productRotation(inverseRotation(world[1]),goal));forwardKinematics();
  }
  if(physicalUpperValid && (!input.action||length(impactReflex)>.001f) && !input.upperReception){
    for(unsigned i=1;i<=6;++i){
      // Arms keep their authored muscle tone while upright. Applying 65% of
      // a freely lagging forearm made the elbow look dislocated even when
      // Bullet's own constraint was valid. Free falls still use full dynamics.
      const bool arm=i>=3;
      if(!arm&&input.touchPending&&input.situation.kind==football_situations::ActionKind::Header)continue;
      const Vec error=capped(logarithm(productRotation(physicalUpper[i],inverseRotation(local[i]))),arm?.20f:i==1?.24f:.14f);
      // Preserve authored locomotion swing at rest. Dynamics add compliance
      // under actual load, instead of a permanent hunched/locked arm pose.
      const float loading=bounded(debug.balanceRisk*1.8f+length(sway)*2.f+length(impactReflex)*3.f,0,1);
      const float gain=arm?.12f+.56f*loading:.20f+.60f*loading;
      local[i]=normalized(productRotation(exponential(scalePoint(error,gain)),local[i]));
    }
    forwardKinematics();
    if(!input.action&&!input.touchPending&&!input.staggering){
      const Vec shoes[2]={positions[9],positions[12]};
      const float loading=bounded(debug.balanceRisk*1.8f+length(sway)*2.f,0,1);
      for(unsigned bone:{7u,8u,10u,11u}){
        const Vec error=capped(logarithm(productRotation(physicalUpper[bone],inverseRotation(local[bone]))),.14f);
        local[bone]=normalized(productRotation(exponential(scalePoint(error,.60f*loading)),local[bone]));
      }
      forwardKinematics();
      // Dynamic knee/pelvic response can alter the bend plane, but the
      // support shoe keeps its real target and every segment keeps its length.
      solveLeg(7,shoes[0],1e-5f);solveLeg(10,shoes[1],1e-5f);
    }
  }
  if(handEnvelope>.002f && !input.upperReception && !input.action){
    if(!handInitialized){handShoulder=length(subtractPoint(input.handTarget,positions[3]))<length(subtractPoint(input.handTarget,positions[5]))?3:5;handPose[0]=local[handShoulder];handPose[1]=local[handShoulder+1];handInitialized=true;}
    reachHand(unsigned(handShoulder),input.handTargetActive?input.handTarget:lastHandTarget,handEnvelope);
  }else if(handEnvelope<.002f){handInitialized=false;}
  handUpdatePending=false;
  separateArms();
  for(unsigned i=0;i<13;++i)additive[i]=normalized(productRotation(local[i],inverseRotation(input.pose[i])));
  debug.lean=length(leanAxis);debug.reach=0;
  for(auto v:reachOffsets)debug.reach=std::max(debug.reach,length(v));
}

void PhysicalRig::reachHand(unsigned shoulder,Vec target,float weight){
  const unsigned elbow=shoulder+1;
  const Vec hand=addPoint(positions[elbow],rotatePoint(world[elbow],{{0,0,-.25f*scale}}));
  const Vec upper=subtractPoint(positions[elbow],positions[shoulder]),lower=subtractPoint(hand,positions[elbow]);
  const float a=length(upper),b=length(lower);
  if(a<.05f || b<.05f)return;
  Vec relative=rotatePoint(inverseRotation(world[1]),subtractPoint(target,positions[shoulder]));
  // Reaching behind the back is not a valid shirt hold. The interaction
  // releases if its real hand can no longer follow the anchored surface.
  relative[1]=std::min(.10f*scale,relative[1]);
  target=addPoint(positions[shoulder],rotatePoint(world[1],relative));
  const Vec direction=unit(subtractPoint(target,positions[shoulder]));
  const float maximum=std::sqrt(a*a+b*b+2*a*b*std::cos(.15f));
  const float minimum=std::sqrt(a*a+b*b+2*a*b*std::cos(2.4f));
  const float distance=bounded(length(subtractPoint(target,positions[shoulder])),minimum,maximum);
  target=addPoint(positions[shoulder],scalePoint(direction,distance));
  const Vec outward=rotatePoint(world[1],{{shoulder==3?.45f:-.45f,.05f,-1.f}});
  const Vec pole=unit(subtractPoint(outward,scalePoint(direction,dotPoint(outward,direction))));
  const float along=(a*a-b*b+distance*distance)/(2*distance);
  const Vec bend=addPoint(addPoint(positions[shoulder],scalePoint(direction,along)),scalePoint(pole,std::sqrt(std::max(0.f,a*a-along*along))));
  const Vec upperDirection=unit(subtractPoint(bend,positions[shoulder])),lowerDirection=unit(subtractPoint(target,bend));
  Quat arm=pes3::swingRotation(unit(reference.offsets[elbow]),upperDirection);
  const Vec hinge=unit(scalePoint(crossPoint(upperDirection,lowerDirection),-1.f));
  const Vec currentAxis=unit(rotatePoint(arm,{{1,0,0}}));
  const float twist=std::atan2(dotPoint(upperDirection,crossPoint(currentAxis,hinge)),dotPoint(currentAxis,hinge));
  arm=normalized(productRotation(exponential(scalePoint(upperDirection,twist)),arm));
  Quat wanted[2]={normalized(productRotation(inverseRotation(world[1]),arm)),exponential({{-std::acos(bounded(dotPoint(upperDirection,lowerDirection),-1,1)),0,0}})};
  for(unsigned i=0;i<2;++i)wanted[i]=anatomicalArm(shoulder+i,wanted[i]);
  // Projecting the analytic elbow plane into its anatomical limits can
  // leave the hand short of a reachable shirt. Refine the constrained goal,
  // then approach it through the same bounded angular-velocity controller.
  // This never expands the grip distance or moves the hand instantaneously.
  for(unsigned iteration=0;iteration<10;++iteration){
    Quat upperQ=normalized(productRotation(world[1],wanted[0]));
    Vec elbowPoint=addPoint(positions[shoulder],rotatePoint(upperQ,scalePoint(reference.offsets[elbow],scale)));
    Vec tip=addPoint(elbowPoint,rotatePoint(productRotation(upperQ,wanted[1]),{{0,0,-.25f*scale}}));
    const Vec axis=rotatePoint(upperQ,{{1,0,0}});
    Vec a=subtractPoint(tip,elbowPoint),b=subtractPoint(target,elbowPoint);
    a=subtractPoint(a,scalePoint(axis,dotPoint(a,axis)));b=subtractPoint(b,scalePoint(axis,dotPoint(b,axis)));
    const float angle=bounded(std::atan2(dotPoint(axis,crossPoint(a,b)),dotPoint(a,b)),-.18f,.18f);
    wanted[1]=anatomicalArm(elbow,productRotation(exponential({{angle,0,0}}),wanted[1]));
    tip=addPoint(elbowPoint,rotatePoint(productRotation(upperQ,wanted[1]),{{0,0,-.25f*scale}}));
    const Quat correction=pes3::swingRotation(unit(subtractPoint(tip,positions[shoulder])),unit(subtractPoint(target,positions[shoulder])));
    upperQ=normalized(productRotation(exponential(capped(logarithm(correction),.18f)),upperQ));
    wanted[0]=anatomicalArm(shoulder,productRotation(inverseRotation(world[1]),upperQ));
  }
  if(handUpdatePending)for(unsigned i=0;i<2;++i){
    const Vec error=logarithm(productRotation(wanted[i],inverseRotation(handPose[i])));
    const Vec speed=capped(scalePoint(error,12.f),3.8f);
    handVelocity[i]=addPoint(handVelocity[i],capped(subtractPoint(speed,handVelocity[i]),24.f*handDt));
    const Vec change=capped(scalePoint(handVelocity[i],handDt),length(error));
    handPose[i]=anatomicalArm(shoulder+i,productRotation(exponential(change),handPose[i]));
  }
  local[shoulder]=blended(local[shoulder],handPose[0],weight);
  local[elbow]=blended(local[elbow],handPose[1],weight);
  debug.armSpeed=std::max(length(handVelocity[0]),length(handVelocity[1]));
  debug.elbowAngle=length(logarithm(handPose[1]));
  forwardKinematics();
}

void constrainArmPose(const pes3::NativeBind &reference,float scale,Pose &local,Vec root,Metrics &debug){
  Points positions{};Pose world{};
  auto forwardKinematics=[&](){positions[0]=root;for(unsigned i=0;i<13;++i){
    const int parent=pes3::nativeParents[i];world[i]=parent<0?local[i]:normalized(productRotation(world[parent],local[i]));
    if(parent>=0)positions[i]=addPoint(positions[parent],rotatePoint(world[parent],scalePoint(reference.offsets[i],scale)));
  }};
  // A small analytic collision pass also protects the displayed, smoothed
  // skeleton. Bullet's proxies alone do not constrain the final blended pose.
  // Clamp the final pose, not merely the IK target. This also constrains the
  // native/physical crossfade and recovery samples. Re-project each collision
  // correction so separating an arm cannot twist its shoulder out of range.
  for(unsigned i:{3u,4u,5u,6u})local[i]=anatomicalArm(i,local[i]);
  forwardKinematics();
  auto closest=[](Vec p,Vec a,Vec b){const Vec ab=subtractPoint(b,a);return addPoint(a,scalePoint(ab,bounded(dotPoint(subtractPoint(p,a),ab)/std::max(1e-8f,dotPoint(ab,ab)),0,1)));};
  for(unsigned shoulder:{3u,5u})for(unsigned iteration=0;iteration<22;++iteration){
    const unsigned elbow=shoulder+1;
    const Vec hand=addPoint(positions[elbow],rotatePoint(world[elbow],{{0,0,-.24f*scale}}));
    Vec correction{{0,0,0}},contact=hand;
    for(unsigned sample=0;sample<=12;++sample){
      // Include the upper arm away from its deliberately overlapping socket.
      const Vec point=sample<=6?addPoint(positions[elbow],scalePoint(subtractPoint(hand,positions[elbow]),sample/6.f)):
        addPoint(positions[shoulder],scalePoint(subtractPoint(positions[elbow],positions[shoulder]),(sample-5)/7.f));
      const Vec localPoint=rotatePoint(inverseRotation(world[1]),subtractPoint(point,positions[1]));
      const float side=shoulder==3?1.f:-1.f;
      Vec displacement{{0,0,0}};
      if(localPoint[2]>=-.10f*scale && localPoint[2]<=.45f*scale){
      // Elliptical torso with allowance for the arm radius and shirt.
      const float rx=.195f*scale,ry=.145f*scale;
      const float ellipse=std::sqrt(localPoint[0]*localPoint[0]/(rx*rx)+localPoint[1]*localPoint[1]/(ry*ry));
      if(ellipse<1){
      const float boundary=side*rx*std::sqrt(std::max(0.f,1-localPoint[1]*localPoint[1]/(ry*ry)));
      displacement=rotatePoint(world[1],{{side*std::max(0.f,side*(boundary-localPoint[0]))+.002f*side,0,0}});
      }}
      // Forearm/hand against head and thighs, and against the other arm.
      // The socket samples are exempt from the head/shoulder overlap.
      if(sample<=6){
        for(unsigned other:{2u,7u,10u,shoulder==3?5u:3u,shoulder==3?6u:4u}){
          const Vec a=positions[other];
          Vec b=other==2?addPoint(a,rotatePoint(world[2],{{0,0,.12f*scale}})):
            other==4||other==6?addPoint(a,rotatePoint(world[other],{{0,0,-.25f*scale}})):positions[other+1];
          const float radius=(other==2?.145f:other==7||other==10?.115f:.09f)*scale;
          const Vec nearest=closest(point,a,b),delta=subtractPoint(point,nearest);
          const float overlap=radius-length(delta);
          if(overlap>0){
            const Vec away=rotatePoint(world[1],{{side,0,0}});
            const Vec push=scalePoint(unit(addPoint(delta,scalePoint(away,.04f)),away),overlap+.002f);
            if(length(push)>length(displacement))displacement=push;
          }
        }
      }
      if(length(displacement)>length(correction)){correction=displacement;contact=point;}
    }
    if(length(correction)<.0001f)break;
    const Vec arm=subtractPoint(contact,positions[shoulder]);
    const Quat swing=pes3::swingRotation(unit(arm),unit(addPoint(arm,capped(correction,.045f))));
    local[shoulder]=anatomicalArm(shoulder,productRotation(productRotation(inverseRotation(world[1]),swing),world[shoulder]));
    forwardKinematics();
  }
  debug.armLimitError=0;debug.armPenetration=0;
  for(unsigned i:{3u,4u,5u,6u})debug.armLimitError=std::max(debug.armLimitError,armLimitError(i,local[i]));
  // Signed geometric diagnostics refer to the resulting displayed skeleton,
  // rather than the hand solver's unconstrained requested angles.
  for(unsigned elbow:{4u,6u})for(unsigned sample=0;sample<=8;++sample){
    Vec p=addPoint(positions[elbow],rotatePoint(world[elbow],{{0,0,-.25f*scale*sample/8.f}}));
    p=rotatePoint(inverseRotation(world[1]),subtractPoint(p,positions[1]));
    if(p[2]>=-.10f*scale && p[2]<=.45f*scale){
      const float ellipse=std::sqrt(p[0]*p[0]/(.185f*.185f*scale*scale)+p[1]*p[1]/(.135f*.135f*scale*scale));
      debug.armPenetration=std::max(debug.armPenetration,std::max(0.f,1-ellipse)*.135f*scale);
    }
  }
}

void PhysicalRig::separateArms(){
  constrainArmPose(reference,scale,local,root,debug);forwardKinematics();
}

void PhysicalRig::groundRecovery(){
  forwardKinematics();float minimum=100;
  for(unsigned i=0;i<13;++i){
    Vec end=positions[i];
    if(i==1)end=positions[2];
    else if(i==3||i==5||i==7||i==8||i==10||i==11)end=positions[i+1];
    else end=addPoint(end,rotatePoint(world[i],scalePoint(tip(i),scale)));
    // Capsules are shorter than their joint-to-joint segment. At least one
    // hand, knee, foot or body surface stays supported throughout recovery.
    const float radius=(i==0?.11f:i==1?.105f:i==2?.085f:i==3||i==5?.045f:.038f)*scale;
    const float low=std::min(positions[i][2],end[2]);
    minimum=std::min(minimum,low-radius*.45f);
  }
  root[2]+=.006f-minimum;forwardKinematics();
  debug.groundContacts=1;debug.penetration=0;
}

void PhysicalRig::recover(const Input &input){
  debug.recoveryPhase=bounded(stateAge/recoveryDuration,0,1);
  if(!recoveryMotion){
    // Headless/unit callers without an authored bank still receive a grounded
    // fallback. The game always supplies the original front/back get-up clips.
    const float t=smooth(stateAge/recoveryDuration);
    for(unsigned i=0;i<13;++i)local[i]=blended(recoveryPose[i],input.pose[i],t);
    root=recoveryStart;groundRecovery();return;
  }
  const float phase=bounded((stateAge-.45f)/.016f,0,float(recoveryMotion->size()-1));
  const unsigned a=unsigned(phase),b=std::min(a+1,unsigned(recoveryMotion->size()-1));
  const float fraction=phase-a,entry=smooth(stateAge/.45f);
  const auto &first=(*recoveryMotion)[0];
  Vec translation=subtractPoint(addPoint(scalePoint((*recoveryMotion)[a].pelvis,1-fraction),scalePoint((*recoveryMotion)[b].pelvis,fraction)),first.pelvis);
  translation=rotatePoint(recoveryYaw,scalePoint(translation,scale));
  root=addPoint(recoveryStart,scalePoint(translation,entry));
  for(unsigned i=0;i<13;++i){
    Quat target=blended((*recoveryMotion)[a].pose[i],(*recoveryMotion)[b].pose[i],fraction);
    if(i==0)target=normalized(productRotation(recoveryYaw,target));
    local[i]=blended(recoveryPose[i],target,entry);
  }
  const float exit=smooth((stateAge-(recoveryDuration-.25f))/.25f);
  for(unsigned i=0;i<13;++i){
    Quat target=input.pose[i];
    if(i==0){
      const Vec oldForward=rotatePoint(input.pose[0],{{0,-1,0}});
      const Vec newForward=rotatePoint(productRotation(recoveryYaw,recoveryMotion->back().pose[0]),{{0,-1,0}});
      const Quat yaw=exponential({{0,0,std::atan2(crossPoint(oldForward,newForward)[2],oldForward[0]*newForward[0]+oldForward[1]*newForward[1])}});
      target=normalized(productRotation(yaw,target));
    }
    local[i]=blended(local[i],target,exit);
  }
  groundRecovery();separateArms();
}
}
