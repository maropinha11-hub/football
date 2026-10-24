"""Actual closing skin contacts must balance both human and CPU bodies."""
import argparse,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':2160');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',line))for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')]
def records(g,prefix,start=0):return[json.loads(line[len(prefix)+1:])for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')]
def key(g,k,mods=()):g.keys([*mods,k],True);g.advance(100);g.keys([*mods,k],False);g.advance(100)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=640,context_y=360,training_physical_rig='true',training_physical_lab='true',player_match='true',player_match_half_seconds=120,player_match_all_restarts='false',simulation_seed=7))as g:
  episodes=[]
  for trial in range(3):
   g.pad(0,0);key(g,'r');g.advance(2700);yaw=g.frames()[-1]['player_yaw'];g.pad(math.cos(yaw),-math.sin(yaw),sprint=True);g.advance(350)
   start=len(g.read_log());key(g,'F2',['Control_L']);g.advance(1200);g.pad(0,0);g.advance(1300)
   setup=ev(g,'PHYSICAL_MATCH_SETUP',start);locked=setup[0]['actor']if setup else'';impacts=[x for x in ev(g,'PHYSICAL_DUEL_IMPACT',start)if locked in [x['actor'],x['opponent']]]
   episodes.extend(impacts)
  check('real sprint challenges create reciprocal finite impact episodes',bool(episodes)and all(x['reciprocal']=='1'and .7<float(x['closing'])and 0<float(x['impulse'])<=240 for x in episodes),episodes)
  balance=ev(g,'PHYSICAL_BALANCE');stagger=ev(g,'PHYSICAL_STAGGER_CLIP');poses=records(g,'VISIBLE_PHYSICS');reacted={};visible={}
  for e in episodes:
   for actor in [e['actor'],e['opponent']]:
    rows=[x for x in balance if x['actor']==actor and 0<=int(x['t'])-int(e['t'])<500]
    reacted[actor]=reacted.get(actor,False)or any(int(x['phase'])>=1 and(float(x['step'])>.03 or float(x['risk'])>.2)for x in rows)or any(x['actor']==actor and 0<=int(x['t'])-int(e['t'])<500 for x in stagger)
    shown=[x for x in poses if str(x['actor'])==actor and -100<=x['t']-int(e['t'])<=650]
    spread=max([math.dist(x['torso'],y['torso'])for x in shown for y in shown]or[0]);visible[actor]=max(visible.get(actor,0),spread)
  human=str(records(g,'PLAYER_MATCH_FRAME')[-1]['locked_id'])
  check('both human and CPU attempt support recovery during actual challenges',reacted.get(human,False)and any(v for k,v in reacted.items()if k!=human),dict(human=human,reactions=reacted))
  check('the final rendered torso visibly reacts in both human and CPU',visible.get(human,0)>.10 and any(v>.10 for k,v in visible.items()if k!=human),dict(torso_direction_range=visible))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
