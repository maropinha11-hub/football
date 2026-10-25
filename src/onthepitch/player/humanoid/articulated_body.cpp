#include "articulated_body.hpp"
#include "learned_muscle_policy.hpp"
#include <btBulletDynamicsCommon.h>
#include <BulletDynamics/ConstraintSolver/btGeneric6DofSpring2Constraint.h>
#include <vector>

namespace football_physics {
namespace {
btVector3 bv(Vec p){return {p[0],p[1],p[2]};}
Vec vec(const btVector3 &p){return {{float(p.x()),float(p.y()),float(p.z())}};}
btQuaternion bq(Quat q){return {q[0],q[1],q[2],q[3]};}
Quat quat(btQuaternion q){return normalized({{float(q.x()),float(q.y()),float(q.z()),float(q.w())}});}
constexpr float fraction[13]={.12f,.3146f,.0694f,.0271f,.0223f,.0271f,.0223f,.1416f,.0433f,.0137f,.1416f,.0433f,.0137f};
constexpr float radius[13]={.11f,.105f,.085f,.045f,.038f,.045f,.038f,.062f,.046f,.043f,.062f,.046f,.043f};
Vec segment(const pes3::NativeBind &bind,unsigned i){
  if(i==0)return {{.19f,0,0}};
  if(i==1)return bind.offsets[2];
  if(i==2)return {{0,0,.15f}};
  if(i==4||i==6)return {{0,0,-.25f}};
  if(i==9||i==12)return {{0,-.17f,-.01f}};
  return bind.offsets[i+1];
}
}
struct ArticulatedBody::World {
  btDefaultCollisionConfiguration configuration;
  btCollisionDispatcher dispatcher{&configuration};
  btDbvtBroadphase broadphase;
  btSequentialImpulseConstraintSolver solver;
  btDiscreteDynamicsWorld dynamics{&dispatcher,&broadphase,&solver,&configuration};
  std::vector<std::unique_ptr<btCollisionShape>> shapes;
  std::vector<std::unique_ptr<btRigidBody>> bodies;
  std::vector<std::unique_ptr<btGeneric6DofSpring2Constraint>> joints;
  std::array<btVector3,13> centers;
  Pose muscleTarget{};
  Pose previousReference{};
  std::array<Vec,13> previousReferenceVelocity{};
  bool referenceReady=false;
  Vec carrierPelvis{{0,0,0}};
  float age=0;
  bool tracking=false;
  World(){
    dynamics.setGravity(btVector3(0,0,-9.81f));
    dynamics.getSolverInfo().m_numIterations=40;
    dynamics.getSolverInfo().m_splitImpulse=true;
    dynamics.getSolverInfo().m_splitImpulsePenetrationThreshold=-.02f;
    dynamics.getSolverInfo().m_erp=.2f;
    shapes.emplace_back(new btStaticPlaneShape(btVector3(0,0,1),0));
    btRigidBody::btRigidBodyConstructionInfo info(0,nullptr,shapes.back().get());
    bodies.emplace_back(new btRigidBody(info));bodies.back()->setFriction(.8f);
    dynamics.addRigidBody(bodies.back().get());
  }
  ~World(){for(auto &j:joints)dynamics.removeConstraint(j.get());for(auto &b:bodies)dynamics.removeRigidBody(b.get());}
};
ArticulatedBody::ArticulatedBody()=default;
ArticulatedBody::~ArticulatedBody()=default;
void ArticulatedBody::start(const pes3::NativeBind &bind,float scale,const Pose &pose,Vec pelvis,Vec velocity,Vec impulse,Vec lever,bool tracking){
  state.reset(new World);auto &s=*state;
  s.tracking=tracking;s.carrierPelvis=pelvis;
  s.muscleTarget=pose;
  std::array<btTransform,13> frames;
  for(unsigned i=0;i<13;++i){
    int parent=pes3::nativeParents[i];
    frames[i]=parent<0?btTransform(bq(pose[i]),bv(pelvis)):
      frames[parent]*btTransform(bq(pose[i]),bv(scalePoint(bind.offsets[i],scale)));
    const Vec axis=scalePoint(segment(bind,i),scale);
    s.centers[i]=i==0?btVector3(0,0,.025f):bv(scalePoint(axis,.5f));
    s.shapes.emplace_back(new btCapsuleShape(radius[i]*scale,std::max(.01f,length(axis)-2*radius[i]*scale)));
    auto *capsule=s.shapes.back().get();
    s.shapes.emplace_back(new btCompoundShape);
    auto *compound=static_cast<btCompoundShape*>(s.shapes.back().get());
    btTransform local(btQuaternion::getIdentity(),btVector3(0,0,0));
    local.setRotation(shortestArcQuat(btVector3(0,1,0),bv(unit(axis))));
    compound->addChildShape(local,capsule);
    btVector3 inertia;const float mass=PhysicalRig::mass*fraction[i];compound->calculateLocalInertia(mass,inertia);
    btRigidBody::btRigidBodyConstructionInfo info(mass,nullptr,compound,inertia);
    info.m_linearDamping=.12f;info.m_angularDamping=.65f;info.m_friction=.8f;info.m_restitution=0;
    s.bodies.emplace_back(new btRigidBody(info));auto &body=*s.bodies.back();
    body.setCenterOfMassTransform(frames[i]*btTransform(btQuaternion::getIdentity(),s.centers[i]));
    body.setLinearVelocity(bv(velocity));body.setSleepingThresholds(.12f,.16f);
    body.setCcdMotionThreshold(.05f);body.setCcdSweptSphereRadius(radius[i]*scale*.7f);
    s.dynamics.addRigidBody(&body);
    if(parent>=0){
      btTransform a(btQuaternion::getIdentity(),bv(scalePoint(bind.offsets[i],scale))-s.centers[parent]);
      btTransform b(btQuaternion::getIdentity(),-s.centers[i]);
      s.joints.emplace_back(new btGeneric6DofSpring2Constraint(*s.bodies[parent+1],body,a,b));
      auto &joint=*s.joints.back();joint.setLinearLowerLimit(btVector3(0,0,0));joint.setLinearUpperLimit(btVector3(0,0,0));
      for(unsigned axis=0;axis<3;++axis)joint.setParam(BT_CONSTRAINT_STOP_ERP,.35f,axis);
      btVector3 lo(-.8f,-.7f,-.7f),hi(.8f,.7f,.7f);
      if(i==7||i==10){lo=btVector3(-.9f,-.7f,-.7f);hi=btVector3(1.9f,.7f,.7f);}
      if(i==8||i==11){lo=btVector3(-2.65f,-.04f,-.04f);hi=btVector3(.03f,.04f,.04f);}
      if(i==4||i==6){lo=btVector3(-.04f,-.10f,-.1f);hi=btVector3(2.65f,.10f,.1f);}
      if(i==3||i==5){lo=btVector3(-2.3f,-1.5f,-1.9f);hi=btVector3(2.3f,1.5f,1.9f);}
      if(i==2){lo=btVector3(-.95f,-.6f,-1.55f);hi=btVector3(.95f,.6f,1.55f);}
      joint.setAngularLowerLimit(lo);joint.setAngularUpperLimit(hi);
      for(unsigned axisIndex=3;axisIndex<6;++axisIndex){
        joint.enableSpring(axisIndex,true);joint.setStiffness(axisIndex,i==1?18.f:3.f);
        joint.setDamping(axisIndex,.8f);joint.setEquilibriumPoint(axisIndex,0);
      }
      s.dynamics.addConstraint(&joint,true);
      // The torso and the shoulder's parent overlap at their attachment.
      // Disable only the immediate grandparent pair, not general self-contact.
      int grand=pes3::nativeParents[parent];
      if(grand>=0 && i!=4 && i!=6)body.setIgnoreCollisionCheck(s.bodies[grand+1].get(),true);
    }
  }
  // Start without a deeply embedded foot proxy. This correction is bounded
  // by the native pose, applied once, before impulses or integration.
  float lift=0;
  for(unsigned i=0;i<13;++i){btVector3 lo,hi;s.bodies[i+1]->getAabb(lo,hi);lift=std::max(lift,float(-lo.z()+.002f));}
  if(tracking)lift=0;
  for(unsigned i=0;i<13;++i){auto t=s.bodies[i+1]->getWorldTransform();t.getOrigin().setZ(t.getOrigin().z()+lift);s.bodies[i+1]->setCenterOfMassTransform(t);}
  btVector3 center(0,0,0);for(unsigned i=0;i<13;++i)center+=s.bodies[i+1]->getCenterOfMassPosition()*fraction[i];
  btMatrix3x3 inertia;inertia.setZero();
  for(unsigned i=0;i<13;++i){auto &b=*s.bodies[i+1];btVector3 r=b.getCenterOfMassPosition()-center;
    btMatrix3x3 own=b.getInvInertiaTensorWorld().inverse();
    for(unsigned row=0;row<3;++row)for(unsigned col=0;col<3;++col)inertia[row][col]+=own[row][col]+PhysicalRig::mass*fraction[i]*((row==col?r.length2():0)-r[row]*r[col]);
  }
  const btVector3 angular=inertia.inverse()*bv(crossPoint(lever,impulse));
  for(unsigned i=0;i<13;++i){auto &body=*s.bodies[i+1];
    body.setLinearVelocity(bv(velocity)+bv(scalePoint(impulse,1/PhysicalRig::mass))+angular.cross(body.getCenterOfMassPosition()-center));
    body.setAngularVelocity(angular);body.activate();
    if(tracking && (i==0 || i==9 || i==12)){
      body.setMassProps(0,btVector3(0,0,0));
      body.setCollisionFlags(body.getCollisionFlags()|btCollisionObject::CF_KINEMATIC_OBJECT);
      body.setActivationState(DISABLE_DEACTIVATION);
    }
  }
}
void ArticulatedBody::impulse(Vec value,Vec lever){
  if(!state||state->bodies.size()<3)return;
  state->bodies[2]->activate(true);state->bodies[2]->applyImpulse(bv(capped(value,80.f)),bv(capped(lever,.8f)));
}
void ArticulatedBody::track(const pes3::NativeBind &bind,float scale,const Pose &target,Vec pelvis,float dt,Vec impulse,Pose &output,Metrics &metrics){
  if(!state || !state->tracking)start(bind,scale,target,pelvis,{{0,0,0}},{{0,0,0}},{{0,0,0}},true);
  auto &s=*state;
  // Simulate joint dynamics in the translating native carrier frame. If
  // only the kinematic pelvis/shoes are transported, Bullet integrates the
  // dynamic links another half-tick beyond them at sprint speed. Transport
  // every segment and its interpolation transform by the same translation;
  // retain relative velocities, actual joint torques, gravity and contacts.
  // A free fall starts a new world with the actual global player velocity.
  const btVector3 transport(pelvis[0]-s.carrierPelvis[0],pelvis[1]-s.carrierPelvis[1],0);
  for(unsigned i=0;i<13;++i){auto &body=*s.bodies[i+1];
    auto t=body.getWorldTransform(),old=body.getInterpolationWorldTransform();
    t.getOrigin()+=transport;old.getOrigin()+=transport;
    body.setCenterOfMassTransform(t);body.setInterpolationWorldTransform(old);
  }
  s.carrierPelvis=pelvis;
  std::array<btTransform,13> desired,previous;
  std::array<Vec,13> referenceVelocity{},referenceAcceleration{};
  for(unsigned i=0;i<13;++i){int parent=pes3::nativeParents[i];
    desired[i]=parent<0?btTransform(bq(target[i]),bv(pelvis)):
      desired[parent]*btTransform(bq(target[i]),bv(scalePoint(bind.offsets[i],scale)));
    auto &body=*s.bodies[i+1];
    previous[i]=body.getWorldTransform();
    const Quat reference=quat(desired[i].getRotation());
    if(s.referenceReady){
      referenceVelocity[i]=capped(scalePoint(logarithm(productRotation(reference,inverseRotation(s.previousReference[i]))),1/dt),8.f);
      referenceAcceleration[i]=capped(scalePoint(subtractPoint(referenceVelocity[i],s.previousReferenceVelocity[i]),1/dt),45.f);
    }
    s.previousReference[i]=reference;s.previousReferenceVelocity[i]=referenceVelocity[i];
  }
  s.referenceReady=true;
  // Quiet active tracking needs fewer constraint iterations than an impact
  // or a free fall. Keep the same 100 Hz tick and both physics substeps.
  s.dynamics.getSolverInfo().m_numIterations=(length(impulse)>.01f||metrics.balanceRisk>.15f)?24:12;
  if(length(impulse)>0)s.bodies[2]->applyImpulse(bv(scalePoint(impulse,.35f)),btVector3(0,0,.12f));
  for(unsigned sub=0;sub<2;++sub){
    for(unsigned i=0;i<13;++i)if(i==0 || i==9 || i==12){
      auto &body=*s.bodies[i+1];const auto final=desired[i]*btTransform(btQuaternion::getIdentity(),s.centers[i]);
      const float t=(sub+1)*.5f;
      const btTransform next(previous[i].getRotation().slerp(final.getRotation(),t),previous[i].getOrigin().lerp(final.getOrigin(),t));
      // Bullet infers kinematic velocity from this pair over the substep.
      // A full-tick displacement before the first half-step doubled that
      // velocity, then set it to zero on the second half of every tick.
      body.setInterpolationWorldTransform(body.getWorldTransform());
      body.setWorldTransform(next);body.activate();
    }
    for(unsigned i=1;i<13;++i){
      if(i==9 || i==12)continue;
      auto &body=*s.bodies[i+1];const int parent=pes3::nativeParents[i];
      auto &base=*s.bodies[parent+1];
      // Muscles control a joint relative to its parent. A world-space servo
      // fights the reference's own pelvis/trunk turn and arrests arm swing.
      const btQuaternion targetOrientation=base.getWorldTransform().getRotation()*bq(target[i]);
      const Vec error=logarithm(quat(targetOrientation*body.getWorldTransform().getRotation().inverse()));
      const Vec wantedVelocity=subtractPoint(referenceVelocity[i],referenceVelocity[parent]);
      const Vec relative=subtractPoint(wantedVelocity,vec(body.getAngularVelocity()-base.getAngularVelocity()));
      Vec wanted;
      for(unsigned axis=0;axis<3;++axis){
        const float feed=referenceAcceleration[i][axis]-referenceAcceleration[parent][axis];
        // Implicit local damping bounds a changing target without freezing
        // authored motion. Lower limbs now exchange actual internal torques.
        wanted[axis]=(football_muscle::acceleration(error[axis],relative[axis])+feed)/(1.f+18.f*dt*.5f);
      }
      const Vec acceleration=capped(wanted,140.f);
      metrics.motorError=std::max(metrics.motorError,length(error));
      metrics.motorAcceleration=std::max(metrics.motorAcceleration,length(acceleration));++metrics.neuralMotorSamples;
      const btVector3 torque=body.getInvInertiaTensorWorld().inverse()*bv(acceleration);
      const Vec muscle=capped(vec(torque),i==1?110.f:i>=7?90.f:18.f);
      body.applyTorque(bv(muscle));base.applyTorque(-bv(muscle));body.activate();base.activate();
    }
    Vec unused;step(dt*.5f,output,unused,metrics);
  }
}
void ArticulatedBody::step(float dt,Pose &pose,Vec &pelvis,Metrics &metrics){
  auto &s=*state;
  if(!s.tracking){
    s.age+=dt;
    // Retain joint muscle tone during a fall. These are internal equal and
    // opposite torques: they cannot lift or suspend the complete body.
    const float height=s.bodies[1]->getCenterOfMassPosition().z();
    const float tone=.20f+.80f*std::exp(-s.age/1.3f);
    Pose targets=s.muscleTarget;
    const float tuck=smooth((.85f-height)/.55f);
    for(unsigned i:{8u,11u})targets[i]=blended(targets[i],exponential({{.85f,0,0}}),tuck*.65f);
    for(unsigned i:{4u,6u})targets[i]=blended(targets[i],exponential({{-.95f,0,0}}),.35f+.35f*tuck);
    // Arms extend toward the impending ground contact, while elbows retain
    // flexion to absorb it. The shoulder and its parent receive opposite work.
    const Vec velocity=vec(s.bodies[1]->getLinearVelocity());
    const Quat trunk=quat(s.bodies[2]->getWorldTransform().getRotation());
    if(height>.24f && (velocity[2]<-.15f || (height<.85f&&dotPoint(velocity,velocity)>1.5f))){
      for(unsigned i:{3u,5u}){
        const Vec side=rotatePoint(trunk,{{i==3?.20f:-.20f,0,0}});
        const Vec direction=unit({{velocity[0]*.28f+side[0],velocity[1]*.28f+side[1],-1.f}});
        const Quat desired=normalized(productRotation(pes3::swingRotation(rotatePoint(trunk,{{0,0,-1}}),direction),trunk));
        targets[i]=blended(targets[i],normalized(productRotation(inverseRotation(trunk),desired)),.7f);
      }
      metrics.brace=1;
    }
    for(unsigned i=1;i<13;++i){
      const int parent=pes3::nativeParents[i];auto &child=*s.bodies[i+1];auto &base=*s.bodies[parent+1];
      const btQuaternion wanted=base.getWorldTransform().getRotation()*bq(targets[i]);
      const Vec error=logarithm(quat(wanted*child.getWorldTransform().getRotation().inverse()));
      const Vec relative=vec(child.getAngularVelocity()-base.getAngularVelocity());
      const float stiffness=i<=2?30.f:i>=7?22.f:12.f;
      const float limit=(i<=2?32.f:i>=7?26.f:9.f)*tone;
      Vec muscle=subtractPoint(scalePoint(error,stiffness*tone),scalePoint(relative,2.f*std::sqrt(tone)));
      if(i<=6){
        Vec acceleration;for(unsigned axis=0;axis<3;++axis)acceleration[axis]=football_muscle::acceleration(error[axis],-relative[axis]);
        muscle=scalePoint(vec(child.getInvInertiaTensorWorld().inverse()*bv(acceleration)),tone);
        metrics.motorError=std::max(metrics.motorError,length(error));++metrics.neuralMotorSamples;
      }
      const Vec torque=capped(muscle,limit);
      child.applyTorque(bv(torque));base.applyTorque(-bv(torque));
      child.activate();base.activate();metrics.muscleEffort+=length(torque)*dt;
    }
    // Supported ankles can exchange an upright correction with the pelvis
    // only while an actual floor manifold still carries a foot.
    std::vector<unsigned> supports;
    for(int m=0;m<s.dispatcher.getNumManifolds();++m){auto *manifold=s.dispatcher.getManifoldByIndexInternal(m);
      for(unsigned foot:{9u,12u})if((manifold->getBody0()==s.bodies[0].get() && manifold->getBody1()==s.bodies[foot+1].get()) ||
          (manifold->getBody1()==s.bodies[0].get() && manifold->getBody0()==s.bodies[foot+1].get())){
        for(int c=0;c<manifold->getNumContacts();++c)if(manifold->getContactPoint(c).getDistance()<.003f){supports.push_back(foot);break;}
      }
    }
    if(!supports.empty() && height>.6f && s.age<.65f){
      auto &hips=*s.bodies[1];const Quat q=quat(hips.getWorldTransform().getRotation());
      const Vec error=logarithm(pes3::swingRotation(rotatePoint(q,{{0,0,1}}),{{0,0,1}}));
      const Vec torque=capped(subtractPoint(scalePoint(error,32.f),scalePoint(vec(hips.getAngularVelocity()),4.f)),24.f);
      hips.applyTorque(bv(torque));for(unsigned foot:supports)s.bodies[foot+1]->applyTorque(-bv(scalePoint(torque,1.f/supports.size())));
      metrics.supportTorque=std::max(metrics.supportTorque,length(torque));
    }
  }
  s.dynamics.stepSimulation(dt,0);metrics.kineticEnergy=0;
  for(unsigned i=0;i<13;++i){
    auto &body=*s.bodies[i+1];const auto q=quat(body.getWorldTransform().getRotation());
    // Contact impulses on very light feet/forearms can otherwise create
    // visually implausible spin. This dissipative safety limit adds no energy.
    body.setAngularVelocity(bv(capped(vec(body.getAngularVelocity()),i==0?4.5f:12.f)));
    const int parent=pes3::nativeParents[i];
    pose[i]=parent<0?q:normalized(productRotation(inverseRotation(quat(s.bodies[parent+1]->getWorldTransform().getRotation())),q));
    if(i==0)pelvis=vec(body.getCenterOfMassPosition()-body.getWorldTransform().getBasis()*s.centers[0]);
    metrics.angularSpeed=std::max(metrics.angularSpeed,float(body.getAngularVelocity().length()));
    if(body.getInvMass()>0){
      metrics.kineticEnergy+=.5f/body.getInvMass()*body.getLinearVelocity().length2();
      const auto omega=body.getAngularVelocity();metrics.kineticEnergy+=.5f*omega.dot(body.getInvInertiaTensorWorld().inverse()*omega);
    }
  }
  for(auto &j:s.joints){j->calculateTransforms();metrics.jointError=std::max(metrics.jointError,float((j->getCalculatedTransformA().getOrigin()-j->getCalculatedTransformB().getOrigin()).length()));}
  for(int i=0;i<s.dispatcher.getNumManifolds();++i){auto *m=s.dispatcher.getManifoldByIndexInternal(i);
    const bool floor=m->getBody0()==s.bodies[0].get() || m->getBody1()==s.bodies[0].get();
    for(int p=0;p<m->getNumContacts();++p)if(m->getContactPoint(p).getDistance()<.003f){
      if(floor){++metrics.groundContacts;metrics.penetration=std::max(metrics.penetration,float(-m->getContactPoint(p).getDistance()));}
      else metrics.selfPenetration=std::max(metrics.selfPenetration,float(-m->getContactPoint(p).getDistance()));
    }
  }
}
}
