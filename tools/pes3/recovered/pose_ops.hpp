#pragma once
// Semantic pose helpers recovered from selected SLES_519.12 routines.
// Host binary32 model, separate operations, no fast-math/FMA. No guest memory.
// Original clock units and model axes are retained; no retargeting assumption.
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <stdexcept>

namespace pes3_pose {
static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559,"binary32 required");
using Vector = std::array<float,4>;
using Matrix = std::array<Vector,4>; // columns
inline float vu(float value) {
  if (!std::isfinite(value)) throw std::domain_error("finite pose domain required");
  std::uint32_t raw; std::memcpy(&raw,&value,4);
  if (!(raw & 0x7f800000u)) { raw &= 0x80000000u; std::memcpy(&value,&raw,4); }
  return value;
}
inline float add(float a,float b) { return vu(vu(a)+vu(b)); }
inline float sub(float a,float b) { return vu(vu(a)-vu(b)); }
inline float mul(float a,float b) { return vu(vu(a)*vu(b)); }
inline float dot(Vector a,Vector b) { // 010D2F70: w,x,y,z reduction order
  float out=add(mul(a[3],b[3]),mul(a[0],b[0]));
  out=add(out,mul(a[1],b[1])); return add(out,mul(a[2],b[2]));
}
inline Vector multiply(Vector a,Vector b) { // 010D3060
  Vector out{};
  out[3]=sub(sub(sub(mul(a[3],b[3]),mul(a[0],b[0])),mul(a[1],b[1])),mul(a[2],b[2]));
  for (unsigned lane=0;lane<3;++lane) {
    const unsigned i=(lane+1)%3,j=(lane+2)%3;
    const float cross=sub(mul(a[i],b[j]),mul(b[i],a[j]));
    out[lane]=add(add(mul(a[lane],b[3]),mul(b[lane],a[3])),mul(cross,1));
  }
  return out;
}
inline Matrix matrix(Vector q) { // 010D2F00, column-major, original operation order
  Vector twice{},square{},positive{},negative{};
  for(unsigned lane=0;lane<4;++lane) twice[lane]=add(q[lane],q[lane]);
  for(unsigned lane=0;lane<3;++lane) {
    square[lane]=mul(twice[lane],q[lane]);
    const float cross=mul(twice[(lane+1)%3],q[(lane+2)%3]);
    positive[lane]=add(cross,mul(twice[lane],q[3]));
    negative[lane]=sub(cross,mul(twice[lane],q[3]));
  }
  return {{{sub(sub(1,square[1]),square[2]),add(0,positive[2]),add(0,negative[1]),0},
           {add(0,negative[2]),sub(sub(1,square[0]),square[2]),add(0,positive[0]),0},
           {add(0,positive[1]),add(0,negative[0]),sub(sub(1,square[0]),square[1]),0},
           {0,0,0,1}}};
}
inline Vector rotate(Vector q,Vector point) { // 010D2FF0, unit-quaternion convention
  const float projection=add(add(mul(q[0],point[0]),mul(q[1],point[1])),mul(q[2],point[2]));
  Vector out{0,0,0,mul(point[3],1)};
  const float scalar_square=mul(q[3],q[3]);
  for(unsigned lane=0;lane<3;++lane) {
    const unsigned i=(lane+1)%3,j=(lane+2)%3;
    const float cross=sub(mul(point[i],q[j]),mul(q[i],point[j]));
    const float acc=add(mul(point[lane],scalar_square),mul(q[lane],projection));
    const float half=sub(acc,mul(cross,q[3]));
    out[lane]=sub(add(half,half),mul(point[lane],1));
  }
  return out;
}
inline Vector blend(Vector a,Vector b,float alpha) { // 010D29B0: shortest-arc NLERP
  if (!std::isfinite(alpha) || alpha<0 || alpha>1) throw std::domain_error("blend weight outside [0,1]");
  if(dot(a,b)<0) for(auto& v:b) v=mul(v,-1);
  const float complement=sub(1,alpha);
  Vector out{};
  for(unsigned lane=0;lane<4;++lane) out[lane]=add(mul(b[lane],alpha),mul(a[lane],complement));
  const float square=dot(out,out);
  if(square>0) {
    const float denominator=vu(std::sqrt(std::abs(vu(square))));
    const float reciprocal=vu(1.0f/denominator);
    for(auto& v:out) v=mul(v,reciprocal);
  }
  return out;
}
} // namespace pes3_pose
