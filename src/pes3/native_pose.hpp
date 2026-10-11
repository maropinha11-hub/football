#pragma once
// FPSoccer adaptation. This is not an original PES routine or a proof of
// native body proportions, contact, source cadence, or action selection.
#include <array>
#include <cmath>

namespace pes3 {
using Rotation = std::array<float,4>;
using SourceRotations = std::array<Rotation,19>;
using NativeRotations = std::array<Rotation,13>;

// Native left is +X when looking down -Y. In the displayed reference pose,
// source branches 3/5/7 and 12/14 occupy +X. These are display correspondences;
// the original game's preferred-foot field is not inferred from them.
constexpr unsigned nativeSourceBones[13] = {0,8,16,12,14,11,13,3,5,7,2,4,6};
constexpr int nativeParents[13] = {-1,0,1,1,3,1,5,0,7,8,0,10,11};
constexpr const char* nativeBoneNames[13] = {
  "body","middle","neck","left_shoulder","left_elbow","right_shoulder",
  "right_elbow","left_thigh","left_knee","left_ankle","right_thigh",
  "right_knee","right_ankle"
};

inline bool unitRotation(Rotation q,Rotation& out) {
  double length=0;
  for (float v:q) { if (!std::isfinite(v)) return false; length+=double(v)*v; }
  if (length<1e-12 || length>1e12) return false;
  const double inverse=1/std::sqrt(length);
  for (unsigned i=0;i<4;++i) out[i]=float(q[i]*inverse);
  return true;
}
inline Rotation inverseRotation(Rotation q) { return {{-q[0],-q[1],-q[2],q[3]}}; }
inline Rotation productRotation(const Rotation& a,const Rotation& b) {
  return {{a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1],
           a[3]*b[1]+a[1]*b[3]+a[2]*b[0]-a[0]*b[2],
           a[3]*b[2]+a[2]*b[3]+a[0]*b[1]-a[1]*b[0],
           a[3]*b[3]-a[0]*b[0]-a[1]*b[1]-a[2]*b[2]}};
}

// Maps source world-space rotational changes relative to clip 47 phase 0
// onto an explicitly supplied native reference. The engine still owns joint
// offsets, root placement, height, physics and touch IK. Output is atomic.
inline bool adaptNativePose(const SourceRotations& current,const SourceRotations& reference,
                            const NativeRotations& nativeReference,NativeRotations& out) {
  // Proper rotation (X,Y,Z)->(X,Z,-Y), not a reflection or a physical scale.
  const Rotation basis={{-0.7071067811865475f,0,0,0.7071067811865475f}};
  SourceRotations source{},rest{};
  NativeRotations base{},global{},local{};
  for (unsigned i=0;i<19;++i)
    if (!unitRotation(current[i],source[i]) || !unitRotation(reference[i],rest[i])) return false;
  for (unsigned i=0;i<13;++i) if (!unitRotation(nativeReference[i],base[i])) return false;
  for (unsigned i=0;i<13;++i) {
    const unsigned bone=nativeSourceBones[i];
    const auto delta=productRotation(source[bone],inverseRotation(rest[bone]));
    const auto nativeDelta=productRotation(productRotation(basis,delta),inverseRotation(basis));
    if (!unitRotation(productRotation(nativeDelta,base[i]),global[i])) return false;
    const auto parent=nativeParents[i]<0 ? Rotation{{0,0,0,1}} : global[nativeParents[i]];
    if (!unitRotation(productRotation(inverseRotation(parent),global[i]),local[i])) return false;
  }
  out=local;
  return true;
}
} // namespace pes3
