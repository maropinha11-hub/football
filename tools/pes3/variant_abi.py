"""Owned ABI for 28/35/48/864, preserving phase vs encoded transitions."""
import ctypes as C
from selection_abi import Input as CommonInput, Decision as CommonDecision

class Input(C.Structure):
    _fields_ = [('common', CommonInput), ('near_squared_distance', C.c_uint32), ('flags_1b0', C.c_uint32),
        ('amplitude_120', C.c_int32), ('current_frame', C.c_float), ('configuration_step', C.c_float)] + \
        [(n, C.c_uint16) for n in ('body_input_difference', 'roster_ac', 'roster_ae')] + \
        [(n, C.c_uint8) for n in ('roster_ab', 'roster_cc', 'attribute_12c', 'auxiliary_105', 'auxiliary_133',
            'timing_byte', 'mode_phase_5', 'mode_2', 'fpu_rounding', 'division_rounding')] + \
        [('reserved', C.c_uint16), ('profile_flag', C.c_int32)]

class Decision(C.Structure):
    _fields_ = [('decision', CommonDecision), ('flags_1a0', C.c_uint32), ('comparison_frame', C.c_float),
        ('animation_rate', C.c_float), ('encoded_start', C.c_int32)] + \
        [(n, C.c_uint8) for n in ('auxiliary_105', 'auxiliary_133', 'phase_130', 'writes', 'transition_kind')] + \
        [('reserved', C.c_uint8 * 3)]

assert C.sizeof(Input) == 88 and C.sizeof(Decision) == 56
SOURCE = '''#include "locomotion_variants.hpp"
static_assert(sizeof(pes3_selection::VariantInput)==88 && sizeof(pes3_selection::VariantDecision)==56,"variant ABI mismatch");
extern "C" int select_variant(const pes3_selection::VariantInput* input,pes3_selection::VariantDecision* output) {
  if(!input || !output) return 0;
  return pes3_selection::select_variant(*input,*output);
}
'''

def configure(library):
    library.select_variant.argtypes = [C.POINTER(Input), C.POINTER(Decision)]
    library.select_variant.restype = C.c_int
    return library
