"""Check baked motions against the actual native bind and approved pass.

This checks every pose for deformation, bad time keys and ground penetration.
It does not replace the rendered selector/contact integration scenarios.
"""
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT/'data/media/training/pes17'
PARENTS = [-1,0,1,1,3,1,5,0,7,8,0,10,11]


def tracks(text):
    result = {}
    for line in text.splitlines():
        fields = line.split(',')
        if len(fields) < 5 or fields[0] == 'extension':
            continue
        width = 4 if fields[0] == 'player' else 5
        result[fields[0]] = [[float(v) for v in fields[i:i+width]]
                             for i in range(1, len(fields), width)]
    return result


def digest(poses):
    # Normalize signed zero and textual numeric spelling; retain all keys.
    normalized = {k:[[0 if v == 0 else v for v in row] for row in rows] for k, rows in poses.items()}
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def multiply(a, b):
    x,y,z,w = a; u,v,s,t = b
    return (w*u+x*t+y*s-z*v, w*v-x*s+y*t+z*u, w*s+x*v-y*u+z*t, w*t-x*u-y*v-z*s)


def rotate(q, v):
    p = multiply(multiply(q, (*v,0)), (-q[0],-q[1],-q[2],q[3]))
    return p[:3]


class PESActionBankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((BANK/'catalog.json').read_text())
        cls.recipes = json.loads((ROOT/'config/pes2017-action-recipes.json').read_text())
        cls.bind = json.loads((ROOT/'tools/animations/native_rig_reference.json').read_text())

    def test_the_user_approved_pass_keeps_its_exact_pose_channels(self):
        self.assertEqual(digest(tracks((BANK/'short_pass.anim').read_text())),
                         self.recipes['approved_shortpass_pose_sha256'])

    def test_inventory_hashes_and_source_provenance(self):
        self.assertEqual(self.catalog['source_clips'], len(self.recipes['actions']))
        self.assertEqual(self.catalog['runtime_candidates'], sum((2 if r.get('mirror') else 1)*(2 if r['role']=='reception' else 1) for r in self.recipes['actions']))
        self.assertEqual(len({r['source'] for r in self.recipes['actions']}), len(self.recipes['actions']))
        self.assertEqual({r['file'] for r in self.catalog['actions']}, {p.name for p in BANK.glob('*.anim')})
        for row in self.catalog['actions']:
            with self.subTest(file=row['file']):
                path = BANK/row['file']; meta = json.loads(path.with_suffix('.json').read_text())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row['sha256'])
                self.assertEqual(row['sha256'], meta['output_sha256'])
                self.assertEqual(meta['source_archive_sha256'], self.recipes['source_archive_sha256'])
                self.assertTrue(meta['source_game_pose_comparison_pending'])
                self.assertIn('not recovered', meta['contact_annotation_origin'])

    def test_all_baked_pose_keys_are_continuous_and_normalized(self):
        for row in self.catalog['actions']:
            with self.subTest(file=row['file']):
                pose = tracks((BANK/row['file']).read_text())
                self.assertEqual(set(pose), {'player', *(b['name'] for b in self.bind['bones'])})
                size = len(pose['player'])
                for name, keys in pose.items():
                    self.assertEqual([r[0] for r in keys], list(range(size)))
                    self.assertTrue(all(math.isfinite(v) for r in keys for v in r))
                    if name == 'player':
                        continue
                    for key in keys:
                        self.assertAlmostEqual(sum(v*v for v in key[1:]), 1, places=5)
                    for a, b in zip(keys, keys[1:]):
                        angle = 2*math.acos(min(1, abs(sum(x*y for x,y in zip(a[1:], b[1:])))))
                        self.assertLess(angle, .351)

    def test_every_pose_preserves_the_native_bones_and_foot_support(self):
        bones = self.bind['bones']
        for row in self.catalog['actions']:
            with self.subTest(file=row['file']):
                pose = tracks((BANK/row['file']).read_text())
                for frame, root in enumerate(pose['player']):
                    global_q = []; positions = []
                    for i, bone in enumerate(bones):
                        q = pose[bone['name']][frame][1:]
                        if i == 0:
                            global_q.append(q); positions.append([root[1], root[2], root[3]+bone['offset'][2]])
                        else:
                            parent = PARENTS[i]; global_q.append(multiply(global_q[parent], q))
                            offset = rotate(global_q[parent], bone['offset'])
                            positions.append([a+b for a,b in zip(positions[parent], offset)])
                            self.assertAlmostEqual(math.dist(positions[i], positions[parent]),
                                                   math.sqrt(sum(v*v for v in bone['offset'])), places=5)
                    for ankle, foot in zip((9,12), self.bind['feet']):
                        for bits in itertools.product((0,1), repeat=3):
                            corner = [foot['max' if bits[k] else 'min'][k] for k in range(3)]
                            self.assertGreaterEqual(positions[ankle][2]+rotate(global_q[ankle], corner)[2], .0079)

    def test_contact_keys_and_standing_entry_are_playable(self):
        for recipe in self.recipes['actions']:
            with self.subTest(file=recipe['file']):
                text = (BANK/(recipe['file']+'.anim')).read_text(); pose = tracks(text)
                events = [line.split(',') for line in text.splitlines() if line.startswith('extension,football,')]
                self.assertEqual(len(events), 1)
                frame = int(events[0][2]); self.assertEqual(frame, recipe['contact'])
                self.assertLess(frame, len(pose['player'])-8)
                self.assertGreaterEqual(frame, 8)
                self.assertTrue(all(math.isfinite(float(v)) for v in events[0][3:]))
                self.assertEqual(re.search(r'<type>(.*?)</type>', text)[1], recipe['action'])
                if recipe.get('speed',[0,1.4])[0] < 2:
                    first, second = pose['player'][:2]
                    self.assertLess(math.dist(first[1:3], second[1:3])*100, 1.8)


if __name__ == '__main__':
    unittest.main()
