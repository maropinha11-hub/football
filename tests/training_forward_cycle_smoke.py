#!/usr/bin/env python3
"""Real SDL/Xbox checks for soft/start gait, complete forward cycles and physical contacts."""
import argparse,hashlib,json,math,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':135');a=p.parse_args()
r={'result':'running','checks':[],'executable_sha256':hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest()}
def rows(s,prefix):return [{k:float(v)for k,v in re.findall(r'(\w+)=(-?[\d.]+)',line)}for line in s.splitlines()if line.startswith(prefix+' ')]
def check(name,ok,evidence):
 q={'check':name,'result':'passed'if ok else'failed','evidence':evidence};r['checks'].append(q);print(json.dumps(q),flush=True)
def retain(name,f):
 gaps=[math.dist(x['player'][:2],x['ball'][:2])for x in f]
 check(name,max(gaps)<1.6 and all(x['with_ball']for x in f),{'maximum_range_m':max(gaps),'ending_range_m':gaps[-1]})
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,config_overrides={'context_x':'320','context_y':'180'})as g:
  g.reset();origin=g.frames()[-1];start=len(g.log.read_text());g.pad(0,-.4);f=g.advance(2000);s=g.log.read_text()[start:]
  state=rows(s,'TRAINING_DRIBBLE_STATE')
  check('light stick moves with the original gait',math.dist(origin['player'][:2],f[-1]['player'][:2])>.8 and f[-1]['speed']>.5 and bool(state)and not any(x['new_cycle']for x in state),{'travel_m':math.dist(origin['player'][:2],f[-1]['player'][:2]),'ending_speed_mps':f[-1]['speed'],'states':state})
  retain('light stick retains ball',f)
  start=len(g.log.read_text());g.pad(0,-1);f=g.advance(5000);s=g.log.read_text()[start:]
  state=rows(s,'TRAINING_DRIBBLE_STATE');new=[x for x in state if x['new_cycle']]
  check('full stick starts natively and enters the new gait',bool(new)and any(not x['new_cycle']for x in state[:3]),{'first_states':state[:9]})
  steady=[x for x in state if new and x['t']>=new[0]['t']+400]
  check('steady forward does not switch back at every touch',len(steady)>=20 and all(x['new_cycle']for x in steady),{'steady_samples':len(steady),'old_pose_samples':sum(not x['new_cycle']for x in steady)})
  poses=rows(s,'TRAINING_NATIVE_DRIBBLE_POSE');jumps=[]
  for first,second in zip(poses,poses[1:]):
   dt=second['t']-first['t'];advance=(second['phase']-first['phase'])%70
   if 0<dt<=120 and advance>max(16,dt*.15):jumps.append({'t':second['t'],'advance_frames':advance,'dt_ms':dt})
  check('both halves form complete continuous loops',len(poses)>30 and max(x['phase']for x in poses)>63 and min(x['phase']for x in poses)<7 and not jumps,{'pose_samples':len(poses),'phase_min':min((x['phase']for x in poses),default=None),'phase_max':max((x['phase']for x in poses),default=None),'phase_jumps':jumps})
  contacts=[x for x in rows(s,'TRAINING_SKIN_CONTACT')if x['accepted']and x['new_cycle']]
  check('new gait pushes at measured shoe contacts',len(contacts)>=4 and all(x['gap']<=.00251 for x in contacts),contacts)
  drawn=rows(s,'TRAINING_RENDER_SURFACE');evidence=[]
  for touch in contacts:
   nearby=[x for x in drawn if x['new_cycle']and abs(x['t']-touch['t'])<=100]
   gap=min((abs(x['gap'])for x in nearby),default=100)
   evidence.append({'t':touch['t'],'closest_rendered_gap_m':gap})
  check('visible shoe follows the actual impacts',bool(evidence)and all(x['closest_rendered_gap_m']<.085 for x in evidence),evidence)
  retain('full loop retains ball',f)
  # Strong-stick noise must not toggle the gait on each threshold crossing.
  start=len(g.log.read_text());f=[]
  for amount in [.87,.96,.85,.94,.88,.97]:g.pad(0,-amount);f+=g.advance(250)
  state=rows(g.log.read_text()[start:],'TRAINING_DRIBBLE_STATE')
  check('strong stick has stable hysteresis',bool(state)and all(x['new_cycle']for x in state),state)
  retain('stick strength changes retain ball',f)
  start=len(g.log.read_text());g.pad(0,-.4);f=g.advance(2000);state=rows(g.log.read_text()[start:],'TRAINING_DRIBBLE_STATE')
  check('soft stick returns smoothly to the old gait',f[-1]['speed']>.5 and bool(state)and all(not x['new_cycle']for x in state[-8:]),{'ending_speed_mps':f[-1]['speed'],'last_states':state[-8:]})
  retain('return to soft gait retains ball',f)
  g.reset();start=len(g.log.read_text());g.pad(0,-1);f=g.advance(3500);state=rows(g.log.read_text()[start:],'TRAINING_DRIBBLE_STATE')
  check('resting start uses old gait before new',len(state)>15 and not any(x['new_cycle']for x in state[:3])and all(x['new_cycle']for x in state[-10:]),{'first_states':state[:8],'last_states':state[-10:]})
  retain('resting start stays connected',f)
  log=g.log.read_text();skin=rows(log,'TRAINING_SKIN_CONTACT');accepted=[x for x in skin if x['accepted']]
  touches=rows(log,'TRAINING_ACTION_TOUCH');times={x['t']for x in accepted}
  check('every authored impulse is guarded by real skin contact',len(touches)>10 and all(x['t']in times for x in touches)and all(x['gap']<=.00251 for x in accepted),{'impulses':len(touches),'measured_contacts':len(accepted),'maximum_accepted_gap_m':max((x['gap']for x in accepted),default=None)})
  g.keys(['Tab'],True);g.keys(['Tab'],False);g.keys(['Tab'],True);g.keys(['Tab'],False);g.advance(500)
  subprocess.run(['import','-window',g.window,str(a.output/'forward-cycle.png')],env=g.env,check=True)
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as error:r['result']='failed';r['error']=str(error);raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
