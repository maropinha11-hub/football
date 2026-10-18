#!/usr/bin/env python3
"""Backward pass must turn the body, finish a real contact and remain usable."""
import argparse,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':173');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def events(s,prefix):return [dict(re.findall(r'(\w+)=([^\s]+)',x))for x in s.splitlines()if x.startswith(prefix+' ')]
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides={'context_x':640,'context_y':360,'training_physical_rig':'true','training_physical_lab':'true'})as g:
  for name,stick in [('straight',(1,0)),('behind',(-1,0)),('behind_on_release',(-1,0))]:
   g.reset();start=len(g.read_log());g.pad(*( (1,0)if name=='behind_on_release'else stick),buttons=1);g.advance(180);g.pad(*stick);f=g.advance(2500);g.pad(0,0)
   log=g.read_log()[start:];hits=[x for x in events(log,'TRAINING_ACTION_TOUCH')if x['function']=='4'];turn=events(log,'PHYSICAL_PASS_TURN')
   check(name+' pass completes with a real foot contact',len(hits)==1 and max(x['ball_speed']for x in f)>4,dict(hits=hits,turn=turn,peak_ball_speed=max(x['ball_speed']for x in f)))
   if name.startswith('behind'):
    selected=[x for x in events(log,'TRAINING_NATIVE_START')if x['function']=='4']
    contact=int(hits[0]['t'])if hits else 0
    before=[x for x in g.frames()if contact-100<=x['t']<=contact]
    facing=math.cos(before[-1]['player_yaw'])if before else 1
    check(name+' pass turns the body and uses a forward pass clip',bool(selected)and all('/000.anim'in x['name']for x in selected)and facing<-.35,dict(turn=turn,selected=selected,facing_dot_original_forward=facing))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
