"""CPU policy search for a bounded angular muscle servo, not full-body RL.
Native joint trajectories supply reference signals. Random inertial strength,
damping and external impacts generate actual reduced-dynamics rollouts.
No heuristic target torques or proprietary motion data are training labels.
"""
import hashlib,json,math
from pathlib import Path
import numpy as np
from build_situational_catalog import ROOT,parse_source,sample

SEED=20261023
rng=np.random.default_rng(SEED)
paths=sorted(p for p in (ROOT/'data/media/animations').rglob('*.anim')if 'procedural_actions'not in p.parts)
rng.shuffle(paths);groups=[paths[:160],paths[160:205],paths[205:]]
def data(paths,seed,count=32,steps=180):
 random=np.random.default_rng(seed);refs=[];used=[]
 for path in paths:
  tracks,events,metadata,_=parse_source(path)
  for bone in ['middle','left_shoulder','right_shoulder']:
   keys=tracks.get(bone)
   if not keys or keys[-1][0]<15:continue
   q=np.array([sample(keys,t,rotation=True)for t in np.linspace(0,keys[-1][0],steps)])
   q=np.where(q[:,3,None]<0,-q,q);angle=2*np.arctan2(np.linalg.norm(q[:,:3],axis=1),q[:,3])
   vec=q[:,:3]*angle[:,None]/np.maximum(1e-6,np.linalg.norm(q[:,:3],axis=1))[:,None]
   axis=int(np.argmax(np.std(vec,axis=0)));ref=np.unwrap(vec[:,axis]);ref=(ref-ref[0])*.55
   if np.std(ref)<.015:continue
   refs.append(ref);used.append(path.relative_to(ROOT).as_posix()+':'+bone)
   if len(refs)>=count:break
  if len(refs)>=count:break
 ref=np.asarray(refs,dtype=np.float64);n=len(ref)
 velocity=np.gradient(ref,.01,axis=1);accel=np.clip(np.gradient(velocity,.01,axis=1),-45,45)
 return dict(ref=ref,velocity=velocity,ff=accel,strength=random.uniform(.75,1.25,n),damping=random.uniform(1.5,3.5,n),
             error=random.uniform(-.16,.16,n),speed=random.uniform(-.8,.8,n),impact=random.uniform(-2.8,2.8,n),sources=used)
train=data(groups[0],SEED+1);validation=data(groups[1],SEED+2);test=data(groups[2],SEED+3,48)
def rollout(weights,d,baseline=False):
 weights=np.atleast_2d(weights);p=len(weights);n=len(d['ref']);steps=d['ref'].shape[1]
 pos=np.broadcast_to(d['ref'][:,0]-d['error'],(p,n)).copy();vel=np.broadcast_to(d['speed'],(p,n)).copy()
 old=np.zeros((p,n));cost=np.zeros((p,n));sq=np.zeros_like(cost);jerk=np.zeros_like(cost);peak=np.zeros_like(cost)
 for t in range(steps):
  error=d['ref'][:,t]-pos;relative=d['velocity'][:,t]-vel
  if baseline=='original':u=625*error-50*vel
  elif baseline=='relative_pd':u=625*error+50*relative+d['ff'][:,t]
  else:
   h=np.tanh(np.clip(error,-.6,.6)[:,:,None]/.4*weights[:,None,:6]+np.clip(relative,-12,12)[:,:,None]/6*weights[:,None,6:12])
   u=140*np.tanh(np.sum(h*weights[:,None,12:18],axis=2))+d['ff'][:,t]
  u=np.clip(u,-140,140);du=u-old;old=u
  # A torque/acceleration-limited rotary link with uncertain response.
  vel+=(u*d['strength']-d['damping']*vel)*.01
  if t==55:vel+=d['impact']
  pos+=vel*.01
  cost+=12*error**2+.08*relative**2+.00015*u**2+.00055*du**2
  sq+=error**2;jerk+=du**2;peak=np.maximum(peak,np.abs(error))
 return dict(cost=np.mean(cost/steps,axis=1),rms=np.sqrt(np.mean(sq/steps,axis=1)),jerk=np.mean(jerk/steps,axis=1),peak=np.max(peak,axis=1))
mean=np.zeros(18);mean[0]=.55;mean[6]=1.05;mean[12]=1.0
std=np.full(18,.40);best=mean.copy();bestval=float('inf');history=[]
for generation in range(55):
 population=mean+std*rng.normal(size=(80,18));population[0]=best
 scores=rollout(population,train)['cost'];elite=population[np.argsort(scores)[:12]]
 mean=.25*mean+.75*np.mean(elite,axis=0);std=np.maximum(.025,.30*std+.70*np.std(elite,axis=0))
 candidate=population[int(np.argmin(scores))];v=float(rollout(candidate,validation)['cost'][0])
 if v<bestval:bestval=v;best=candidate.copy()
 if generation%5==0:history.append(dict(generation=generation,train=float(np.min(scores)),validation=bestval))
baseline=rollout(best,test,'original');relative_pd=rollout(best,test,'relative_pd');learned=rollout(best,test)
metrics=lambda row:{k:float(v[0])for k,v in row.items()}
accepted=learned['cost'][0]<baseline['cost'][0]*.90 and learned['cost'][0]<relative_pd['cost'][0]*.95 and learned['rms'][0]<.18 and learned['peak'][0]<.65
sources={p:hashlib.sha256((ROOT/p.split(':')[0]).read_bytes()).hexdigest()for d in [train,validation,test]for p in d['sources']}
report=dict(result='passed'if accepted else'rejected',algorithm='cross-entropy neural policy search on perturbed angular dynamics',seed=SEED,
 architecture=dict(inputs=['angular error / 0.4 rad','relative angular velocity / 6 rad/s'],hidden=6,activation='tanh',outputs=['bounded angular acceleration'],parameters=18),
 training=dict(generations=55,population=80,elite=12,rollout_steps=180,dt=.01,train_sources=train['sources'],validation_sources=validation['sources'],test_sources=test['sources'],source_sha256=sources),
 held_out=dict(original_motor=metrics(baseline),relative_pd_motor=metrics(relative_pd),learned_motor=metrics(learned)),history=history,weights=best.tolist(),
 scope='Learned upper-body angular servo with native motion references and domain-randomized reduced dynamics. Not Euphoria, AMP, a trained whole-body locomotion/balance policy, or proof of full-body sim-to-game transfer.')
out=ROOT/'config/learned-muscle-policy.json';out.write_text(json.dumps(report,indent=2)+'\n')
if not accepted:raise SystemExit('Policy rejected: '+json.dumps(report['held_out']))
values=','.join(f'{x:.9f}f'for x in best)
(ROOT/'src/onthepitch/player/humanoid/learned_muscle_policy.hpp').write_text('''#pragma once
// Generated by tools/animations/train_muscle_policy.py; reduced motor policy.
#include <algorithm>
#include <cmath>
namespace football_muscle {
constexpr bool trained=true;
constexpr float weights[18]={'''+values+'''};
inline float acceleration(float error,float relativeVelocity){
 if(!std::isfinite(error)||!std::isfinite(relativeVelocity))return 0;
 const float e=std::max(-.6f,std::min(.6f,error))/.4f;
 const float v=std::max(-12.f,std::min(12.f,relativeVelocity))/6.f;
 float result=0;for(unsigned i=0;i<6;++i)result+=std::tanh(e*weights[i]+v*weights[i+6])*weights[i+12];
 return 140.f*std::tanh(result);
}
}
''')
print(json.dumps(dict(result='passed',held_out=report['held_out'],generations=55)))
