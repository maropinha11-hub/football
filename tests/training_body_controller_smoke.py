#!/usr/bin/env python3
"""Rendered comparison of native continuity and a completely dynamic body.

This does not certify learned football skills or robust free-body locomotion.
"""
import argparse,hashlib,json,math,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':4200');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def events(g,prefix,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[start:].splitlines()if x.startswith(prefix+' ')]
def key(g,k,mods=()):g.keys([*mods,k],True);g.advance(80);g.keys([*mods,k],False);g.advance(80)
def capture(g,name):subprocess.run(['import','-window',g.window,str(a.output/name)],env=g.env,check=True)
def states(g,start=0):return[x for x in events(g,'BODY_CONTROLLER',start)if x['mode']=='2']
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,
      config_overrides=dict(context_x=640,context_y=360,training_physical_rig='true',training_physical_lab='true',simulation_seed=7))as g:
  g.reset();key(g,'F4',['Control_L','Shift_L']);start=len(g.read_log());key(g,'F12');g.pad(0,-.5);g.advance(2500);g.pad(0,0);capture(g,'procedural-reference.png')
  proc=events(g,'BODY_CONTROLLER',start)
  check('F12 selects native-phase continuity while retaining its physical muscle layer',any(x['mode']=='1'and int(x['segments'])==10 for x in proc),proc[-3:])
  start=len(g.read_log());key(g,'F12');g.pad(0,-.5);g.advance(450);g.pad(0,0);entry=states(g,start)
  check('entry from native movement establishes physical support before accepting locomotion',bool(entry)and all(float(x['height'])>.8 and float(x['upright'])>.9 for x in entry),entry)
  g.reset();start=len(g.read_log());g.advance(4000);capture(g,'free-body-standing.png');quiet=states(g,start)
  check('all thirteen links remain dynamic with one world and no installed failed learned policy',len(quiet)>20 and all(x['segments']=='13'and x['worlds']=='1'and x['learned']=='0'for x in quiet),dict(samples=len(quiet),last=quiet[-3:]))
  check('the rendered free body stands on its own soles',bool(quiet)and min(float(x['height'])for x in quiet)>.70 and min(float(x['upright'])for x in quiet)>.85,quiet[-3:])
  start=len(g.read_log());key(g,'F8');g.advance(2300);capture(g,'small-push-recovery.png');small=states(g,start)
  check('a small unforced impulse produces physical motion and recovers standing support',bool(small)and max(float(x['speed'])for x in small)>.03 and all(float(x['height'])>.70 for x in small)and float(small[-1]['upright'])>.85,dict(peak_speed=max([float(x['speed'])for x in small]or[0]),last=small[-3:]))
  g.reset();start=len(g.read_log());key(g,'F9');g.advance(1800);capture(g,'free-body-protection.png');fall=states(g,start);guard=events(g,'PROTECTIVE_FALL',start)
  check('large loss of support remains dynamic and recruits protective arm targets',bool(fall)and all(x['segments']=='13'for x in fall)and any(float(x['reach'])>.3 for x in guard),dict(samples=len(fall),guard=guard[-3:]))
  renders=events(g,'PHYSICAL_RIG_RENDER',start)
  check('visible free-body bone lengths stay finite through impact',bool(renders)and all(math.isfinite(float(x['root_height']))and float(x['length_error'])<1e-5 for x in renders),dict(samples=len(renders),maximum_error=max([float(x['length_error'])for x in renders]or[1])))
  g.reset();start=len(g.read_log());g.pad(0,-.5);travel=g.advance(6000);g.pad(0,0);capture(g,'free-body-reference-search.png')
  bank=events(g,'FRAME_REFERENCE_BANK',start);matches=events(g,'FRAME_REFERENCE_MATCH',start)
  check('an unapproved interior-frame matcher no longer overrides the physical support controller',not matches,dict(bank=bank,matches=matches[:5]))
  # Record the remaining stability gap instead of treating a successful
  # nearest-neighbour search as proof of a learned locomotion skill.
  motion=states(g,start);settled=[x for x in motion if int(x['t'])>=int(motion[0]['t'])+1400]if motion else[]
  r['free_body_locomotion_observation']=dict(samples=len(motion),duration_ms=6000,startup_excluded_ms=1400,travel_m=math.dist(travel[0]['player'],travel[-1]['player'])if len(travel)>1 else 0,upright_fraction=sum(float(x['height'])>.7 and float(x['upright'])>.8 for x in settled)/max(1,len(settled)),scope='diagnostic after startup exclusion; no robust walking or football policy claimed')
  start=len(g.read_log());key(g,'F12');g.pad(0,-.5);moved=g.advance(2000);g.pad(0,0)
  toggles=events(g,'BODY_CONTROLLER_TOGGLE',start)
  check('switching back restores the approved playable controller',any(x['mode']=='0'for x in toggles)and len(moved)>5 and math.dist(moved[0]['player'],moved[-1]['player'])>.4,toggles)
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
