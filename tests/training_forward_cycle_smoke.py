#!/usr/bin/env python3
"""Real SDL/Xbox checks: touch, let the ball roll, move normally, touch again."""
import argparse,hashlib,json,math,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':135');a=p.parse_args()
r={'result':'running','checks':[],'executable_sha256':hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest()}
def events(s,prefix):return [dict(re.findall(r'(\w+)=([^\s]+)',x))for x in s.splitlines()if x.startswith(prefix+' ')]
def check(name,ok,evidence):
 row={'check':name,'result':'passed'if ok else'failed','evidence':evidence};r['checks'].append(row);print(json.dumps(row),flush=True)
def retain(name,frames):
 gaps=[math.dist(x['player'][:2],x['ball'][:2])for x in frames]
 check(name,max(gaps)<2.0 and all(x['with_ball']for x in frames),{'maximum_range_m':max(gaps),'ending_range_m':gaps[-1]})
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,config_overrides={'context_x':320,'context_y':180})as g:
  g.reset();start=len(g.log.read_text());g.pad(0,-.4);f=g.advance(2200);s=g.log.read_text()[start:]
  check('light stick retains the original gait',f[-1]['speed']>.5 and not any(x['new_cycle']=='1'for x in events(s,'TRAINING_DRIBBLE_STATE')),{'ending_speed_mps':f[-1]['speed']});retain('light stick retains the ball',f)
  g.reset();origin=g.frames()[-1];start=len(g.log.read_text());g.pad(0,-1);f=g.advance(6500);s=g.log.read_text()[start:]
  hits=[x for x in events(s,'TRAINING_SKIN_CONTACT')if x['accepted']=='1'and x['new_cycle']=='1'and'foot'in x.get('part','')]
  check('forward dribble uses the added animation at real foot contacts',len(hits)>=3 and all(float(x['gap'])<=.00251 for x in hits),hits)
  changes=events(s,'TRAINING_ANIMATION_CHANGE');coasts=[x for x in changes if x['old_cycle']=='1'and x['new_cycle']=='0'and x['function']=='1']
  check('touch animations return to normal locomotion while the ball rolls',len(coasts)>=2,coasts)
  source_exits=[x for x in changes if x['old_cycle']=='1']
  check('each forward touch gesture completes before normal locomotion',bool(source_exits)and all(int(x['old_frame'])>=int(x['old_frames'])-1 for x in source_exits),source_exits)
  travel=math.dist(origin['player'][:2],f[-1]['player'][:2]);rolling=[x for x in f if x['function']==1 and x['ball_speed']>1]
  check('player advances across the pitch rather than looping in place',travel>16 and f[-1]['speed']>2.5,{'travel_m':travel,'ending_speed_mps':f[-1]['speed']})
  check('ball rolls during ordinary locomotion between touches',len(rolling)>8,{'rolling_samples':len(rolling),'total_samples':len(f)})
  retain('forward touch/coast sequence retains the ball',f)
  drawn=events(s,'TRAINING_RENDER_SURFACE');rendered=[]
  for hit in hits:
   samples=[abs(float(x['gap']))for x in drawn if x['new_cycle']=='1'and abs(int(x['t'])-int(hit['t']))<=100]
   rendered.append({'t':hit['t'],'gap_m':min(samples,default=100)})
  check('visible shoes follow the physical dribble impacts',bool(rendered)and all(x['gap_m']<.085 for x in rendered),rendered)
  for name,stick in [('right',(.7071,-.7071)),('left',(-.7071,-.7071)),('reverse',(0,1))]:
   g.reset();g.pad(0,-1);g.advance(1600);start=len(g.log.read_text());g.pad(*stick);f=g.advance(1600);g.pad(0,-1);f+=g.advance(1800);s=g.log.read_text()[start:]
   retain(name+' turn and return keeps native ball control',f)
   foot=[int(x['t'])for x in events(s,'TRAINING_ACTION_TOUCH')if x['function']=='2'];intervals=[b-a for a,b in zip(foot,foot[1:])]
   check(name+' turn does not produce rapid consecutive dribble taps',bool(foot)and all(x>=420 for x in intervals),{'touches_ms':foot,'intervals_ms':intervals})
  g.reset();f=[]
  for _ in range(3):g.pad(0,-1,sprint=True);f+=g.advance(900);g.pad(0,-1);f+=g.advance(1400)
  retain('three RB bursts/releases recover before the next forward touch',f)
  log=g.log.read_text();accepted=[x for x in events(log,'TRAINING_SKIN_CONTACT')if x['accepted']=='1'];times={x['t']for x in accepted};impulses=events(log,'TRAINING_ACTION_TOUCH')
  check('every authored impulse retains the original real-contact tolerance',bool(impulses)and all(x['t']in times for x in impulses)and all(float(x['gap'])<=.00251 for x in accepted),{'impulses':len(impulses),'maximum_gap_m':max(float(x['gap'])for x in accepted)})
  g.keys(['Tab'],True);g.keys(['Tab'],False);g.keys(['Tab'],True);g.keys(['Tab'],False);g.advance(400)
  subprocess.run(['import','-window',g.window,str(a.output/'touch-and-coast.png')],env=g.env,check=True)
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r['result']='failed';r['error']=str(e);raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
