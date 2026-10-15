#!/usr/bin/env python3
"""Rendered Xbox tests for a chest layer over freely controlled native legs."""
import argparse,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':137');a=p.parse_args()
r={'result':'running','checks':[],'executable_sha256':hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest()}
def events(s,prefix):return [dict(re.findall(r'(\w+)=([^\s]+)',x))for x in s.splitlines()if x.startswith(prefix+' ')]
def check(name,ok,evidence):
 row={'check':name,'result':'passed'if ok else'failed','evidence':evidence};r['checks'].append(row);print(json.dumps(row),flush=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,config_overrides={'context_x':320,'context_y':180})as g:
  candidates=events(g.log.read_text(),'TRAINING_CHEST_CANDIDATE')
  check('both source receptions remain available and play more slowly',len(candidates)==2 and {x['mode']for x in candidates}=={'Stand','Run'}and all(int(x['frames'])> (151 if x['mode']=='Stand'else 91)for x in candidates),candidates)
  for name,stick in [('forward',(0,-1)),('backward',(0,1)),('lateral',(1,0))]:
   g.reset();start=len(g.log.read_text());g.keys(['F5'],True);g.keys(['F5'],False)
   g.wait(lambda:any(x.get('upper_layer')=='1'for x in events(g.log.read_text()[start:],'TRAINING_ACTION_TOUCH')))
   s=g.log.read_text()[start:];hits=[x for x in events(s,'TRAINING_ACTION_TOUCH')if x.get('upper_layer')=='1']
   check('chest-directed delivery makes one real upper-layer contact: '+name,len(hits)==1 and hits[0]['part']=='trunk',hits)
   before=g.frames()[-1];g.pad(*stick);f=g.advance(550);s=g.log.read_text()[start:]
   path=sum(math.dist(x['player'][:2],y['player'][:2])for x,y in zip([before]+f,f));active=[x for x in events(s,'TRAINING_UPPER_STATE')if float(x['t'])>before['t']]
   check('legs respond while chest gesture continues: '+name,path>.20 and max(x['speed']for x in f)>1 and bool(active),{'path_m':path,'maximum_speed_mps':max(x['speed']for x in f),'upper_states':active})
   masks=events(s,'TRAINING_UPPER_MASK')
   check('upper layer changes the spine without moving the root or legs: '+name,bool(masks)and all(float(x['legs_error'])<1e-6 and float(x['root_error'])<1e-6 for x in masks)and max(float(x['spine_delta'])for x in masks)>.01,masks)
   g.advance(1600);ends=events(g.log.read_text()[start:],'TRAINING_UPPER_END')
   check('upper gesture fades out without a locomotion lock: '+name,bool(ends)and any(x['touched']=='1'for x in ends),ends)
  g.reset();start=len(g.log.read_text());g.pad(0,-.55);g.keys(['F5'],True);g.keys(['F5'],False);f=g.advance(2400);s=g.log.read_text()[start:]
  starts=events(s,'TRAINING_UPPER_START');hits=[x for x in events(s,'TRAINING_ACTION_TOUCH')if x.get('upper_layer')=='1']
  check('moderate forward input selects the running upper-body gesture',bool(starts)and starts[0]['mode']=='forward',starts)
  check('running upper gesture makes one chest contact with moving legs',len(hits)==1 and max(x['speed']for x in f)>1,hits)
  g.reset();start=len(g.log.read_text());g.keys(['F5'],True);g.keys(['F5'],False)
  g.wait(lambda:bool(events(g.log.read_text()[start:],'TRAINING_UPPER_START')));g.advance(50);before=g.frames()[-1];g.pad(1,0);f=g.advance(900);s=g.log.read_text()[start:]
  path=sum(math.dist(x['player'][:2],y['player'][:2])for x,y in zip([before]+f,f))
  check('legs respond before the ball arrives instead of locking onto it',path>.4 and max(x['speed']for x in f)>1,{'path_m':path,'peak_speed_mps':max(x['speed']for x in f)})
  ends=events(s,'TRAINING_UPPER_END');hits=[x for x in events(s,'TRAINING_ACTION_TOUCH')if x.get('upper_layer')=='1']
  check('moving out of the chest trajectory fades the missed gesture without a catch',not hits and bool(ends)and ends[0]['touched']=='0',{'ends':ends,'upper_contacts':hits})
  g.reset();start=len(g.log.read_text());g.pad(1,0);g.keys(['F5'],True);g.keys(['F5'],False);g.advance(2000);s=g.log.read_text()[start:]
  check('lateral choice does not force a chest animation or invisible catch',not events(s,'TRAINING_UPPER_START')and not any(x.get('upper_layer')=='1'for x in events(s,'TRAINING_ACTION_TOUCH')),events(s,'TRAINING_UPPER_START'))
  g.reset();start=len(g.log.read_text());g.keys(['F4'],True);g.keys(['F4'],False);g.advance(2300);s=g.log.read_text()[start:];hits=events(s,'TRAINING_ACTION_TOUCH')
  check('low delivery keeps native foot reception',not events(s,'TRAINING_UPPER_START')and any('foot'in x['part']for x in hits),hits)
  log=g.log.read_text();accepted=events(log,'TRAINING_SKIN_CONTACT');times={x['t']for x in accepted if x['accepted']=='1'};chest={x['t']for x in accepted if x['accepted']=='1'and x.get('part')=='chest'};hits=events(log,'TRAINING_ACTION_TOUCH')
  check('all impulses require real skin contact, chest impacts specifically require the chest',bool(hits)and all(x['t']in times for x in hits)and all(x['t']in chest for x in hits if x.get('upper_layer')=='1'),{'impulses':len(hits),'upper_impulses':sum(x.get('upper_layer')=='1'for x in hits)})
  check('added full-body receptions never replace locomotion',not any(x['new_chest']=='1'for x in events(log,'TRAINING_ANIMATION_CHANGE')),events(log,'TRAINING_UPPER_START'))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r['result']='failed';r['error']=str(e);raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
