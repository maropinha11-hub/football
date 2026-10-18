#pragma once
#include <algorithm>
#include <array>
#include <cmath>

// Static, band-limited microrelief: all prediction horizons see the same
// ground. Metres, m/s; no time noise, random kicks or impulses at a distance.
namespace football_turf {
using Vec=std::array<float,3>;
inline float bound(float v,float lo,float hi){return std::isfinite(v)?std::max(lo,std::min(hi,v)):lo;}
struct Surface {float height=0,dx=0,dy=0,restitution=1,resistance=1;};
inline Surface sample(float x,float y,float roughness){
  Surface s;const float r=bound(roughness,0,1);
  if(r==0||!std::isfinite(x)||!std::isfinite(y))return s;
  const float a=7*x+4*y+.8f,b=17*x-11*y+1.7f,c=31*x+19*y+2.4f;
  s.height=r*(.004f*(1+std::sin(a))+.0025f*(1+std::sin(b))+.0012f*(1+std::sin(c)));
  s.dx=r*(.028f*std::cos(a)+.0425f*std::cos(b)+.0372f*std::cos(c));
  s.dy=r*(.016f*std::cos(a)-.0275f*std::cos(b)+.0228f*std::cos(c));
  s.restitution=1-r*.10f+r*.10f*std::sin(.7f*x+.9f*y);
  s.resistance=1+r*.22f*std::sin(2.3f*x-3.7f*y+.4f);
  return s;
}
struct Response {bool contact=false;float normalSpeed=0,energyBefore=0,energyAfter=0;Surface surface;};
inline Response contact(Vec &position,Vec &velocity,float roughness,float bounce,float linearLoss){
  Response out;out.surface=sample(position[0],position[1],roughness);
  if(roughness<=0||position[2]>.11005f+out.surface.height)return out;
  out.contact=true;position[2]=std::max(position[2],.11f+out.surface.height);
  const float inv=1/std::sqrt(1+out.surface.dx*out.surface.dx+out.surface.dy*out.surface.dy);
  const Vec normal{{-out.surface.dx*inv,-out.surface.dy*inv,inv}};
  for(unsigned i=0;i<3;++i){out.normalSpeed+=velocity[i]*normal[i];out.energyBefore+=velocity[i]*velocity[i];}
  if(out.normalSpeed<0){
    // Gentle contacts settle; firmer slope impacts convert some existing
    // horizontal momentum into a small skip. Restitution never adds energy.
    const float blend=bound((-out.normalSpeed-.08f)/.45f,0,1);
    const float restitution=bound(bounce,0,.95f)*out.surface.restitution*blend;
    const float separating=std::max(0.f,-out.normalSpeed*restitution-linearLoss);
    for(unsigned i=0;i<3;++i)velocity[i]+=normal[i]*(separating-out.normalSpeed);
  }
  if(std::hypot(velocity[0],velocity[1])<.04f&&std::fabs(velocity[2])<.12f)velocity={{0,0,0}};
  for(float v:velocity)out.energyAfter+=v*v;
  if(out.energyAfter>out.energyBefore&&out.energyAfter>0){
    const float scale=std::sqrt(out.energyBefore/out.energyAfter);
    for(float &v:velocity)v*=scale;
    out.energyAfter=out.energyBefore;
  }
  return out;
}
inline void preventPenetration(Vec &position,float roughness){
  if(roughness>0)position[2]=std::max(position[2],.11f+sample(position[0],position[1],roughness).height);
}
}
