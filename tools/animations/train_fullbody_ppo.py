#!/usr/bin/env python3
"""PPO on the game's complete Bullet body; trained weights require held-out approval.

PyTorch is a training-only dependency. Neither PyTorch nor this pipe server is
required by the Windows game. A training checkpoint is never installed implicitly.
"""
import argparse, hashlib, json, os, struct, subprocess, time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.distributions.normal import Normal

from fullbody_protocol import Environment

def network(features, outputs, output_gain):
    model=nn.Sequential(nn.Linear(features,128),nn.Tanh(),nn.Linear(128,128),nn.Tanh(),nn.Linear(128,outputs))
    for layer in model:
        if isinstance(layer,nn.Linear):nn.init.orthogonal_(layer.weight,np.sqrt(2));nn.init.constant_(layer.bias,0)
    nn.init.orthogonal_(model[-1].weight,output_gain);return model

class Agent(nn.Module):
    def __init__(self):
        super().__init__();self.actor=network(148,20,.01);self.critic=network(148,1,1);self.logstd=nn.Parameter(torch.full((20,),-3.0))
    def policy(self, obs, action=None, deterministic=False):
        mean=self.actor(obs);distribution=Normal(mean,self.logstd.clamp(-4.,-.7).exp())
        if action is None:action=mean if deterministic else distribution.sample()
        return action,distribution.log_prob(action).sum(-1),distribution.entropy().sum(-1),self.critic(obs).squeeze(-1)

@torch.no_grad()
def evaluate(agent, executable, level, seeds=(1001,2003,3001), steps=500):
    rows=[]
    for seed in seeds:
        with Environment(executable,1,seed)as env:
            observation=env.reset(level);reward=0.;minimum=2.;min_up=1.;failures=0;error=0.;travel=0.;progress=0.;goal=0.;lift=0.;single_support=0
            for _ in range(steps):
                action,*_=agent.policy(torch.as_tensor(observation),deterministic=True)
                observation,r,d,diagnostics=env.step(action.numpy(),level);reward+=float(r[0]);minimum=min(minimum,float(diagnostics[0,0]));min_up=min(min_up,float(diagnostics[0,1]));failures+=int(diagnostics[0,4]);error+=float(diagnostics[0,3]);travel=max(travel,float(diagnostics[0,2]))
                if env.diagnostics>=9:progress=float(diagnostics[0,6]);goal=float(diagnostics[0,7]);lift=max(lift,float(diagnostics[0,8]));single_support+=int(observation[0,123]+observation[0,124]==1)
            rows.append(dict(seed=seed,level=level,reward=reward,minimum_height=minimum,minimum_upright=min_up,falls=failures,mean_velocity_error=error/steps,travel=travel,forward_progress=progress,commanded_distance=goal,progress_ratio=progress/max(goal,.001),maximum_foot_height=lift,single_support_fraction=single_support/steps))
    return rows

def save_checkpoint(agent, optimizer, path):
    temporary=path.with_suffix('.partial.pt')
    torch.save(dict(model=agent.state_dict(),optimizer=optimizer.state_dict()),temporary)
    temporary.replace(path)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--executable',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--steps',type=int,default=2_000_000);p.add_argument('--environments',type=int,default=16);p.add_argument('--horizon',type=int,default=256);p.add_argument('--seed',type=int,default=11)
    p.add_argument('--resume',type=Path);p.add_argument('--level',type=float,default=0.);p.add_argument('--auto-curriculum',action='store_true');p.add_argument('--evaluate-only',action='store_true');p.add_argument('--exploration',type=float);p.add_argument('--reference-variant',choices=('legacy','flat-soles'),default='legacy');a=p.parse_args()
    os.environ['FOOTBALL_RL_REFERENCE']=a.reference_variant
    torch.set_num_threads(2);torch.set_num_interop_threads(1);np.random.seed(a.seed);torch.manual_seed(a.seed)
    a.executable=a.executable.resolve();a.output.mkdir(parents=True,exist_ok=True)
    agent=Agent();optimizer=torch.optim.Adam(agent.parameters(),lr=2e-4,eps=1e-5)
    if a.resume:
        saved=torch.load(a.resume,map_location='cpu',weights_only=True);agent.load_state_dict(saved['model'])
        if not a.evaluate_only and 'optimizer'in saved:optimizer.load_state_dict(saved['optimizer'])
    if a.exploration is not None:
        with torch.no_grad():agent.logstd.fill_(a.exploration)
    if a.evaluate_only:
        rows=evaluate(agent,a.executable,a.level);print(json.dumps(rows,indent=2));(a.output/'evaluation.json').write_text(json.dumps(rows,indent=2)+'\n');return
    n=a.environments;t=a.horizon;updates=max(1,a.steps//(n*t));level=a.level;started=time.monotonic();total=0;history=[]
    with Environment(a.executable,n,a.seed)as env:
        observation=env.reset(level)
        for update in range(updates):
            observations=torch.empty((t,n,148));actions=torch.empty((t,n,20));logs=torch.empty((t,n));values=torch.empty((t,n));rewards=torch.empty((t,n));dones=torch.empty((t,n))
            falls=0;health=[];errors=[]
            for step in range(t):
                observations[step]=torch.as_tensor(observation)
                with torch.no_grad():action,log,_,value=agent.policy(observations[step])
                actions[step]=action;logs[step]=log;values[step]=value
                observation,r,d,metrics=env.step(action.numpy(),level);rewards[step]=torch.as_tensor(r);dones[step]=torch.as_tensor(d)
                falls+=int(metrics[:,4].sum());health.extend(metrics[:,0].tolist());errors.extend(metrics[:,3].tolist())
            total+=t*n
            with torch.no_grad():last=agent.critic(torch.as_tensor(observation)).squeeze(-1)
            advantages=torch.zeros_like(rewards);gae=torch.zeros(n)
            for step in reversed(range(t)):
                following=last if step==t-1 else values[step+1];alive=1-dones[step]
                delta=rewards[step]+.99*following*alive-values[step];gae=delta+.99*.95*alive*gae;advantages[step]=gae
            returns=(advantages+values).flatten();advantages=advantages.flatten();advantages=(advantages-advantages.mean())/(advantages.std()+1e-8)
            flat_obs=observations.reshape(-1,148);flat_actions=actions.reshape(-1,20);flat_logs=logs.flatten()
            clips=[];kls=[]
            for epoch in range(5):
                permutation=torch.randperm(t*n)
                for indices in permutation.split(512):
                    _,new_log,entropy,value=agent.policy(flat_obs[indices],flat_actions[indices]);ratio=(new_log-flat_logs[indices]).exp()
                    policy_loss=torch.maximum(-advantages[indices]*ratio,-advantages[indices]*ratio.clamp(.8,1.2)).mean()
                    value_loss=.5*(value-returns[indices]).square().mean();loss=policy_loss+.5*value_loss-.001*entropy.mean()
                    optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(agent.parameters(),.5);optimizer.step()
                    with torch.no_grad():kls.append(float(((ratio-1)-(new_log-flat_logs[indices])).mean()));clips.append(float(((ratio-1).abs()>.2).float().mean()))
                if kls and np.mean(kls[-8:])>.025:break
            row=dict(update=update+1,steps=total,level=level,falls=falls,mean_height=float(np.mean(health)),mean_velocity_error=float(np.mean(errors)),reward=float(rewards.mean()),kl=float(np.mean(kls)),clip=float(np.mean(clips)),seconds=time.monotonic()-started,logstd=float(agent.logstd.mean()))
            history.append(row)
            if update%4==0 or update==updates-1:
                print(json.dumps(row),flush=True);save_checkpoint(agent,optimizer,a.output/'checkpoint.pt')
                (a.output/'progress.json').write_text(json.dumps(dict(result='training',runtime_loaded=False,history=history),indent=2)+'\n')
            if a.auto_curriculum and(update+1)%16==0:
                rows=evaluate(agent,a.executable,level,seeds=(71,83),steps=250)
                if all(r['falls']==0 and r['minimum_height']>.78 and r['minimum_upright']>.85 and(level<.35 or r['progress_ratio']>.55)for r in rows):
                    level=min(1.,level+.10);observation=env.reset(level);print(json.dumps(dict(curriculum_level=level,training_evaluation=rows)),flush=True)
        save_checkpoint(agent,optimizer,a.output/'checkpoint.pt')
    heldout=evaluate(agent,a.executable,level)
    accepted=all(r['falls']==0 and r['minimum_height']>.78 and r['minimum_upright']>.85 and r['mean_velocity_error']<.18 and(level<.05 or(r['progress_ratio']>.7 and r['maximum_foot_height']>.10 and r['single_support_fraction']>.05))for r in heldout)
    report=dict(reference_variant=a.reference_variant,result='accepted_for_this_curriculum_only'if accepted else'rejected',runtime_loaded=False,scope='stand/balance/locomotion curriculum; no ball or opponents trained',steps=total,level=level,seed=a.seed,executable_sha256=hashlib.sha256(a.executable.read_bytes()).hexdigest(),observations=148,actions=20,history=history,heldout=heldout,seconds=time.monotonic()-started)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='history'}),flush=True)
if __name__=='__main__':main()
