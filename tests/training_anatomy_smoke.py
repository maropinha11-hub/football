#!/usr/bin/env python3
"""Observe the rendered arms, graduated impacts and actual grip slowdown."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from native_training_harness import NativeTraining

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':186');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def events(g,prefix,start=0):
 return [dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[start:].splitlines()if x.startswith(prefix+' ')]
def key(g,k):g.keys([k],True);g.advance(100);g.keys([k],False);g.advance(100)
def capture(g,name):subprocess.run(['import','-window',g.window,str(a.output/(name+'.png'))],env=g.env,check=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides={'context_x':640,'context_y':360,'training_physical_rig':'true','training_physical_lab':'true'})as g:
  g.reset();start=len(g.read_log());origin=g.frames()[-1]['player']
  g.keys(['Shift_L'],True);key(g,'F8');g.keys(['Shift_L'],False);g.advance(400);capture(g,'recoverable-strong-impact');f=g.advance(2600)
  controlled=events(g,'PHYSICAL_BALANCE_BANK')[0]['actor']
  rows=events(g,'PHYSICAL_IMPACT_TEST',start);balance=[x for x in events(g,'PHYSICAL_BALANCE',start)if x['actor']==controlled];states=events(g,'PHYSICAL_RIG_STATE',start)
  movement=[x for x in g.frames()if x['t']>=int(rows[0]['t'])]if rows else[]
  displacement=max((math.dist(origin[:2],x['player'][:2])for x in movement),default=0)
  check('Shift+F8 requests a stronger ordinary impulse without forcing a fall',bool(rows)and rows[0]['level']=='strong'and float(rows[0]['impulse'])==190 and rows[0]['forced']=='0',rows)
  check('strong contact uses an authored protective step and recovers upright',displacement>.04 and bool(events(g,'PHYSICAL_STAGGER_CLIP',start)) and any(x['function']==12 for x in movement) and not any(x['to']=='1'for x in states)and f[-1]['speed']<.5,dict(displacement_m=displacement,final_speed=f[-1]['speed'],states=states))
  check('capture-point recovery demand falls after its initial peak',bool(balance)and max(float(x['step'])for x in balance)>.05 and float(balance[-1]['risk'])<.05,balance[:10]+balance[-3:])
  for delay in [100,200]:
   g.reset();g.advance(delay);origin=g.frames()[-1]['player'];start=len(g.read_log())
   g.keys(['Shift_L'],True);key(g,'F8');g.keys(['Shift_L'],False);f=g.advance(2600)
   impacts=events(g,'PHYSICAL_IMPACT_TEST',start);states=events(g,'PHYSICAL_RIG_STATE',start)
   movement=[x for x in g.frames()if x['t']>=int(impacts[0]['t'])]
   displacement=max(math.dist(origin[:2],x['player'][:2])for x in movement)
   check('support step survives idle phase offset '+str(delay)+' ms',displacement>.04 and bool(events(g,'PHYSICAL_STAGGER_CLIP',start)) and any(x['function']==12 for x in movement) and not any(x['to']=='1'for x in states)and f[-1]['speed']<.5,dict(displacement_m=displacement,final_speed=f[-1]['speed'],states=states))
  g.reset();start=len(g.read_log());g.keys(['Control_L'],True);key(g,'F8');g.keys(['Control_L'],False);g.advance(1300);capture(g,'overload-impact');g.advance(6500)
  states=events(g,'PHYSICAL_RIG_STATE',start);rows=events(g,'PHYSICAL_IMPACT_TEST',start)
  check('Ctrl+F8 overload tries balance before an unforced fall and original get-up',bool(rows)and rows[0]['forced']=='0'and any(x['from']=='0'and x['to']=='1'and int(x['t'])-int(rows[0]['t'])>=200 for x in states)and any(x['from']=='2'and x['to']=='0'for x in states),dict(impacts=rows,states=states))
  g.reset();key(g,'F10');start=len(g.read_log());g.keys(['h'],True);g.advance(900);capture(g,'bounded-shirt-reach');g.advance(1100);g.keys(['h'],False);g.advance(300)
  forces=events(g,'PHYSICAL_GRIP_FORCE',start)
  slowing=[x for x in forces if float(x['intended_speed'])-float(x['actual_speed'])>.03]
  check('shirt hold actually slows the escaping partner rather than only logging a force',len(slowing)>=4,dict(samples=len(forces),slowed_samples=len(slowing),examples=slowing[:6]))
  # Exercise running, diagonal turns and release as well as the hand reach.
  for x,y in [(0,-1),(.7,-.7),(-.7,.7),(0,1)]:
   g.pad(x,y,sprint=True);g.advance(500)
  g.pad(0,0);g.advance(500)
  final=events(g,'PHYSICAL_ARM_RENDER')
  check('final rendered arm poses obey joint limits after all crossfades',len(final)>100 and all(float(x['error'])<.00001 for x in final),dict(samples=len(final),maximum_error_rad=max(float(x['error'])for x in final)))
  check('final rendered forearms remain outside the trunk proxy',bool(final)and max(float(x['penetration'])for x in final)<.004,dict(maximum_penetration_m=max(float(x['penetration'])for x in final)))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
