#pragma once
// 01139E30: copy composed matrices, or scale each column by its own
// appearance coefficient. 0113C870: physics position -> render position.
// Retains original coordinate spaces; does not claim metres or native axes.
#include "bind_arithmetic.hpp"

namespace pes3_pose {
using RenderMatrices=std::array<Matrix,bone_count>;
using RenderScales=std::array<Vector,bone_count>;
inline RenderMatrices render_matrices(const RenderMatrices& source,const RenderScales* scales,
    unsigned count=bone_count,BindArithmetic math={}) {
  if(count>bone_count)throw std::domain_error("render bone count outside owned rig");
  RenderMatrices result{};
  for(unsigned i=0;i<count;++i) {
    for(const auto& column:source[i])for(float v:column)
      if(!std::isfinite(v))throw std::domain_error("nonfinite composed matrix");
    if(!scales) {result[i]=source[i];continue;}
    for(unsigned column=0;column<4;++column) {
      if(!std::isfinite((*scales)[i][column]))throw std::domain_error("nonfinite render scale");
      for(unsigned lane=0;lane<4;++lane)
        result[i][column][lane]=math.vm(source[i][column][lane],(*scales)[i][column]);
    }
    result[i][3][3]=1; // original explicit store after multiplying the W column
  }
  return result;
}
inline std::array<float,3> render_position(std::array<float,3> physics,BindArithmetic math={}) {
  for(float v:physics)if(!std::isfinite(v))throw std::domain_error("nonfinite physics position");
  return {math.fm(-0.2f,physics[0]),math.fm(0.2f,physics[1]),math.fm(0.2f,physics[2])};
}
} // namespace pes3_pose
