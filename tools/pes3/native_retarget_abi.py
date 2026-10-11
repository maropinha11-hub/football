"""Exercise the production anatomical adapter, including actual engine bind data."""
import ctypes as C
import re
import subprocess
from pathlib import Path

Rotation=C.c_float*4
Point=C.c_float*3
SourceRotations=Rotation*19
SourcePoints=Point*19
NativeRotations=Rotation*13
NativePoints=Point*13
PARENTS=(-1,0,1,1,3,1,5,0,7,8,0,10,11)
MAPPING=(0,8,16,11,13,12,14,2,4,6,3,5,7)
CHILDREN=(1,2,-1,4,-1,6,-1,8,9,-1,11,12,-1)
SOURCE_CHILDREN=(8,16,-1,13,17,14,18,4,6,-1,5,7,-1)

class NativeBind(C.Structure):
    _fields_=[('rotations',NativeRotations),('offsets',NativePoints),('footMin',Point*2),('footMax',Point*2)]
class NativePose(C.Structure):
    _fields_=[('local',NativeRotations),('positions',NativePoints),('rootHeight',C.c_float),('maximumDirectionError',C.c_float)]
assert C.sizeof(NativeBind)==412 and C.sizeof(NativePose)==372

def build(output):
    root=Path(__file__).resolve().parents[2]
    output.mkdir(parents=True,exist_ok=True)
    cpp=output/'retarget_abi.cpp'
    cpp.write_text('''#include "native_pose.hpp"
extern "C" int retarget(const pes3::SourceRotations* c,const pes3::SourceRotations* r,
 const pes3::SourcePoints* p,const pes3::SourcePoints* s,const pes3::NativeBind* b,pes3::NativePose* o) {
 return pes3::retargetSkeleton(*c,*r,*p,*s,*b,*o);
}
extern "C" void basis_point(const pes3::Point* p,pes3::Point* out) {
 *out=pes3::sourcePointToNative(*p);
}
extern "C" void basis_rotation(pes3::Rotation* out) { *out=pes3::sourceToNativeBasis; }
''')
    path=output/'retarget_abi.so'
    subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off',
                    '-shared','-fPIC','-I'+str(root/'src/pes3'),str(cpp),'-o',str(path)],check=True)
    lib=C.CDLL(str(path))
    lib.retarget.argtypes=[C.POINTER(SourceRotations),C.POINTER(SourceRotations),C.POINTER(SourcePoints),
                          C.POINTER(SourcePoints),C.POINTER(NativeBind),C.POINTER(NativePose)]
    lib.retarget.restype=C.c_int
    lib.basis_point.argtypes=[C.POINTER(Point),C.POINTER(Point)]
    lib.basis_rotation.argtypes=[C.POINTER(Rotation)]
    return lib

def from_log(path):
    """Read the first complete character bind captured by the real mesh loader."""
    bind=NativeBind();bones=set();feet=set()
    for line in path.read_text().splitlines():
        m=re.fullmatch(r'PES3_BIND bone=(\d+) offset=\[([^]]+)\] rotation=\[([^]]+)\]',line)
        if m and int(m[1])not in bones:
            i=int(m[1]);bind.offsets[i]=Point(*map(float,m[2].split(',')))
            bind.rotations[i]=Rotation(*map(float,m[3].split(',')));bones.add(i)
        m=re.fullmatch(r'PES3_BIND_FOOT side=(\d+) min=\[([^]]+)\] max=\[([^]]+)\]',line)
        if m and int(m[1])not in feet:
            i=int(m[1]);bind.footMin[i]=Point(*map(float,m[2].split(',')))
            bind.footMax[i]=Point(*map(float,m[3].split(',')));feet.add(i)
        if len(bones)==13 and len(feet)==2:return bind
    raise ValueError('engine log has no complete skin bind')

def product(a,b):
    x,y,z,w=a;X,Y,Z,W=b
    return (w*X+x*W+y*Z-z*Y,w*Y+y*W+z*X-x*Z,w*Z+z*W+x*Y-y*X,w*W-x*X-y*Y-z*Z)
def rotate(q,p):
    # Independent quaternion multiplication, not the adapter's cross formula.
    return product(product(q,(*p,0)),(-q[0],-q[1],-q[2],q[3]))[:3]
def globals_for(local):
    out=[]
    for i,p in enumerate(PARENTS):out.append(tuple(local[i])if p<0 else product(out[p],local[i]))
    return out
def direction(points,i):
    if i==0:return tuple(points[8][a]-(points[2][a]+points[3][a])*.5 for a in range(3))
    return tuple(points[SOURCE_CHILDREN[i]][a]-points[MAPPING[i]][a]for a in range(3))
