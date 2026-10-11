#pragma once
// Original 0116AFE0..0116B078. Source phase units are retained; no assumed fps.
// A marker is eligible in the asymmetric window (-step/2, +step/2].
// This is temporal eligibility only, not proof of a foot/head or ball contact.
#include "bind_arithmetic.hpp"

namespace pes3_events {
struct PhaseGate {
  float phase=0, step=0;
  std::uint8_t blend_window=0, blend_tick=0, cycle_fix=0;
};
inline bool phase_gate(const PhaseGate& input, std::int32_t marker,
                       const pes3_pose::BindArithmetic& math={}) {
  if(!std::isfinite(input.phase) || !std::isfinite(input.step))
    throw std::domain_error("finite animation phase and step required");
  if((input.blend_window || input.cycle_fix) && !input.blend_tick) return false;
  const float target=math.rounded(static_cast<double>(marker));
  const float half=math.divide(input.step,2);
  const float delta=math.fs(input.phase,target);
  return delta<=half && !(delta<=-half);
}
} // namespace pes3_events
