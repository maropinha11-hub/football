"""Owned integer ABI for the recovered locomotion speed tail."""
import ctypes as C

class Input(C.Structure):
    _fields_ = [('current_amplitude', C.c_int32), ('selected_amplitude', C.c_int32),
        ('roster_ae', C.c_uint16), ('attribute_124', C.c_uint8), ('mode_phase_5', C.c_uint8),
        ('mode_2', C.c_uint8), ('reserved', C.c_uint8 * 3), ('profile_flag', C.c_int32)]

assert C.sizeof(Input) == 20
SOURCE = '''#include "locomotion_speed.hpp"
static_assert(sizeof(pes3_selection::SpeedInput)==20,"speed ABI mismatch");
extern "C" int step_speed(const pes3_selection::SpeedInput* input) {
  return pes3_selection::step_speed(*input);
}
'''

def configure(library):
    library.step_speed.argtypes = [C.POINTER(Input)]
    library.step_speed.restype = C.c_int32
    return library
