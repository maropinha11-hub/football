"""Owned forecast/decision ABI for recovered locomotion prediction."""
import ctypes as C

class Input(C.Structure):
    _fields_ = [('player_xz', C.c_float * 2), ('position_divisor', C.c_float), ('roster_a3', C.c_uint8),
               ('fpu_rounding', C.c_uint8), ('division_rounding', C.c_uint8), ('sqrt_rounding', C.c_uint8)]
class Sample(C.Structure):
    _fields_ = [('xyz', C.c_float * 3), ('validity', C.c_int32)]
class Decision(C.Structure):
    _fields_ = [('amplitude', C.c_int32), ('sample_index', C.c_uint16), ('reserved', C.c_uint16), ('distance_truncated', C.c_int32)]
class GateInput(C.Structure):
    _fields_ = [('other_squared_distance', C.c_uint32), ('ball_axis_2c', C.c_float), ('prediction_y_7b4', C.c_float),
               ('action_input_heading', C.c_uint16), ('body_heading', C.c_uint16), ('roster_a3', C.c_uint8), ('reserved', C.c_uint8 * 3)]
assert C.sizeof(Input) == 16 and C.sizeof(Sample) == 16 and C.sizeof(Decision) == 12 and C.sizeof(GateInput) == 20
SOURCE = '''#include "locomotion_prediction.hpp"
static_assert(sizeof(pes3_motion::ChaseInput)==16 && sizeof(pes3_motion::ForecastSample)==16 && sizeof(pes3_motion::ChaseDecision)==12 && sizeof(pes3_motion::ChaseGateInput)==20,"prediction ABI mismatch");
extern "C" int predict_chase(const pes3_motion::ChaseInput* input,const pes3_motion::ForecastSample* samples,unsigned count,pes3_motion::ChaseDecision* output) {
  if(!input || !output) return 0;
  return pes3_motion::predict_chase(*input,samples,count,*output);
}
extern "C" int chase_gate(const pes3_motion::ChaseGateInput* input,unsigned char* output) {
  if(!input || !output) return 0;
  return pes3_motion::chase_gate(*input,*output);
}
'''

def configure(library):
    library.predict_chase.argtypes = [C.POINTER(Input), C.POINTER(Sample), C.c_uint, C.POINTER(Decision)]
    library.predict_chase.restype = C.c_int
    library.chase_gate.argtypes = [C.POINTER(GateInput), C.POINTER(C.c_uint8)]
    library.chase_gate.restype = C.c_int
    return library
