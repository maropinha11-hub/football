#!/usr/bin/env python3
"""Stress snapshot clearing while graphics reads live solo and 22-player poses."""
import argparse,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':287');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest(),cadence={})
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def key(g,k):g.keys([k],True);g.keys([k],False)
try:
 for match in [False,True]:
  name='match'if match else'solo'
  with NativeTraining(a.build,a.output/name,display=a.display,analog_pad=True,config_overrides={'context_x':480,'context_y':270,'training_physical_rig':'true','training_physical_lab':'true','player_match':'true'if match else'false','player_match_half_seconds':120,'simulation_seed':9})as g:
   if match:g.advance(2600)
   else:g.reset()
   g.keys(['Right'],True)
   for i in range(20):
    g.pad(0,-1);key(g,'F7');g.advance(100)
    if i%4==3:key(g,'r');g.advance(100)
   g.keys(['Right'],False);g.pad(0,0);g.advance(500)
   toggles=[int(x)for x in re.findall(r'PHYSICAL_RIG_TOGGLE enabled=(\d)',g.read_log())]
   check(name+' physics toggles repeatedly off/on while rendering',len(toggles)==20 and toggles==[i%2 for i in range(20)],dict(toggles=toggles))
   f=g.frames();check(name+' snapshots remain finite through resets and toggles',len(f)>40 and all(math.isfinite(v)for x in f for k in ['player','ball']for v in x[k]),dict(samples=len(f)))
   if match:
    m=[json.loads(x[19:])for x in g.read_log().splitlines()if x.startswith('PLAYER_MATCH_FRAME ')]
    check('all 22 actors and the same human survive repeated toggles',all(len(x['players'])==22 and x['human_count']==1 and x['selected_id']==x['locked_id']for x in m),dict(samples=len(m)))
   if len(f)>10:
    lo,hi=f[5],f[-1];r['cadence'][name]=dict(simulated_ms=hi['t']-lo['t'],wall_ms=hi['wall_ms']-lo['wall_ms'])
   g.keys(['Escape'],True);g.game.wait(timeout=20);check(name+' exits without heap corruption after repeated toggles',g.game.returncode==0,dict(exit_code=g.game.returncode))
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
