import hashlib,json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class LearnedMusclePolicy(unittest.TestCase):
 def setUp(self):self.model=json.loads((ROOT/'config/learned-muscle-policy.json').read_text())
 def test_heldout_reward_and_jerk(self):
  m=self.model;self.assertEqual(m['result'],'passed');test=m['held_out'];self.assertLess(test['learned_motor']['cost'],.9*test['original_motor']['cost']);self.assertLess(test['learned_motor']['cost'],.95*test['relative_pd_motor']['cost']);self.assertLess(test['learned_motor']['jerk'],test['relative_pd_motor']['jerk']);self.assertLess(test['learned_motor']['rms'],.18)
 def test_unseen_native_references_and_provenance(self):
  train={x.split(':')[0]for x in self.model['training']['train_sources']};test={x.split(':')[0]for x in self.model['training']['test_sources']};self.assertFalse(train&test)
  for name,expected in self.model['training']['source_sha256'].items():self.assertEqual(hashlib.sha256((ROOT/name.split(':')[0]).read_bytes()).hexdigest(),expected)
 def test_cpp_inference_weights_match_training(self):
  text=(ROOT/'src/onthepitch/player/humanoid/learned_muscle_policy.hpp').read_text();weights=[float(x.rstrip('f'))for x in re.search(r'weights\[18\]=\{([^}]+)',text)[1].split(',')];self.assertEqual(len(weights),18)
  for a,b in zip(weights,self.model['weights']):self.assertAlmostEqual(a,b,places=8)
if __name__=='__main__':unittest.main()
