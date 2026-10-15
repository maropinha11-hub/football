#!/usr/bin/env python3
"""Real SDL checks: complete standing/forward chest receptions and queued movement."""
import argparse,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':137');a=p.parse_args()
r={'result':'running','checks':[],'executable_sha256':hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest()}
def events(s,prefix):
 return [dict(re.findall(r'(\w+)=([^\s]+)',line))for line in s.splitlines()if line.startswith(prefix+' ')]
def check(name,ok,evidence):
 row={'check':name,'result':'passed'if ok else'failed','evidence':evidence};r['checks'].append(row);print(json.dumps(row),flush=True)
def start_events(s):return [x for x in events(s,'TRAINING_NATIVE_START')if x['added_chest']=='1']
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,config_overrides={'context_x':320,'context_y':180})as g:
  log=g.log.read_text();candidates=events(log,'TRAINING_CHEST_CANDIDATE')
  check('both chest clips are additional native candidates',len(candidates)==2 and {x['mode']for x in candidates}=={'Stand','Run'}and all(x['native_preserved']=='1'for x in candidates),candidates)
  for name,stick in [('forward',(0,-1)),('backward',(0,1)),('lateral',(1,0))]:
   g.reset();start=len(g.log.read_text());g.keys(['F5'],True);g.keys(['F5'],False)
   g.wait(lambda:any(x['function']=='3'for x in events(g.log.read_text()[start:],'TRAINING_ACTION_TOUCH')))
   selected=start_events(g.log.read_text()[start:]);check('idle delivery selects standing chest: '+name,bool(selected)and selected[0]['mode']=='stand',selected)
   g.pad(*stick);g.advance(350)
   s=g.log.read_text()[start:];early=[x for x in events(s,'TRAINING_ANIMATION_CHANGE')if x['old_chest']=='1']
   check('standing reception is not cut by '+name+' input',not early and g.frames()[-1]['function']==3,{'early_transitions':early,'frame':g.frames()[-1]})
   frames=g.advance(1800);s=g.log.read_text()[start:];ends=[x for x in events(s,'TRAINING_ANIMATION_CHANGE')if x['old_chest']=='1']
   check('standing reception finishes before '+name+' locomotion',bool(ends)and all(int(x['old_frame'])>=int(x['old_frames'])-1 for x in ends),ends)
   travelled=sum(math.dist(x['player'][:2],y['player'][:2])for x,y in zip(frames,frames[1:]))
   check('held '+name+' input resumes after full reception',travelled>.3 and max(x['speed']for x in frames)>1,{'path_m':travelled,'peak_speed_mps':max(x['speed']for x in frames),'ending_range_m':math.dist(frames[-1]['player'][:2],frames[-1]['ball'][:2])})
  for amount in (.55,1.0):
   g.reset();start=len(g.log.read_text());g.pad(0,-amount);g.keys(['F5'],True);g.keys(['F5'],False);frames=g.advance(2300)
   s=g.log.read_text()[start:];selected=start_events(s);hits=events(s,'TRAINING_ACTION_TOUCH');chest=[x for x in hits if x['function']=='3']
   check('forward input selects Chest_Run at '+str(amount),bool(selected)and selected[0]['mode']=='forward'and'Chest_Run'in selected[0]['name'],selected)
   check('forward chest makes one real trunk contact at '+str(amount),len(chest)==1 and chest[0]['part']=='trunk',chest)
   ends=[x for x in events(s,'TRAINING_ANIMATION_CHANGE')if x['old_chest']=='1']
   check('forward reception completes its authored cycle at '+str(amount),bool(ends)and all(int(x['old_frame'])>=int(x['old_frames'])-1 for x in ends),ends)
   gaps=[math.dist(x['player'][:2],x['ball'][:2])for x in frames if x['t']>int(chest[0]['t'])+200]if chest else[]
   check('forward reception continues toward the ball at '+str(amount),bool(gaps)and max(gaps)<1.8 and frames[-1]['speed']>1,{'ending_speed_mps':frames[-1]['speed'],'max_post_contact_range_m':max(gaps,default=None)})
  log=g.log.read_text();accepted={x['t']for x in events(log,'TRAINING_SKIN_CONTACT')if x['accepted']=='1'};hits=events(log,'TRAINING_ACTION_TOUCH')
  check('every authored reception/action impulse has a measured skin contact',bool(hits)and all(x['t']in accepted for x in hits),{'impulses':len(hits)})
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r['result']='failed';r['error']=str(e);raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
