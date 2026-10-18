#!/usr/bin/env python3
"""Stress caption redraws, accelerated clocks, restarts and orderly shutdown."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':397');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 x=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(x);print(json.dumps(x),flush=True)
def tap(g,key):g.keys([key],True);g.keys([key],False);g.advance(100)
try:
 for iteration in range(3):
  # Isolate caption/clock concurrency with a reproducible match. The shipped
  # human restarts have their own rendered tests; they must not leave this
  # unattended clock/exit stress waiting for a manual throw-in.
  with NativeTraining(a.build,a.output/str(iteration),display=a.display,analog_pad=True,camera=1,config_overrides={'context_x':480,'context_y':270,'player_match':'true','player_match_half_seconds':8,'training_physical_rig':'false','player_match_all_restarts':'false','simulation_seed':7})as g:
   g.advance(2700)
   for _ in range(24):tap(g,'Tab')
   g.wait(lambda:'PLAYER_MATCH_END 'in g.read_log(),seconds=50)
   frames=[json.loads(l[19:])for l in g.read_log().splitlines()if l.startswith('PLAYER_MATCH_FRAME ')]
   check('cycle '+str(iteration)+' completes both halves with all actors',bool(frames)and {1,2}<={f['phase']for f in frames}and all(len(f['players'])==22 for f in frames),dict(samples=len(frames)))
   check('cycle '+str(iteration)+' exercises every camera while clock captions change',{0,1,2}<={f['camera']for f in g.frames()},dict(modes=sorted({f['camera']for f in g.frames()}),camera_requests=24))
   tap(g,'r');g.advance(2700)
   for _ in range(8):tap(g,'Tab')
   tap(g,'e');last=[json.loads(l[19:])for l in g.read_log().splitlines()if l.startswith('PLAYER_MATCH_FRAME ')][-1]
   check('cycle '+str(iteration)+' restarts the score and preserves the selected human',last['home']==last['away']==0 and last['selected_id']==last['locked_id']and last['human_count']==1,dict(clock=last['clock'],home=last['home'],away=last['away']))
   if iteration==0:subprocess.run(['import','-window',g.window,str(a.output/'hud-message.png')],env=g.env,check=True)
   g.keys(['Escape'],True);g.game.wait(timeout=15);check('cycle '+str(iteration)+' exits without allocator failure',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
