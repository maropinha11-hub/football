"""Check the production pose adapter's hierarchy, axes and atomic rejection."""
import ctypes as C
import math
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=r'''
#include "native_pose.hpp"
extern "C" int adapt(const pes3::SourceRotations* current,const pes3::SourceRotations* reference,
 const pes3::NativeRotations* base,pes3::NativeRotations* out) {
 return pes3::adaptNativePose(*current,*reference,*base,*out);
}
'''
Rotation=C.c_float*4
Source=Rotation*19
Native=Rotation*13
PARENTS=(-1,0,1,1,3,1,5,0,7,8,0,10,11)

def identity(kind): return kind(*(Rotation(0,0,0,1)for _ in range(len(kind()))))
def axis(axis,angle):
    q=[0.,0.,0.,math.cos(angle/2)];q[axis]=math.sin(angle/2);return Rotation(*q)
def product(a,b):
    x,y,z,w=a;X,Y,Z,W=b
    return Rotation(w*X+x*W+y*Z-z*Y,w*Y+y*W+z*X-x*Z,w*Z+z*W+x*Y-y*X,w*W-x*X-y*Y-z*Z)
def inverse(q):return Rotation(-q[0],-q[1],-q[2],q[3])
def global_rotations(local):
    out=Native()
    for i,p in enumerate(PARENTS):out[i]=local[i]if p<0 else product(out[p],local[i])
    return out

class NativePoseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory(prefix='pes3-native-pose-')
        path=Path(cls.folder.name);(path/'adapter.cpp').write_text(SOURCE)
        subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off',
                        '-shared','-fPIC','-I'+str(ROOT/'src/pes3'),str(path/'adapter.cpp'),'-o',str(path/'adapter.so')],check=True)
        cls.lib=C.CDLL(str(path/'adapter.so'));cls.lib.adapt.argtypes=[C.POINTER(Source),C.POINTER(Source),C.POINTER(Native),C.POINTER(Native)]
        cls.lib.adapt.restype=C.c_int
    @classmethod
    def tearDownClass(cls):cls.folder.cleanup()
    def same(self,a,b):
        self.assertGreater(abs(sum(x*y for x,y in zip(a,b))),.99999)
    def adapt(self,current,reference=None,base=None):
        out=Native();self.assertEqual(self.lib.adapt(C.byref(current),C.byref(reference or identity(Source)),C.byref(base or identity(Native)),C.byref(out)),1)
        for q in out:self.assertAlmostEqual(sum(x*x for x in q),1,places=5)
        return out
    def test_reference_preserves_native_pose_and_collapses_parents(self):
        local=Native(*(axis(i%3,.08*(i+1))for i in range(13)))
        source=Source(*(axis(i%3,.07*(i+1))for i in range(19)))
        out=self.adapt(source,source,global_rotations(local))
        for a,b in zip(local,out):self.same(a,b)
    def test_source_y_rotation_maps_to_negative_native_z(self):
        current=Source(*(axis(1,math.pi/2)for _ in range(19)))
        out=self.adapt(current);self.same(out[0],axis(2,-math.pi/2))
        for q in list(out)[1:]:self.same(q,(0,0,0,1))
    def test_parent_motion_is_not_applied_twice_to_elbow(self):
        source=identity(Source);source[11]=source[13]=axis(0,.7)
        out=self.adapt(source);self.same(out[3],axis(0,-.7));self.same(out[4],(0,0,0,1))
        for i in range(13):
            if i not in (3,):self.same(out[i],(0,0,0,1))
    def test_quaternion_sign_does_not_change_pose(self):
        current=Source(*(Rotation(0,0,0,-1)for _ in range(19)))
        for q in self.adapt(current):self.same(q,(0,0,0,1))
    def test_non_unit_inputs_are_normalized(self):
        source=Source(*(Rotation(0,0,0,2)for _ in range(19)))
        for q in self.adapt(source):self.same(q,(0,0,0,1))
    def test_invalid_source_reference_and_native_preserve_output(self):
        for collection in ('current','reference','base'):
            for bad in (float('nan'),float('inf'),0.):
                current=identity(Source);reference=identity(Source);base=identity(Native)
                data={'current':current,'reference':reference,'base':base}[collection]
                data[2]=Rotation(0,0,0,bad)
                out=Native(*(Rotation(42,43,44,45)for _ in range(13)));before=bytes(out)
                self.assertEqual(self.lib.adapt(C.byref(current),C.byref(reference),C.byref(base),C.byref(out)),0)
                self.assertEqual(bytes(out),before)

if __name__=='__main__':unittest.main()
