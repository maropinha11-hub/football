"""Behavioral checks of the native, fully dynamic learning environment."""
from pathlib import Path
import os
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/animations'))
from fullbody_protocol import Environment

EXE=Path(os.environ.get('FOOTBALL_RL_ENVIRONMENT',ROOT/'build/fullbody_environment'))

@unittest.skipUnless(EXE.exists(),'native fullbody_environment has not been built')
class PhysicalLearningEnvironment(unittest.TestCase):
    def test_proprioception_and_local_commands(self):
        with Environment(EXE,2,7001)as env:
            observation=env.reset(0)
            self.assertEqual(observation.shape,(2,148))
            self.assertTrue(np.isfinite(observation).all())
            np.testing.assert_allclose(np.linalg.norm(observation[:,:3],axis=1),1,atol=1e-5)
            np.testing.assert_allclose(observation[:,117:120],0,atol=1e-5)
            self.assertTrue((observation[:,122]>.9).all())
            for _ in range(50):observation,reward,done,metrics=env.step(np.zeros((2,20)),0)
            self.assertTrue(np.isfinite(reward).all())
            self.assertTrue((metrics[:,5]>0).all())
    def test_actions_change_real_joints_and_falls_reset_the_environment(self):
        with Environment(EXE,1,7003)as env:
            start=env.reset(0).copy();largest=0.;falls=0
            for _ in range(200):
                observation,_,done,metrics=env.step(np.ones((1,20)),0)
                largest=max(largest,float(np.max(np.abs(observation[:,9:45]-start[:,9:45]))));falls+=int(metrics[0,4])
                if done[0]:self.assertGreater(observation[0,122],.9)
            self.assertGreater(largest,.05)
            self.assertGreater(falls,0)
    def test_rejects_invalid_requests_before_sending_them(self):
        with Environment(EXE,1,7007)as env:
            for action in(np.zeros((2,20)),np.full((1,20),np.nan)):
                with self.assertRaises(ValueError):env.step(action,0)
            with self.assertRaises(ValueError):env.reset(float('nan'))
            self.assertTrue(np.isfinite(env.step(np.zeros((1,20)),0)[0]).all())
    def test_seeded_native_rollouts_are_repeatable(self):
        rng=np.random.default_rng(83)
        with Environment(EXE,1,7011)as a,Environment(EXE,1,7011)as b:
            np.testing.assert_array_equal(a.reset(.4),b.reset(.4))
            for _ in range(20):
                action=rng.normal(0,.1,(1,20));left=a.step(action,.4);right=b.step(action,.4)
                for x,y in zip(left,right):np.testing.assert_allclose(x,y,atol=1e-6,rtol=1e-6)

if __name__=='__main__':unittest.main()
