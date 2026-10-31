"""Require intentional airborne actions, not eventual passive body collisions."""
import argparse,hashlib,json,math,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':2100');p.add_argument('--pes-actions',action='store_true');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',line))for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')]
def records(g,prefix,start=0):return list({(x['t'],x.get('actor',-1)):x for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')for x in [json.loads(line[len(prefix)+1:])]}.values())
def key(g,k,mods=()):g.keys([*mods,k],True);g.advance(100);g.keys([*mods,k],False);g.advance(100)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=640,context_y=360,training_physical_rig='true',training_physical_lab='true',player_match='true',player_match_half_seconds=120,player_match_all_restarts='false',simulation_seed=7),extra_arguments=['--pes-actions']if a.pes_actions else[])as g:
  bank=ev(g,'PHYSICAL_RECEIVE_BANK');check('derived full-body actions load from native sources',bool(bank)and int(bank[0]['clips'])>=100,bank)
  for cpu in [False,True]:
   for name,k,mods,parts in [('shin','F5',['7'],['foot','lowerleg']),('thigh','F5',['8'],['foot','lowerleg','upperleg']),('descending','F5',['9'],['trunk','head']),('jump','F6',['Shift_L'],['head'])]:
    g.pad(0,0);key(g,'r');g.advance(2700);start=len(g.read_log());key(g,k,(['h']if cpu else[])+mods)
    capture_at=1100 if name=='jump'else 400
    g.advance(capture_at);subprocess.run(['import','-window',g.window,str(a.output/(('cpu-'if cpu else'human-')+name+'.png'))],env=g.env,check=True);g.advance(1700)
    deliveries=ev(g,'TRAINING_DELIVERY',start);actor=deliveries[0]['actor']if deliveries else'';when=int(deliveries[0]['t'])if deliveries else 0
    check(('CPU 'if cpu else'human ')+name+' starts a new incoming ball without the previous attempt owner',bool(deliveries)and deliveries[0].get('last_actor')=='-1',deliveries)
    selected=[x for x in ev(g,'NATIVE_APPROVED_SELECT',start)if x.get('actor')==actor and int(x['t'])<when+1000 and (x.get('function')=='3' or 'head'in x.get('source',''))]
    contacts=[x for x in ev(g,'TRAINING_ACTION_TOUCH',start)if x.get('actor')==actor and int(x['t'])<when+1300 and float(x.get('z',0))>.27 and any(part in x.get('part','')for part in parts)]
    title=('CPU 'if cpu else'human ')+name
    if any(x.get('part')=='head'for x in contacts):
     touch=min(int(x['t'])for x in contacts if x.get('part')=='head')
     repeats=[x for x in ev(g,'TRAINING_BODY_TOUCH',start)if x.get('actor')==actor and x.get('part')=='neck'and touch<int(x['t'])<=touch+350]
     check(title+' cushions without repeatedly hammering the ball against its own head',len(repeats)<=2,repeats)
    check(title+' intentionally selects and completes an airborne skin contact',bool(selected)and bool(contacts),dict(delivery=deliveries,selected=selected,contacts=contacts,body=ev(g,'TRAINING_BODY_TOUCH',start)))
    until=min([int(x['t'])for x in contacts]or[when+1300]);poses=[x for x in records(g,'VISIBLE_PHYSICS',start)if str(x['actor'])==actor and when<=x['t']<=until+80]
    lift=max([max(x['left'][2],x['right'][2])for x in poses]or[0]);flight=max([min(x['left'][2],x['right'][2])for x in poses]or[0])
    if name in ['shin','thigh']:check(title+' visibly reaches with the leg before impact',lift>.24,dict(max_ankle_height=lift,samples=len(poses)))
    if name=='jump':check(title+' actually lifts both feet off the pitch',flight>.20,dict(minimum_ankle_height_peak=flight,max_ankle_height=lift,samples=len(poses)))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
