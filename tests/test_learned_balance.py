import json,re,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
class LearnedBalance(unittest.TestCase):
 def test_held_out_planner_predictions(self):
  text=(ROOT/'src/onthepitch/player/humanoid/learned_balance_policy.hpp').read_text()
  arrays={name:np.array([float(x.rstrip('f'))for x in values.split(',')])for name,values in re.findall(r'constexpr float (\w+)\[\d+\]=\{([^}]+)',text)}
  self.assertEqual({k:len(v)for k,v in arrays.items()},{'w':120,'b':24,'v':48,'c':2})
  random=np.random.default_rng(20261027);x=random.uniform([-.25,-2.8,.68,.10,0],[.25,2.8,1.2,.42,1],(5000,5))
  position,velocity,height,stance,brace=x.T;capture=position+velocity/np.sqrt(9.81/height)
  step=np.sign(capture)*np.minimum(.42,np.maximum(0,np.abs(capture)-(.095+stance*.5)))
  hip=np.clip((position+velocity*.11-step*.30)/height,-.32,.32)
  prediction=(np.tanh((x/[.25,2.8,1.2,.42,1])@arrays['w'].reshape(5,24)+arrays['b'])@arrays['v'].reshape(24,2)+arrays['c'])*[.42,.32]
  rmse=np.sqrt(np.mean((prediction-np.stack([step,hip],axis=1))**2,axis=0))
  report=json.loads((ROOT/'config/learned-balance-policy.json').read_text())
  self.assertEqual(report['result'],'passed');self.assertLess(rmse[0],.025);self.assertLess(rmse[1],.025)
  self.assertAlmostEqual(rmse[0],report['held_out_rmse']['step_metres'],places=7)
  self.assertAlmostEqual(rmse[1],report['held_out_rmse']['hip_radians'],places=7)
if __name__=='__main__':unittest.main()
