#!/usr/bin/env python3
"""ARS residual torque learning in the native Bullet body, with a held-out gate.

This learns standing/push recovery, not complete football skills. The actor is
a linear 12-observation -> 36-joint-angle residual over the implicit motors.
No labelled pendulum or PD examples are used: rewards come from real rollouts.
"""
import argparse, concurrent.futures, hashlib, json, os, subprocess, tempfile
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]

def rollout(task):
    executable,weights,seed,push,seconds=task
    with tempfile.NamedTemporaryFile(mode='w',suffix='.weights',dir='/tmp') as file:
        np.savetxt(file,weights.reshape(-1),fmt='%.9g');file.flush()
        command=[executable,'--policy',file.name,'--seed',str(seed),'--push',str(push),'--seconds',str(seconds)]
        if os.environ.get('FOOTBALL_FULLBODY_LEGACY_V1')=='1':command.append('--legacy-v1')
        result=subprocess.run(command,
                              check=True,capture_output=True,text=True,timeout=30)
    return json.loads(result.stdout)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable',type=Path,default=ROOT/'build/fullbody_lab')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--epochs',type=int,default=120)
    p.add_argument('--directions',type=int,default=24)
    p.add_argument('--workers',type=int,default=2)
    p.add_argument('--legacy-v1',action='store_true')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    os.environ['FOOTBALL_FULLBODY_LEGACY_V1']='1'if a.legacy_v1 else'0'
    exe=str(a.executable.resolve());rng=np.random.default_rng(20261026)
    actor=np.zeros((36,12));best=actor.copy();best_reward=-1e9;history=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for epoch in range(a.epochs):
            noise=rng.normal(0,1,(a.directions,36,12))
            sigma=.025 if epoch<40 else .015
            seed=11+epoch%4;push=0 if epoch<30 else (epoch%3)*15
            tasks=[(exe,actor+sign*sigma*n,seed,push,4)for n in noise for sign in [1,-1]]
            rows=list(pool.map(rollout,tasks));rewards=np.array([r['reward']for r in rows]).reshape(-1,2)
            elite=np.argsort(rewards.max(axis=1))[-max(4,a.directions//2):]
            scale=max(float(rewards[elite].std()),.02)
            gradient=np.mean((rewards[elite,0]-rewards[elite,1])[:,None,None]*noise[elite],axis=0)/scale
            actor=np.clip(actor+.025*gradient,-2,2)
            evaluation=list(pool.map(rollout,[(exe,actor,s,p,5)for s in [11,12,13,14]for p in [0,15,30]]))
            score=float(np.mean([r['reward']for r in evaluation]))
            if score>best_reward:best_reward=score;best=actor.copy();np.savetxt(a.output/'candidate.weights',best.reshape(-1),fmt='%.9g')
            elif epoch%5==4:actor=best.copy()
            row=dict(epoch=epoch,reward=score,best_reward=best_reward,
                     standing=float(np.mean([r['standing_fraction']for r in evaluation])))
            history.append(row);print(json.dumps(row),flush=True)
            (a.output/'history.json').write_text(json.dumps(history,indent=2)+'\n')
        contexts=[(s,push)for s in range(101,113)for push in [0,15,30]]
        baseline=list(pool.map(rollout,[(exe,np.zeros_like(best),s,p,6)for s,p in contexts]))
        heldout=list(pool.map(rollout,[(exe,best,s,p,6)for s,p in contexts]))
    accepted=all(r['standing_fraction']>.95 and r['joint_error']<.05 and r['minimum_upright']>.7 for r in heldout)
    report=dict(result='accepted'if accepted else'rejected_for_runtime',
                algorithm='augmented random search; physical return, linear residual joint-angle policy',
                seed=20261026,simulator='legacy_v1'if a.legacy_v1 else'native_support_feedback',architecture=[12,36],train_seeds=[11,12,13,14],
                heldout_seeds=list(range(101,113)),heldout_pushes_ns=[0,15,30],epochs=a.epochs,
                executable_sha256=hashlib.sha256(Path(exe).read_bytes()).hexdigest(),
                baseline=baseline,heldout=heldout,weights=best.tolist(),
                scope='standing and small push recovery only; no learned football, locomotion or get-up policy')
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k not in ['weights','baseline','heldout']}))
    # A failed candidate is deliberately not installed into the game.
    if accepted:
        header='#pragma once\nnamespace football_fullbody_ml {\nconstexpr float weights[432]={'+','.join(f'{x:.9f}f' if abs(x)>1e-10 else '0.f'for x in best.flat)+'};\n}\n'
        (a.output/'learned_fullbody_policy.hpp').write_text(header)

if __name__=='__main__':main()
