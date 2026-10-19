#!/usr/bin/env python3
"""Compare final rendered joint continuity with independent versus coherent poses."""
import argparse,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':248');a=p.parse_args()
r=dict(result='running',checks=[],measurements=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def velocity(q,p,dt):
 # shortest quaternion rotation from p to q, in local radians/second
 dot=sum(x*y for x,y in zip(q,p));q=[x*(-1 if dot<0 else 1)for x in q]
 x,y,z,w=q;u,v,s,t=p
 delta=[-w*u+x*t-y*s+z*v,-w*v+x*s+y*t-z*u,-w*s-x*v+y*u+z*t,w*t+x*u+y*v+z*s]
 n=math.sqrt(sum(x*x for x in delta[:3]));scale=2*math.atan2(n,delta[3])/max(n,1e-12)/dt
 return [x*scale for x in delta[:3]]
def metrics(log):
 rows=[]
 for line in log.splitlines():
  if not line.startswith('MOTION_SIM '):continue
  d=dict(re.findall(r'(\w+)=([^\s]+)',line));t=int(d['t']);pose=[[float(v)for v in q.split(',')]for q in d['pose'].split(';')]
  if not rows or t>rows[-1][0]:rows.append((t,pose))
  elif t==rows[-1][0]:rows[-1]=(t,pose) # Keep the final contact evaluation of this tick.
 speeds=[];accelerations=[];previous=None
 for (t,p),(now,q)in zip(rows,rows[1:]):
  dt=(now-t)*.001
  if not .001<=dt<=.2:previous=None;continue
  v=[velocity(q[i],p[i],dt)for i in range(3,13)]
  speeds.extend(math.sqrt(sum(x*x for x in bone))for bone in v)
  if previous:
   accelerations.extend(math.sqrt(sum((x-y)**2 for x,y in zip(bone,old)))/dt for bone,old in zip(v,previous))
  previous=v
 def quantile(xs,f):return sorted(xs)[min(len(xs)-1,int(len(xs)*f))]if xs else 0
 return dict(samples=len(rows),speed_p99=quantile(speeds,.99),acceleration_p95=quantile(accelerations,.95),acceleration_rms=math.sqrt(sum(x*x for x in accelerations)/max(1,len(accelerations))))
try:
 for coherent in [False,True]:
  with NativeTraining(a.build,a.output/('coherent'if coherent else'previous'),display=a.display,analog_pad=True,camera=1,
      config_overrides=dict(context_x=480,context_y=270,training_physical_rig='true',training_physical_lab='true',training_motion_diagnostics='true',training_coherent_pose=str(coherent).lower(),training_motion_tracking=str(coherent).lower(),training_motion_continuity=str(coherent).lower(),simulation_seed=7))as g:
   for name,x,y,sprint in [('running',0,-1,True),('strafe',1,0,False)]:
    g.reset();start=len(g.read_log());origin=g.frames()[-1];g.pad(x,y,sprint=sprint);frames=g.advance(3200);g.pad(0,0)
    m=metrics(g.read_log()[start:]);m.update(coherent=coherent,scenario=name,travel=math.dist(origin['player'][:2],frames[-1]['player'][:2]));r['measurements'].append(m)
    rendered=[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[start:].splitlines()if x.startswith('MOTION_RENDER ')]
    check(name+' '+str(coherent)+' has finite motion and responds to input',m['samples']>250 and len(rendered)>25 and m['travel']>3 and all(math.isfinite(m[k])for k in ['speed_p99','acceleration_p95','acceleration_rms']),dict(**m,rendered_samples=len(rendered)))
    if coherent:check(name+' renders the same final lower-body pose as the contact simulation',bool(rendered)and max(float(x['lower_error'])for x in rendered)<.0001,dict(maximum_error=max((float(x['lower_error'])for x in rendered),default=999)))
   g.keys(['Escape'],True);g.game.wait(timeout=15)
 for name in ['running','strafe']:
  old,new=[x for x in r['measurements']if x['scenario']==name]
  check(name+' reduces fixed-step high-frequency joint acceleration',new['acceleration_rms']<old['acceleration_rms']*.95,dict(previous=old,coherent=new))
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
