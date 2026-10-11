#!/usr/bin/env python3
"""Verify the actual rotation adapter against independent matrix composition.

This tests an FPSoccer adaptation, not PES action selection or full gameplay.
The received source bank remains local and is not included in the report.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from runtime_abi import build,Frame

ROOT=Path(__file__).resolve().parents[2]
Rotation=C.c_float*4
Source=Rotation*19
Native=Rotation*13
MAPPING=(0,8,16,12,14,11,13,3,5,7,2,4,6)
PARENTS=(-1,0,1,1,3,1,5,0,7,8,0,10,11)
NAMES=('body','middle','neck','left_shoulder','left_elbow','right_shoulder','right_elbow',
       'left_thigh','left_knee','left_ankle','right_thigh','right_knee','right_ankle')
BASIS=((1,0,0),(0,0,1),(0,-1,0))
IDENTITY=((1,0,0),(0,1,0),(0,0,1))

def floats(words):return struct.unpack('<4f',struct.pack('<4I',*words))
def rotations(frame):return Source(*(Rotation(*floats(b.composed_rotation))for b in frame.rig.bones))
def transpose(a):return tuple(zip(*a))
def multiply(a,b):return tuple(tuple(sum(a[r][k]*b[k][c]for k in range(3))for c in range(3))for r in range(3))
def matrix(q):
    length=sum(float(v)**2 for v in q)**.5;x,y,z,w=(v/length for v in q)
    return ((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),
            (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),
            (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)))
def quaternion_product(a,b):
    x,y,z,w=a;X,Y,Z,W=b
    return (w*X+x*W+y*Z-z*Y,w*Y+y*W+z*X-x*Z,w*Z+z*W+x*Y-y*X,w*W-x*X-y*Y-z*Z)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    banklib,_=build(args.output)
    cpp=args.output/'native_pose_abi.cpp'
    cpp.write_text('#include "native_pose.hpp"\nextern "C" int adapt(const pes3::SourceRotations* c,const pes3::SourceRotations* r,const pes3::NativeRotations* b,pes3::NativeRotations* o) { return pes3::adaptNativePose(*c,*r,*b,*o); }\n')
    library=args.output/'native_pose_abi.so'
    subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off','-shared','-fPIC',
                    '-I'+str(ROOT/'src/pes3'),str(cpp),'-o',str(library)],check=True)
    adapter=C.CDLL(str(library));adapter.adapt.argtypes=[C.POINTER(Source),C.POINTER(Source),C.POINTER(Native),C.POINTER(Native)]
    adapter.adapt.restype=C.c_int
    bank=banklib.bank_create()
    try:
        assert banklib.bank_load(bank,str(args.bundle.resolve()).encode()),'source bank rejected'
        neutral=Frame();assert banklib.bank_sample(bank,47,0,C.byref(neutral))
        reference=rotations(neutral)
        # Confirm displayed branch sides using received source geometry.
        points=[floats(b.composed_translation)for b in neutral.rig.bones]
        assert points[3][0]>0>points[2][0] and points[12][0]>0>points[11][0]
        neutral_path=ROOT/'data/media/animations/base.anim.util'
        native_keys={}
        for line in neutral_path.read_text().splitlines():
            words=line.split(',')
            if words[0]in NAMES:native_keys[words[0]]=tuple(map(float,words[2:6]))
        native_globals=[]
        for i,name in enumerate(NAMES):
            q=native_keys[name]
            native_globals.append(q if PARENTS[i]<0 else quaternion_product(native_globals[PARENTS[i]],q))
        native=Native(*(Rotation(*q)for q in native_globals))
        durations=[];raw=args.bundle.read_bytes();count=struct.unpack_from('<I',raw,8)[0]
        for clip in range(count):durations.append(struct.unpack_from('<f',raw,32+16*clip+4)[0])
        maximum=0.;cases=0
        for clip,duration in enumerate(durations):
            for phase in (0,duration*.5,duration):
                frame=Frame();assert banklib.bank_sample(bank,clip,phase,C.byref(frame)),(clip,phase)
                current=rotations(frame);out=Native()
                assert adapter.adapt(C.byref(current),C.byref(reference),C.byref(native),C.byref(out)),(clip,phase)
                globals_out=[]
                for i,q in enumerate(out):
                    assert abs(sum(float(v)**2 for v in q)-1)<2e-6,(clip,phase,i)
                    local=matrix(q);parent=IDENTITY if PARENTS[i]<0 else globals_out[PARENTS[i]]
                    actual=multiply(parent,local);globals_out.append(actual)
                    bone=MAPPING[i]
                    delta=multiply(matrix(current[bone]),transpose(matrix(reference[bone])))
                    expected=multiply(multiply(multiply(BASIS,delta),transpose(BASIS)),matrix(native[i]))
                    error=max(abs(actual[r][c]-expected[r][c])for r in range(3)for c in range(3))
                    assert error<4e-6,(clip,phase,i,error)
                    maximum=max(maximum,error)
                cases+=1
        receipt={'result':'passed','cases':cases,'source_clips':count,'target_rotations':cases*13,
                 'maximum_matrix_absolute_error':maximum,'source_reference':{'clip':47,'phase':0},
                 'native_reference_file':'data/media/animations/base.anim.util',
                 'native_reference_sha256':hashlib.sha256(neutral_path.read_bytes()).hexdigest(),
                 'source_bank_sha256':hashlib.sha256(raw).hexdigest(),'mapping':dict(zip(NAMES,MAPPING)),
                 'source_positive_x_branches_confirmed':[3,12],
                 'adapter_sha256':hashlib.sha256((ROOT/'src/pes3/native_pose.hpp').read_bytes()).hexdigest(),
                 'scope':'Independent matrix check of calibrated world rotation deltas and native parent collapse. Not source mesh equivalence, bone translations, original preferred-foot identification, live selection, cadence, blending, contacts or full gameplay.'}
        (args.output/'validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt,indent=2))
    finally:banklib.bank_destroy(bank)

if __name__=='__main__':main()
