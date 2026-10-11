"""Owned ABI for the recovered direction block, not original PS2 structs."""
import ctypes as C

class Input(C.Structure):
    _fields_ = [(n, C.c_float * 2) for n in ('player_xz', 'ball_far_xz', 'ball_near_xz')] + \
        [(n, C.c_uint16) for n in ('body_heading', 'movement_heading', 'ball_heading', 'turn_heading', 'clip', 'substate')] + \
        [('direction_mask', C.c_uint32)]

class Decision(C.Structure):
    _fields_ = [('near_squared_distance', C.c_uint32)] + [(n, C.c_uint16) for n in
        ('target_heading', 'body_heading', 'movement_heading', 'substate', 'ball_heading_span',
         'body_input_difference', 'body_target_difference', 'action_input_heading')]

assert C.sizeof(Input) == 40 and C.sizeof(Decision) == 20
SOURCE = '''#include "locomotion_direction.hpp"
static_assert(sizeof(pes3_motion::DirectionInput)==40 && sizeof(pes3_motion::DirectionDecision)==20,"direction ABI mismatch");
extern "C" int select_direction(const pes3_motion::DirectionInput* input,pes3_motion::DirectionDecision* output) {
  if(!input || !output) return 0;
  return pes3_motion::select_direction(*input,*output);
}
'''

def configure(library):
    library.select_direction.argtypes = [C.POINTER(Input), C.POINTER(Decision)]
    library.select_direction.restype = C.c_int
    return library
