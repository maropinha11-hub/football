#!/usr/bin/env python3
"""Observe protective falls, upright walking and persistent CPU body state."""
import argparse,hashlib,json,math,re,statistics,subprocess,time
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':4100');p.add_argument('--match',action='store_true');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[start:].splitlines()if x.startswith(prefix+' ')]
def records(g,prefix,start=0):return list({(x['t'],x.get('actor',0)):x for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')for x in [json.loads(line[len(prefix)+1:])]}.values())
def key(g,k,mods=()):g.keys([*mods,k],True);g.advance(100);g.keys([*mods,k],False);g.advance(100)
def capture(g,name):subprocess.run(['import','-window',g.window,str(a.output/name)],env=g.env,check=True)
def angle(a,b):return 2*math.acos(min(1.,abs(sum(x*y for x,y in zip(a,b)))))
try:
 config=dict(context_x=640,context_y=360,training_physical_rig='true',training_physical_lab='true',training_performance='true',simulation_seed=7)
 if a.match:config.update(player_match='true',player_match_half_seconds=120,player_match_all_restarts='false')
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=config)as g:
  if a.match:
   g.advance(6000);before=ev(g,'PHYSICAL_ACTIVE_STATE');actors={x['actor']for x in before}
   check('all 22 actors retain muscular physical state including the quiet CPU',len(actors)==22 and all(x['mode']!='0' or (int(x['world_builds'])==1 and int(x['muscles'])>0) for x in before),dict(actors=sorted(actors),samples=len(before)))
   latest={x['actor']:x for x in before};fresh={actor for actor,x in latest.items()if x['mode']=='0'}
   previous_protection={x['actor']for x in ev(g,'PROTECTIVE_FALL')if x['actor']not in fresh and float(x['reach'])>.3 and float(x['torque'])>10}
   start=len(g.read_log());start_t=g.frames()[-1]['t'];clock=time.monotonic();key(g,'F9',['Control_L','Shift_L']);g.advance(900);capture(g,'simultaneous-falls.png')
   for _ in range(6):g.advance(2000)
   elapsed=time.monotonic()-clock;sim=(g.frames()[-1]['t']-start_t)/1000
   falls=ev(g,'PROTECTIVE_FALL',start);actors={x['actor']for x in falls};protected={x['actor']for x in falls if float(x['reach'])>.3 and float(x['torque'])>10}
   check('CPU and player actively protect during simultaneous physical falls',len(latest)==22 and fresh<=actors and fresh<=protected and set(latest)<=protected|previous_protection,dict(falling=sorted(actors),protected=sorted(protected),already_in_physical_fall=sorted(set(latest)-fresh),prior_protection=sorted(previous_protection)))
   states=ev(g,'PHYSICAL_ACTIVE_STATE',start)
   check('falling/get-up do not rebuild the physical worlds',bool(states)and all(int(x['world_builds'])<=1 for x in states),dict(samples=len(states),max_builds=max([int(x['world_builds'])for x in states]or[0])))
   check('a simultaneous 22-body stress event keeps bounded simulation pace',sim/elapsed>.90,dict(simulated_seconds=sim,wall_seconds=elapsed,pace=sim/elapsed))
   check('the match returns to real play with one fixed human',any(x['human']=='1'and x['mode']=='0'for x in states),states[-8:])
  else:
   g.reset();key(g,'F4',['Control_L','Shift_L']);g.pad(0,-.5);g.advance(4500);capture(g,'walking-support.png');g.pad(0,0)
   visible=[x for x in records(g,'VISIBLE_PHYSICS')if x['human']==1 and x['walk']>.99]
   heights=[x['pelvis'][2]-min(x['left'][2],x['right'][2])for x in visible]
   check('walking carries the hips above the persistent crouch while keeping support',bool(heights)and statistics.median(heights)>.73 and max(heights)-min(heights)<.09,dict(median_hip_above_ankle=statistics.median(heights)if heights else 0,range=[min(heights),max(heights)]if heights else[],samples=len(heights)))
   g.reset();when=g.frames()[-1]['t'];start=len(g.read_log());g.pad(0,-.5);g.advance(4500);g.pad(0,0)
   carried=[x for x in records(g,'VISIBLE_PHYSICS',start)if x['human']==1 and x['t']>when+1200]
   heights=[x['pelvis'][2]for x in carried]
   check('walking with the ball avoids exaggerated vertical bouncing',len(heights)>20 and max(heights)-min(heights)<.08,dict(samples=len(heights),range_m=max(heights)-min(heights)if heights else 0))
   floor_hands=0
   for direction in range(4):
    g.reset();start=len(g.read_log());key(g,'F9');g.advance(300);capture(g,'fall-'+str(direction)+'-prepare.png');g.advance(600);capture(g,'fall-'+str(direction)+'-impact.png');g.advance(6500)
    falls=ev(g,'PROTECTIVE_FALL',start);frames=records(g,'PHYSICAL_RIG_FRAME',start);fall_frames=[x for x in frames if x['mode']==1]
    before=[x for x in falls if float(x['reach'])>.3 and float(x['torque'])>10 and any(abs(f['t']-int(x['t']))<=10 and f['root'][2]>.45 for f in fall_frames)]
    floor_hands+=any(int(x['hands'])>0 for x in falls)
    check('direction '+str(direction)+' recruits protective muscles before reaching the floor',bool(before),dict(protective_samples=len(before),peak_guard=max([float(x['reach'])for x in falls]or[0]),peak_torque=max([float(x['torque'])for x in falls]or[0])))
    rotation=sum(angle(x['root_q'],y['root_q'])for x,y in zip(fall_frames,fall_frames[1:]))
    check('direction '+str(direction)+' falls without repeated rolls or disconnected joints',bool(fall_frames)and rotation<5.5 and max(x['joint_error']for x in fall_frames)<.08,dict(rotation_rad=rotation,max_joint_error=max([x['joint_error']for x in fall_frames]or[0])))
    check('direction '+str(direction)+' recovers control',bool(frames)and frames[-1]['mode']==0,frames[-1]if frames else{})
    key(g,'F3')
   check('protective hands make actual ground contact during the fall trials',floor_hands>=2,dict(trials_with_forearm_ground_contact=floor_hands,trials=4))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
