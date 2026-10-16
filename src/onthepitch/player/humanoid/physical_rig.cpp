#include "physical_rig.hpp"
#include "articulated_body.hpp"

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
void PhysicalRig::reset(){ready=false;state=Mode::Active;stateAge=settled=filteredTurn=unstableTime=protection=0;pendingImpulse=pendingTorque=reachOffset=sway=swayVelocity=filteredAcceleration=previousVelocity={{0,0,0}};angularVelocity={};articulated.reset();physicalUpperValid=false;recoveryMotion=nullptr;reachOffsets={};for(auto &q:additive)q={{0,0,0,1}};debug={};}
void PhysicalRig::impulse(Vec value,Vec lever){value=capped(value,360);pendingImpulse=addPoint(pendingImpulse,value);pendingTorque=addPoint(pendingTorque,crossPoint(lever,value));}

void PhysicalRig::forwardKinematics(){
  positions[0]=root;
  for(unsigned i=0;i<13;++i){
    const int parent=pes3::nativeParents[i];
    world[i]=parent<0?local[i]:normalized(productRotation(world[parent],local[i]));
    if(parent>=0)positions[i]=addPoint(positions[parent],rotatePoint(world[parent],scalePoint(reference.offsets[i],scale)));
  }
}

void PhysicalRig::solveLeg(unsigned hip,Vec target){
  const unsigned knee=hip+1,ankle=hip+2;
  const Vec upper=subtractPoint(positions[knee],positions[hip]),lower=subtractPoint(positions[ankle],positions[knee]);
  const float a=length(upper),b=length(lower);
  if(a<.05f||b<.05f)return;
  Vec direction=unit(subtractPoint(target,positions[hip]));
  const float distance=bounded(length(subtractPoint(target,positions[hip])),std::fabs(a-b)+.003f,a+b-.003f);
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

PhysicalRig::PhysicalRig()=default;
PhysicalRig::~PhysicalRig()=default;
void PhysicalRig::step(const Input &input,float dt){
  dt=bounded(dt,.001f,.02f);
  protection+=(float(input.protect)-protection)*(1-std::exp(-7*dt));
  if(!ready){local=input.pose;root=input.pelvis;previousVelocity=input.velocity;lastForward=input.forward;ready=true;forwardKinematics();}
  debug={};
  Vec acceleration=scalePoint(subtractPoint(input.velocity,previousVelocity),1/dt);
  filteredAcceleration=addPoint(filteredAcceleration,scalePoint(subtractPoint(capped(acceleration,10),filteredAcceleration),1-std::exp(-6*dt)));
  const float turn=std::atan2(crossPoint(lastForward,input.forward)[2],bounded(dotPoint(lastForward,input.forward),-1,1))/dt;
  filteredTurn+=(bounded(turn,-6,6)-filteredTurn)*(1-std::exp(-6*dt));
  previousVelocity=input.velocity;lastForward=input.forward;
  debug.turnRate=filteredTurn;debug.effort=bounded(length(filteredAcceleration)/12+std::fabs(filteredTurn)*length(input.velocity)/55,0,1);
  const float impulseSize=length(pendingImpulse);
  if(state==Mode::Active && impulseSize>=145.f+40.f*protection){
    state=Mode::Falling;stateAge=settled=0;
    articulated.reset(new ArticulatedBody);
    // Torque is converted to a whole-body angular velocity using the actual
    // assembly inertia, instead of spinning a single pelvis with arbitrary I.
    const Vec lever=impulseSize>0?scalePoint(crossPoint(pendingImpulse,pendingTorque),1/(impulseSize*impulseSize)):Vec{{0,0,0}};
    articulated->start(reference,scale,local,root,input.velocity,pendingImpulse,lever);
  }else if(state==Mode::Active && impulseSize>0){
    swayVelocity=addPoint(swayVelocity,scalePoint(pendingTorque,1/3.f));
  }
  const Vec activeImpulse=state==Mode::Active?pendingImpulse:Vec{{0,0,0}};
  pendingImpulse=pendingTorque={{0,0,0}};
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
    if(!articulated)articulated.reset(new ArticulatedBody);
    articulated->track(reference,scale,local,root,dt,activeImpulse,physicalUpper,debug);
    physicalUpperValid=true;evaluate(input);
  }else if(state==Mode::Falling){
    for(unsigned sub=0;sub<2;++sub)articulated->step(dt*.5f,local,root,debug);
    forwardKinematics();
    // Rest is measured from kinetic energy, not from a root whose velocity
    // was zeroed by a penetration correction.
    if(stateAge>1.2f && debug.kineticEnergy<8.f)settled+=dt;else settled=0;
    if(settled>.65f || stateAge>4.2f){
      state=Mode::Recovering;stateAge=0;recoveryStart=root;recoveryPose=local;articulated.reset();
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
    if(stateAge>=recoveryDuration){state=Mode::Active;stateAge=0;reachOffset=sway=swayVelocity={{0,0,0}};reachOffsets={};}
  }
  forwardKinematics();
  const Vec midpoint=scalePoint(addPoint(positions[9],positions[12]),.5f);
  Vec xcom=addPoint(root,scalePoint(input.velocity,1/std::sqrt(9.81f/std::max(.4f,root[2]))));xcom[2]=midpoint[2];
  debug.supportMargin=.22f-length(subtractPoint(xcom,midpoint));
}
void PhysicalRig::evaluate(const Input &input){
  if(!ready || state!=Mode::Active)return;
  root=input.pelvis;
  local=input.pose;forwardKinematics();const Vec left=positions[9],right=positions[12];
  Vec horizontal=capped(filteredAcceleration,5);
  Vec leanAxis=crossPoint({{0,0,1}},scalePoint(horizontal,1/9.81f));
  leanAxis=capped(addPoint(scalePoint(leanAxis,.14f),sway),.38f);
  const float actionBias=input.upperReception || input.action?0.f:1.f;
  leanAxis=scalePoint(leanAxis,actionBias);
  Pose target=input.pose;
  // Active movement stays on its native smoothed lower-body animation.
  // Only additive upper-body balance is applied; no absolute-pose overwrite.
  const Quat head=world[2];
  target[1]=normalized(productRotation(exponential(rotatePoint(inverseRotation(world[0]),leanAxis)),target[1]));
  if(!input.upperReception){
    const float shield=input.opponentDistance<1.15f?(.45f+.8f*protection)*(1-input.opponentDistance/1.15f):0;
    const bool opponentRight=dotPoint(input.opponent,crossPoint(input.forward,{{0,0,1}}))>0;
    for(unsigned i:{3u,5u}){
      const float armShield=shield*((i==5)==opponentRight?1.f:.1f);
      const float counterbalance=bounded(length(sway)*.75f,0,.20f);
      target[i]=normalized(productRotation(exponential({{-.4f*length(sway),-filteredTurn*.012f+(i==5?armShield+counterbalance:-armShield-counterbalance),0}}),target[i]));
    }
  }
  local=target;forwardKinematics();
  local[2]=normalized(productRotation(inverseRotation(world[1]),head));forwardKinematics();
  for(unsigned ankle:{9u,12u})if(length(reachOffsets[ankle])>1e-6f)
    solveLeg(ankle-2,addPoint(positions[ankle],reachOffsets[ankle]));
  {
    Vec upperReach=rotatePoint(inverseRotation(world[0]),capped(addPoint(reachOffsets[1],reachOffsets[2]),.03f));
    const Vec bend=capped(crossPoint({{0,0,1}},scalePoint(upperReach,1/.45f)),.10f);
    local[1]=normalized(productRotation(exponential(bend),local[1]));
    forwardKinematics();
  }
  if(physicalUpperValid && !input.action && !input.upperReception){
    for(unsigned i=1;i<=6;++i){
      const Vec error=capped(logarithm(productRotation(physicalUpper[i],inverseRotation(local[i]))),i==1?.22f:.55f);
      local[i]=normalized(productRotation(exponential(scalePoint(error,.65f)),local[i]));
    }
    forwardKinematics();
  }
  if(input.handTargetActive && !input.upperReception && !input.action){
    const unsigned shoulder=length(subtractPoint(input.handTarget,positions[3]))<length(subtractPoint(input.handTarget,positions[5]))?3:5;
    reachHand(shoulder,input.handTarget,protection);
  }
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
  const Vec direction=unit(subtractPoint(target,positions[shoulder]));
  const float distance=bounded(length(subtractPoint(target,positions[shoulder])),std::fabs(a-b)+.01f,a+b-.006f);
  target=addPoint(positions[shoulder],scalePoint(direction,distance));
  const Vec outward=rotatePoint(world[1],{{shoulder==3?1.f:-1.f,0,.1f}});
  const Vec pole=unit(subtractPoint(outward,scalePoint(direction,dotPoint(outward,direction))));
  const float along=(a*a-b*b+distance*distance)/(2*distance);
  const Vec bend=addPoint(addPoint(positions[shoulder],scalePoint(direction,along)),scalePoint(pole,std::sqrt(std::max(0.f,a*a-along*along))));
  const Quat arm=normalized(productRotation(pes3::swingRotation(unit(upper),unit(subtractPoint(bend,positions[shoulder]))),world[shoulder]));
  const Quat forearm=normalized(productRotation(pes3::swingRotation(unit(lower),unit(subtractPoint(target,bend))),world[elbow]));
  local[shoulder]=blended(local[shoulder],normalized(productRotation(inverseRotation(world[1]),arm)),weight);
  local[elbow]=blended(local[elbow],normalized(productRotation(inverseRotation(arm),forearm)),weight);
  forwardKinematics();
}

void PhysicalRig::separateArms(){
  // A small analytic collision pass also protects the displayed, smoothed
  // skeleton. Bullet's proxies alone do not constrain the final blended pose.
  // Only shoulder swing changes; bone lengths and the native elbow bend stay.
  for(unsigned shoulder:{3u,5u})for(unsigned iteration=0;iteration<14;++iteration){
    const unsigned elbow=shoulder+1;
    const Vec hand=addPoint(positions[elbow],rotatePoint(world[elbow],{{0,0,-.24f*scale}}));
    Vec correction{{0,0,0}},contact=hand;
    for(unsigned sample=0;sample<=6;++sample){
      const Vec point=addPoint(positions[elbow],scalePoint(subtractPoint(hand,positions[elbow]),sample/6.f));
      const Vec localPoint=rotatePoint(inverseRotation(world[1]),subtractPoint(point,positions[1]));
      if(localPoint[2]<-.10f*scale || localPoint[2]>.45f*scale)continue;
      // Elliptical torso with allowance for the arm radius and shirt.
      const float rx=.185f*scale,ry=.135f*scale;
      const float ellipse=std::sqrt(localPoint[0]*localPoint[0]/(rx*rx)+localPoint[1]*localPoint[1]/(ry*ry));
      if(ellipse>=1)continue;
      const float side=shoulder==3?1.f:-1.f;
      const float boundary=side*rx*std::sqrt(std::max(0.f,1-localPoint[1]*localPoint[1]/(ry*ry)));
      const Vec displacement=rotatePoint(world[1],{{side*std::max(0.f,side*(boundary-localPoint[0]))+.002f*side,0,0}});
      if(length(displacement)>length(correction)){correction=displacement;contact=point;}
    }
    if(length(correction)<.0001f)break;
    const Vec arm=subtractPoint(contact,positions[shoulder]);
    const Quat swing=pes3::swingRotation(unit(arm),unit(addPoint(arm,capped(correction,.045f))));
    local[shoulder]=normalized(productRotation(productRotation(inverseRotation(world[1]),swing),world[shoulder]));
    forwardKinematics();
  }
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
