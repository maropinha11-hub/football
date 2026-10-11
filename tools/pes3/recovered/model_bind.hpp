#pragma once
// 0113A1C0 / 01116190 / 01115B80 / 01113A10 on canonical zeroed storage.
// Source model matrices and owned indices, never guest pointers or cached poses.
// Explicit nearest/chop finite binary32 profiles; no scale/axis/clock/contact assumption.
#include "bind_arithmetic.hpp"

namespace pes3_pose {
struct ModelBind {
  Rig pose{};
  std::array<Vector,bone_count> channel_rotation{}, channel_translation{};
};
inline Matrix rigid_inverse(const Matrix& m,BindArithmetic math={}) { // 01093E60: transpose, not determinant inversion
  Matrix out{};
  for(unsigned col=0;col<3;++col)
    for(unsigned row=0;row<3;++row) out[col][row]=m[row][col];
  out[3][3]=1;
  for(unsigned row=0;row<3;++row) {
    float acc=math.vm(out[0][row],m[3][0]);
    acc=math.va(acc,math.vm(out[1][row],m[3][1]));
    acc=math.va(acc,math.vm(out[2][row],m[3][2]));
    out[3][row]=math.vs(0,acc);
  }
  return out;
}
inline Matrix matrix_product(const Matrix& a,const Matrix& b,BindArithmetic math={}) { // 01093D48
  Matrix out{};
  for(unsigned col=0;col<4;++col) for(unsigned row=0;row<4;++row) {
    float acc=math.vm(a[0][row],b[col][0]);
    acc=math.va(acc,math.vm(a[1][row],b[col][1]));
    acc=math.va(acc,math.vm(a[2][row],b[col][2]));
    out[col][row]=math.va(acc,math.vm(a[3][row],b[col][3]));
  }
  return out;
}
inline Vector reference_mirror_correction(Vector current,Vector paired,BindArithmetic math={}) { // 01113B28..C7C
  const auto q=math.product(conjugate(current),paired);
  if(!(q[3]<0.9f) || (std::abs(q[0])<0.01f && std::abs(q[2])<0.01f)) return {0,0,0,1};
  // The initializer calls original sin/cos only at the fixed float 0x3FC90FDB
  // (pi/2). These are its verified outputs, not host libm approximations.
  std::uint32_t cosine_bits=0xb33bbe2e; float cosine;
  std::memcpy(&cosine,&cosine_bits,4);
  const float sine=math.chop ? 0.999999940395355224609375f : 1.0f;
  if(std::abs(q[0])<0.01f && std::abs(q[1])<0.01f) return {sine,0,0,cosine};
  return {0,0,sine,cosine};
}
inline ModelBind initialize_model(const std::array<Matrix,bone_count>& matrices,
    const std::array<std::int32_t,bone_count>& parents,
    const std::array<std::int32_t,bone_count>& pairs,BindArithmetic math={}) {
  ModelBind result{};
  for(unsigned i=0;i<bone_count;++i) {
    auto& b=result.pose.bones[i]; b.parent=parents[i];b.mirror=pairs[i];
    b.matrix=matrices[i];
    for(const auto& column:b.matrix) for(float v:column)
      if(!std::isfinite(v)) throw std::domain_error("nonfinite source matrix");
    if(b.matrix[0][3]!=0 || b.matrix[1][3]!=0 || b.matrix[2][3]!=0 || b.matrix[3][3]!=1)
      throw std::domain_error("nonaffine source matrix");
  }
  validate(result.pose);
  for(unsigned i=0;i<bone_count;++i) {
    auto& b=result.pose.bones[i];
    const auto local=b.parent<0 ? b.matrix : matrix_product(rigid_inverse(matrices[b.parent],math),b.matrix,math);
    b.local_rotation=result.channel_rotation[i]=math.quaternion(local);
    b.local_translation=result.channel_translation[i]=local[3];
    b.local_translation[3]=result.channel_translation[i][3]=1;
    b.composed_rotation=math.quaternion(b.matrix);
    b.composed_translation=b.matrix[3];
  }
  for(auto& b:result.pose.bones) if(b.mirror>=0)
    b.mirror_correction=reference_mirror_correction(b.composed_rotation,result.pose.bones[b.mirror].composed_rotation,math);
  result.pose.flags={0,6,0,0};
  validate(result.pose); return result;
}
} // namespace pes3_pose
