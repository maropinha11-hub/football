#!/usr/bin/env python3
"""Rendered Xbox checks for native right-foot dribbling in every direction."""
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
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides={'context_x':320,'context_y':180})as g:
  for name,stick in [('up',(0,-1)),('right',(1,0)),('down',(0,1)),('left',(-1,0)),('diagonal',(.7071,-.7071))]:
   g.reset();origin=g.frames()[-1];start=len(g.read_log());g.pad(*stick);f=g.advance(4500);s=g.read_log()[start:]
   starts=[x for x in events(s,'TRAINING_NATIVE_START')if x['function']=='2']
   hits=[x for x in events(s,'TRAINING_SKIN_CONTACT')if x['accepted']=='1'and'foot'in x.get('part','')]
   right=sum(x.get('part')=='right_foot'for x in hits)
   check(name+' uses the native third-person gait instead of DefenseJog',any(x['name']=='media/animations/ballcontrol/walk/000.anim'for x in starts)and all('DefenseJog'not in x['name']for x in starts),starts)
   check(name+' prefers actual right-foot contacts',len(hits)>=4 and right/len(hits)>=.75,{'right_foot':right,'total':len(hits)})
   retain(name+' keeps the ball under native control',f)
   travel=math.dist(origin['player'][:2],f[-1]['player'][:2]);check(name+' advances without looping in place',travel>8 and f[-1]['speed']>2,{'travel_m':travel,'ending_speed_mps':f[-1]['speed']})
  g.reset();g.pad(0,-.4);f=g.advance(1800);retain('light stick retains the slow native gait and ball',f)
  for name,stick in [('right',(.7071,-.7071)),('left',(-.7071,-.7071)),('reverse',(0,1))]:
   g.reset();g.pad(0,-1);g.advance(1600);start=len(g.read_log());g.pad(*stick);f=g.advance(1600);g.pad(0,-1);f+=g.advance(1800);s=g.read_log()[start:]
   retain(name+' turn and return keeps native ball control',f)
   foot=[int(x['t'])for x in events(s,'TRAINING_ACTION_TOUCH')if x['function']=='2'];intervals=[b-a for a,b in zip(foot,foot[1:])]
   check(name+' turn does not produce rapid consecutive dribble taps',bool(foot)and all(x>=420 for x in intervals),{'touches_ms':foot,'intervals_ms':intervals})
  g.reset();f=[]
  for _ in range(3):g.pad(0,-1,sprint=True);f+=g.advance(900);g.pad(0,-1);f+=g.advance(1400)
  retain('three RB bursts/releases retain the native recovery',f)
  log=g.read_log();accepted=[x for x in events(log,'TRAINING_SKIN_CONTACT')if x['accepted']=='1'];times={x['t']for x in accepted};impulses=events(log,'TRAINING_ACTION_TOUCH')
  check('every authored impulse requires real skin contact',bool(impulses)and all(x['t']in times for x in impulses)and all(float(x['gap'])<=.00251 for x in accepted),{'impulses':len(impulses),'maximum_gap_m':max(float(x['gap'])for x in accepted)})
  check('imported forward gait is never selected in any direction',not any(x['new_cycle']=='1'for x in events(log,'TRAINING_ANIMATION_CHANGE')),{'changes':len(events(log,'TRAINING_ANIMATION_CHANGE'))})
  subprocess.run(['import','-window',g.window,str(a.output/'native-right-foot.png')],env=g.env,check=True)
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r['result']='failed';r['error']=str(e);raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
