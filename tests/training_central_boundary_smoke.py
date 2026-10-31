#!/usr/bin/env python3
"""Real foot receptions down the leg gap, including an in-play endline."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':3900');p.add_argument('--side',type=int,default=1);p.add_argument('--pes-actions',action='store_true');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def events(g,prefix,start):return[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[start:].splitlines()if x.startswith(prefix+' ')]
def key(g,k,mods=()):g.keys([*mods,k],True);g.advance(100);g.keys([*mods,k],False);g.advance(100)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=480,context_y=270,training_physical_rig='true',training_physical_lab='true',player_match='true',player_match_half_seconds=120,player_match_all_restarts='false',simulation_seed=7,training_boundary_side=a.side,training_contact_verify='true',training_performance='true'),extra_arguments=['--pes-actions']if a.pes_actions else[])as g:
  for cpu,boundary in [(False,False),(True,False),(True,True)]:
   for lateral in [None,'Shift_L','Control_L'] if not boundary else [None]:
    g.pad(0,0);key(g,'r');g.advance(2700);start=len(g.read_log())
    mods=['z']+(['h']if cpu else[])+(['b']if boundary else[])+([lateral]if lateral else[])
    key(g,'F4',mods);g.advance(1550)
    delivery=events(g,'TRAINING_DELIVERY',start);actor=delivery[0]['actor']if delivery else'';when=int(delivery[0]['t'])if delivery else 0
    # At the opponent's endline the native CPU may deliberately finish a
    # cross first-time instead of trapping it. Require an actual football
    # action and the same timed skin contact; a passive collision still fails.
    functions=['2','3','4','5','6','8']if boundary else['2','3']
    touches=[x for x in events(g,'TRAINING_ACTION_TOUCH',start)if x.get('actor')==actor and x.get('function')in functions and 'foot'in x.get('part','')and int(x['t'])<when+1600]
    skin=[x for x in events(g,'TRAINING_SKIN_CONTACT',start)if x.get('actor',actor)==actor and x.get('accepted')=='1']
    prepared=[x for x in events(g,'PREPARED_BODY_RECEPTION',start)if x.get('actor')==actor and int(x['t'])<when+1600 and float(x['skin_gap'])<=.00051 and float(x['outgoing'])<float(x['incoming']) and any(part in x['part']for part in ['knee','ankle','thigh'])]
    foot=bool(touches)and any(x['t']==y['t']and x['part']==y['part']and float(y['gap'])<=.00251 for x in touches for y in skin)
    check(('CPU'if cpu else'human')+(' endline reception/first-time action'if boundary else' central control')+' '+str(lateral)+' uses a real receiving foot or prepared shin',foot or bool(prepared),dict(delivery=delivery,touches=touches,prepared_shin=prepared,skin=skin[-8:],reach=events(g,'NATIVE_REACH_PLAN',start)[:8]))
    if boundary:
     setup=events(g,'BOUNDARY_RECEIVE_SETUP',start)
     check('fixture remains inside the final 20 cm of the goal line',bool(setup)and 0<float(setup[0]['distance_to_line'])<.2,setup)
    if boundary:subprocess.run(['import','-window',g.window,str(a.output/'endline-reception.png')],env=g.env,check=True)
  profiles=events(g,'CONTACT_SKIN_PROFILE',0)
  check('indexed skin agrees with the original weighted mesh query',bool(profiles)and all(float(x['max_error'])<.00001 for x in profiles),profiles[-4:])
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
