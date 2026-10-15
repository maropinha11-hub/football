#!/usr/bin/env python3
"""Rendered Xbox checks: chest gesture, phased arms, native legs and reception axis."""
import argparse,hashlib,json,math,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':137');a=p.parse_args()
r={'result':'running','checks':[],'executable_sha256':hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest()}
def events(s,prefix):return [dict(re.findall(r'(\w+)=([^\s]+)',x))for x in s.splitlines()if x.startswith(prefix+' ')]
def check(name,ok,evidence):
 row={'check':name,'result':'passed'if ok else'failed','evidence':evidence};r['checks'].append(row);print(json.dumps(row),flush=True)
def delivery(g):g.keys(['F5'],True);g.keys(['F5'],False)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,config_overrides={'context_x':320,'context_y':180})as g:
  candidates=events(g.log.read_text(),'TRAINING_CHEST_CANDIDATE')
  check('both source receptions remain available at the approved cadence',len(candidates)==2 and {x['mode']for x in candidates}=={'Stand','Run'}and all(int(x['frames'])> (151 if x['mode']=='Stand'else 91)for x in candidates),candidates)
  for name,stick in [('forward',(0,-1)),('backward',(0,1))]:
   g.reset();start=len(g.log.read_text());delivery(g)
   g.wait(lambda:any(x.get('upper_layer')=='1'for x in events(g.log.read_text()[start:],'TRAINING_ACTION_TOUCH')))
   hits=[x for x in events(g.log.read_text()[start:],'TRAINING_ACTION_TOUCH')if x.get('upper_layer')=='1']
   check('chest delivery makes one real upper-layer contact: '+name,len(hits)==1 and hits[0]['part']=='trunk',hits)
   before=g.frames()[-1];g.pad(*stick);f=g.advance(400);s=g.log.read_text()[start:]
   path=sum(math.dist(x['player'][:2],y['player'][:2])for x,y in zip([before]+f,f))
   check('forward/back adjustment remains responsive during the gesture: '+name,path>.08 and max(x['speed']for x in f)>.5,{'path_m':path,'maximum_speed_mps':max(x['speed']for x in f)})
   masks=events(s,'TRAINING_UPPER_MASK')
   check('chest layer preserves native pelvis and legs: '+name,bool(masks)and all(float(x['legs_error'])<1e-6 and float(x['root_error'])<1e-6 for x in masks)and max(float(x['spine_delta'])for x in masks)>.01,{'samples':len(masks),'maximum_arm_error':max((float(x['arms_error'])for x in masks),default=100)})
   g.advance(1800);ends=events(g.log.read_text()[start:],'TRAINING_UPPER_END')
   masks=events(g.log.read_text()[start:],'TRAINING_UPPER_MASK')
   check('arms use reception first and smoothly return to native locomotion: '+name,
     any(float(x['arm_weight'])>.85 and float(x['arms_error'])>.1 for x in masks)and
     any(float(x['arm_weight'])<.001 and float(x['arms_error'])<1e-6 and float(x['phase'])>50 for x in masks),
     {'samples':len(masks),'peak_arm_gesture_weight':max(float(x['arm_weight'])for x in masks),'minimum_late_arm_weight':min((float(x['arm_weight'])for x in masks if float(x['phase'])>50),default=1)})
   check('upper gesture fades without a full-body lock: '+name,bool(ends)and any(x['touched']=='1'for x in ends),ends)
  g.reset();start=len(g.log.read_text());delivery(g)
  g.wait(lambda:bool(events(g.log.read_text()[start:],'TRAINING_UPPER_START')));g.advance(50);before=g.frames()[-1];g.pad(1,0)
  g.wait(lambda:any(x.get('upper_layer')=='1'for x in events(g.log.read_text()[start:],'TRAINING_ACTION_TOUCH')))
  f=[x for x in g.frames()if x['t']>before['t']];travel=max([math.dist(before['player'][:2],x['player'][:2])for x in f]+[0])
  check('side input cannot turn or displace the player before chest contact',travel<.12 and all(abs(x['yaw']-before['yaw'])<.12 for x in f),{'maximum_displacement_m':travel,'samples':len(f)})
  g.advance(2100);s=g.log.read_text()[start:]
  check('ignored lateral input still permits an actual chest reception',len([x for x in events(s,'TRAINING_ACTION_TOUCH')if x.get('upper_layer')=='1'])==1,events(s,'TRAINING_UPPER_START'))
  g.reset();start=len(g.log.read_text());g.pad(0,-.55);delivery(g);f=g.advance(2400);s=g.log.read_text()[start:]
  starts=events(s,'TRAINING_UPPER_START');hits=[x for x in events(s,'TRAINING_ACTION_TOUCH')if x.get('upper_layer')=='1']
  check('moderate forward input selects the running chest gesture',bool(starts)and starts[0]['mode']=='forward',starts)
  check('running gesture makes a real chest contact with native legs',len(hits)==1 and max(x['speed']for x in f)>.5,hits)
  g.reset();start=len(g.log.read_text());delivery(g);f=g.advance(2400);s=g.log.read_text()[start:]
  check('released stick keeps reception stationary rather than walking through the ball',max(x['speed']for x in f if x['ball'][2]>.8)<.6,{'aerial_peak_speed_mps':max(x['speed']for x in f if x['ball'][2]>.8)})
  # Third-person input is world-space, but reception adjustments use the
  # same fixed axis. Initial facing is +X; world Y must not turn the chest.
  g.keys(['Tab'],True);g.keys(['Tab'],False);g.keys(['Tab'],True);g.keys(['Tab'],False)
  g.reset();start=len(g.log.read_text());delivery(g)
  g.wait(lambda:bool(events(g.log.read_text()[start:],'TRAINING_UPPER_START')));before=g.frames()[-1];g.pad(0,-1)
  g.wait(lambda:any(x.get('upper_layer')=='1'for x in events(g.log.read_text()[start:],'TRAINING_ACTION_TOUCH')))
  f=[x for x in g.frames()if x['t']>before['t']]
  check('third-person lateral world input cannot turn a pending reception',g.frames()[-1]['camera']==1 and all(abs(x['player'][1]-before['player'][1])<.1 for x in f),{'camera':g.frames()[-1]['camera'],'samples':len(f)})
  g.pad(1,0);g.advance(250);subprocess.run(['import','-window',g.window,str(a.output/'native-arms-chest.png')],env=g.env,check=True)
  g.keys(['Tab'],True);g.keys(['Tab'],False);g.reset()
  g.reset();start=len(g.log.read_text());g.keys(['F4'],True);g.keys(['F4'],False);g.advance(2300);s=g.log.read_text()[start:];hits=events(s,'TRAINING_ACTION_TOUCH')
  check('low delivery retains native foot reception',not events(s,'TRAINING_UPPER_START')and any('foot'in x['part']for x in hits),hits)
  log=g.log.read_text();accepted=events(log,'TRAINING_SKIN_CONTACT');times={x['t']for x in accepted if x['accepted']=='1'};chest={x['t']for x in accepted if x['accepted']=='1'and x.get('part')=='chest'};hits=events(log,'TRAINING_ACTION_TOUCH')
  check('all authored impulses require real skin contact, upper contacts specifically require chest skin',bool(hits)and all(x['t']in times for x in hits)and all(x['t']in chest for x in hits if x.get('upper_layer')=='1')and all(float(x['gap'])<=.00251 for x in accepted if x['accepted']=='1'),{'impulses':len(hits),'upper_impulses':sum(x.get('upper_layer')=='1'for x in hits)})
  # A fast incoming ball can cross the entire contact band between two
  # rendered frames. Compare matching historical times, not the latest raw
  # animation snapshot to an older interpolated ball. The native temporal
  # smoother displays 20 ms of history for both the ball and body.
  drawn=events(log,'TRAINING_RENDER_CHEST');physics=[x for x in accepted if x.get('part')=='chest' and x['accepted']=='0'];pairs=[]
  for sample in drawn:
   near=min(physics,key=lambda x:abs(int(x['t'])-(int(sample['t'])-20)),default=None)
   if near is not None and abs(int(near['t'])-(int(sample['t'])-20))<=5 and .04<float(near['gap'])<1:
    pairs.append(abs(float(sample['gap'])-float(near['gap'])))
  check('rendered chest and physical skin agree on the incoming trajectory',len(pairs)>=3 and max(pairs)<.08,{'paired_samples':len(pairs),'maximum_gap_difference_m':max(pairs,default=100)})
  check('added full-body clips never replace native locomotion',not any(x['new_chest']=='1'for x in events(log,'TRAINING_ANIMATION_CHANGE')),events(log,'TRAINING_UPPER_START'))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r['result']='failed';r['error']=str(e);raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
