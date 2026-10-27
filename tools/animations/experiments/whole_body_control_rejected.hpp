#pragma once
#include "onthepitch/player/humanoid/physical_rig.hpp"

namespace football_physics {
namespace whole_body {
constexpr unsigned dofs=42;
constexpr unsigned capacity=96;
using Row=std::array<double,capacity>;
using Matrix=std::array<Row,capacity>;
struct Link {Vec position{},origin{},velocity{},omega{};Quat rotation{{0,0,0,1}};float mass=0;std::array<Vec,3> inertia{};};
struct Result {std::array<Vec,13> torque{};Row acceleration{};float requestedTorque=0,supportResidual=0,maximumTorque=0;bool finite=true;};
struct Model {Matrix mass{};Row bias{};};
inline bool solve(Matrix a,Row b,unsigned n,Row &x){
  for(unsigned k=0;k<n;++k){unsigned pivot=k;for(unsigned i=k+1;i<n;++i)if(std::fabs(a[i][k])>std::fabs(a[pivot][k]))pivot=i;
    if(std::fabs(a[pivot][k])<1e-10)return false;
    std::swap(a[k],a[pivot]);std::swap(b[k],b[pivot]);
    for(unsigned i=k+1;i<n;++i){const double f=a[i][k]/a[k][k];
      for(unsigned j=k+1;j<n;++j)a[i][j]-=f*a[k][j];b[i]-=f*b[k];}
  }
  x={};for(int i=int(n)-1;i>=0;--i){double v=b[i];for(unsigned j=i+1;j<n;++j)v-=a[i][j]*x[j];x[i]=v/a[i][i];}
  return true;
}
inline Vec basis(unsigned axis){Vec result{{0,0,0}};result[axis]=1;return result;}
inline Vec inertia(const Link &b,Vec v){return {{dotPoint(b.inertia[0],v),dotPoint(b.inertia[1],v),dotPoint(b.inertia[2],v)}};}
inline void jacobian(const std::array<Link,13> &links,unsigned bone,Vec point,std::array<Vec,dofs> &linear,std::array<Vec,dofs> &angular){
  linear={};angular={};
  for(unsigned axis=0;axis<3;++axis){linear[axis]=basis(axis);angular[axis+3]=basis(axis);
    linear[axis+3]=crossPoint(basis(axis),subtractPoint(point,links[0].origin));}
  for(int joint=int(bone);joint>0;joint=pes3::nativeParents[joint])for(unsigned axis=0;axis<3;++axis){
    const unsigned d=6+(joint-1)*3+axis;angular[d]=basis(axis);linear[d]=crossPoint(basis(axis),subtractPoint(point,links[joint].origin));}
}
inline Vec pointVelocity(const Link &b,Vec p){return addPoint(b.velocity,crossPoint(b.omega,subtractPoint(p,b.position)));}
inline Vec biasAcceleration(const std::array<Link,13> &links,unsigned bone,Vec point){
  const Vec vp=pointVelocity(links[bone],point),vr=pointVelocity(links[0],links[0].origin);
  Vec result=crossPoint(links[0].omega,subtractPoint(vp,vr));
  for(int joint=int(bone);joint>0;joint=pes3::nativeParents[joint]){
    const unsigned parent=pes3::nativeParents[joint];
    result=addPoint(result,crossPoint(subtractPoint(links[joint].omega,links[parent].omega),
      subtractPoint(vp,pointVelocity(links[joint],links[joint].origin))));}
  return result;
}
// Floating-base inverse dynamics. Contact equations inform torque selection;
// no contacts, root constraints, external support forces or transforms are set.
inline Model dynamics(const std::array<Link,13> &links){
  Model out;auto &mass=out.mass;auto &bias=out.bias;
  for(unsigned i=0;i<13;++i){std::array<Vec,dofs> v{},w{};jacobian(links,i,links[i].position,v,w);
    const Vec acceleration=subtractPoint(biasAcceleration(links,i,links[i].position),{{0,0,-9.81f}});
    const Vec gyro=crossPoint(links[i].omega,inertia(links[i],links[i].omega));
    for(unsigned j=0;j<dofs;++j){bias[j]+=links[i].mass*dotPoint(v[j],acceleration)+dotPoint(w[j],gyro);
      for(unsigned k=0;k<=j;++k)mass[j][k]+=links[i].mass*dotPoint(v[j],v[k])+dotPoint(w[j],inertia(links[i],w[k]));}
  }
  for(unsigned j=0;j<dofs;++j)for(unsigned k=0;k<j;++k)mass[k][j]=mass[j][k];
  return out;
}
inline Result control(const std::array<Link,13> &links,const Pose &reference,Vec targetRoot,Vec targetVelocity,
    const std::array<bool,2> &support,float scale){
  Result result;const auto model=dynamics(links);const auto &mass=model.mass;const auto &bias=model.bias;Row desired{};
  const Vec rootV=pointVelocity(links[0],links[0].origin);
  const Vec rootAcceleration=capped(addPoint(scalePoint(subtractPoint(targetRoot,links[0].origin),80.f),
    scalePoint(subtractPoint(targetVelocity,rootV),18.f)),25.f);
  const Vec rootAngular=capped(subtractPoint(scalePoint(logarithm(productRotation(reference[0],inverseRotation(links[0].rotation))),100.f),scalePoint(links[0].omega,20.f)),35.f);
  for(unsigned axis=0;axis<3;++axis){desired[axis]=rootAcceleration[axis];desired[axis+3]=rootAngular[axis];}
  for(unsigned i=1;i<13;++i){const auto &parent=links[pes3::nativeParents[i]];
    const Quat current=productRotation(inverseRotation(parent.rotation),links[i].rotation);
    const Vec error=rotatePoint(parent.rotation,logarithm(productRotation(reference[i],inverseRotation(current))));
    const Vec a=capped(subtractPoint(scalePoint(error,100.f),scalePoint(subtractPoint(links[i].omega,parent.omega),20.f)),60.f);
    for(unsigned axis=0;axis<3;++axis)desired[6+(i-1)*3+axis]=a[axis];
  }
  Matrix contact{};Row contactBias{};unsigned rows=0;
  for(unsigned side=0;side<2;++side)if(support[side]){const unsigned foot=side?12:9;
    const Vec point=addPoint(links[foot].position,rotatePoint(links[foot].rotation,{{0,0,-.07f*scale}}));
    std::array<Vec,dofs> v{},w{};jacobian(links,foot,point,v,w);
    const Vec velocity=pointVelocity(links[foot],point),a=biasAcceleration(links,foot,point);
    const Vec tilt=logarithm(pes3::swingRotation(rotatePoint(links[foot].rotation,{{0,0,1}}),{{0,0,1}}));
    const Vec spin=subtractPoint(scalePoint(tilt,60.f),scalePoint(links[foot].omega,14.f));
    for(unsigned axis=0;axis<3;++axis){for(unsigned d=0;d<dofs;++d){contact[rows+axis][d]=v[d][axis];contact[rows+3+axis][d]=w[d][axis];}
      contactBias[rows+axis]=-a[axis]-velocity[axis]*18.f;contactBias[rows+3+axis]=spin[axis];}
    rows+=6;
  }
  if(!rows)return result;
  // Joint acceleration and ground wrench are solved together. Clipping a
  // wrench after solving inverse dynamics violates the floating-base equations.
  const unsigned variables=dofs+rows;
  Matrix equations{};Row right{},goal=desired,invWeight{};unsigned equalities=0;
  for(unsigned d=0;d<dofs;++d)invWeight[d]=d<6?.04:1.;
  for(unsigned c=0;c<rows;++c){
    equations[equalities]=contact[c];right[equalities++]=contactBias[c];
    invWeight[dofs+c]=c%6<3?10000.:25.;
    if(c%6==2)goal[dofs+c]=PhysicalRig::mass*9.81f/(rows/6);
  }
  for(unsigned d=0;d<6;++d){
    for(unsigned j=0;j<dofs;++j)equations[equalities][j]=mass[d][j];
    for(unsigned c=0;c<rows;++c)equations[equalities][dofs+c]=-contact[c][d];
    right[equalities++]=-bias[d];
  }
  for(unsigned bone:{4u,6u,8u,11u}){
    const auto &parent=links[pes3::nativeParents[bone]];
    const Vec relative=rotatePoint(inverseRotation(parent.rotation),subtractPoint(links[bone].omega,parent.omega));
    const Vec angle=logarithm(productRotation(inverseRotation(parent.rotation),links[bone].rotation));
    for(unsigned axis=1;axis<3;++axis){const Vec normal=rotatePoint(parent.rotation,basis(axis));
      for(unsigned c=0;c<3;++c)equations[equalities][6+(bone-1)*3+c]=normal[c];
      right[equalities++]=-14.f*relative[axis]-60.f*angle[axis];
    }
  }
  Matrix inequalities{};Row bound{};unsigned bounds=0;
  auto inequality=[&](unsigned c,unsigned d,double multiplier,double load){
    inequalities[bounds][dofs+c+d]=multiplier;inequalities[bounds][dofs+c+2]-=load;bound[bounds++]=0.;};
  for(unsigned c=0;c<rows;c+=6){
    inequalities[bounds][dofs+c+2]=-1;bound[bounds++]=0;
    inequalities[bounds][dofs+c+2]=1;bound[bounds++]=PhysicalRig::mass*9.81f*2.f;
    for(double sign:{-1.,1.}){inequality(c,0,sign,.85);inequality(c,1,sign,.85);
      inequality(c,3,sign,.10*scale);inequality(c,4,sign,.045*scale);inequality(c,5,sign,.025*scale);}
  }
  const unsigned fixed=equalities;
  for(unsigned bone=1;bone<13;++bone){const float limit=bone==9||bone==12?80.f:bone>=7?180.f:bone==1?140.f:bone==2?18.f:35.f;
    for(unsigned axis=0;axis<3;++axis){const unsigned d=6+(bone-1)*3+axis;
      for(double sign:{-1.,1.}){for(unsigned j=0;j<dofs;++j)inequalities[bounds][j]=sign*mass[d][j];
        for(unsigned c=0;c<rows;++c)inequalities[bounds][dofs+c]=-sign*contact[c][d];
        bound[bounds++]=limit-sign*bias[d];}
    }
  }
  Row solution{};std::array<bool,capacity> active{};std::array<unsigned,capacity> activeIDs{};
  bool solved=false;
  for(unsigned iteration=0;iteration<80;++iteration){
    Matrix gram{};Row rhs{},lambda{};
    for(unsigned i=0;i<equalities;++i){rhs[i]=right[i];
      for(unsigned d=0;d<variables;++d)rhs[i]-=equations[i][d]*goal[d];
      for(unsigned j=0;j<=i;++j){for(unsigned d=0;d<variables;++d)gram[i][j]+=equations[i][d]*invWeight[d]*equations[j][d];gram[j][i]=gram[i][j];}
      gram[i][i]+=1e-8;
    }
    if(!solve(gram,rhs,equalities,lambda))break;
    double wrong=1e-5;unsigned remove=~0u;
    for(unsigned i=fixed;i<equalities;++i)if(lambda[i]>wrong){wrong=lambda[i];remove=i;}
    if(remove!=~0u){active[activeIDs[remove]]=false;
      for(unsigned i=remove+1;i<equalities;++i){equations[i-1]=equations[i];right[i-1]=right[i];activeIDs[i-1]=activeIDs[i];}
      --equalities;continue;
    }
    solution=goal;
    for(unsigned d=0;d<variables;++d)for(unsigned c=0;c<equalities;++c)solution[d]+=invWeight[d]*equations[c][d]*lambda[c];
    double worst=1e-4;unsigned selected=~0u;
    for(unsigned i=0;i<bounds;++i)if(!active[i]){double violation=-bound[i];
      for(unsigned d=0;d<variables;++d)violation+=inequalities[i][d]*solution[d];
      if(violation>worst){worst=violation;selected=i;}}
    if(selected==~0u){solved=true;break;}
    equations[equalities]=inequalities[selected];activeIDs[equalities]=selected;right[equalities++]=bound[selected];active[selected]=true;
  }
  if(!solved){result.finite=false;return result;}
  result.acceleration=solution;
  Row force=bias;
  for(unsigned d=0;d<dofs;++d){
    for(unsigned j=0;j<dofs;++j)force[d]+=mass[d][j]*solution[j];
    for(unsigned c=0;c<rows;++c)force[d]-=contact[c][d]*solution[dofs+c];
  }
  for(unsigned d=0;d<6;++d)result.supportResidual=std::max(result.supportResidual,float(std::fabs(force[d])));
  for(unsigned i=1;i<13;++i){Vec torque{};for(unsigned axis=0;axis<3;++axis){torque[axis]=force[6+(i-1)*3+axis];result.finite&=std::isfinite(torque[axis]);}
    const float limit=i==9||i==12?80.f:i>=7?180.f:i==1?140.f:i==2?18.f:35.f;
    result.requestedTorque=std::max(result.requestedTorque,length(torque));
    result.torque[i]=capped(torque,limit);result.maximumTorque=std::max(result.maximumTorque,length(result.torque[i]));}
  return result;
}
}
}
