#pragma once
// Clip 741: original 016D2088..016D2110 and five original signed-16 points.
// Unlike the other published static tracks, this clip reads context+0x41C.
// The input is a source-space context field, not an assumed height in metres.
#include "bind_arithmetic.hpp"

namespace pes3_events {
struct Anchor741 {
  std::int16_t xyz[3]{};
  std::uint16_t reference_index=7;
  std::uint32_t choice=0;
};
inline Anchor741 anchor_741(float context_y, const pes3_pose::BindArithmetic& math={}) {
  if(!std::isfinite(context_y)) throw std::domain_error("finite anchor context required");
  const float difference=math.fs(-209.0f,context_y);
  if(difference < -2147483648.0f || difference >= 2147483648.0f)
    throw std::domain_error("anchor difference outside signed-word conversion");
  const auto delta=static_cast<std::int32_t>(difference); // original CVT.W.S truncates
  const unsigned choice=delta>=37?0:delta>=13?1:delta>=-16?2:delta>=-51?3:4;
  constexpr std::int16_t points[5][3]={
    {-70,-265,-156},{-55,-235,-157},{-38,-209,-164},{-20,-178,-173},{11,-149,-177}
  };
  Anchor741 out;
  out.choice=choice;
  std::memcpy(out.xyz,points[choice],sizeof(out.xyz));
  return out;
}
} // namespace pes3_events
