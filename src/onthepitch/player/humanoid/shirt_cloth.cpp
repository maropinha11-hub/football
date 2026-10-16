#include "shirt_cloth.hpp"
#include <set>

namespace football_physics {
void ShirtCloth::configure(const std::vector<Vec>& rest,const std::vector<unsigned>& triangles,const std::vector<float>& move){
  mapping.clear();x.clear();mobility.clear();edges.clear();ready=false;movableCount=0;
  for(unsigned i=0;i<rest.size();++i){
    unsigned id=0;for(;id<x.size();++id)if(length(subtractPoint(rest[i],x[id]))<.0001f)break;
    if(id==x.size()){x.push_back(rest[i]);mobility.push_back(move[i]);}
    else mobility[id]=std::min(mobility[id],move[i]);
    mapping.push_back(id);
  }
  std::set<std::pair<unsigned,unsigned>> unique;
  for(unsigned t=0;t+2<triangles.size();t+=3)for(unsigned e=0;e<3;++e){
    unsigned a=mapping.at(triangles[t+e]),b=mapping.at(triangles[t+(e+1)%3]);
    if(a>b)std::swap(a,b);
    if(a!=b && (mobility[a]>0 || mobility[b]>0) && unique.emplace(a,b).second)edges.push_back({a,b,0});
  }
  for(float w:mobility)movableCount+=w>0;
  velocity.resize(x.size());displayed.resize(rest.size());
}
void ShirtCloth::step(const std::vector<Vec>& target,const std::vector<Vec>& normal,float dt,Vec gripPoint,Vec gripForce){
  if(target.size()!=mapping.size())return;
  std::vector<Vec> goals(x.size()),normals(x.size());
  for(unsigned i=0;i<mapping.size();++i){goals[mapping[i]]=target[i];normals[mapping[i]]=unit(normal[i]);}
  if(!ready || (!goals.empty() && length(subtractPoint(goals[0],previousTarget[0]))>1.5f)){
    x=goals;velocity.assign(x.size(),{{0,0,0}});previousTarget=goals;ready=true;
  }
  peakOffset=peakStretch=0;dt=bounded(dt,0,.10f);
  const unsigned steps=std::max(1u,unsigned(std::ceil(dt/.005f)));const float h=dt/steps;
  unsigned grip=0;float nearest=100;
  for(unsigned i=0;i<x.size();++i)if(mobility[i]>0){const float d=length(subtractPoint(goals[i],gripPoint));if(d<nearest){grip=i;nearest=d;}}
  for(unsigned sub=0;sub<steps && h>0;++sub){
    std::vector<Vec> before=x;
    for(unsigned i=0;i<x.size();++i){
      if(mobility[i]<=0){x[i]=goals[i];continue;}
      // Distribute the limited hand force over a patch, never a single light
      // vertex. The gameplay constraint applies the opposite force to actors.
      const float patch=std::exp(-std::pow(length(subtractPoint(goals[i],goals[grip]))/.11f,2.f));
      Vec force=addPoint({{0,0,-1.8f}},scalePoint(capped(gripForce,150),patch*.32f));
      Vec acceleration=addPoint(scalePoint(subtractPoint(goals[i],x[i]),220.f),force);
      velocity[i]=scalePoint(addPoint(velocity[i],scalePoint(acceleration,h)),std::exp(-9*h));
      x[i]=addPoint(x[i],scalePoint(velocity[i],h));
    }
    for(auto &edge:edges)edge.lambda=0;
    for(unsigned iteration=0;iteration<6;++iteration){
      for(auto &edge:edges){
        const Vec delta=subtractPoint(x[edge.b],x[edge.a]);const float distance=length(delta);
        if(distance<1e-7f)continue;
        const float rest=length(subtractPoint(goals[edge.b],goals[edge.a]));
        const float alpha=.000018f/(h*h),wa=mobility[edge.a],wb=mobility[edge.b];
        const float lambda=(-(distance-rest)-alpha*edge.lambda)/(wa+wb+alpha);edge.lambda+=lambda;
        const Vec correction=scalePoint(delta,lambda/distance);
        x[edge.a]=subtractPoint(x[edge.a],scalePoint(correction,wa));x[edge.b]=addPoint(x[edge.b],scalePoint(correction,wb));
      }
      for(unsigned i=0;i<x.size();++i)if(mobility[i]>0){
        Vec offset=subtractPoint(x[i],goals[i]);
        // Native skin is a local unilateral collision surface. This is a
        // shirt shell, not a simulation of cloth threading under the body.
        const float inward=dotPoint(offset,normals[i]);
        if(inward<0)offset=subtractPoint(offset,scalePoint(normals[i],inward));
        x[i]=addPoint(goals[i],capped(offset,length(gripForce)>1?.12f:.045f));
        if(x[i][2]<.004f)x[i][2]=.004f;
      }
    }
    for(unsigned i=0;i<x.size();++i)velocity[i]=capped(scalePoint(subtractPoint(x[i],before[i]),1/h),3.f);
  }
  for(const auto &edge:edges){const float rest=length(subtractPoint(goals[edge.b],goals[edge.a]));if(rest>.001f)peakStretch=std::max(peakStretch,length(subtractPoint(x[edge.b],x[edge.a]))/rest);}
  for(unsigned i=0;i<mapping.size();++i){displayed[i]=x[mapping[i]];peakOffset=std::max(peakOffset,length(subtractPoint(displayed[i],target[i])));}
  previousTarget=goals;
}
}
