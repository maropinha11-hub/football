#!/usr/bin/env python3
"""Rendered support-step, active fall and all-player match contact checks."""
import argparse,hashlib,json,math,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':187');p.add_argument('--match',action='store_true');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def events(g,prefix,start=0):return [dict(re.findall(r'(\w+)=([^\s]+)',line))for line in g.log.read_text()[start:].splitlines()if line.startswith(prefix+' ')]
def key(g,k):g.keys([k],True);g.advance(100);g.keys([k],False);g.advance(100)
def capture(g,name):subprocess.run(['import','-window',g.window,str(a.output/(name+'.png'))],env=g.env,check=True)
def matchframes(g):return [json.loads(s[19:])for s in g.log.read_text().splitlines()if s.startswith('PLAYER_MATCH_FRAME ')]
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides={'context_x':640,'context_y':360,'training_physical_rig':'true','training_physical_lab':'true','player_match':'true'if a.match else'false','player_match_half_seconds':60,'simulation_seed':9})as g:
  if not a.match:
   clips=[]
   for direction in range(4):
    g.reset();start=len(g.log.read_text());origin=g.frames()[-1]['player']
    g.keys(['Shift_L'],True);key(g,'F8');g.keys(['Shift_L'],False)
    capture(g,'support-step-'+str(direction));f=g.advance(2200)
    rows=events(g,'PHYSICAL_STAGGER_CLIP',start);states=events(g,'PHYSICAL_RIG_STATE',start)
    check('impact direction '+str(direction)+' selects a full-body native protective step',bool(rows)and all('protect' in x['clip']or'trip_t1' in x['clip']for x in rows),rows)
    check('impact direction '+str(direction)+' regains upright control',not any(x['to']=='1'for x in states)and f[-1]['speed']<.5,dict(states=states,final_speed=f[-1]['speed'],displacement_m=math.dist(origin[:2],f[-1]['player'][:2])))
    clips.extend(x['clip']for x in rows);key(g,'F3')
   check('directional blows choose multiple authored whole-body reactions',len(set(clips))>=3,sorted(set(clips)))
   g.reset();start=len(g.log.read_text());g.keys(['Control_L'],True);key(g,'F8');g.keys(['Control_L'],False)
   g.advance(500);capture(g,'muscular-fall');g.advance(8500)
   impacts=events(g,'PHYSICAL_IMPACT_TEST',start);states=events(g,'PHYSICAL_RIG_STATE',start);support=events(g,'PHYSICAL_SUPPORT',start)
   falls=[s for s in support if s['mode']=='1']
   check('overload first uses a protective step then yields to an unforced fall',bool(events(g,'PHYSICAL_STAGGER_CLIP',start))and any(x['to']=='1'and int(x['t'])-int(impacts[0]['t'])>=200 for x in states),dict(impacts=impacts,states=states))
   check('fall retains internal muscle torque instead of becoming completely passive',len(falls)>5 and any(float(x['muscles'])>.001 for x in falls),falls[:10])
   check('fall completes the native get-up and returns control',any(x['from']=='2'and x['to']=='0'for x in states),states)
  else:
   g.advance(2500);log=g.log.read_text();configured=events(g,'PHYSICAL_MATCH_ACTOR')+events(g,'PHYSICAL_BALANCE_BANK')
   ids={int(x['actor'])for x in configured};f=matchframes(g)[-1]
   check('all 22 match players have a physical actor',ids=={x['id']for x in f['players']},sorted(ids))
   for _ in range(40):
    f=matchframes(g)[-1];human=next(x for x in f['players']if x['human']);opponent=min((x for x in f['players']if x['team']==1 and x['id']!=18),key=lambda x:math.dist(x['p'][:2],human['p'][:2]))
    dx,dy=[opponent['p'][i]-human['p'][i]for i in range(2)];size=max(.001,math.hypot(dx,dy));g.pad(dx/size,-dy/size,sprint=True);g.advance(400)
   g.pad(0,0);g.advance(1500);capture(g,'physical-full-match');f=matchframes(g);human=f[-1]['locked_id']
   check('native collision disturbs CPU bodies as well as the human',any(int(x['actor'])!=human for x in events(g,'PHYSICAL_STAGGER_REQUEST')),events(g,'PHYSICAL_STAGGER_REQUEST')[:15])
   check('CPU contact selects full-body protective animation',any(int(x['actor'])!=human for x in events(g,'PHYSICAL_STAGGER_CLIP')),events(g,'PHYSICAL_STAGGER_CLIP')[:15])
   check('formations and one-player control remain intact',all(x['human_count']==1 and x['selected_id']==x['locked_id']and len(x['players'])==22 for x in f),dict(frames=len(f)))
   check('native AI still makes ball decisions',len(events(g,'PLAYER_MATCH_ACTION'))>3,events(g,'PLAYER_MATCH_ACTION')[:8])
   # Exercise the explicit close-contact setup and both keyboard intents.
   start=len(g.log.read_text());g.keys(['m','F2'],True);g.advance(100);g.keys(['m','F2'],False);g.advance(500)
   check('match laboratory reaches a real opponent and applies a body contest',bool(events(g,'PHYSICAL_MATCH_SETUP',start))and bool(events(g,'PHYSICAL_MATCH_CONTEST',start)),events(g,'PHYSICAL_MATCH_CONTEST',start))
   g.keys(['n'],True);g.advance(300);g.keys(['n'],False);g.keys(['h'],True);g.advance(400);g.keys(['h'],False)
   intents=events(g,'PHYSICAL_MATCH_CONTACT',start)
   check('protection and shirt-reaching input are available in the full match',any(x['shield']=='1'for x in intents)and any(x['reaching']=='1'for x in intents),intents[-8:])
   key(g,'F7');start=len(g.log.read_text());g.advance(400)
   check('comparison toggle also disables every CPU physical rig',not events(g,'PHYSICAL_BALANCE',start),events(g,'PHYSICAL_BALANCE',start)[:3])
   key(g,'F7');g.advance(500)
  arms=events(g,'PHYSICAL_ARM_RENDER');check('final rendered arms keep their anatomical limits',len(arms)>100 and max(float(x['error'])for x in arms)<1e-5 and max(float(x['penetration'])for x in arms)<.004,dict(samples=len(arms),maximum_error_rad=max(float(x['error'])for x in arms),maximum_penetration_m=max(float(x['penetration'])for x in arms)))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
