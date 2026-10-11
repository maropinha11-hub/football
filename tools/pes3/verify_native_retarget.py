#!/usr/bin/env python3
"""Check physical limb directions and support with the actual native mesh bind."""
import argparse
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import struct
from runtime_abi import build as build_bank,Frame
from native_retarget_abi import (build as build_adapter,from_log,NativePose,SourceRotations,
    SourcePoints,Rotation,Point,PARENTS,CHILDREN,SOURCE_CHILDREN,globals_for,rotate,direction)

ROOT=Path(__file__).resolve().parents[2]
def floats(words):return struct.unpack('<4f',struct.pack('<4I',*words))
def rotations(frame):return SourceRotations(*(Rotation(*floats(b.composed_rotation))for b in frame.rig.bones))
def points(frame):
    fit=1.8/670.5759
    return SourcePoints(*(Point(p[0]*fit,p[2]*fit,-p[1]*fit)
                          for p in (floats(b.composed_translation)for b in frame.rig.bones)))
def norm(v):return math.sqrt(sum(a*a for a in v))
def unit(v):return [a/norm(v)for a in v]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--engine-log',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    banklib,_=build_bank(args.output);adapter=build_adapter(args.output);bind=from_log(args.engine_log)
    bank=banklib.bank_create();cases=0;max_direction=0;max_length=0;max_fk=0;min_floor=100;max_height=0
    raw=args.bundle.read_bytes();count=struct.unpack_from('<I',raw,8)[0]
    try:
        assert banklib.bank_load(bank,str(args.bundle.resolve()).encode())
        reference=Frame();assert banklib.bank_sample(bank,47,0,C.byref(reference))
        qref=rotations(reference);pref=points(reference)
        for clip in range(count):
            duration=struct.unpack_from('<f',raw,32+16*clip+4)[0]
            # Entire bank, not only the handful of displayed/captured clips.
            for fraction in (0,1/6,1/3,1/2,2/3,5/6,1):
                phase=duration*fraction;frame=Frame();out=NativePose()
                assert banklib.bank_sample(bank,clip,phase,C.byref(frame)),(clip,phase)
                qs=rotations(frame);ps=points(frame)
                assert adapter.retarget(C.byref(qs),C.byref(qref),C.byref(ps),C.byref(pref),C.byref(bind),C.byref(out)),(clip,phase,'rejected')
                globals_=globals_for(out.local)
                for i,parent in enumerate(PARENTS):
                    assert abs(norm(out.local[i])-1)<2e-6,(clip,phase,i,'quaternion')
                    if parent>=0:
                        length_error=abs(math.dist(out.positions[i],out.positions[parent])-norm(bind.offsets[i]))
                        max_length=max(max_length,length_error)
                        assert length_error<2e-6,(clip,phase,i,'length',length_error)
                        offset=rotate(globals_[parent],bind.offsets[i])
                        expected=[out.positions[parent][a]+offset[a]for a in range(3)]
                        error=math.dist(out.positions[i],expected);max_fk=max(max_fk,error)
                        assert error<2e-6,(clip,phase,i,'FK',error)
                    if SOURCE_CHILDREN[i]>=0:
                        axis=bind.offsets[CHILDREN[i]]if CHILDREN[i]>=0 else (0,0,-1)
                        expected=unit(direction(ps,i));actual=unit(rotate(globals_[i],axis))
                        error=math.dist(expected,actual);max_direction=max(max_direction,error)
                        assert error<.00002,(clip,phase,i,'direction',error)
                floor=100
                for f,ankle in enumerate((9,12)):
                    for corner in range(8):
                        point=[(bind.footMax if corner&(1<<a)else bind.footMin)[f][a]for a in range(3)]
                        floor=min(floor,out.positions[ankle][2]+rotate(globals_[ankle],point)[2])
                min_floor=min(min_floor,floor);max_height=max(max_height,out.rootHeight)
                assert floor>=.00798,(clip,phase,'floor',floor)
                cases+=1
        result={'result':'passed','source_clips':count,'poses':cases,'directions_checked':cases*10,
                'maximum_unit_direction_error':max_direction,'maximum_bone_length_error':max_length,
                'maximum_forward_kinematics_error':max_fk,'minimum_foot_box_z':min_floor,'maximum_root_height':max_height,
                'native_bind':{'rotations':[list(q)for q in bind.rotations],'offsets':[list(p)for p in bind.offsets],
                               'foot_min':[list(p)for p in bind.footMin],'foot_max':[list(p)for p in bind.footMax]},
                'source_bank_sha256':hashlib.sha256(raw).hexdigest(),
                'adapter_sha256':hashlib.sha256((ROOT/'src/pes3/native_pose.hpp').read_bytes()).hexdigest(),
                'scope':'Physical segment alignment, native bone lengths, parent composition and ankle skin box support. Not original skin equivalence, all-vertex collision, live action selection, contact timing or full PES gameplay.'}
        (args.output/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items()if k!='native_bind'},indent=2))
    finally:banklib.bank_destroy(bank)

if __name__=='__main__':main()
