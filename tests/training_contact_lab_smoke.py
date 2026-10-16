#!/usr/bin/env python3
"""Rendered checks for grounded get-ups, real hand reach and shirt contact."""
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
p.add_argument('--display',default=':172');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def events(g,prefix,start=0):
 return [dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.log.read_text()[start:].splitlines()if x.startswith(prefix+' ')]
def frames(g):return [json.loads(x[19:])for x in g.log.read_text().splitlines()if x.startswith('PHYSICAL_RIG_FRAME ')]
def key(g,k):g.keys([k],True);g.advance(100);g.keys([k],False);g.advance(100)
def screenshot(g,name):subprocess.run(['import','-window',g.window,str(a.output/(name+'.png'))],env=g.env,check=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides={'context_x':640,'context_y':360,'training_physical_rig':'true','training_physical_lab':'true'})as g:
  g.reset();check('physical cloth is attached to actual rendered shirt vertices',bool(events(g,'PHYSICAL_CLOTH')),events(g,'PHYSICAL_CLOTH')[-4:])
  start=g.frames()[-1]['t'];key(g,'F9')
  g.wait(lambda:any(f['mode']==2 and f['t']>start for f in frames(g)),seconds=20)
  screenshot(g,'getup-entry');g.advance(650);screenshot(g,'getup-supported')
  g.wait(lambda:any(f['mode']==0 and f['t']>start+3500 for f in frames(g)),seconds=20)
  recovery=[f for f in frames(g)if f['t']>start and f['mode']==2]
  check('get-up keeps a measured body support on the floor',bool(recovery)and all(f['ground_contacts']>=1 for f in recovery),dict(samples=len(recovery),minimum_contacts=min(f['ground_contacts']for f in recovery)))
  check('get-up raises the pelvis through a staged authored motion',len(recovery)>15 and max(f['root'][2]for f in recovery)-min(f['root'][2]for f in recovery)>.35,dict(height_range=[min(f['root'][2]for f in recovery),max(f['root'][2]for f in recovery)]))
  support=[x for x in events(g,'PHYSICAL_RENDER_SUPPORT')if min(f['t']for f in recovery)+100<=int(x['t'])<=max(f['t']for f in recovery)-100]
  check('the rendered skin remains supported during get-up',bool(support)and max(abs(float(x['minimum_z']))for x in support)<.025,dict(samples=len(support),height_range=[min(float(x['minimum_z'])for x in support),max(float(x['minimum_z'])for x in support)]if support else []))
  check('fall and get-up remain finite',all(math.isfinite(f[k])for f in frames(g)for k in ['energy','joint_error','self_penetration']),dict(samples=len(frames(g))))
  g.reset();key(g,'F10');g.advance(400)
  lab=events(g,'PHYSICAL_LAB');partner=events(g,'PHYSICAL_PARTNER')
  check('F10 creates the side-contact exercise',lab[-1]['exercise']=='1' and partner and float(partner[-1]['distance'])<.85,dict(lab=lab[-1],partner=partner[-1]))
  start=len(g.log.read_text());g.keys(['h'],True);g.advance(1800);screenshot(g,'shirt-grip')
  grips=events(g,'PHYSICAL_GRIP',start);forces=events(g,'PHYSICAL_GRIP_FORCE',start)
  check('shirt grip starts only after the hand reaches the shirt',any(x['state']=='begin' and float(x['hand_gap'])<.10 for x in grips),grips)
  check('held shirt applies equal and opposite bounded forces',bool(forces)and all(abs(float(x['force'])-float(x['reaction']))<.001 and float(x['force'])<=150.01 for x in forces),forces[:8])
  cloth=events(g,'PHYSICAL_CLOTH',start)
  pulled=[x for x in cloth if float(x['grip'])>1]
  check('shirt vertices visibly deform under the gameplay grip',bool(pulled)and max(float(x['displacement'])for x in pulled)>.003 and max(float(x['displacement'])for x in pulled)<.121,pulled[:8])
  g.keys(['h'],False);g.advance(700)
  check('releasing the button releases the physical shirt constraint',any(x['state']=='release'for x in events(g,'PHYSICAL_GRIP',start)),events(g,'PHYSICAL_GRIP',start))
  g.keys(['n'],True);g.advance(500);g.keys(['n'],False)
  check('shielding is available without moving or awarding the ball',any(x['shield']=='1'for x in events(g,'PHYSICAL_PARTNER',start)),events(g,'PHYSICAL_PARTNER',start)[-6:])
  key(g,'F10');g.advance(1700);screenshot(g,'body-contact')
  contacts=events(g,'PHYSICAL_PAIR_CONTACT',start)
  check('approaching partner produces actual close-range body contact',bool(contacts)and all(float(x['distance'])<.521 for x in contacts),contacts[:8])
  key(g,'m');g.advance(400)
  check('body-contest test is gated by contact range',bool(events(g,'PHYSICAL_CONTEST',start))and all(float(x['distance'])<.561 for x in events(g,'PHYSICAL_CONTEST',start)),events(g,'PHYSICAL_CONTEST',start))
  g.reset();key(g,'F10');g.advance(300)
  check('contact partner can be removed and grip state resets',events(g,'PHYSICAL_LAB')[-1]['exercise']=='0',events(g,'PHYSICAL_LAB')[-1])
  g.pad(0,-1);f=g.advance(1800);g.pad(0,0)
  check('approved dribble remains usable after physical exercises',max(x['speed']for x in f)>3 and max(math.dist(x['player'][:2],x['ball'][:2])for x in f)<2,dict(peak_speed=max(x['speed']for x in f)))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
