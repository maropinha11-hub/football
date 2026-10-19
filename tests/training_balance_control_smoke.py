#!/usr/bin/env python3
"""Real virtual-Xbox checks for contextual LT, stable contact and head clearance."""
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
p.add_argument('--display',default=':180');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def events(g,prefix,start=0):
 return [dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[start:].splitlines()if x.startswith(prefix+' ')]
def key(g,k):g.keys([k],True);g.advance(100);g.keys([k],False);g.advance(100)
def capture(g,name):subprocess.run(['import','-window',g.window,str(a.output/(name+'.png'))],env=g.env,check=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides={'context_x':640,'context_y':360,'simulation_seed':7,'training_physical_rig':'true','training_physical_lab':'true'})as g:
  g.reset();banks=events(g,'PHYSICAL_BALANCE_BANK')
  check('recovery matcher indexes real native sources and procedural variants',bool(banks)and all(int(x['sources'])>=10 and int(x['variants'])==int(x['sources'])*16 for x in banks),banks)
  start=len(g.read_log());key(g,'F8');g.advance(1400)
  balance=events(g,'PHYSICAL_BALANCE',start)
  check('recoverable impact queries a reference and attempts active balance',any(int(x['choice'])>=0 and int(x['phase'])in [1,2]for x in balance),balance[:12])
  states=events(g,'PHYSICAL_RIG_STATE',start)
  check('ordinary push stays on its feet',not any(x['to']=='1'for x in states),states)
  g.reset();key(g,'F10');g.advance(300)
  start=len(g.read_log());g.pad(0,0,buttons=1<<7);g.advance(600);g.pad(0,0)
  check('L3 no longer starts a shirt hold',not any(x['state']=='begin'for x in events(g,'PHYSICAL_GRIP',start)),events(g,'PHYSICAL_GRIP',start))
  g.reset();start=len(g.read_log());g.pad(0,0,left_trigger=1);g.advance(1000);capture(g,'lt-shield')
  partner=events(g,'PHYSICAL_PARTNER',start)
  check('LT with the ball shields the body',any(x['trigger']=='1'and x['with_ball']=='1'and x['shield']=='1'for x in partner),partner[-8:])
  check('LT with the ball does not attach a shirt hold',not any(x['state']=='begin'for x in events(g,'PHYSICAL_GRIP',start)),events(g,'PHYSICAL_GRIP',start))
  g.pad(0,0);g.advance(500);key(g,'F11');start=len(g.read_log())
  g.pad(0,0,left_trigger=1);g.advance(2000);capture(g,'lt-grip')
  grips=events(g,'PHYSICAL_GRIP',start);forces=events(g,'PHYSICAL_GRIP_FORCE',start);partner=events(g,'PHYSICAL_PARTNER',start)
  check('LT without the ball reaches then grips actual shirt surface',any(x['state']=='begin'and float(x['hand_gap'])<.10 for x in grips)and any(x['with_ball']=='0'and x['reaching']=='1'for x in partner),grips)
  check('held partner actively attempts to escape',any(float(x.get('intended_speed','0'))>.30 and float(x.get('actual_speed','0'))>0 for x in forces),forces[-12:])
  check('LT hold exerts reciprocal limited traction while the hand remains in reach',bool(forces) and all(float(x['force'])<=260.01 and abs(float(x['force'])-float(x['reaction']))<.001 for x in forces),forces[:10])
  g.advance(2600);grips=events(g,'PHYSICAL_GRIP',start)
  # A real native touch may recover possession and legitimately end LT's
  # hold before the partner escapes. Seed own possession without releasing LT
  # to verify that the trigger does not remain stuck in its previous mode.
  key(g,'F2');g.advance(600);partner=events(g,'PHYSICAL_PARTNER',start)
  check('held LT returns to protection when possession returns to the player',any(x['with_ball']=='1'and x['shield']=='1'and x['grip']=='0'for x in partner[-6:]),partner[-6:])
  g.pad(0,0);g.advance(300)
  # The actual LT trial above already kept its hand attached until a real
  # escape. Reuse that continuous hold, including the still-held-trigger
  # interval, instead of introducing a second pose-dependent keyboard setup.
  manual=start
  sustained=events(g,'PHYSICAL_GRIP_FORCE',manual)
  check('reachable hold transmits reciprocal limited traction and slows escape',len(sustained)>=5 and all(float(x['force'])<=260.01 and abs(float(x['force'])-float(x['reaction']))<.001 for x in sustained) and any(float(x['force'])>0 and float(x['actual_speed'])<float(x['intended_speed'])*.75 for x in sustained),sustained[:10])
  grips=events(g,'PHYSICAL_GRIP',manual)
  begins=[int(x['t'])for x in grips if x['state']=='begin'];releases=[x for x in grips if x['state']=='release'and x.get('reason')in ['escaped','reach','fall']]
  partner=events(g,'PHYSICAL_PARTNER',manual)
  physicalRelease=any((x['reason']=='escaped'and int(x['t'])-min(begins or[0])>=600)or(x['reason']=='reach'and any(int(x['t'])<=int(p['t'])<=int(x['t'])+300 and (float(p['hand_gap'])>.23 or float(p['distance'])>1.08)for p in partner))or(x['reason']=='fall'and any(z['to']=='1'for z in events(g,'PHYSICAL_RIG_STATE',manual)))for x in releases)
  # Deliberate escape has its 600 ms effort gate above. A hand that already
  # lost the shirt, or an actual fall, must release immediately; requiring a
  # minimum half-second hold here would demand an invisible physical anchor.
  check('a held opponent can escape or break actual anatomical reach',bool(begins)and physicalRelease,dict(grips=grips,partner_samples=partner[:16]))
  check('a broken hold cannot instantly reattach without button release',sum(x['state']=='begin'for x in grips)==1,grips)
  g.advance(200)
  arms=events(g,'PHYSICAL_BALANCE',start)
  check('hand solver limits angular speed and elbow flexion',bool(arms)and all(float(x['arm_speed'])<=3.81 and float(x['elbow'])<=2.41 for x in arms),dict(samples=len(arms),peak_speed=max(float(x['arm_speed'])for x in arms)))
  g.reset();key(g,'F10');g.advance(1600)
  start=len(g.read_log());g.advance(2200)
  contacts=events(g,'PHYSICAL_PAIR_CONTACT',start);surface=events(g,'PHYSICAL_BODY_DUEL',start);states=events(g,'PHYSICAL_RIG_STATE',start)
  # Real posed shoulders/arms may stop the approach before the old root
  # capsule overlaps. Require the actual new surface contact in that case.
  actualSurface=bool(surface)and all(0<float(x['normal_force'])<=260.01 and 0<float(x['penetration'])<=.08001 and x['reciprocal']=='1'for x in surface)
  check('continuous normal pressure produces contact without automatic knockdowns',(bool(contacts)or actualSurface)and not any(x['to']=='1'for x in states),dict(contacts=contacts[:10],surface=surface[:10],states=states))
  key(g,'Tab');g.keys(['Down','Right'],True);g.advance(550);g.keys(['Down','Right'],False);capture(g,'fp-look-down')
  start=len(g.read_log());key(g,'F9');g.advance(700);capture(g,'fp-fall');g.advance(6000)
  eyes=events(g,'PHYSICAL_EYE',start)
  check('first-person eye remains outside rendered trunk while falling and recovering',len(eyes)>=20 and all(float(x['clearance'])>=.0645 and math.isfinite(float(x['correction']))for x in eyes),dict(samples=len(eyes),minimum_clearance=min(float(x['clearance'])for x in eyes)if eyes else None))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
