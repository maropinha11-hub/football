"""Numeric ABI for the recovered 61/62/63 branches."""
import ctypes as C
from selection_abi import Input as CommonInput, Decision as CommonDecision

class Input(C.Structure):
    _fields_ = [('common', CommonInput), ('near_squared_distance', C.c_uint32), ('cap_squared_distance', C.c_uint32),
        ('prediction_y_7cc', C.c_float), ('roster_a3', C.c_uint8), ('timing_byte', C.c_uint8),
        ('auxiliary_105', C.c_uint8), ('reserved', C.c_uint8)]

class Decision(C.Structure):
    _fields_ = [('decision', CommonDecision), ('auxiliary_105', C.c_uint8), ('phase_130', C.c_uint8),
               ('writes', C.c_uint8), ('reserved', C.c_uint8)]

assert C.sizeof(Input) == 60 and C.sizeof(Decision) == 36
SOURCE = '''#include "locomotion_special.hpp"
static_assert(sizeof(pes3_selection::SpecialInput)==60 && sizeof(pes3_selection::SpecialDecision)==36,"special ABI mismatch");
extern "C" int select_special(const pes3_selection::SpecialInput* input,pes3_selection::SpecialDecision* output) {
  if(!input || !output) return 0;
  return pes3_selection::select_special(*input,*output);
}
'''

def configure(library):
    library.select_special.argtypes = [C.POINTER(Input), C.POINTER(Decision)]
    library.select_special.restype = C.c_int
    return library
