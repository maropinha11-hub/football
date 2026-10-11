"""Physical axes, bind calibration, length conservation and safe invalid input."""
import ctypes as C
import math
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/pes3'))
from native_retarget_abi import (build,NativeBind,NativePose,NativeRotations,NativePoints,Point,Rotation,
    SourcePoints,SourceRotations,PARENTS,CHILDREN,direction,globals_for,rotate)

def reference_points():
    p=SourcePoints()
    for i,v in {0:(0,0,1),2:(-.09,0,.95),3:(.09,0,.95),4:(-.09,-.05,.54),5:(.09,-.05,.54),
                6:(-.09,-.1,.09),7:(.09,-.1,.09),8:(0,0,1.1),16:(0,0,1.62),
                11:(-.2,0,1.57),12:(.2,0,1.57),13:(-.26,-.03,1.3),14:(.26,-.03,1.3),
                17:(-.24,-.15,1.06),18:(.24,-.15,1.06)}.items():p[i]=Point(*v)
    return p
def native_bind():
    offsets=((0,0,.96),(0,0,.15),(0,-.03,.5),(.16,-.01,.48),(-.01,0,-.33),(-.16,-.01,.48),
             (.01,0,-.33),(.087,0,-.01),(0,0,-.42),(0,-.04,-.44),(-.087,0,-.01),(0,0,-.42),(0,-.04,-.44))
    return NativeBind(NativeRotations(*(Rotation(0,0,0,1)for _ in range(13))),
                      NativePoints(*(Point(*v)for v in offsets)),
                      (Point*2)(Point(-.05,-.16,-.05),Point(-.05,-.16,-.05)),
                      (Point*2)(Point(.05,.08,.04),Point(.05,.08,.04)))
def identity():return SourceRotations(*(Rotation(0,0,0,1)for _ in range(19)))

class RetargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory(prefix='pes3-retarget-test-')
        cls.lib=build(Path(cls.folder.name))
    @classmethod
    def tearDownClass(cls):cls.folder.cleanup()
    def evaluate(self,points=None,rotations=None,bind=None):
        out=NativePose();p=points or reference_points();b=bind or native_bind()
        self.assertEqual(self.lib.retarget(C.byref(rotations or identity()),C.byref(identity()),
            C.byref(p),C.byref(reference_points()),C.byref(b),C.byref(out)),1)
        self.assert_physical(p,b,out)
        return out
    def assert_physical(self,p,b,out):
        qs=globals_for(out.local)
        for i,c in enumerate(CHILDREN):
            self.assertAlmostEqual(sum(v*v for v in out.local[i]),1,places=5)
            if c>=0:
                actual=rotate(qs[i],b.offsets[c]);expected=direction(p,i)
                na=math.sqrt(sum(v*v for v in actual));ne=math.sqrt(sum(v*v for v in expected))
                self.assertLess(math.dist([v/na for v in actual],[v/ne for v in expected]),2e-5)
            if PARENTS[i]>=0:
                self.assertAlmostEqual(math.dist(out.positions[i],out.positions[PARENTS[i]]),
                                       math.sqrt(sum(v*v for v in b.offsets[i])),places=5)
        lowest=10
        for f,ankle in enumerate((9,12)):
            for corner in range(8):
                point=[(b.footMax if corner&(1<<a)else b.footMin)[f][a]for a in range(3)]
                lowest=min(lowest,out.positions[ankle][2]+rotate(qs[ankle],point)[2])
        self.assertGreaterEqual(lowest,.00799)
    def test_bent_source_reference_is_not_mistaken_for_native_straight_bind(self):self.evaluate()
    def test_collapsed_spine_tracks_endpoints_with_independent_upper_body_rotation(self):
        p=reference_points();p[16]=Point(.12,-.12,1.6);p[18]=Point(.3,-.2,1.2)
        self.evaluate(p)
    def test_global_turn_keeps_hierarchy_and_segment_directions(self):
        p=reference_points()
        for i,v in enumerate(p):p[i]=Point(-v[1],v[0],v[2])
        q=SourceRotations(*(Rotation(0,-math.sqrt(.5),0,math.sqrt(.5))for _ in range(19)))
        self.evaluate(p,q)
    def test_antiparallel_limb_axes_remain_finite(self):
        p=reference_points();p[5]=Point(.09,0,1.4);p[7]=Point(.09,0,1.84)
        self.evaluate(p)
    def test_airborne_displacement_scales_by_measured_leg_lengths(self):
        first=self.evaluate();p=reference_points();b=native_bind()
        for i,v in enumerate(p):p[i]=Point(v[0],v[1],v[2]+.4)
        second=self.evaluate(p)
        native=sum(math.sqrt(sum(v*v for v in b.offsets[i]))for i in (8,9,11,12))
        rest=reference_points();source=sum(math.dist(rest[a],rest[c])for a,c in ((3,5),(5,7),(2,4),(4,6)))
        self.assertAlmostEqual(second.rootHeight-first.rootHeight,.4*native/source,places=5)
    def test_invalid_geometry_does_not_partially_modify_output(self):
        for invalid in ('nan_point','zero_segment','nan_foot','reversed_foot','zero_bind_segment','nan_rotation'):
            p=reference_points();b=native_bind();q=identity()
            if invalid=='nan_point':p[7][0]=float('nan')
            if invalid=='zero_segment':p[7]=p[5]
            if invalid=='nan_foot':b.footMin[0][0]=float('nan')
            if invalid=='reversed_foot':b.footMin[0][0]=1
            if invalid=='zero_bind_segment':b.offsets[8]=Point(0,0,0)
            if invalid=='nan_rotation':q[0][0]=float('nan')
            out=NativePose();C.memset(C.byref(out),42,C.sizeof(out));before=bytes(out)
            self.assertEqual(self.lib.retarget(C.byref(q),C.byref(identity()),C.byref(p),
                C.byref(reference_points()),C.byref(b),C.byref(out)),0,invalid)
            self.assertEqual(bytes(out),before,invalid)

if __name__=='__main__':unittest.main()
