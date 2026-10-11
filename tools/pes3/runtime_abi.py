"""Build the actual production source sampler; no alternative pose algorithm."""
import ctypes as C
from pathlib import Path
import subprocess

from rig import Rig

class Track(C.Structure):
    _fields_=[('rotation_a',C.c_float*4),('rotation_b',C.c_float*4),
              ('translation_a',C.c_float*4),('translation_b',C.c_float*4),
              ('rotation_duration',C.c_float),('rotation_elapsed',C.c_float),
              ('translation_duration',C.c_float),('translation_elapsed',C.c_float)]
class Channels(C.Structure):
    _fields_=[('clamped_time',C.c_float),('interval_index',C.c_uint),('channel_count',C.c_uint),
              ('reserved',C.c_uint),('bones',Track*19)]
class BonePose(C.Structure):
    _fields_=[('rotation',C.c_float*4),('translation',C.c_float*4)]
class Pose(C.Structure):
    _fields_=[('bones',BonePose*19)]
class Frame(C.Structure):
    _fields_=[('channels',Channels),('local',Pose),('rig',Rig)]
assert C.sizeof(Frame)==5504

SOURCE='''#include "animation_bank.hpp"
static_assert(sizeof(pes3::Frame)==5504,"runtime frame ABI");
extern "C" void* bank_create() { return new pes3::AnimationBank; }
extern "C" void bank_destroy(void* bank) { delete static_cast<pes3::AnimationBank*>(bank); }
extern "C" int bank_load(void* bank,const char* path) {
  std::string error;return bank&&path&&static_cast<pes3::AnimationBank*>(bank)->load(path,error);
}
extern "C" unsigned bank_count(void* bank) { return static_cast<pes3::AnimationBank*>(bank)->count(); }
extern "C" int bank_sample(void* bank,unsigned clip,float time,pes3::Frame* out) {
  return bank&&out&&static_cast<pes3::AnimationBank*>(bank)->sample(clip,time,*out);
}
extern "C" int bank_inspect(const unsigned char* data,unsigned size,unsigned* count) {
  if(!data||!count)return 0;
  std::vector<unsigned char> input(data,data+size);
  std::vector<pes3::Clip> clips;std::string error;
  if(!pes3::AnimationBank::inspect(input,clips,error))return 0;
  *count=clips.size();return 1;
}
extern "C" int playback_test(float initial,float dt,float rate,float duration,float* phase,unsigned* playing) {
  if(!phase||!playing)return 0;
  pes3::Playback p;p.phase=initial;
  try {p.advance(dt,rate,duration);*phase=p.phase;*playing=p.playing;return 1;}
  catch(const std::exception&){return 0;}
}
'''

def build(output):
    root=Path(__file__).resolve().parents[2]
    output.mkdir(parents=True,exist_ok=True)
    source=output/'runtime_abi.cpp';source.write_text(SOURCE)
    path=output/'libpes3_runtime.so'
    cmd=['g++','-std=c++14','-O2','-Wall','-Wextra','-fno-fast-math','-ffp-contract=off',
         '-shared','-fPIC','-I'+str(root/'src/pes3'),str(source),
         *map(str,(root/'src/pes3'/n for n in ('animation_bank.cpp','pes_animation_pose.cpp','pes_pose_math.cpp'))),
         '-o',str(path)]
    subprocess.run(cmd,check=True)
    lib=C.CDLL(str(path.resolve()))
    lib.bank_create.restype=C.c_void_p
    lib.bank_destroy.argtypes=[C.c_void_p]
    lib.bank_load.argtypes=[C.c_void_p,C.c_char_p];lib.bank_load.restype=C.c_int
    lib.bank_count.argtypes=[C.c_void_p];lib.bank_count.restype=C.c_uint
    lib.bank_sample.argtypes=[C.c_void_p,C.c_uint,C.c_float,C.POINTER(Frame)]
    lib.bank_sample.restype=C.c_int
    lib.bank_inspect.argtypes=[C.POINTER(C.c_ubyte),C.c_uint,C.POINTER(C.c_uint)]
    lib.bank_inspect.restype=C.c_int
    lib.playback_test.argtypes=[C.c_float]*4+[C.POINTER(C.c_float),C.POINTER(C.c_uint)]
    lib.playback_test.restype=C.c_int
    lib.pes_animation_channels_decode.argtypes=[C.POINTER(C.c_ubyte),C.c_uint,C.c_float,C.POINTER(Channels)]
    lib.pes_animation_channels_decode.restype=C.c_int
    lib.pes_animation_pose_evaluate.argtypes=[C.POINTER(Channels),C.POINTER(Pose)]
    lib.pes_animation_pose_evaluate.restype=C.c_int
    return lib,cmd
