"""Continuous load, rendered recovery and central ground reception regressions."""
import argparse,hashlib,json,math,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':2500');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[start:].splitlines()if x.startswith(prefix+' ')]
def records(g,prefix,start=0):return[json.loads(x[len(prefix)+1:])for x in g.read_log()[start:].splitlines()if x.startswith(prefix+' ')]
def key(g,k,mods=()):g.keys([*mods,k],True);g.advance(100);g.keys([*mods,k],False);g.advance(100)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=640,context_y=360,training_physical_rig='true',training_physical_lab='true',simulation_seed=7))as g:
  g.reset();before=records(g,'VISIBLE_PHYSICS')[-1];start=len(g.read_log());g.keys(['u'],True);g.advance(1600)
  subprocess.run(['import','-window',g.window,str(a.output/'continuous-push.png')],env=g.env,check=True)
  g.keys(['u'],False);g.advance(2200)
  loads=ev(g,'PHYSICAL_CONTINUOUS_PUSH',start);balance=ev(g,'PHYSICAL_BALANCE',start);poses=records(g,'VISIBLE_PHYSICS',start);steps=ev(g,'PROCEDURAL_SUPPORT_STEP',start)
  change=max([math.dist(before['torso'],x['torso'])for x in poses]or[0])
  check('held input applies a continuous force over separate simulation ticks',len(loads)>=12 and len({x['t']for x in loads})==len(loads),dict(samples=len(loads)))
  check('sustained moderate push displays torso yielding and a lifted recovery support',change>.10 and bool(steps)and max(float(x['lift'])for x in steps)>.025,dict(torso_range=change,peak_step_lift=max([float(x['lift'])for x in steps]or[0])))
  states=ev(g,'PHYSICAL_RIG_STATE',start)
  check('moderate load recovers without an immediate limp fall',not any(x['to']=='1'for x in states)and g.frames()[-1]['speed']<.25,dict(states=states,final_speed=g.frames()[-1]['speed']))
  g.reset();start=len(g.read_log());g.keys(['Control_L','u'],True);g.advance(1400);g.keys(['Control_L','u'],False);g.advance(8000)
  states=ev(g,'PHYSICAL_RIG_STATE',start)
  check('continued excessive load can overcome support after a recovery attempt',any(x['to']=='1'for x in states)and bool(ev(g,'PROCEDURAL_SUPPORT_STEP',start)),dict(states=states))
  check('the overloaded body completes get-up and releases old load',any(x['from']=='2'and x['to']=='0'for x in states)and g.frames()[-1]['speed']<.5,dict(states=states,final_speed=g.frames()[-1]['speed']))
  for mods in [[],['Shift_L'],['Control_L']]:
   g.reset();start=len(g.read_log());key(g,'F4',['z',*mods]);g.advance(2300)
   touches=ev(g,'TRAINING_ACTION_TOUCH',start);plans=ev(g,'TRAINING_KICK_PLAN',start)
   check('central ground delivery '+str(mods)+' has intentional skin control rather than passing untouched between legs',bool(touches)and any(x['accepted']=='1'and float(x['gap'])<=.0025 for x in ev(g,'TRAINING_SKIN_CONTACT',start)),dict(touches=touches,accepted_plans=sum(x.get('accepted')=='1'for x in plans)))
  arms=ev(g,'PHYSICAL_ARM_RENDER');check('final visible shoulders and elbows retain anatomical limits',bool(arms)and max(float(x['error'])for x in arms)<.00001 and max(float(x['penetration'])for x in arms)<.004,dict(samples=len(arms)))
  for strength,sprint in [(.5,False),(1,False),(1,True)]:
   g.reset();key(g,'F2',['z']);start=len(g.read_log());origin=g.frames()[-1];yaw=origin['player_yaw']
   g.pad(math.cos(yaw)*strength,-math.sin(yaw)*strength,sprint=sprint);frames=g.advance(2200);g.pad(0,0)
   touches=ev(g,'TRAINING_ACTION_TOUCH',start);skin=ev(g,'TRAINING_SKIN_CONTACT',start)
   check('owned close ball starts a real foot touch '+str((strength,sprint)),bool(touches)and any(x['accepted']=='1'and float(x['gap'])<=.0025 for x in skin),dict(touches=touches))
   travel=math.dist(origin['player'][:2],frames[-1]['player'][:2]);gap=max(math.dist(f['player'][:2],f['ball'][:2])for f in frames)
   check('owned close ball departs continuously without losing its ball '+str((strength,sprint)),travel>.45 and gap<1.8,dict(travel_m=travel,maximum_ball_gap=gap,final_speed=frames[-1]['speed']))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 with NativeTraining(a.build,a.output/'match',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=640,context_y=360,training_physical_rig='true',training_physical_lab='true',player_match='true',player_match_all_restarts='false',simulation_seed=7))as g:
  for mods in [[],['Shift_L']]:
   key(g,'r');g.advance(2700);start=len(g.read_log());key(g,'F4',['h','z',*mods]);g.advance(2400)
   delivery=ev(g,'TRAINING_DELIVERY',start);actor=delivery[0]['actor']if delivery else''
   touches=[x for x in ev(g,'TRAINING_ACTION_TOUCH',start)if x.get('actor')==actor]
   check('CPU central delivery '+str(mods)+' intentionally controls with its actual foot',bool(delivery)and bool(touches),dict(actor=actor,touches=touches))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('match clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
