import ctypes as C
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/pes3'))
from runtime_abi import build,Frame

def bundle():
    # Two irregular endpoints, finite root coordinates, 19 quaternion tracks.
    key=struct.pack('<4h3f',0,0,0,32767,0,-400,0)+struct.pack('<4h',0,0,0,32767)*18
    block=struct.pack('<7I',0x20011119,0x20000002,0x40a00000,60,28+3*164,0,0)+key*3
    block+=struct.pack('<I',3)+struct.pack('<fI',1.25,28)+struct.pack('<fI',5,192)+struct.pack('<fI',0,356)
    header=b'FPSANM14'+struct.pack('<6I',1,32,14,19,164,0)
    return header+struct.pack('<4I',0,0x40a00000,48,len(block))+block

class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='pes3-runtime-tests-')
        cls.lib,_=build(Path(cls.temp.name))
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def inspect(self,data):
        buf=(C.c_ubyte*len(data)).from_buffer_copy(data);count=C.c_uint(0xfeed)
        status=self.lib.bank_inspect(buf,len(buf),C.byref(count))
        if not status:self.assertEqual(count.value,0xfeed)
        return status,count.value
    def test_irregular_source_endpoints_are_valid(self):
        self.assertEqual(self.inspect(bundle()),(1,1))
    def test_invalid_structure_rejected_atomically(self):
        raw=bundle()
        for offset,value in ((8,0),(12,0),(16,15),(20,13),(24,0),(28,1),(32,1),(36,0),
                             (40,0xffffffff),(44,0xffffffff),(48+16,0xffffffff),
                             (48+28+8,0x7fc00000),(48+28+3*164,0xffffffff),
                             (48+28+3*164+4,0x7fc00000),
                             (48+28+3*164+12,0x3f000000),
                             (48+28+3*164+20,0x3f800000)):
            with self.subTest(offset=offset):
                corrupt=bytearray(raw);struct.pack_into('<I',corrupt,offset,value)
                self.assertEqual(self.inspect(corrupt)[0],0)
        self.assertEqual(self.inspect(raw+b'x')[0],0)
        self.assertEqual(self.inspect(raw[:-1])[0],0)
    def test_unknown_bundle_cannot_be_loaded_for_runtime(self):
        path=Path(self.temp.name)/'unverified.fpsa';path.write_bytes(bundle())
        bank=self.lib.bank_create()
        try:
            self.assertEqual(self.lib.bank_load(bank,str(path).encode()),0)
            self.assertEqual(self.lib.bank_count(bank),0)
        finally:self.lib.bank_destroy(bank)
    def test_empty_bank_cannot_change_frame(self):
        bank=self.lib.bank_create();frame=Frame();C.memset(C.byref(frame),0x5b,C.sizeof(frame))
        before=bytes(frame)
        try:
            for clip,t in ((0,0),(0,float('nan')),(0xffffffff,0)):
                self.assertEqual(self.lib.bank_sample(bank,clip,t,C.byref(frame)),0)
                self.assertEqual(bytes(frame),before)
        finally:self.lib.bank_destroy(bank)
    def test_playback_clamps_at_endpoint_without_implicit_loop(self):
        phase=C.c_float();playing=C.c_uint()
        self.assertEqual(self.lib.playback_test(4.9,.01,60,5,C.byref(phase),C.byref(playing)),1)
        self.assertEqual((phase.value,playing.value),(5,0))
    def test_invalid_time_rejected_atomically(self):
        for dt,rate,duration in ((-1,60,5),(math.nan,60,5),(.01,0,5),(.01,math.inf,5),(.01,60,0)):
            phase=C.c_float(22);playing=C.c_uint(33)
            self.assertEqual(self.lib.playback_test(0,dt,rate,duration,C.byref(phase),C.byref(playing)),0)
            self.assertEqual((phase.value,playing.value),(22,33))

if __name__=='__main__':unittest.main()
