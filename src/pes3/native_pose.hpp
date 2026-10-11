#pragma once
// FPSoccer adaptation. This is not an original PES routine or a proof of
// native body proportions, contact, source cadence, or action selection.
#include <array>
#include <cmath>

namespace pes3 {
using Rotation = std::array<float,4>;
using SourceRotations = std::array<Rotation,19>;
using NativeRotations = std::array<Rotation,13>;
using Point = std::array<float,3>;
using SourcePoints = std::array<Point,19>;
using NativePoints = std::array<Point,13>;
struct NativeBind {
  NativeRotations rotations{};
  NativePoints offsets{};
  std::array<Point,2> footMin{},footMax{};
};
struct NativePose {
  NativeRotations local{};
  NativePoints positions{}; // Forward kinematics relative to the actor root.
  float rootHeight=0;
  float maximumDirectionError=0;
};

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
inline Point subtractPoint(Point a,Point b) { return {{a[0]-b[0],a[1]-b[1],a[2]-b[2]}}; }
inline Point addPoint(Point a,Point b) { return {{a[0]+b[0],a[1]+b[1],a[2]+b[2]}}; }
inline Point scalePoint(Point a,float v) { return {{a[0]*v,a[1]*v,a[2]*v}}; }
inline float dotPoint(Point a,Point b) { return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }
inline Point crossPoint(Point a,Point b) {
  return {{a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]}};
}
inline bool unitPoint(Point p,Point& out) {
  double n=0;for(float v:p) { if(!std::isfinite(v))return false;n+=double(v)*v; }
  if(n<1e-12 || n>1e12)return false;
  out=scalePoint(p,float(1/std::sqrt(n)));return true;
}
inline Point rotatePoint(Rotation q,Point p) {
  const Point axis={{q[0],q[1],q[2]}};
  const auto t=scalePoint(crossPoint(axis,p),2);
  return addPoint(addPoint(p,scalePoint(t,q[3])),crossPoint(axis,t));
}
inline Rotation swingRotation(Point from,Point to) {
  const float c=std::fmax(-1.f,std::fmin(1.f,dotPoint(from,to)));
  Point axis=crossPoint(from,to);
  if(c<-.999999f) {
    if(!unitPoint(crossPoint(from,{{1,0,0}}),axis))unitPoint(crossPoint(from,{{0,1,0}}),axis);
    return {{axis[0],axis[1],axis[2],0}};
  }
  Rotation out;unitRotation({{axis[0],axis[1],axis[2],1+c}},out);return out;
}
inline bool alignPrimary(Rotation candidate,Point localAxis,Point goal,Rotation& out) {
  Point a,b;if(!unitPoint(rotatePoint(candidate,localAxis),a)||!unitPoint(goal,b))return false;
  return unitRotation(productRotation(swingRotation(a,b),candidate),out);
}
inline bool alignSide(Rotation candidate,Point localPrimary,Point goal,Point localSide,Point side,Rotation& out) {
  if(!alignPrimary(candidate,localPrimary,goal,out))return false;
  Point primary;if(!unitPoint(goal,primary))return false;
  Point from=rotatePoint(out,localSide),to=side;
  from=subtractPoint(from,scalePoint(primary,dotPoint(from,primary)));
  to=subtractPoint(to,scalePoint(primary,dotPoint(to,primary)));
  if(!unitPoint(from,from)||!unitPoint(to,to))return true;
  return unitRotation(productRotation(swingRotation(from,to),out),out);
}

// Anatomical axes are calibrated from joint positions and the actual native
// skin bind. Quaternion deltas alone cannot guarantee a limb follows its
// source segment. Collapsed spine nodes are aimed using current endpoints.
inline bool retargetSkeleton(const SourceRotations& current,const SourceRotations& reference,
                             const SourcePoints& points,const SourcePoints& restPoints,
                             const NativeBind& native,NativePose& out) {
  SourceRotations source{},rest{};NativeRotations base{},aligned{},global{};
  for(unsigned i=0;i<19;++i) {
    if(!unitRotation(current[i],source[i])||!unitRotation(reference[i],rest[i]))return false;
    for(float p:points[i])if(!std::isfinite(p)||std::fabs(p)>100000)return false;
    for(float p:restPoints[i])if(!std::isfinite(p)||std::fabs(p)>100000)return false;
  }
  for(unsigned i=0;i<13;++i) {
    if(!unitRotation(native.rotations[i],base[i]))return false;
    for(float p:native.offsets[i])if(!std::isfinite(p)||std::fabs(p)>4)return false;
  }
  // Points are already in the display basis; rotations remain source format.
  const Rotation basis={{-.7071067811865475f,0,0,.7071067811865475f}};
  const int child[13]={1,2,-1,4,-1,6,-1,8,9,-1,11,12,-1};
  const int sourceChild[13]={8,16,-1,14,18,13,17,5,7,-1,4,6,-1};
  auto direction=[&](const SourcePoints& p,unsigned i) {
    if(i==0)return subtractPoint(p[8],scalePoint(addPoint(p[2],p[3]),.5f));
    return subtractPoint(p[sourceChild[i]],p[nativeSourceBones[i]]);
  };
  for(unsigned i=0;i<13;++i) {
    Point axis=child[i]>=0 ? native.offsets[child[i]] : Point{{0,0,-1}};
    const bool segment=sourceChild[i]>=0;
    aligned[i]=base[i];
    if(segment&&!alignPrimary(base[i],axis,direction(restPoints,i),aligned[i]))return false;
    const auto delta=productRotation(source[nativeSourceBones[i]],inverseRotation(rest[nativeSourceBones[i]]));
    const auto d=productRotation(productRotation(basis,delta),inverseRotation(basis));
    if(!unitRotation(productRotation(d,aligned[i]),global[i]))return false;
    if(segment&&!alignPrimary(global[i],axis,direction(points,i),global[i]))return false;
    if(i==0&&!alignSide(global[i],axis,direction(points,i),{{1,0,0}},subtractPoint(points[3],points[2]),global[i]))return false;
    if(i==1&&!alignSide(global[i],axis,direction(points,i),{{1,0,0}},subtractPoint(points[12],points[11]),global[i]))return false;
  }
  NativePose result;
  for(unsigned i=0;i<13;++i) {
    const int parent=nativeParents[i];
    if(!unitRotation(productRotation(parent<0 ? Rotation{{0,0,0,1}} : inverseRotation(global[parent]),global[i]),result.local[i]))return false;
    result.positions[i]=parent<0 ? Point{{0,0,0}} : addPoint(result.positions[parent],rotatePoint(global[parent],native.offsets[i]));
    if(child[i]>=0) {
      Point actual,expected;
      if(!unitPoint(rotatePoint(global[i],native.offsets[child[i]]),actual)||!unitPoint(direction(points,i),expected))return false;
      const auto error=subtractPoint(actual,expected);
      result.maximumDirectionError=std::fmax(result.maximumDirectionError,std::sqrt(dotPoint(error,error)));
    }
  }
  // Preserve source airborne displacement, fit the native foot volumes above
  // the pitch, and never accumulate a visual root offset across frames.
  float minimum=1e9f;
  for(unsigned f=0;f<2;++f) {
    const unsigned ankle=f ? 12 : 9;
    for(unsigned a=0;a<3;++a)if(!std::isfinite(native.footMin[f][a])||!std::isfinite(native.footMax[f][a])||
      native.footMin[f][a]>native.footMax[f][a]||std::fabs(native.footMin[f][a])>1||std::fabs(native.footMax[f][a])>1)return false;
    for(unsigned corner=0;corner<8;++corner) {
      Point p;for(unsigned a=0;a<3;++a)p[a]=(corner&(1u<<a))?native.footMax[f][a]:native.footMin[f][a];
      minimum=std::fmin(minimum,result.positions[ankle][2]+rotatePoint(global[ankle],p)[2]);
    }
  }
  auto length=[](Point p) { return std::sqrt(dotPoint(p,p)); };
  const float nativeLeg=length(native.offsets[8])+length(native.offsets[9])+length(native.offsets[11])+length(native.offsets[12]);
  const float sourceLeg=length(subtractPoint(restPoints[5],restPoints[3]))+length(subtractPoint(restPoints[7],restPoints[5]))+
    length(subtractPoint(restPoints[4],restPoints[2]))+length(subtractPoint(restPoints[6],restPoints[4]));
  if(!(sourceLeg>1e-6f&&nativeLeg>.1f))return false;
  const float airborne=std::fmax(0.f,(std::fmin(points[6][2],points[7][2])-std::fmin(restPoints[6][2],restPoints[7][2]))*nativeLeg/sourceLeg);
  result.rootHeight=airborne-minimum+.008f;
  if(!std::isfinite(result.rootHeight)||result.rootHeight<-.1f||result.rootHeight>5)return false;
  for(auto& p:result.positions)p[2]+=result.rootHeight;
  out=result;return true;
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
