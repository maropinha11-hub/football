"""Identity of the uploaded approved build and the native animation bank."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ApprovedBase(unittest.TestCase):
    def test_original_native_tracks_are_byte_identical(self):
        manifest=json.loads((ROOT/'config/approved-base.json').read_text())
        self.assertEqual(manifest['uploaded_executable_sha256'],
                         '23230593d0f2735381a5522e21c71abc4977f76d32352bee814ebd096b4a30a3')
        for name,digest in manifest['original_animation_sha256'].items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest)

    def test_uploaded_locomotion_is_absent(self):
        self.assertFalse(list((ROOT/'data/media/animations/mocap').glob('*.anim')))

    def test_approved_speed_and_cadence_are_preserved(self):
        values={}
        for line in (ROOT/'config/training.config').read_text().splitlines():
            tokens=line.split('"')
            if len(tokens)>=4:values[tokens[1]]=tokens[3]
        for key,value in {'training_walk_speed_scale':'0.72',
                          'training_sprint_speed_scale':'0.90',
                          'training_animation_time_scale':'1.12',
                          'training_transition_frames':'16'}.items():
            self.assertEqual(values[key],value)
        self.assertNotIn('training_motion_matching',values)

if __name__=='__main__':unittest.main()
