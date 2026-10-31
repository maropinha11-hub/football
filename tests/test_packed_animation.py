"""Float-bit parity between the Python writer and actual native asset decoder."""
import math
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/animations'))
from packed_animation import pack_text,read_text
from test_pes_action_bank import tracks

def bits(v):return struct.pack('<f',v)

class PackedAnimationTests(unittest.TestCase):
    def fixture(self):
        rng=random.Random(914)
        names=['player','body','middle','neck','left_shoulder','left_elbow','right_shoulder','right_elbow',
               'left_thigh','left_knee','left_ankle','right_thigh','right_knee','right_ankle']
        lines=[]
        for index,name in enumerate(names):
            fields=[name];width=3 if index==0 else 4
            for key in range(1200):
                fields.append(str(key))
                fields.extend(format(math.sin(key*.017+axis)*rng.uniform(.9,1.1),'.9g')for axis in range(width))
            lines.append(','.join(fields))
        return '\n'.join(lines)+'\n<type>movement</type>\n<loop>false</loop>\n'

    def compare(self,a,b):
        a,b=tracks(a),tracks(b)
        self.assertEqual(set(a),set(b))
        for name,rows in a.items():
            self.assertEqual(len(rows),len(b[name]))
            for left,right in zip(rows,b[name]):
                self.assertEqual(left[0],right[0])
                self.assertEqual([bits(v)for v in left[1:]],[bits(v)for v in right[1:]])

    def test_predictive_storage_preserves_every_runtime_float_bit_and_metadata(self):
        text=self.fixture()
        with tempfile.TemporaryDirectory()as temp:
            path=Path(temp)/'pose.anim';path.write_bytes(pack_text(text))
            self.compare(text,read_text(path))
            self.assertTrue(read_text(path).endswith('<type>movement</type>\n<loop>false</loop>\n'))

    @unittest.skipUnless((ROOT/'build/asset_line_tests').exists(),'Native decoder is built by CMake')
    def test_native_decoder_matches_the_writer_even_for_rows_over_the_old_line_limit(self):
        text=self.fixture()
        with tempfile.TemporaryDirectory()as temp:
            path=Path(temp)/'pose.anim';path.write_bytes(pack_text(text))
            result=subprocess.run([str(ROOT/'build/asset_line_tests'),str(path)],text=True,capture_output=True,check=True)
            self.compare(text,result.stdout)

    def test_truncated_and_invalid_dimensions_do_not_decode_as_a_partial_animation(self):
        packed=pack_text(self.fixture())
        with tempfile.TemporaryDirectory()as temp:
            path=Path(temp)/'bad.anim'
            for data in [packed[:20],packed[:-1],b'FBAN2'+struct.pack('<I',2000000)]:
                path.write_bytes(data)
                with self.assertRaises(ValueError):read_text(path)
                if (ROOT/'build/asset_line_tests').exists():
                    result=subprocess.run([str(ROOT/'build/asset_line_tests'),str(path)],capture_output=True)
                    self.assertEqual(result.returncode,3)
