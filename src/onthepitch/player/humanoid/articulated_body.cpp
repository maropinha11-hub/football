#include "articulated_body.hpp"
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
  s.tracking=tracking;
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
      int grand=pes3::nativeParents[parent];if(grand>=0)body.setIgnoreCollisionCheck(s.bodies[grand+1].get(),true);
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
    if(tracking && (i==0 || i>=7)){
      body.setMassProps(0,btVector3(0,0,0));
      body.setCollisionFlags(body.getCollisionFlags()|btCollisionObject::CF_KINEMATIC_OBJECT);
      body.setActivationState(DISABLE_DEACTIVATION);
    }
  }
}
void ArticulatedBody::track(const pes3::NativeBind &bind,float scale,const Pose &target,Vec pelvis,float dt,Vec impulse,Pose &output,Metrics &metrics){
  if(!state || !state->tracking)start(bind,scale,target,pelvis,{{0,0,0}},{{0,0,0}},{{0,0,0}},true);
  auto &s=*state;std::array<btTransform,13> desired;
  for(unsigned i=0;i<13;++i){int parent=pes3::nativeParents[i];
    desired[i]=parent<0?btTransform(bq(target[i]),bv(pelvis)):
      desired[parent]*btTransform(bq(target[i]),bv(scalePoint(bind.offsets[i],scale)));
    auto &body=*s.bodies[i+1];
    if(i==0||i>=7){
      auto before=body.getWorldTransform();auto next=desired[i]*btTransform(btQuaternion::getIdentity(),s.centers[i]);
      body.setWorldTransform(next);body.setInterpolationWorldTransform(before);body.activate();
    }
  }
  if(length(impulse)>0)s.bodies[2]->applyImpulse(bv(scalePoint(impulse,.35f)),btVector3(0,0,.12f));
  for(unsigned sub=0;sub<2;++sub){
    for(unsigned i=1;i<=6;++i){auto &body=*s.bodies[i+1];
      const Vec error=logarithm(quat(desired[i].getRotation()*body.getWorldTransform().getRotation().inverse()));
      const Vec acceleration=capped(subtractPoint(scalePoint(error,625.f),scalePoint(vec(body.getAngularVelocity()),50.f)),140.f);
      const btVector3 torque=body.getInvInertiaTensorWorld().inverse()*bv(acceleration);
      body.applyTorque(bv(capped(vec(torque),i==1?90.f:12.f)));body.activate();
    }
    Vec unused;step(dt*.5f,output,unused,metrics);
  }
}
void ArticulatedBody::step(float dt,Pose &pose,Vec &pelvis,Metrics &metrics){
  auto &s=*state;s.dynamics.stepSimulation(dt,0);metrics.kineticEnergy=0;
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
    for(int p=0;p<m->getNumContacts();++p)if(m->getContactPoint(p).getDistance()<.003f){++metrics.groundContacts;metrics.penetration=std::max(metrics.penetration,float(-m->getContactPoint(p).getDistance()));}
  }
}
}
