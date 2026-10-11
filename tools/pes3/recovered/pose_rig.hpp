#pragma once
// Recovered rig operations on owned numeric structures, never PS2 pointers.
// Selected host binary32 model; not a resumed frame or a mesh retargeter.
#include "pose_ops.hpp"

namespace pes3_pose {
constexpr unsigned bone_count = 19;
struct Bone {
  std::int32_t parent = -1, mirror = -1;
  std::uint32_t mirror_policy = 0, processed = 0;
  Vector local_translation{}, local_rotation{}, composed_rotation{}, composed_translation{};
  Matrix matrix{};
  Vector cached_rotation{}, mirror_correction{};
};
struct Rig {
  std::array<std::uint32_t,4> flags{}; // instance bytes +28 through +31
  std::array<Bone,bone_count> bones{};
};
inline void validate(const Rig& rig) {
  for(auto f:rig.flags) if(f>255) throw std::domain_error("flag outside byte domain");
  for(unsigned i=0;i<bone_count;++i) {
    const auto& b=rig.bones[i];
    if((i==0 && b.parent!=-1) || (i && (b.parent<0 || b.parent>=static_cast<int>(i))))
      throw std::domain_error("parent outside topological rig");
    if(b.mirror < -1 || b.mirror>=static_cast<int>(bone_count) || b.mirror==static_cast<int>(i)
       || (b.mirror>=0 && rig.bones[b.mirror].mirror!=static_cast<int>(i)))
      throw std::domain_error("nonreciprocal mirror pair");
    if(b.mirror_policy>255 || b.processed>255) throw std::domain_error("bone flag outside byte domain");
    const Vector* fields[]={&b.local_translation,&b.local_rotation,&b.composed_rotation,
      &b.composed_translation,&b.cached_rotation,&b.mirror_correction};
    for(const auto* field:fields) for(float v:*field) if(!std::isfinite(v))
      throw std::domain_error("nonfinite bone field");
    for(const auto& column:b.matrix) for(float v:column) if(!std::isfinite(v))
      throw std::domain_error("nonfinite matrix");
  }
}
inline Vector conjugate(Vector q) { // 010D3040: VU multiply, not division by norm
  for(unsigned i=0;i<3;++i) q[i]=mul(q[i],-1);
  q[3]=mul(q[3],1); return q;
}
inline Vector linear(Vector a,Vector b,float weight_a) { // 01093F10, all four lanes
  const float weight_b=sub(1,weight_a);
  Vector out{};
  for(unsigned i=0;i<4;++i) out[i]=add(mul(a[i],weight_a),mul(b[i],weight_b));
  return out;
}
inline Vector matrix_point(const Matrix& m,Vector point) { // 01116160, implicit w=1
  Vector out{};
  for(unsigned i=0;i<4;++i) {
    float acc=mul(m[0][i],point[0]);
    acc=add(acc,mul(m[1][i],point[1]));
    acc=add(acc,mul(m[2][i],point[2]));
    out[i]=add(acc,mul(m[3][i],1));
  }
  return out;
}
// COP1 operations retain finite subnormals, unlike the selected VU helpers.
inline float fp(float v) {
  if(!std::isfinite(v)) throw std::domain_error("finite matrix quaternion domain required");
  return v;
}
inline float fa(float a,float b) { return fp(a+b); }
inline float fs(float a,float b) { return fp(a-b); }
inline float fm(float a,float b) { return fp(a*b); }
inline float fd(float a,float b) {
  if(!b) throw std::domain_error("zero matrix quaternion divisor");
  return fp(a/b);
}
inline Vector matrix_quaternion(const Matrix& m) { // 010D2C50, original threshold/order
  const float d0=m[0][0],d1=m[1][1],d2=m[2][2];
  const float trace=fa(1,fa(d2,fa(d0,d1)));
  Vector q{};
  if(trace>0.1f) {
    const float s=fp(static_cast<float>(std::sqrt(static_cast<double>(trace))));
    q[3]=fd(s,2);
    const float factor=fd(0.5f,s);
    q[0]=fm(factor,fs(m[1][2],m[2][1]));
    q[1]=fm(factor,fs(m[2][0],m[0][2]));
    q[2]=fm(factor,fs(m[0][1],m[1][0]));
  } else {
    unsigned i=d0<d1 ? 1 : 0;
    if(m[i][i]<d2) i=2;
    const unsigned j=(i+1)%3,k=(i+2)%3;
    const float square=fa(1,fs(fs(m[i][i],m[j][j]),m[k][k]));
    float s=fp(static_cast<float>(std::sqrt(static_cast<double>(square))));
    q[i]=fd(s,2);
    if(s!=0) s=fd(0.5f,s);
    // Keep the source operand order for the off-diagonal sums.
    if(i==0) {
      q[1]=fm(s,fa(m[0][1],m[1][0]));
      q[2]=fm(s,fa(m[2][0],m[0][2]));
      q[3]=fm(s,fs(m[1][2],m[2][1]));
    } else if(i==1) {
      q[0]=fm(s,fa(m[0][1],m[1][0]));
      q[2]=fm(s,fa(m[1][2],m[2][1]));
      q[3]=fm(s,fs(m[2][0],m[0][2]));
    } else {
      q[0]=fm(s,fa(m[2][0],m[0][2]));
      q[1]=fm(s,fa(m[1][2],m[2][1]));
      q[3]=fm(s,fs(m[0][1],m[1][0]));
    }
  }
  return q;
}
inline void compose_matrices(Rig& rig) { // 01116060, unconditional local -> composed
  rig.flags[1]|=6;
  for(auto& b:rig.bones) {
    if(b.parent<0) {
      b.matrix=matrix(b.local_rotation);
      b.local_translation[3]=1;
      b.matrix[3]=b.local_translation;
      b.composed_rotation=b.local_rotation;
      b.composed_translation=b.local_translation;
    } else {
      const auto& p=rig.bones[b.parent];
      b.composed_rotation=multiply(p.composed_rotation,b.local_rotation);
      b.matrix=matrix(b.composed_rotation);
      b.composed_translation=matrix_point(p.matrix,b.local_translation);
      b.composed_translation[3]=1;
      b.matrix[3]=b.composed_translation;
    }
    b.matrix[3][3]=1;
  }
}
inline void ensure_composed(Rig& rig) { // 011157E0, selected existing local branch
  if(rig.flags[1]&2) return;
  if(!(rig.flags[1]&1)) {
    if(!(rig.flags[1]&4)) throw std::domain_error("clip decode fallback not recovered here");
    for(auto& b:rig.bones) {
      b.composed_rotation=matrix_quaternion(b.matrix);
      b.composed_translation=b.matrix[3];
    }
    rig.flags[1]|=2; return;
  }
  for(auto& b:rig.bones) {
    if(b.parent<0) {
      b.composed_rotation=b.local_rotation;
      b.composed_translation=b.local_translation;
    } else {
      const auto& p=rig.bones[b.parent];
      b.composed_rotation=multiply(p.composed_rotation,b.local_rotation);
      b.composed_translation=rotate(p.composed_rotation,b.local_translation);
      for(unsigned i=0;i<4;++i) b.composed_translation[i]=add(b.composed_translation[i],p.composed_translation[i]);
    }
    b.composed_translation[3]=1;
  }
  // Preserve the original flags, even though this branch does not write matrices.
  rig.flags[1]|=6;
}
inline void ensure_local(Rig& rig) { // 01115940, selected composed quaternion branch
  if(rig.flags[1]&1) return;
  const bool from_matrix=!(rig.flags[1]&2);
  if(from_matrix && !(rig.flags[1]&4)) throw std::domain_error("clip decode fallback not recovered here");
  for(auto& b:rig.bones) {
    if(from_matrix) {
      b.composed_rotation=matrix_quaternion(b.matrix);
      b.composed_translation=b.matrix[3];
    }
    if(b.parent<0) {
      b.local_rotation=b.composed_rotation;
      b.local_translation=b.composed_translation;
    } else {
      const auto& p=rig.bones[b.parent];
      const auto inverse=conjugate(p.composed_rotation);
      b.local_rotation=multiply(inverse,b.composed_rotation);
      Vector delta{};
      for(unsigned i=0;i<4;++i) delta[i]=sub(b.composed_translation[i],p.composed_translation[i]);
      b.local_translation=rotate(inverse,delta);
    }
  }
  rig.flags[1]|=from_matrix ? 3 : 1;
}
inline void mirror_raw(Rig& rig) { // 01115C60, two passes and pair basis corrections
  for(auto& b:rig.bones) {
    if(b.parent<0) {
      b.composed_rotation=multiply({0,1,0,0},b.local_rotation);
      b.local_translation[3]=1;
      b.composed_translation=b.local_translation;
      // These are COP1 negations: preserve their exact sign operation.
      b.composed_translation[0]=-b.composed_translation[0];
      b.composed_translation[2]=-b.composed_translation[2];
    } else {
      const auto& p=rig.bones[b.parent];
      b.composed_rotation=multiply(p.composed_rotation,b.local_rotation);
      b.composed_translation=rotate(p.composed_rotation,b.local_translation);
      for(unsigned i=0;i<4;++i) b.composed_translation[i]=add(b.composed_translation[i],p.composed_translation[i]);
      b.composed_translation[3]=1;
    }
    b.processed=0;
  }
  constexpr Vector q_sign={-1,-1,1,1},p_sign={1,1,-1,1};
  for(auto& b:rig.bones) {
    if(b.processed) continue;
    if(b.mirror<0) {
      if(b.mirror_policy==0) {
        b.composed_rotation[0]=-b.composed_rotation[0];
        b.composed_rotation[1]=-b.composed_rotation[1];
        b.composed_translation[2]=-b.composed_translation[2];
      }
      continue;
    }
    b.composed_rotation=multiply(b.composed_rotation,b.mirror_correction);
    auto& other=rig.bones[b.mirror];
    const Vector previous_q=other.composed_rotation,previous_p=other.composed_translation;
    for(unsigned i=0;i<4;++i) {
      other.composed_rotation[i]=mul(b.composed_rotation[i],q_sign[i]);
      b.composed_rotation[i]=mul(previous_q[i],q_sign[i]);
      other.composed_translation[i]=mul(b.composed_translation[i],p_sign[i]);
      b.composed_translation[i]=mul(previous_p[i],p_sign[i]);
    }
    b.processed=other.processed=1;
    b.composed_rotation=multiply(b.composed_rotation,conjugate(b.mirror_correction));
  }
}
inline void apply_mirror(Rig& rig) { // 01115C20
  ensure_composed(rig);
  mirror_raw(rig);
  rig.flags[1]=(rig.flags[1]&0xc0)|2;
}
inline void mirror_gate(Rig& rig) { // 011156B0
  if(rig.flags[2]) return;
  if(bool(rig.flags[1]&0x40)!=bool(rig.flags[1]&8)) {
    apply_mirror(rig);
    rig.flags[1]^=8;
  }
}
inline void materialize(Rig& rig) { // 01115EA0, supported existing representations
  mirror_gate(rig);
  if(!(rig.flags[1]&4)) {
    if(rig.flags[1]&2) {
      rig.flags[1]|=4;
      for(auto& bone:rig.bones) {
        bone.matrix=matrix(bone.composed_rotation);
        bone.matrix[3]=bone.composed_translation;
        bone.matrix[3][3]=1;
      }
    } else if(rig.flags[1]&1) compose_matrices(rig);
    else throw std::domain_error("clip decode fallback not recovered here");
  }
  for(auto& bone:rig.bones) bone.cached_rotation=bone.local_rotation;
}
inline void mix(Rig& destination,Rig& a,Rig& b,float weight_b,bool translate_all) { // 01115520
  if(!std::isfinite(weight_b) || weight_b<0 || weight_b>1)
    throw std::domain_error("blend weight outside [0,1]");
  if(destination.flags[3]) destination.flags[1]|=0x40;
  else destination.flags[1]&=~0x40u;
  mirror_gate(a); mirror_gate(b);
  ensure_local(a); ensure_local(b);
  destination.flags[1]=(destination.flags[1]&0xc0)|1;
  for(unsigned i=0;i<bone_count;++i) {
    auto& d=destination.bones[i];
    d.local_rotation=blend(a.bones[i].local_rotation,b.bones[i].local_rotation,weight_b);
    d.local_translation=(translate_all || d.parent<0)
      ? linear(a.bones[i].local_translation,b.bones[i].local_translation,sub(1,weight_b))
      : a.bones[i].local_translation;
  }
}
} // namespace pes3_pose
