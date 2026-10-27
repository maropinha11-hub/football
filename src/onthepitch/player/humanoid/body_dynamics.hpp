#pragma once
#include "physical_rig.hpp"

namespace football_physics {
namespace whole_body {
constexpr unsigned dofs=42;
constexpr unsigned capacity=dofs;
using Row=std::array<double,capacity>;
using Matrix=std::array<Row,capacity>;
struct Link {Vec position{},origin{},velocity{},omega{};Quat rotation{{0,0,0,1}};float mass=0;std::array<Vec,3> inertia{};};
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
}
}
