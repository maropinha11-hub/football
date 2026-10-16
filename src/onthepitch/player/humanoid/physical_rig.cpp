#include "physical_rig.hpp"

namespace football_physics {
namespace {
// Segment fractions use de Leva's male reference. Splitting the trunk into
// pelvis/spine and combining forearm+hand are explicit game approximations.
constexpr float fractions[13]={.12f,.3146f,.0694f,.0271f,.0223f,.0271f,.0223f,.1416f,.0433f,.0137f,.1416f,.0433f,.0137f};
constexpr float radii[13]={.135f,.145f,.10f,.055f,.045f,.055f,.045f,.075f,.055f,.045f,.075f,.055f,.045f};
Vec tip(unsigned i){if(i==2)return {{0,0,.17f}};if(i==4||i==6)return {{0,0,-.27f}};if(i==9||i==12)return {{0,-.16f,-.02f}};return {{0,0,0}};}
}

void PhysicalRig::configure(const pes3::NativeBind &bind,float heightScale){reference=bind;scale=bounded(heightScale,.7f,1.3f);reset();}
void PhysicalRig::reset(){ready=false;state=Mode::Active;stateAge=settled=filteredTurn=unstableTime=0;pendingImpulse=pendingTorque=reachOffset=sway=swayVelocity=filteredAcceleration=previousVelocity={{0,0,0}};angularVelocity={};debug={};}
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

void PhysicalRig::jointLimits(unsigned i){
  Vec v=logarithm(local[i]);
  if(i==8||i==11){v[0]=bounded(v[0],0,2.7f);v[1]=bounded(v[1],-.10f,.10f);v[2]=bounded(v[2],-.10f,.10f);}
  else if(i==4||i==6){v[0]=bounded(v[0],-2.65f,.06f);v[1]=bounded(v[1],-.15f,.15f);v[2]=bounded(v[2],-.15f,.15f);}
  else if(i==9||i==12){v[0]=bounded(v[0],-.85f,.85f);v[1]=bounded(v[1],-.35f,.35f);v[2]=bounded(v[2],-.4f,.4f);}
  else if(i==1){v=capped(v,.85f);}
  else if(i==2){v=capped(v,1.3f);}
  else if(i==7||i==10){v[0]=bounded(v[0],-2.2f,.65f);v[1]=bounded(v[1],-.8f,.8f);v[2]=bounded(v[2],-.8f,.8f);}
  else v=capped(v,2.8f);
  local[i]=exponential(v);
}

void PhysicalRig::drive(const Pose &target,float dt,float frequency,float accelerationLimit){
  const float kp=frequency*frequency,kd=2*frequency;
  for(unsigned i=0;i<13;++i){
    Vec error=logarithm(productRotation(target[i],inverseRotation(local[i])));
    // Backward-Euler PD denominator damps high gains at fixed 200 Hz.
    Vec acceleration=scalePoint(subtractPoint(scalePoint(error,kp),scalePoint(angularVelocity[i],kd+dt*kp)),1/(1+dt*kd+dt*dt*kp));
    angularVelocity[i]=capped(addPoint(angularVelocity[i],scalePoint(capped(acceleration,accelerationLimit),dt)),12);
    local[i]=normalized(productRotation(exponential(scalePoint(angularVelocity[i],dt)),local[i]));
  }
}

void PhysicalRig::ground(float dt){
  // Unilateral compliant contacts for articulated capsules. FK enforces exact
  // bone lengths; this XPBD projection acts on the root generalized body.
  std::array<float,26> lambdas{};
  constexpr float inverseMass=1/mass,inverseInertia=1/8.f;
  for(unsigned iteration=0;iteration<8;++iteration){
    forwardKinematics();
    for(unsigned c=0;c<26;++c){
      const unsigned i=c/2;
      const Vec point=c%2?addPoint(positions[i],rotatePoint(world[i],scalePoint(tip(i),scale))):positions[i];
      const float constraint=point[2]-radii[i]*scale;
      if(constraint>=0)continue;
      const Vec lever=subtractPoint(point,root),angularGradient=crossPoint(lever,{{0,0,1}});
      const float compliance=1e-7f/(dt*dt);
      const float delta=(-constraint-compliance*lambdas[c])/(inverseMass+inverseInertia*dotPoint(angularGradient,angularGradient)+compliance);
      const float next=std::max(0.f,lambdas[c]+delta),change=next-lambdas[c];lambdas[c]=next;
      root[2]+=change*inverseMass;
      local[0]=normalized(productRotation(exponential(capped(scalePoint(angularGradient,change*inverseInertia),.06f)),local[0]));
      ++debug.groundContacts;
    }
  }
  forwardKinematics();
  // Conservative final separation makes the proxy contact tolerance explicit.
  float penetration=0;
  for(unsigned i=0;i<13;++i){
    const Vec end=addPoint(positions[i],rotatePoint(world[i],scalePoint(tip(i),scale)));
    penetration=std::max(penetration,radii[i]*scale-std::min(positions[i][2],end[2]));
  }
  root[2]+=std::max(0.f,penetration);
  if(debug.groundContacts){
    rootVelocity[2]=std::max(0.f,rootVelocity[2])*.05f;
    const float drag=std::exp(-6.f*dt);rootVelocity[0]*=drag;rootVelocity[1]*=drag;
    for(auto &v:angularVelocity)v=scalePoint(v,std::exp(-4.f*dt));
  }
  forwardKinematics();debug.penetration=std::max(0.f,penetration);
}

void PhysicalRig::step(const Input &input,float dt){
  dt=bounded(dt,.001f,.02f);
  if(!ready){local=input.pose;root=input.pelvis;previousVelocity=input.velocity;lastForward=input.forward;ready=true;forwardKinematics();}
  debug={};
  const float impulseSize=length(pendingImpulse);
  if(impulseSize>0){
    swayVelocity=addPoint(swayVelocity,scalePoint(pendingTorque,1/9.f));
    if(state==Mode::Active && impulseSize>=145){state=Mode::Falling;stateAge=settled=0;rootVelocity=addPoint(input.velocity,scalePoint(pendingImpulse,1/mass));angularVelocity[0]=addPoint(angularVelocity[0],scalePoint(pendingTorque,1/8.f));}
    else if(state!=Mode::Active){rootVelocity=addPoint(rootVelocity,scalePoint(pendingImpulse,1/mass));angularVelocity[0]=addPoint(angularVelocity[0],scalePoint(pendingTorque,1/8.f));}
    pendingImpulse=pendingTorque={{0,0,0}};
  }
  stateAge+=dt;
  Vec acceleration=scalePoint(subtractPoint(input.velocity,previousVelocity),1/dt);
  filteredAcceleration=addPoint(filteredAcceleration,scalePoint(subtractPoint(capped(acceleration,14),filteredAcceleration),1-std::exp(-8*dt)));
  const float turn=std::atan2(crossPoint(lastForward,input.forward)[2],bounded(dotPoint(lastForward,input.forward),-1,1))/dt;
  filteredTurn+=(bounded(turn,-7,7)-filteredTurn)*(1-std::exp(-7*dt));
  previousVelocity=input.velocity;lastForward=input.forward;
  debug.turnRate=filteredTurn;debug.effort=bounded(length(filteredAcceleration)/12+std::fabs(filteredTurn)*length(input.velocity)/55,0,1);
  const float lateralDemand=std::fabs(dotPoint(filteredAcceleration,unit(crossPoint(input.forward,{{0,0,1}}))));
  const bool unsafeCut=!input.action && !input.upperReception && length(input.velocity)>5.8f && std::fabs(filteredTurn)>3.2f && lateralDemand>6.5f;
  unstableTime=unsafeCut?unstableTime+dt:std::max(0.f,unstableTime-2*dt);
  if(state==Mode::Active && unstableTime>.20f){
    state=Mode::Falling;stateAge=settled=0;rootVelocity=input.velocity;
    angularVelocity[0]=scalePoint(unit(crossPoint({{0,0,1}},filteredAcceleration)),2.8f);
  }
  for(unsigned sub=0;sub<2;++sub){
    const float h=dt*.5f;
    if(state==Mode::Active){
      // Lean follows resultant acceleration; turns counter-rotate torso and
      // arms. A critically damped inertial response preserves cadence.
      swayVelocity=addPoint(swayVelocity,scalePoint(subtractPoint(scalePoint(sway,-90),scalePoint(swayVelocity,19)),h));
      sway=addPoint(sway,scalePoint(swayVelocity,h));sway=capped(sway,.35f);
      const Vec wanted=capped(scalePoint(input.reach,input.reachWeight),.14f);
      reachOffset=addPoint(reachOffset,capped(subtractPoint(wanted,reachOffset),.55f*h));
      evaluate(input);
    }else if(state==Mode::Falling){
      rootVelocity[2]-=9.81f*h;root=addPoint(root,scalePoint(rootVelocity,h));
      forwardKinematics();
      for(unsigned i=1;i<13;++i){
        const Vec segment=(i==4||i==6||i==2||i==9||i==12)?tip(i):Vec{{0,0,-.20f}};
        const Vec force=rotatePoint(inverseRotation(world[i]),{{0,0,-9.81f*mass*fractions[i]}});
        const Vec torque=crossPoint(scalePoint(segment,.45f*scale),force);
        const float inertia=std::max(.04f,mass*fractions[i]*dotPoint(segment,segment)/3);
        angularVelocity[i]=capped(addPoint(angularVelocity[i],scalePoint(torque,h/inertia)),7);
      }
      for(unsigned i=0;i<13;++i){local[i]=normalized(productRotation(exponential(scalePoint(angularVelocity[i],h)),local[i]));if(i)jointLimits(i);}
      ground(h);
      if(stateAge>1.2f && length(rootVelocity)<.25f)settled+=h;else settled=0;
      if(settled>.45f || stateAge>3.6f){state=Mode::Recovering;stateAge=0;recoveryStart=root;angularVelocity={};}
    }else{
      const float blend=smooth(stateAge/1.65f);
      root=addPoint(scalePoint(recoveryStart,1-blend),scalePoint(input.pelvis,blend));
      drive(input.pose,h,16,90);ground(h);
      if(stateAge>=1.65f){state=Mode::Active;stateAge=0;local=input.pose;root=input.pelvis;reachOffset=sway=swayVelocity={{0,0,0}};angularVelocity={};}
    }
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
  leanAxis=capped(addPoint(scalePoint(leanAxis,.28f),sway),.24f);
  const float actionBias=input.upperReception || input.action?0.f:1.f;
  leanAxis=scalePoint(leanAxis,actionBias);
  Pose target=input.pose;
  target[0]=normalized(productRotation(exponential(scalePoint(leanAxis,.35f)),target[0]));
  target[1]=normalized(productRotation(exponential({{0,0,-filteredTurn*.025f*actionBias}}),target[1]));
  if(!input.upperReception){
    const Vec localLean=rotatePoint(inverseRotation(world[0]),scalePoint(leanAxis,.65f));
    target[1]=normalized(productRotation(exponential(localLean),target[1]));
    const float shield=input.opponentDistance<1.5f?(.30f*(1-input.opponentDistance/1.5f)):0;
    const bool opponentRight=dotPoint(input.opponent,crossPoint(input.forward,{{0,0,1}}))>0;
    for(unsigned i:{3u,5u}){
      const float armShield=shield*((i==5)==opponentRight?1.f:.2f);
      target[i]=normalized(productRotation(exponential({{-.05f*debug.effort,-filteredTurn*.025f+(i==5?armShield:-armShield),0}}),target[i]));
    }
  }
  // Integrate only the additive response, rather than delaying the source
  // animation. This keeps authored kick speed and foot strike phase intact.
  local=target;forwardKinematics();
  // An unchanged source pose needs no stance projection. Projecting a
  // straight authored leg can otherwise shorten its strike by millimetres.
  if(length(leanAxis)>1e-6f){solveLeg(7,left);solveLeg(10,right);}
  if(input.reachBone==9||input.reachBone==12){
    const unsigned ankle=unsigned(input.reachBone);solveLeg(ankle-2,addPoint(positions[ankle],reachOffset));
  }else if(input.reachBone==1 || input.reachBone==2){
    Vec upperReach=rotatePoint(inverseRotation(world[0]),capped(reachOffset,.045f));
    const Vec bend=capped(crossPoint({{0,0,1}},scalePoint(upperReach,1/.45f)),.10f);
    local[1]=normalized(productRotation(exponential(bend),local[1]));
    forwardKinematics();
  }
  debug.lean=length(leanAxis);debug.reach=length(reachOffset);
}
}
