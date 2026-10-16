#!/usr/bin/env python3
"""Exercise the reported F8/F9 and locomotion failures, not only finite bones."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
from native_training_harness import NativeTraining

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':170');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def qangle(a,b):return 2*math.acos(min(1,abs(sum(x*y for x,y in zip(a,b)))/math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))))
def frames(g):return [json.loads(x[19:])for x in g.log.read_text().splitlines()if x.startswith('PHYSICAL_RIG_FRAME ')]
def spine(log):return [list(map(float,q.split(',')))for q in re.findall(r'TRAINING_CONTACT_JOINTS[^\n]* j1=\[([^]]+)\]',log)]
def key(g,k):g.keys([k],True);g.keys([k],False)
def shot(g,name):subprocess.run(['import','-window',g.window,str(a.output/(name+'.png'))],env=g.env,check=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides={'context_x':640,'context_y':360,'training_physical_rig':'true','training_physical_lab':'true'})as g:
  speeds=[];travels=[]
  for enabled in (True,False):
   g.reset()
   if not enabled:key(g,'F7')
   origin=g.frames()[-1];g.pad(0,-1);f=g.advance(3000);g.pad(0,0)
   speeds.append(statistics.median(x['speed']for x in f[-20:]));travels.append(math.dist(origin['player'][:2],f[-1]['player'][:2]))
  check('physical tracking does not turn the approved dribble into slow motion',abs(speeds[0]-speeds[1])<.5 and min(travels)>7,dict(speed_mps=speeds,travel_m=travels))
  key(g,'F7');g.reset();before=spine(g.log.read_text())[-1];start=len(g.log.read_text());g.advance(700)
  normal=max(qangle(before,q)for q in spine(g.log.read_text()[start:]))
  g.reset();before=spine(g.log.read_text())[-1];start=len(g.log.read_text());key(g,'F8');g.advance(250);shot(g,'impact-f8');g.advance(600)
  pushed=max(qangle(before,q)for q in spine(g.log.read_text()[start:]))
  check('F8 makes the rendered torso visibly react beyond normal idle sway',pushed>normal+.05 and pushed<1.0,dict(idle_rotation_rad=normal,pushed_rotation_rad=pushed))
  g.reset();start_t=g.frames()[-1]['t'];key(g,'F9');g.advance(450);shot(g,'fall-450ms');g.advance(650);shot(g,'fall-1100ms');g.advance(1400);shot(g,'fall-2500ms')
  g.wait(lambda:any(f['mode']==0 and f['t']>start_t+3000 for f in frames(g)),seconds=20)
  fall=[f for f in frames(g)if f['mode']==1 and f['t']>start_t]
  rotation=sum(qangle(x['root_q'],y['root_q'])for x,y in zip(fall,fall[1:]))
  check('F9 produces one bounded fall rather than repeated somersaults',bool(fall)and rotation<5.5 and max(f['angular_speed']for f in fall)<=12.01,dict(root_rotation_rad=rotation,peak_segment_angular_speed_rad_s=max(f['angular_speed']for f in fall)))
  check('the body reaches the floor with connected Bullet joints',min(f['root'][2]for f in fall)<.45 and max(f['joint_error']for f in fall)<.08,dict(minimum_pelvis_m=min(f['root'][2]for f in fall),maximum_joint_anchor_error_m=max(f['joint_error']for f in fall)))
  check('physical diagnostics remain finite for active motors and free falls',all(math.isfinite(f[k])for f in frames(g)for k in ['energy','angular_speed','joint_error']),dict(samples=len(frames(g))))
  log=g.log.read_text();matches=[dict(re.findall(r'(\w+)=([^\s]+)',s))for s in log.splitlines()if s.startswith('MOTION_MATCH ')]
  check('motion matching searches multiple eligible native animations',sum(int(x['candidates'])>1 for x in matches)>10,dict(queries=len(matches),multiple_candidates=sum(int(x['candidates'])>1 for x in matches),indexed_entries=max(int(x['indexed'])for x in matches)))
  g.reset();key(g,'Tab');g.keys(['Right'],True);f=g.advance(250);g.keys(['Right'],False)
  check('camera sensitivity is increased from the previous profile',abs(f[-1]['head_yaw'])>1.05,dict(head_yaw_after_250ms=f[-1]['head_yaw']))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
