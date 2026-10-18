#pragma once
#include "physical_rig.hpp"

namespace football_physics {
struct BodyContact {bool touching=false;Vec point{{0,0,0}},normal{{1,0,0}};float penetration=0;};
struct BodyProxy {Vec center;float radius;};
inline std::array<BodyProxy,10> bodyProxies(const Points &points,const Pose &rotations,float scale){
  return {{{points[0],.14f*scale},
    {addPoint(points[1],scalePoint(subtractPoint(points[2],points[1]),.5f)),.18f*scale},
    {points[3],.09f*scale},{points[5],.09f*scale},
    {points[4],.055f*scale},{points[6],.055f*scale},
    {addPoint(points[4],rotatePoint(rotations[4],{{0,0,-.25f*scale}})),.045f*scale},
    {addPoint(points[6],rotatePoint(rotations[6],{{0,0,-.25f*scale}})),.045f*scale},
    {scalePoint(addPoint(points[3],points[4]),.5f),.06f*scale},
    {scalePoint(addPoint(points[5],points[6]),.5f),.06f*scale}}};
}
inline BodyContact bodyContact(const std::array<BodyProxy,10> &a,const std::array<BodyProxy,10> &b){
  BodyContact best;float deepest=-1e9f;
  for(const auto &first:a)for(const auto &second:b){
    Vec normal=subtractPoint(second.center,first.center);const float d=length(normal),depth=first.radius+second.radius-d;
    if(depth<0||depth<=deepest)continue;
    normal=unit(normal,{{1,0,0}});
    // An upright football challenge transmits horizontal pressure. A hand
    // above someone's shoulder must not manufacture a vertical launch.
    if(normal[0]*normal[0]+normal[1]*normal[1]<.09f)continue;
    deepest=depth;best.touching=true;best.penetration=std::min(.08f,depth);
    best.point=scalePoint(addPoint(addPoint(first.center,scalePoint(normal,first.radius)),
      subtractPoint(second.center,scalePoint(normal,second.radius))),.5f);
    best.normal=unit({{normal[0],normal[1],0}},{{1,0,0}});
  }
  return best;
}
inline float bodyPressure(float penetration,float closing){
  if(!std::isfinite(penetration)||!std::isfinite(closing))return 0;
  return bounded(std::max(0.f,penetration)*3500.f+std::max(0.f,closing)*90.f,0,260);
}
}
