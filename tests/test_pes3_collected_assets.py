"""Resource corruption, interval bounds and portable bind contracts."""
import ctypes as C
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/pes3'))
from collected_assets import sections,inner_wrapper,animation_blocks
from model_reference import packed
from verify_model_bind import ModelBind,SOURCE
from verify_render_pose import SOURCE as RENDER_SOURCE

class ResourceLayoutTests(unittest.TestCase):
    def animation_bank(self,profile_offsets=(8,12),metadata_size=16):
        block=struct.pack('<7I',0x20011119,0x20000002,40,0,192,0,0)+bytes(164)+struct.pack('<3I',1,0,0)
        motion=struct.pack('<4I',2,8,16,224)+block+bytes(4)+block
        first=struct.pack('<II',0x600,len(motion))+bytes(24)+motion
        profiles=struct.pack('<2I',*profile_offsets)+b'abcdEFGH'
        metadata=struct.pack('<II',0x900,metadata_size)+bytes(24)+bytes(range(16))
        return struct.pack('<5I',3,8,20,20+len(first),20+len(first)+len(profiles))+first+profiles+metadata

    def test_animation_auxiliary_bytes_are_preserved_without_contact_labels(self):
        blocks,rows,_=animation_blocks(self.animation_bank(),2)
        self.assertEqual([duration for duration,_ in blocks],[40,40])
        self.assertEqual([row['metadata_raw_hex']for row in rows],
                         [bytes(range(8)).hex(),bytes(range(8,16)).hex()])
        self.assertEqual([row['motion_profile_bytes']for row in rows],[4,4])
        self.assertTrue(all('contact'not in key for row in rows for key in row))

    def test_animation_auxiliary_intervals_and_record_count_are_enforced(self):
        for offsets in((4,12),(8,8),(12,8),(8,16)):
            with self.assertRaises(ValueError):animation_blocks(self.animation_bank(offsets),2)
        for size in(8,24):
            with self.assertRaises(ValueError):animation_blocks(self.animation_bank(metadata_size=size),2)

    def test_directories_reject_overlap_reverse_and_out_of_bounds(self):
        for offsets in ((16,16),(20,16),(16,100),(8,16)):
            data=struct.pack('<4I',2,8,*offsets)+b'abcdefghijklmnop'
            with self.assertRaises(ValueError):sections(data)

    def test_directories_preserve_padding_and_non_ascii_payloads(self):
        data=struct.pack('<4I',2,8,16,20)+b'\x00\xff\x10\x11\x00\x00\xff'
        self.assertEqual(sections(data),[(16,b'\x00\xff\x10\x11'),(20,b'\x00\x00\xff')])

    def test_nested_checksums_sizes_stream_end_and_tag_are_enforced(self):
        payload=b'model\x00'*100;compressed=zlib.compress(payload)
        good=struct.pack('<III',0x10300,len(compressed),len(payload))+bytes(20)+compressed
        self.assertEqual(inner_wrapper(good+b'\x00'*15,0x10300)[0],payload)
        bad_checksum=bytearray(good);bad_checksum[-1]^=1
        for bad,tag in ((bytes(bad_checksum),0x10300),(good[:-1],0x10300),(good,0x10600),
                        (good[:8]+struct.pack('<I',len(payload)-1)+good[12:],0x10300),
                        (good[:4]+struct.pack('<I',len(compressed)+1)+good[8:]+b'\x00',0x10300)):
            with self.assertRaises(ValueError):inner_wrapper(bad,tag)

class PackedInstructionTests(unittest.TestCase):
    def run_pack(self,fn,sa,alias=False):
        r=[0]*32;upper=[0]*32
        r[1]=0x2222222211111111;upper[1]=0x4444444433333333
        r[2]=0x6666666655555555;upper[2]=0x8888888877777777
        dest=1 if alias else 3
        word=28<<26|1<<21|2<<16|dest<<11|sa<<6|fn
        packed(word,r,upper)
        return (r[dest]&0xffffffff,r[dest]>>32,upper[dest]&0xffffffff,upper[dest]>>32)

    def test_transpose_rearrangements_keep_all_four_lanes_and_alias(self):
        expected={(8,18):(0x55555555,0x11111111,0x66666666,0x22222222),
            (40,18):(0x77777777,0x33333333,0x88888888,0x44444444),
            (9,14):(0x55555555,0x66666666,0x11111111,0x22222222),
            (41,14):(0x33333333,0x44444444,0x77777777,0x88888888),
            (41,27):(0x55555555,0x55555555,0x77777777,0x77777777)}
        for (fn,sa),result in expected.items():
            for alias in(False,True):self.assertEqual(self.run_pack(fn,sa,alias),result)

    def test_unhandled_packed_instructions_fail_without_mutation(self):
        r=list(range(32));upper=list(range(32));before=(r[:],upper[:])
        with self.assertRaises(ValueError):packed(28<<26|3<<11,r,upper)
        self.assertEqual((r,upper),before)

@unittest.skipUnless(shutil.which('g++'),'g++ unavailable')
class ModelBindContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='pes3-bind-test-');p=Path(cls.temp.name)
        (p/'bind.cpp').write_text(SOURCE+'\n#include <cfenv>\nextern "C" int bind_rounding(){return std::fegetround();}\n')
        subprocess.run(['g++','-std=c++14','-O0','-Wall','-Wextra','-Werror','-fno-fast-math',
            '-ffp-contract=off','-fsanitize=undefined','-fno-sanitize-recover=all','-shared','-fPIC',
            '-I',str(ROOT/'tools/pes3/recovered'),str(p/'bind.cpp'),'-o',str(p/'bind.so')],check=True,capture_output=True)
        cls.lib=C.CDLL(str(p/'bind.so'));cls.lib.model_bind.argtypes=[C.POINTER(C.c_float),C.POINTER(C.c_int32),C.POINTER(C.c_int32),C.POINTER(ModelBind)]
        cls.lib.model_bind.restype=C.c_int
        cls.lib.model_bind_profile.argtypes=cls.lib.model_bind.argtypes[:-1]+[C.c_uint,C.POINTER(ModelBind)]
        cls.lib.model_bind_profile.restype=C.c_int
        cls.lib.bind_rounding.argtypes=[];cls.lib.bind_rounding.restype=C.c_int
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def inputs(self):
        matrices=(C.c_float*304)()
        for i in range(19):
            for diagonal in(0,5,10,15):matrices[16*i+diagonal]=1
            matrices[16*i+12]=i
        return matrices,(C.c_int32*19)(-1,*range(18)),(C.c_int32*19)(*([-1]*19))
    def test_bind_tracks_use_parent_frames_and_preserve_source_matrices(self):
        m,p,pairs=self.inputs();out=ModelBind();self.assertEqual(self.lib.model_bind(m,p,pairs,C.byref(out)),1)
        self.assertEqual(list(out.pose.flags),[0,6,0,0])
        bits=lambda f:struct.unpack('<I',struct.pack('<f',f))[0]
        for i in range(19):
            self.assertEqual(out.channel_translation[i][0],bits(1 if i else 0))
            self.assertEqual(out.channel_translation[i][3],bits(1))
            self.assertEqual(bytes(out.pose.bones[i].matrix),bytes(m)[64*i:64*(i+1)])
    def test_invalid_reference_inputs_reject_atomically(self):
        for kind in('cycle','asymmetric_pair','self_pair','projective','nan','overflow'):
            m,p,pairs=self.inputs();out=ModelBind();C.memset(C.byref(out),0x5a,C.sizeof(out));before=bytes(out)
            if kind=='cycle':p[2]=2
            elif kind=='asymmetric_pair':pairs[2]=3
            elif kind=='self_pair':pairs[2]=2
            elif kind=='projective':m[3]=.5
            elif kind=='nan':m[0]=float('nan')
            else:m[0]=3.4e38;m[16]=3.4e38
            self.assertEqual(self.lib.model_bind(m,p,pairs,C.byref(out)),0,kind)
            self.assertEqual(bytes(out),before,kind)
    def test_profiles_are_explicit_interleavable_and_preserve_global_rounding(self):
        m,p,pairs=self.inputs();m[0]=.70710677;m[1]=.70710677;m[4]=-.70710677;m[5]=.70710677
        m[12]=1.234567;m[13]=2.345678;m[28]=4.321987;m[29]=8.765432
        before=self.lib.bind_rounding();nearest=ModelBind();chop=ModelBind();again=ModelBind()
        for profile,out in((0,nearest),(1,chop),(0,again)):
            self.assertEqual(self.lib.model_bind_profile(m,p,pairs,profile,C.byref(out)),1)
            self.assertEqual(self.lib.bind_rounding(),before)
        self.assertNotEqual(bytes(nearest),bytes(chop));self.assertEqual(bytes(nearest),bytes(again))
        C.memset(C.byref(again),0x5a,C.sizeof(again));saved=bytes(again)
        self.assertEqual(self.lib.model_bind_profile(m,p,pairs,2,C.byref(again)),0)
        self.assertEqual(bytes(again),saved)
@unittest.skipUnless(shutil.which('g++'),'g++ unavailable')
class RenderContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='pes3-render-test-');p=Path(cls.temp.name)
        (p/'render.cpp').write_text(RENDER_SOURCE)
        subprocess.run(['g++','-std=c++14','-O0','-Wall','-Wextra','-Werror','-fno-fast-math',
            '-ffp-contract=off','-fsanitize=undefined','-fno-sanitize-recover=all','-shared','-fPIC',
            '-I',str(ROOT/'tools/pes3/recovered'),str(p/'render.cpp'),'-o',str(p/'render.so')],check=True,capture_output=True)
        cls.lib=C.CDLL(str(p/'render.so'));ptr=C.POINTER(C.c_float)
        cls.lib.owned_render_matrices.argtypes=[ptr,ptr,C.c_uint,C.c_uint,ptr];cls.lib.owned_render_matrices.restype=C.c_int
        cls.lib.owned_render_position.argtypes=[ptr,C.c_uint,ptr];cls.lib.owned_render_position.restype=C.c_int
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_raw_copy_preserves_bits_and_in_place_scaled_output_is_safe(self):
        data=bytes.fromhex('0000008001000000')+struct.pack('<302f',*([.125,1.0]*151))
        matrices=(C.c_float*304).from_buffer_copy(data);out=(C.c_float*304)()
        self.assertEqual(self.lib.owned_render_matrices(matrices,None,19,1,out),1)
        self.assertEqual(bytes(out),data)
        scales=(C.c_float*76)(*([.123456,.234567,.345678,.456789]*19));preserved=bytes(scales)
        self.assertEqual(self.lib.owned_render_matrices(matrices,scales,19,1,out),1)
        self.assertEqual(self.lib.owned_render_matrices(matrices,scales,19,1,matrices),1)
        self.assertEqual(bytes(matrices),bytes(out));self.assertEqual(bytes(scales),preserved)
    def test_invalid_domain_does_not_partially_commit(self):
        for kind in('count','profile','nan_matrix','nan_scale','overflow'):
            matrices=(C.c_float*304)(*([1]*304));scales=(C.c_float*76)(*([1]*76))
            out=(C.c_float*304)();C.memset(out,0x5a,C.sizeof(out));before=bytes(out)
            if kind=='nan_matrix':matrices[20]=float('nan')
            elif kind=='nan_scale':scales[4]=float('nan')
            elif kind=='overflow':matrices[16]=3.4e38;scales[4]=3.4e38
            self.assertEqual(self.lib.owned_render_matrices(matrices,scales,20 if kind=='count'else 19,
                2 if kind=='profile'else 1,out),0,kind)
            self.assertEqual(bytes(out),before,kind)
        position=(C.c_float*3)(1,float('nan'),3);out=(C.c_float*3)(7,8,9);before=bytes(out)
        self.assertEqual(self.lib.owned_render_position(position,1,out),0);self.assertEqual(bytes(out),before)

if __name__=='__main__':unittest.main()
