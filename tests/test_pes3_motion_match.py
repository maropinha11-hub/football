"""Hybrid matching: contact clock, safe FK blending, and incompatible fallback."""
import ctypes as C
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/pes3'))
from native_retarget_abi import NativeBind,NativePose,Point,Rotation,globals_for,rotate
from test_pes3_retarget import native_bind

class Request(C.Structure):
    _fields_=[('poses',NativePose*9),('contact',C.c_float),('contactBone',C.c_int)]
class Choice(C.Structure):
    _fields_=[('accepted',C.c_bool),('clip',C.c_uint),('sourceContact',C.c_float),('error',C.c_float),('mirrored',C.c_bool)]

SOURCE='''#include "motion_match.hpp"
static_assert(sizeof(pes3::MotionRequest)==sizeof(pes3::NativePose)*9+8,"request ABI");
extern "C" float warp(float t,float n,float s) {return pes3::warpPhase(t,n,s);}
extern "C" int rebuild(const pes3::NativeBind* b,pes3::NativePose* p,int support) {
 return pes3::rebuildPose(*b,*p,support);}
extern "C" int blend(const pes3::NativeBind* b,const pes3::NativePose* a,const pes3::NativePose* c,
 float w,pes3::NativePose* out) {return pes3::blendPose(*b,*a,*c,w,*out);}
extern "C" int mirror(const pes3::NativeBind* b,const pes3::NativePose* a,pes3::NativePose* out) {
 return pes3::mirrorPose(*b,*a,*out);}
struct State {pes3::AnimationBank bank;pes3::MotionMatcher matcher;};
extern "C" void* create(const char* path,const pes3::NativeBind* bind) {
 auto* p=new State;std::string error;
 if(!p->bank.load(path,error)||!p->matcher.initialize(p->bank,*bind)){delete p;return nullptr;}return p;}
extern "C" void destroy(void* state){delete static_cast<State*>(state);}
extern "C" unsigned candidates(void* state){return static_cast<State*>(state)->matcher.candidates();}
extern "C" void choose(void* state,const pes3::MotionRequest* request,pes3::MotionChoice* out) {
 *out=static_cast<State*>(state)->matcher.choose(*request);}
extern "C" int sample(void* state,const pes3::MotionChoice* choice,float time,float contact,pes3::NativePose* out) {
 return static_cast<State*>(state)->matcher.sample(*choice,time,contact,*out);}
'''

class MotionMatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory(prefix='pes3-hybrid-test-')
        cpp=Path(cls.folder.name)/'abi.cpp';cpp.write_text(SOURCE)
        output=Path(cls.folder.name)/'abi.so'
        subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra','-Werror',
                        '-fno-fast-math','-ffp-contract=off','-shared','-fPIC','-I'+str(ROOT/'src/pes3'),
                        str(cpp),*[str(ROOT/'src/pes3'/n)for n in
                        ('motion_match.cpp','animation_bank.cpp','pes_animation_pose.cpp','pes_pose_math.cpp')],
                        '-o',str(output)],check=True)
        cls.lib=C.CDLL(str(output));lib=cls.lib
        lib.warp.argtypes=[C.c_float]*3;lib.warp.restype=C.c_float
        lib.rebuild.argtypes=[C.POINTER(NativeBind),C.POINTER(NativePose),C.c_int]
        lib.blend.argtypes=[C.POINTER(NativeBind),C.POINTER(NativePose),C.POINTER(NativePose),C.c_float,C.POINTER(NativePose)]
        lib.mirror.argtypes=[C.POINTER(NativeBind),C.POINTER(NativePose),C.POINTER(NativePose)]
        lib.create.argtypes=[C.c_char_p,C.POINTER(NativeBind)];lib.create.restype=C.c_void_p
        lib.destroy.argtypes=[C.c_void_p];lib.candidates.argtypes=[C.c_void_p];lib.candidates.restype=C.c_uint
        lib.choose.argtypes=[C.c_void_p,C.POINTER(Request),C.POINTER(Choice)]
        lib.sample.argtypes=[C.c_void_p,C.POINTER(Choice),C.c_float,C.c_float,C.POINTER(NativePose)]
        cls.state=None
        path=os.environ.get('PES3_TEST_BANK')
        if path:
            cls.state=lib.create(path.encode(),C.byref(native_bind()))
            if not cls.state:raise RuntimeError('configured source bank failed to initialize')
    @classmethod
    def tearDownClass(cls):
        if cls.state:cls.lib.destroy(cls.state)
        cls.folder.cleanup()
    def pose(self,height=.96):
        pose=NativePose();pose.rootHeight=height
        for i in range(13):pose.local[i]=Rotation(0,0,0,1)
        self.assertEqual(self.lib.rebuild(C.byref(native_bind()),C.byref(pose),1),1)
        return pose
    def test_contact_clock_hits_native_event_and_preserves_endpoints(self):
        for contact in (.1,.25,.5,.9):
            for anchor in (.1875,.5,.8125):
                self.assertAlmostEqual(self.lib.warp(contact,contact,anchor),anchor,places=6)
                self.assertEqual(self.lib.warp(0,contact,anchor),0)
                self.assertEqual(self.lib.warp(1,contact,anchor),1)
                phases=[self.lib.warp(i/100,contact,anchor)for i in range(101)]
                self.assertEqual(phases,sorted(phases))
                self.assertLess(abs(self.lib.warp(contact-.00001,contact,anchor)-
                                    self.lib.warp(contact+.00001,contact,anchor)),.0002)
    def test_no_contact_uses_normalized_native_clock(self):
        for contact in (-1,0,1):
            self.assertAlmostEqual(self.lib.warp(.37,contact,.75),.37,places=6)
        self.assertEqual(self.lib.warp(-2,-1,.5),0)
        self.assertEqual(self.lib.warp(2,-1,.5),1)
    def test_blending_antipodal_rotations_preserves_lengths_and_support(self):
        a=self.pose();b=self.pose(.8);b.local[8]=Rotation(.5,0,0,math.sqrt(.75))
        for i in range(13):b.local[i]=Rotation(*(-v for v in b.local[i]))
        self.assertEqual(self.lib.rebuild(C.byref(native_bind()),C.byref(b),1),1)
        for weight in (0,.1,.5,.9,1):
            out=NativePose();bind=native_bind()
            self.assertEqual(self.lib.blend(C.byref(bind),C.byref(a),C.byref(b),weight,C.byref(out)),1)
            qs=globals_for(out.local)
            for i,parent in enumerate((-1,0,1,1,3,1,5,0,7,8,0,10,11)):
                if parent>=0:self.assertAlmostEqual(math.dist(out.positions[i],out.positions[parent]),
                            math.sqrt(sum(v*v for v in bind.offsets[i])),places=5)
            for foot,ankle in enumerate((9,12)):
                for corner in range(8):
                    p=[(bind.footMax if corner&(1<<axis)else bind.footMin)[foot][axis]for axis in range(3)]
                    self.assertGreaterEqual(out.positions[ankle][2]+rotate(qs[ankle],p)[2],.00799)
    def test_invalid_blend_leaves_output_unchanged(self):
        for invalid in ('weight','rotation','root','position'):
            a=self.pose();b=self.pose();out=NativePose();C.memset(C.byref(out),0x5a,C.sizeof(out))
            weight=.5
            if invalid=='weight':weight=math.nan
            elif invalid=='rotation':b.local[5]=Rotation(0,0,0,0)
            elif invalid=='root':b.rootHeight=math.inf
            else:b.positions[9]=Point(math.nan,0,0)
            before=bytes(out)
            self.assertEqual(self.lib.blend(C.byref(native_bind()),C.byref(a),C.byref(b),weight,C.byref(out)),0)
            self.assertEqual(bytes(out),before)
    def test_missing_bank_cannot_enable_layer(self):
        self.assertFalse(self.lib.create(b'/tmp/no-such-pes3-motion-bank.fpsa',C.byref(native_bind())))
    def test_anatomical_mirror_swaps_the_contact_leg_and_is_an_involution(self):
        pose=self.pose();pose.local[7]=Rotation(-.5,0,0,math.sqrt(.75))
        self.assertEqual(self.lib.rebuild(C.byref(native_bind()),C.byref(pose),1),1)
        mirrored=NativePose();restored=NativePose()
        self.assertEqual(self.lib.mirror(C.byref(native_bind()),C.byref(pose),C.byref(mirrored)),1)
        self.assertLess(math.dist(pose.local[7],mirrored.local[10]),.00001)
        self.assertGreater(math.dist(mirrored.positions[9],mirrored.positions[12]),.2)
        self.assertEqual(self.lib.mirror(C.byref(native_bind()),C.byref(mirrored),C.byref(restored)),1)
        for a,b in zip(pose.local,restored.local):self.assertLess(math.dist(a,b),.00001)
    def test_real_bank_matches_motion_and_rejects_incompatible_poses(self):
        if not self.state:self.skipTest('PES3_TEST_BANK enables private local resource validation')
        self.assertEqual(self.lib.candidates(self.state),1105)
        for clip,bone,contact,mirrored in ((47,-1,-1,False),(269,12,.4,False),(236,9,.6,True),(797,2,.5,False),
                                         (269,12,0,False),(269,12,1,False)):
            request=Request();request.contact=contact;request.contactBone=bone
            source=Choice(True,clip,contact if contact in (0,1)else .5,0,mirrored)
            for i in range(9):
                self.assertEqual(self.lib.sample(self.state,C.byref(source),i/8,contact,C.byref(request.poses[i])),1)
            choice=Choice();self.lib.choose(self.state,C.byref(request),C.byref(choice))
            self.assertTrue(choice.accepted,(clip,choice.clip,choice.error))
            self.assertLess(choice.error,.004)
            if contact in (0,1):self.assertEqual(choice.sourceContact,contact)
        for pose in request.poses:
            pose.rootHeight+=4
            for point in pose.positions:point[2]+=4
        self.lib.choose(self.state,C.byref(request),C.byref(choice));self.assertFalse(choice.accepted)
        request.contactBone=999
        self.lib.choose(self.state,C.byref(request),C.byref(choice));self.assertFalse(choice.accepted)
        output=NativePose();C.memset(C.byref(output),0x5a,C.sizeof(output));before=bytes(output)
        self.assertEqual(self.lib.sample(self.state,C.byref(choice),.5,.5,C.byref(output)),0)
        self.assertEqual(bytes(output),before)
        for time,contact,anchor in ((math.nan,.5,.5),(.5,math.nan,.5),(.5,2,.5),(.5,.5,math.nan),(.5,.5,2),
                                    (.5,0,.5),(.5,1,.5)):
            source=Choice(True,269,anchor,0)
            self.assertEqual(self.lib.sample(self.state,C.byref(source),time,contact,C.byref(output)),0)
            self.assertEqual(bytes(output),before)

if __name__=='__main__':unittest.main()
