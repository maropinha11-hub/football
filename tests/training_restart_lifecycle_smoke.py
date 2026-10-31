#!/usr/bin/env python3
"""Exercise actual restart contacts, early input and legal throw-in support."""
import argparse,hashlib,json,re
from pathlib import Path
from native_training_harness import NativeTraining

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':247');p.add_argument('--pes-actions',action='store_true');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):
 return [dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[start:].splitlines()if x.startswith(prefix+' ')]
try:
 with NativeTraining(a.build,a.output/'match',display=a.display,analog_pad=True,camera=1,
    config_overrides=dict(context_x=480,context_y=270,player_match='true',training_physical_rig='true',training_physical_lab='true',player_match_half_seconds=120,simulation_seed=7),extra_arguments=['--pes-actions']if a.pes_actions else[])as g:
  g.advance(2700)
  for i,kind in enumerate(['free_kick','penalty','corner','throw_in','goal_kick']):
   start=len(g.read_log());g.keys(['F10'],True);g.advance(100);g.keys(['F10'],False);g.advance(250)
   aim=(0,1)if i==3 else(-.2,1)if i==2 else(1,0)
   # Releasing a charged kick before the signal used to kick the ball anyway.
   g.pad(*aim,buttons=4 if i==1 else 1,sprint=True);g.advance(250);g.pad(*aim,sprint=True);g.advance(1400)
   g.pad(*aim,buttons=4 if i==1 else 1);g.advance(300);g.pad(*aim);g.advance(2400);g.pad(0,0)
   prepared=ev(g,'RESTART_PREPARED',start);authorized=ev(g,'RESTART_AUTHORIZED',start)
   released=ev(g,'RESTART_RELEASED',start);completed=ev(g,'RESTART_COMPLETED',start)
   # A later ordinary ball-out may legitimately start another sequence.
   stamp=prepared[0]if prepared else{};actor=stamp.get('actor');type_=stamp.get('type')
   auth=[x for x in authorized if x.get('actor')==actor and x.get('type')==type_]
   rel=[x for x in released if x.get('actor')==actor and x.get('type')==type_]
   done=[x for x in completed if x.get('actor')==actor and x.get('type')==type_]
   hits=[x for x in ev(g,'TRAINING_ACTION_TOUCH',start)if x.get('actor')==actor]
   check(kind+' cannot touch the ball before its whistle',bool(auth)and all(int(x['t'])>=int(auth[0]['t'])for x in hits),dict(prepared=prepared,authorized=auth,hits=hits))
   check(kind+' completes once after an actual taker contact',len(rel)==1 and len(done)==1 and bool(hits)and int(rel[0]['t'])<=int(done[0]['t'])<=int(rel[0]['t'])+20 and any(x['t']==rel[0]['t']for x in hits),dict(released=rel,completed=done,hits=hits))
   frames=[json.loads(x[19:])for x in g.read_log()[start:].splitlines()if x.startswith('PLAYER_MATCH_FRAME ')]
   check(kind+' returns to live play with one locked human',bool(done)and any(x['t']>=int(done[0]['t'])and x['in_play']and not x['set_piece']for x in frames)and all(x['human_count']==1 and x['selected_id']==x['locked_id']for x in frames),dict(tail={k:v for k,v in frames[-1].items()if k!='players'}if frames else{}))
   if i==3:
    feet=ev(g,'RESTART_FOOTING',start)
    check('throw-in keeps both actual foot surfaces outside the sideline',bool(feet)and all(float(x['margin'])>=.0249 for x in feet),dict(samples=len(feet),minimum_margin=min((float(x['margin'])for x in feet),default=-99)))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
