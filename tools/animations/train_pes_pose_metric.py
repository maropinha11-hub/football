"""Fit and hold out a pose/trajectory metric on the actual retargeted library.

This learns selection costs, not new poses, physics or a balance controller.
Direction/speed variants and mirrors of a motion family stay in one partition.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
from packed_animation import read_text

def product(a,b):
    xyz=a[:,:3]*b[:,3:]+b[:,:3]*a[:,3:]+np.cross(a[:,:3],b[:,:3])
    return np.column_stack((xyz,a[:,3]*b[:,3]-np.sum(a[:,:3]*b[:,:3],axis=1)))

def rotate(q,v):
    v=np.broadcast_to(v,q[:,:3].shape)
    t=2*np.cross(q[:,:3],v)
    return v+q[:,3:]*t+np.cross(q[:,:3],t)

def extract(bank):
    catalog=json.loads((bank/'catalog.json').read_text())
    bind=json.loads((ROOT/'tools/animations/native_rig_reference.json').read_text())
    parents=[-1,0,1,1,3,1,5,0,7,8,0,10,11]
    arrays=[];names=[];kinds=[];clip_ids=[];frames=[];families=[]
    for clip_id,row in enumerate(catalog['actions']):
        tracks={}
        for line in read_text(bank/row['file']).splitlines():
            fields=line.split(',')
            if fields[0]not in ['player',*(b['name']for b in bind['bones'])]:continue
            width=4 if fields[0]=='player'else 5
            tracks[fields[0]]=np.asarray(fields[1:],dtype=np.float64).reshape(-1,width)[:,1:]
        root=tracks['player'].copy();root[:,2]+=.96
        n=len(root);global_q=[];positions=[]
        for bone,b in enumerate(bind['bones']):
            q=tracks[b['name']];q/=np.linalg.norm(q,axis=1)[:,None]
            parent=parents[bone]
            global_q.append(q if parent<0 else product(global_q[parent],q))
            positions.append(root if parent<0 else positions[parent]+rotate(global_q[parent],np.asarray(b['offset'])))
        joints=[9,12,2,4,6];p=np.stack([positions[j]-root for j in joints],axis=1).reshape(n,15)
        world=np.stack([positions[j]for j in joints],axis=1).reshape(n,15)
        velocity=np.concatenate((np.diff(world,axis=0)*100,np.zeros((1,15))),axis=0)
        columns=[p,velocity];time=np.arange(n)
        tail=root[-1]-root[-2]
        for ticks in [15,30,45]:
            at=time+ticks;future=root[np.minimum(at,n-1)].copy()+np.maximum(at-(n-1),0)[:,None]*tail
            delta=future-root;delta[:,2]=0;columns.append(delta)
        for ticks in [15,30,45]:
            q=global_q[0][np.minimum(time+ticks,n-1)]
            facing=rotate(q,np.array([0,-1,0]));facing[:,2]=0;columns.append(facing)
        for foot in [9,12]:
            vertical=np.concatenate((np.diff(positions[foot][:,2])*100,[0]))
            columns.append(((positions[foot][:,2]<.12)&(np.abs(vertical)<.4))[:,None].astype(float))
        x=np.column_stack(columns)
        assert x.shape==(n,50)and np.isfinite(x).all()
        selected=np.arange(0,max(1,n-2),2);arrays.append(x[selected])
        names.extend([row['source']]*len(selected));kinds.extend([row['role']]*len(selected))
        clip_ids.extend([clip_id]*len(selected));frames.extend(selected)
        family=re.sub(r'(?:^|_)(?:f?\d{3}|ver\d+|[0-4])(?=_|$)','_',row['source'])
        families.extend([family]*len(selected))
    return np.vstack(arrays),np.asarray(names),np.asarray(kinds),np.asarray(clip_ids),np.asarray(frames),np.asarray(families)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bank',type=Path,required=True);p.add_argument('--header',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--cache',type=Path,required=True)
    a=p.parse_args();seed=20261031;rng=np.random.default_rng(seed)
    bank_hash=hashlib.sha256((a.bank/'catalog.json').read_bytes()).hexdigest()
    if a.cache.exists():
        cached=np.load(a.cache);assert str(cached['bank_hash'])==bank_hash
        x,names,kinds,clips,frames,families=[cached[k]for k in ['x','names','kinds','clips','frames','families']]
    else:
        x,names,kinds,clips,frames,families=extract(a.bank)
        np.savez_compressed(a.cache,x=x,names=names,kinds=kinds,clips=clips,frames=frames,families=families,bank_hash=bank_hash)
    split=np.array([int(hashlib.sha256(n.encode()).hexdigest()[:8],16)%5 for n in families])
    ids={'train':np.flatnonzero(split>=2),'validation':np.flatnonzero(split==0),'test':np.flatnonzero(split==1)}
    base=np.r_[np.ones(15),np.full(15,np.sqrt(.015)),np.full(9,np.sqrt(1.5)),np.full(9,np.sqrt(.2)),[.5,.5]]
    floor=np.r_[np.full(15,.12),np.full(15,.75),np.full(9,.18),np.full(9,.35),[.4,.4]]
    scale=base/np.maximum(x[ids['train']].std(axis=0),floor)
    def triplets(indices,count):
        eligible=indices[(indices+1<len(x))&(clips[np.minimum(indices+1,len(x)-1)]==clips[indices])]
        aa=rng.choice(eligible,count);horizon=rng.integers(1,5,count);pp=aa.copy()
        for i,(anchor,offset) in enumerate(zip(aa,horizon)):
            target=min(anchor+offset,len(x)-1)
            while clips[target]!=clips[anchor]:target-=1
            pp[i]=max(anchor+1,target)
        nn=np.empty(count,dtype=int)
        groups={k:indices[kinds[indices]==k]for k in set(kinds[indices])}
        for begin in range(0,count,256):
            end=min(count,begin+256);anchor=aa[begin:end]
            opts=np.stack([rng.choice(groups[kinds[i]],24)for i in anchor])
            delta=(x[opts,30:48]-x[pp[begin:end],None,30:48])*scale[None,None,30:48]
            gap=((x[opts,:15]-x[pp[begin:end],None,:15])**2).sum(axis=2)
            costs=(delta**2).sum(axis=2);costs[(gap<.025**2)|(opts==pp[begin:end,None])]=np.inf
            chosen=np.argmin(costs,axis=1);nn[begin:end]=opts[np.arange(len(anchor)),chosen]
        query=x[aa].copy();query[:,30:48]=x[pp,30:48];query[:,:15]+=rng.normal(0,.01,query[:,:15].shape)
        dp=((query-x[pp])*scale)**2;dn=((query-x[nn])*scale)**2
        baseline=float(np.mean(np.sum(((query-x[pp])*base)**2,axis=1)<np.sum(((query-x[nn])*base)**2,axis=1)))
        return dp-dn,baseline
    train,original_train=triplets(ids['train'],65000)
    validation,original_validation=triplets(ids['validation'],12000)
    test,original_test=triplets(ids['test'],12000)
    accuracy=lambda d,w:float(np.mean(d@w<0))
    weights=np.ones(50);best=weights.copy();best_score=accuracy(validation,weights);m=np.zeros(50);v=np.zeros(50);history=[]
    for step in range(1,901):
        d=train[rng.integers(0,len(train),2048)]
        sigmoid=1/(1+np.exp(-np.clip(.12+d@weights,-40,40)))
        gradient=(sigmoid[:,None]*d).mean(axis=0)+.008*(weights-1)
        m=.9*m+.1*gradient;v=.999*v+.001*gradient*gradient
        weights-=.025*(m/(1-.9**step))/(np.sqrt(v/(1-.999**step))+1e-8);weights=np.clip(weights,.08,6)
        for left,right in [(0,3),(9,12),(15,18),(24,27)]:
            weights[left:left+3]=weights[right:right+3]=(weights[left:left+3]+weights[right:right+3])*.5
        weights[48:50]=weights[48:50].mean()
        if step%50==0:
            score=accuracy(validation,weights);history.append(dict(step=step,accuracy=score))
            if score>best_score:best=weights.copy();best_score=score
    normalized=accuracy(test,np.ones(50));learned=accuracy(test,best)
    accepted=learned>normalized+.0005 and learned>=original_test
    learned_scale=scale*np.sqrt(best)
    report=dict(result='passed'if accepted else'rejected',algorithm='Positive diagonal metric learned with temporal ranking',
                bank_catalog_sha256=bank_hash,seed=seed,source_clips=len(set(clips.tolist())),sampled_frames=len(x),dimensions=50,
                partitions={k:dict(frames=len(v),families=len(set(families[v].tolist())))for k,v in ids.items()},
                split_rule='Direction, speed and mirror variants remain with their normalized motion family.',
                task='Rank 20-80 ms real continuations under 1 cm pose noise and requested future trajectory.',
                test_pair_accuracy=dict(original=original_test,normalization_only=normalized,learned=learned),
                scale=learned_scale.tolist(),weights=best.tolist(),validation_history=history,
                limitations='Selection metric only; synthetic temporal queries from real poses, not original PES ball traces, motion synthesis or a learned physical controller.')
    if accepted:
        values=','.join(format(float(v),'.9e')+'f'for v in learned_scale)
        a.header.write_text('#pragma once\n// Generated by train_pes_pose_metric.py; family-held-out evaluation in docs.\nnamespace football_pes_matching {\nconstexpr bool trained=true;\nconstexpr float scale[50]={'+values+'};\n}\n')
        report['header_sha256']=hashlib.sha256(a.header.read_bytes()).hexdigest()
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['result','source_clips','sampled_frames','partitions','test_pair_accuracy']}))
    raise SystemExit(0 if accepted else 1)

if __name__=='__main__':main()
