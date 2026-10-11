"""Owned ABI for consecutive direction/dispatch/speed, not a full PES frame."""
import ctypes as C
from direction_abi import Input as DirectionInput, Decision as DirectionDecision
from variant_abi import Input as VariantInput
from selection_abi import Decision as CommonDecision
from speed_abi import Input as SpeedInput

class Input(C.Structure):
    _fields_ = [('direction', DirectionInput), ('selection', VariantInput), ('cap_squared_distance', C.c_uint32),
        ('prediction_y_7cc', C.c_float), ('roster_a3', C.c_uint8), ('reserved', C.c_uint8 * 3), ('speed', SpeedInput)]
class Decision(C.Structure):
    _fields_ = [('direction', DirectionDecision), ('decision', CommonDecision), ('updated_amplitude', C.c_int32),
        ('flags_1a0', C.c_uint32), ('comparison_frame', C.c_float), ('encoded_start', C.c_int32), ('animation_rate', C.c_float)] + \
        [(n, C.c_uint8) for n in ('auxiliary_105', 'auxiliary_133', 'phase_130', 'writes', 'transition_kind')] + \
        [('reserved', C.c_uint8 * 3)]
assert C.sizeof(Input) == 160 and C.sizeof(Decision) == 80
SOURCE = '''#include "locomotion_chain.hpp"
static_assert(sizeof(pes3_selection::ChainInput)==160 && sizeof(pes3_selection::ChainDecision)==80,"chain ABI mismatch");
extern "C" int step_locomotion(const pes3_selection::ChainInput* input,pes3_selection::ChainDecision* output) {
  if(!input || !output) return 0;
  return pes3_selection::step_locomotion(*input,*output);
}
'''
def configure(lib):
    lib.step_locomotion.argtypes = [C.POINTER(Input), C.POINTER(Decision)]
    lib.step_locomotion.restype = C.c_int
    return lib
