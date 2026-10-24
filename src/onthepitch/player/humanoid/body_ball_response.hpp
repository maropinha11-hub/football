#pragma once
#include "../../../pes3/native_pose.hpp"
#include <algorithm>
#include <cmath>

namespace football_contacts {
// Coulomb friction is limited by the normal impulse. Multiplying tangent
// velocity on every simulation tick made a falling ball stick to a back or
// thigh even when there was almost no normal load.
inline pes3::Point bodyResponse(pes3::Point relative,pes3::Point normal,bool cushion) {
  const float inward=pes3::dotPoint(relative,normal);
  if(inward>=0)return relative;
  const float restitution=cushion?.035f:.18f;
  const auto tangent=pes3::subtractPoint(relative,pes3::scalePoint(normal,inward));
  const float speed=std::sqrt(pes3::dotPoint(tangent,tangent));
  const float friction=(cushion?.50f:.22f)*(1+restitution)*-inward;
  const float keep=std::max(0.f,1-friction/std::max(.00001f,speed));
  return pes3::addPoint(pes3::scalePoint(tangent,keep),pes3::scalePoint(normal,-restitution*inward));
}
}
