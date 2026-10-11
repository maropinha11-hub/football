"""Owned animation-marker predicate ABI; source phase units remain unchanged."""
import ctypes as C


class Input(C.Structure):
    _fields_ = [('phase', C.c_float), ('step', C.c_float),
                ('blend_window', C.c_uint8), ('blend_tick', C.c_uint8),
                ('cycle_fix', C.c_uint8), ('reserved', C.c_uint8)]


class Anchor741(C.Structure):
    _fields_ = [('xyz', C.c_int16 * 3), ('reference_index', C.c_uint16), ('choice', C.c_uint32)]


SOURCE = '''#include "animation_events.hpp"
#include "ball_anchor_741.hpp"
static_assert(sizeof(pes3_events::PhaseGate)==12,"phase gate ABI");
static_assert(sizeof(pes3_events::Anchor741)==12,"anchor 741 ABI");
extern "C" int owned_phase_gate(const pes3_events::PhaseGate* input,
    std::int32_t marker,unsigned chop,unsigned* output) {
  if(!input||!output||chop>1)return 0;
  try {
    const unsigned result=pes3_events::phase_gate(*input,marker,pes3_pose::BindArithmetic{bool(chop)});
    *output=result;return 1;
  }catch(const std::exception&){return 0;}
}
extern "C" int owned_anchor_741(float context,unsigned chop,pes3_events::Anchor741* output) {
  if(!output||chop>1)return 0;
  try {
    const auto result=pes3_events::anchor_741(context,pes3_pose::BindArithmetic{bool(chop)});
    *output=result;return 1;
  }catch(const std::exception&){return 0;}
}
'''


def configure(lib):
    lib.owned_phase_gate.argtypes = [C.POINTER(Input), C.c_int32, C.c_uint, C.POINTER(C.c_uint)]
    lib.owned_phase_gate.restype = C.c_int
    lib.owned_anchor_741.argtypes = [C.c_float, C.c_uint, C.POINTER(Anchor741)]
    lib.owned_anchor_741.restype = C.c_int
    return lib
