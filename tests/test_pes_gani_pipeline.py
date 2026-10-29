import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/animations'))
import read_pes_gani as reader


def fixture():
    # Independent little-endian source: one root-translation channel,
    # two half-float keys in centimetres. No original game data is included.
    position=struct.pack('<3eb3e',100,0,0,3,200,0,0)
    g=bytearray(0xb8+len(position));struct.pack_into('<III',g,0,int.from_bytes(b'gani','little'),0x20,len(g))
    struct.pack_into('<5I',g,0x90,1,1,30,3,0);struct.pack_into('<I',g,0xa4,0x18)
    struct.pack_into('<IB3x',g,0xa8,0,1);struct.pack_into('<IhBb',g,0xb0,8,0,0,16);g[0xb8:]=position
    m=bytearray(48);struct.pack_into('<IIHH',m,0,int.from_bytes(b'MTAR','little'),1,21,29)
    struct.pack_into('<IiII',m,32,1914981404,26199,48,len(g));m.extend(g)
    ask=struct.pack('<iiIii8f',1,1,0,40,-1,0,0,0,0,0,0,0,1)+b'sk_belly\0'
    rig=bytearray(68);struct.pack_into('<8I',rig,0,0,0,0,1,1,0,0,68);struct.pack_into('<I',rig,32,36)
    struct.pack_into('<16H',rig,36,0,0,1,0,0xffff,0xffff,*([0]*10))
    return bytes(m),ask,bytes(rig)


class PesGaniPipeline(unittest.TestCase):
    def test_all_shipped_names_match_the_fox_hasher(self):
        names=json.loads((reader.VENDOR/'clip_name_map.json').read_text())
        self.assertEqual(len(names),4105)
        for name,record in names.items():self.assertEqual(reader.foxhash.strcode32(name),record['hash'],name)

    def test_root_translation_is_converted_once_and_kept_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);mtar,ask,rig=fixture()
            for name,data in [('body.mtar',mtar),('body.ask',ask),('body.frig',rig)]: (root/name).write_bytes(data)
            report=reader.inspect(root/'body.mtar',root/'body.ask',root/'body.frig',root/'decoded')
            self.assertEqual(report['decoded'],1);self.assertFalse(report['retargeted']);self.assertFalse(report['gameplay_recovered'])
            clip=json.loads(next((root/'decoded').glob('00000-*.json')).read_text())
            self.assertEqual(clip['name'],'run_2_0');self.assertEqual(clip['root']['pos'],[[0,1.,0.,0.],[3,2.,0.,0.]])
            self.assertEqual(clip['tracks'],{});self.assertEqual(clip['frames'],3)
            self.assertEqual(reader.inspect(root/'body.mtar')['named'],1)

    def test_truncated_or_oversized_tables_are_rejected(self):
        data,ask,rig=fixture()
        for raw in (b'',data[:20],data[:40],data[:48]):
            with self.assertRaises(ValueError):reader.mtar(raw)
        corrupt=bytearray(data);struct.pack_into('<I',corrupt,4,0xffffffff)
        with self.assertRaises(ValueError):reader.mtar(corrupt)
        corrupt=bytearray(data[48:]);struct.pack_into('<I',corrupt,0x90,0xffffffff)
        with self.assertRaises(ValueError):reader.gani(corrupt)
        with self.assertRaises(ValueError):reader.skeleton(ask[:15])
        with self.assertRaises(ValueError):reader.rig(rig[:40],1)

    def test_invalid_decoded_pose_cannot_silently_become_an_animation(self):
        for track in ({'pos':[[0,float('nan'),0,0]]},{'rot':[[0,0,0,0,0]]},{'pos':[[0,0,0,0],[0,1,0,0]]}):
            with self.assertRaises(ValueError):reader.validate_clip(dict(root=track,tracks={},frames=3))

    def test_half_angle_quaternions_are_unit_and_not_a_2017_scale_guess(self):
        q=reader.pesmtar.quat([.5,1,0],[0,0,0])
        self.assertAlmostEqual(sum(x*x for x in q),1)
        self.assertAlmostEqual(2*math.acos(q[3]),math.pi/2)


if __name__=='__main__':unittest.main()
