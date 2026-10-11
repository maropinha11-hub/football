"""Numeric ABI shared by semantic selector checks; no source game dependency."""
import ctypes as C

class Input(C.Structure):
    _fields_ = [(n, C.c_int32) for n in ('initial_amplitude', 'current_amplitude', 'ball_amplitude', 'chase_amplitude')] + \
        [(n, C.c_uint32) for n in ('state_flags', 'direction_mask')] + \
        [(n, C.c_uint16) for n in ('body_heading', 'movement_heading', 'clip', 'substate', 'turn_heading')] + \
        [(n, C.c_uint8) for n in ('player_id', 'context_player', 'attribute_124', 'phase_130', 'auxiliary_134', 'chase_gate', 'clip_restart')] + \
        [('reserved', C.c_uint8 * 3)]

class Decision(C.Structure):
    _fields_ = [('selected_amplitude', C.c_int32), ('amplitude_before_speed', C.c_int32), ('frame_override', C.c_float)] + \
        [(n, C.c_uint16) for n in ('substate', 'turn_heading', 'requested_clip', 'reserved16')] + \
        [('start_frame', C.c_uint32)] + \
        [(n, C.c_uint8) for n in ('auxiliary_134', 'change_clip', 'refresh_window', 'writes')] + [('reserved32', C.c_uint32)]

assert C.sizeof(Input) == 44 and C.sizeof(Decision) == 32
SOURCE = '''#include "locomotion_selection.hpp"
static_assert(sizeof(pes3_selection::Input)==44 && sizeof(pes3_selection::Decision)==32,"selection ABI mismatch");
extern "C" int select_locomotion(const pes3_selection::Input* input,pes3_selection::Decision* output) {
  if(!input || !output) return 0;
  return static_cast<int>(pes3_selection::select(*input,*output));
}
'''

def configure(library):
    library.select_locomotion.argtypes = [C.POINTER(Input), C.POINTER(Decision)]
    library.select_locomotion.restype = C.c_int
    return library
