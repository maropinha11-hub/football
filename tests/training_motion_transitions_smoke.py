#!/usr/bin/env python3
"""Check off-ball response and joint hinges during rapid locomotion changes."""
import argparse,collections,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':249');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=480,context_y=270,training_physical_rig='true',training_physical_lab='true',training_motion_diagnostics='true',simulation_seed=7))as g:
  g.reset();g.pad(1,0,buttons=1);g.advance(180);g.pad(0,0);g.advance(1100)
  for name,x,y,sprint,duration in [('run',0,-1,True,1800),('strafe',1,0,False,750),('stop',0,0,False,650),('restart',-1,0,False,750),('reverse',1,0,False,850),('stop_again',0,0,False,700)]:
   before=g.frames()[-1];start=len(g.read_log());g.pad(x,y,sprint=sprint);frames=g.advance(duration)
   if x or y:
    tail=frames[-3:];dx=tail[-1]['player'][0]-tail[0]['player'][0];dy=tail[-1]['player'][1]-tail[0]['player'][1]
    aligned=(dx*x-dy*y)/max(.00001,math.hypot(dx,dy)*math.hypot(x,y))
    check(name+' responds to the requested direction away from the ball',aligned>.7 and math.dist(before['player'][:2],frames[-1]['player'][:2])>.25,dict(alignment=aligned,travel=math.dist(before['player'][:2],frames[-1]['player'][:2]),ball_gap=math.dist(frames[-1]['player'][:2],frames[-1]['ball'][:2])))
   else:check(name+' does not wait for the end of a long clip',frames[-1]['speed']<.75,dict(final_speed=frames[-1]['speed'],travel=math.dist(before['player'][:2],frames[-1]['player'][:2])))
  poses=[]
  for line in g.read_log().splitlines():
   if line.startswith('MOTION_SIM '):
    d=dict(re.findall(r'(\w+)=([^\s]+)',line));poses.append([[float(v)for v in q.split(',')]for q in d['pose'].split(';')])
  swing=max(2*math.asin(min(1,math.hypot(q[i][1],q[i][2])))for q in poses for i in [8,11])
  check('knees preserve their hinge instead of twisting the mesh',swing<.35,dict(maximum_lateral_rotation_rad=swing))
  blends=collections.defaultdict(dict)
  for line in g.read_log().splitlines():
   if line.startswith('MOTION_MIXER '):
    d=dict(re.findall(r'(\w+)=([^\s]+)',line));blends[(d['actor'],int(d['t'])-int(d['age']),d['source'])][int(d['age'])]=d
  advancing=[]
  for key,rows in blends.items():
   lo,hi=min(rows),max(rows)
   if hi>=80 and float(rows[hi]['source_phase'])-float(rows[lo]['source_phase'])>4:advancing.append(key)
  check('outgoing animation keeps advancing during a gradual transition',len(advancing)>=2 and all(0<=float(d['weight'])<=1 for rows in blends.values()for d in rows.values()),dict(transitions=len(blends),advancing_transitions=len(advancing)))
  check('root and ball remain finite through starts, stops and reversals',all(math.isfinite(v)for f in g.frames()for v in f['player']+f['ball']),dict(samples=len(g.frames())))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
