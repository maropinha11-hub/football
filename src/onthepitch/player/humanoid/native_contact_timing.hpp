#pragma once
#include <cmath>
namespace football_contact {
// The native whole-player approach integrates to exactly its requested
// displacement. Future contact queries must integrate this same curve.
inline float approachWeight(unsigned frame,unsigned count){
  return count?1.f-.1f*std::cos(6.283185307179586f*frame/count):0.f;
}
}
