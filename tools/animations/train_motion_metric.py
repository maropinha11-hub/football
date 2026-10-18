#!/usr/bin/env python3
"""Learn a positive diagonal pose metric from the game's exported native frames.

This is metric learning, not a generative network or a learned balance policy.
Clip families (including mirrors) are separated before triplets are sampled.
"""
import argparse,hashlib,json,re
from pathlib import Path
import numpy as np

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--input',type=Path,required=True)
p.add_argument('--header',type=Path,required=True)
p.add_argument('--report',type=Path,required=True)
p.add_argument('--seed',type=int,default=61127)
a=p.parse_args();rng=np.random.default_rng(a.seed)
rows=[json.loads(x)for x in a.input.read_text().splitlines()]
x=np.asarray([r['feature']for r in rows],dtype=np.float64)
assert x.shape[1]==50 and np.isfinite(x).all()
family=[r['name'].replace('_mirror','')for r in rows]
split=np.array([int(hashlib.sha256(n.encode()).hexdigest()[:8],16)%5 for n in family])
parts={'train':np.flatnonzero(split>=2),'validation':np.flatnonzero(split==0),'test':np.flatnonzero(split==1)}
lookup={(r['clip'],r['frame']):i for i,r in enumerate(rows)}
next_row=np.array([lookup.get((r['clip'],r['frame']+2),-1)for r in rows])
base=np.array([1.0 if i<15 else .20 if i<30 else 1.2247449 if i<39 else .4472136 if i<48 else 1.2 for i in range(50)])
floor=np.array([.10 if i<15 else .75 if i<30 else .18 if i<39 else .35 if i<48 else .40 for i in range(50)])
standard=np.maximum(x[parts['train']].std(axis=0),floor)
scale=base/standard

def triplets(ids,count):
 eligible=ids[next_row[ids]>=0];assert len(eligible)>100
 anchor=rng.choice(eligible,count);positive=next_row[anchor]
 negative=np.empty(count,dtype=np.int64)
 kinds=np.array([r['kind']for r in rows]);groups={kind:ids[kinds[ids]==kind]for kind in np.unique(kinds[ids])}
 # Match the intended future path before selecting a difficult wrong pose.
 # Actual lower-body poses and foot-contact phase distinguish the candidates.
 for begin in range(0,count,256):
  end=min(count,begin+256);aa=anchor[begin:end];n=len(aa)
  options=np.stack([rng.choice(groups[kinds[index]],24)for index in aa])
  delta=(x[options,30:48]-x[positive[begin:end],None,30:48])*scale[None,None,30:48]
  distance=np.square(delta).sum(axis=2)
  pose_gap=np.square(x[options,:15]-x[positive[begin:end],None,:15]).sum(axis=2)
  distance[(pose_gap<.025**2)|(options==positive[begin:end,None])]=np.inf
  choices=np.argmin(distance,axis=1);negative[begin:end]=options[np.arange(n),choices]
  invalid=~np.isfinite(distance[np.arange(n),choices])
  if invalid.any():negative[begin:end][invalid]=rng.choice(ids,int(invalid.sum()))
 query=x[anchor].copy();query[:,30:48]=x[positive,30:48]
 query[:,:15]+=rng.normal(0,.002,query[:,:15].shape)
 pos=np.square((query-x[positive])*scale);neg=np.square((query-x[negative])*scale)
 return pos,neg,query,positive,negative

train=triplets(parts['train'],65000);validation=triplets(parts['validation'],12000);test=triplets(parts['test'],12000)
def accuracy(dataset,w):return float(np.mean((dataset[0]-dataset[1])@w<0))
weight=np.ones(50);m=np.zeros(50);v=np.zeros(50);best=weight.copy();best_score=accuracy(validation,weight);history=[]
for step in range(1,901):
 indices=rng.integers(0,len(train[0]),2048)
 delta=train[0][indices]-train[1][indices]
 margin=.12+delta@weight;sigmoid=1/(1+np.exp(-np.clip(margin,-40,40)))
 gradient=(sigmoid[:,None]*delta).mean(axis=0)+.008*(weight-1)
 m=.9*m+.1*gradient;v=.999*v+.001*gradient*gradient
 weight-=.025*(m/(1-.9**step))/(np.sqrt(v/(1-.999**step))+1e-8)
 weight=np.clip(weight,.08,6)
 # Mirrored body sides must not acquire a different cost simply from sampling.
 for left,right in [(0,3),(9,12),(15,18),(24,27)]:
  pair=(weight[left:left+3]+weight[right:right+3])*.5
  weight[left:left+3]=pair;weight[right:right+3]=pair
 weight[48:50]=weight[48:50].mean()
 if step%50==0:
  score=accuracy(validation,weight);history.append({'step':step,'validation_pair_accuracy':score})
  if score>best_score:best_score=score;best=weight.copy()
learned_scale=scale*np.sqrt(best)
q=test[2];positive=x[test[3]];negative=x[test[4]]
original=float(np.mean(np.square((q-positive)*base).sum(axis=1)<np.square((q-negative)*base).sum(axis=1)))
normalized=accuracy(test,np.ones(50));learned=accuracy(test,best)
# A learned metric is shipped only when the unseen clip families improve.
accepted=learned>normalized+.0005 and learned>=original
report={'result':'passed'if accepted else'rejected','algorithm':'positive diagonal Mahalanobis metric, supervised temporal ranking','seed':a.seed,'bank_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'frames':len(rows),'clips':len({r['clip']for r in rows}),'families':len(set(family)),'dimensions':50,'partitions':{name:{'frames':len(ids),'families':len({family[i]for i in ids})}for name,ids in parts.items()},'triplets':{'train':65000,'validation':12000,'test':12000},'test_pair_accuracy':{'original':original,'normalization_only':normalized,'learned':learned},'scale':learned_scale.tolist(),'learned_weights':best.tolist(),'validation_history':history,'scope':'native pose/trajectory selection only; no neural motion synthesis, external capture, or reinforcement-trained physical controller'}
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n')
if accepted:
 values=','.join(f'{z:.9g}f'if '.'in f'{z:.9g}'or'e'in f'{z:.9g}'else f'{z:.9g}.0f'for z in learned_scale)
 a.header.parent.mkdir(parents=True,exist_ok=True)
 a.header.write_text('#pragma once\n// Generated by tools/animations/train_motion_metric.py from the native bank.\n// Training/test clip families are disjoint, including mirrored variants.\nnamespace football_physics {\nconstexpr bool kMotionMetricTrained=true;\nconstexpr float kMotionMetricScale[50]={'+values+'};\n}\n')
print(json.dumps({k:report[k]for k in ['result','algorithm','frames','clips','families','test_pair_accuracy','partitions']}))
raise SystemExit(0 if accepted else 1)
