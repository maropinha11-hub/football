"""Prove that generated shoe techniques preserve native gait and timing."""
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/animations'))
from build_situational_catalog import parse_source, sample


class NativeStrikeVariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = json.loads((ROOT/'config/procedural-strikes.json').read_text())

    def test_bank_records_real_native_sources(self):
        self.assertEqual(self.bank['generated_files'], 26)
        self.assertEqual(self.bank['new_captures'], 0)
        self.assertEqual(len({r['path'] for r in self.bank['clips']}), 26)
        for row in self.bank['clips']:
            original = ROOT/'data/media/animations'/row['source']
            self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), row['source_sha256'])

    def test_roots_hips_knees_and_contact_times_remain_native(self):
        for row in self.bank['clips']:
            with self.subTest(row['path']):
                native, events, metadata, _ = parse_source(ROOT/'data/media/animations'/row['source'])
                tracks, new_events, new_metadata, _ = parse_source(ROOT/row['path'])
                self.assertEqual(events, new_events)
                self.assertEqual(events[0][0], row['contact_frame'])
                self.assertEqual(metadata['type'], new_metadata['type'])
                ankle = row['foot'].replace('foot', 'ankle')
                changed = {ankle, 'middle', 'left_shoulder', 'right_shoulder'}
                self.assertEqual(native.keys(), tracks.keys())
                for bone in native.keys() - changed:
                    self.assertEqual(native[bone], tracks[bone], bone)

    def test_new_curves_are_finite_normalized_and_have_native_endpoints(self):
        for row in self.bank['clips']:
            native, _, _, _ = parse_source(ROOT/'data/media/animations'/row['source'])
            tracks, _, _, _ = parse_source(ROOT/row['path'])
            end = max(keys[-1][0] for keys in native.values())
            for bone in [row['foot'].replace('foot', 'ankle'), 'middle', 'left_shoulder', 'right_shoulder']:
                self.assertEqual(len(tracks[bone]), end+1)
                for _, q in tracks[bone]:
                    self.assertTrue(all(math.isfinite(v) for v in q))
                    self.assertAlmostEqual(sum(v*v for v in q), 1., places=6)
                for frame in [0, end]:
                    a, b = sample(native[bone], frame, True), sample(tracks[bone], frame, True)
                    self.assertGreater(abs(sum(x*y for x,y in zip(a,b))), .999999)
                before = sample(native[bone], row['contact_frame'], True)
                after = sample(tracks[bone], row['contact_frame'], True)
                self.assertLess(abs(sum(x*y for x,y in zip(before,after))), .99999)


if __name__ == '__main__':
    unittest.main()
