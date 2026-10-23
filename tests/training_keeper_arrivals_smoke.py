"""Rendered saves and displaced backpasses: assert actual contact and outcomes."""
import argparse,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':850');p.add_argument('--central-only',action='store_true');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',line))for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')]
def key(g,k,mods=[]):g.keys(mods+[k],True);g.advance(80);g.keys(mods+[k],False);g.advance(120)
def mf(g,start=0):return[json.loads(line[19:])for line in g.read_log()[start:].splitlines()if line.startswith('PLAYER_MATCH_FRAME ')]
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=480,context_y=270,training_physical_rig='true',training_physical_lab='true',player_match='true',player_match_half_seconds=120,simulation_seed=7,training_keeper_lab_start=7 if a.central_only else 0))as g:
  g.advance(2700)
  for trial in (range(7,9)if a.central_only else range(11)):
   if trial>(7 if a.central_only else 0):key(g,'r');g.advance(2700)
   start=len(g.read_log());key(g,'F6',['Control_L'])
   setup=ev(g,'KEEPER_LAB_SETUP',start)[-1]
   check('lab scenario '+str(trial)+' uses the requested initial condition',int(setup['mode'])==trial,setup)
   if trial<7:continue
   g.advance(3600);keeper=setup['actor'];frames=mf(g,start)
   hits=[x for x in ev(g,'TRAINING_ACTION_TOUCH',start)if x.get('actor')==keeper]
   body=[x for x in ev(g,'TRAINING_BODY_TOUCH',start)if x.get('actor')==keeper]
   check('arrival '+str(trial)+' is actually intercepted on the body',bool(hits or body),dict(hits=hits,body=body))
   check('reachable arrival '+str(trial)+' is kept out of goal',bool(frames)and all(f['home']==0 and f['away']==0 for f in frames),dict(scores=[[f['t'],f['home'],f['away']]for f in frames],hits=hits,body=body))
   if trial>=9:
    check('backpass '+str(trial)+' is handled only with legal body parts',all('elbow'not in x.get('part','')and 'hand'not in x.get('part','')for x in hits+body),dict(hits=hits,body=body))
  check('all rendered player and ball positions remain finite',all(math.isfinite(v)for f in g.frames()for k in ['player','ball']for v in f[k]),dict(frames=len(g.frames())))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
