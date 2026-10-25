#!/usr/bin/env python3
"""Compare the same 22-player simulation with reference/indexed skin queries."""
import argparse,hashlib,json,re,statistics,time
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':3920');a=p.parse_args()
r=dict(result='running',checks=[],runs=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
try:
 for reference in [True,False]:
  config=dict(context_x=320,context_y=180,training_physical_rig='true',training_performance='true',training_contact_reference='true'if reference else'false',simulation_seed=7,player_match='true',player_match_half_seconds=120,player_match_all_restarts='false')
  with NativeTraining(a.build,a.output/('reference'if reference else'indexed'),display=a.display,analog_pad=True,camera=1,config_overrides=config)as g:
   g.advance(5000);start_t=g.frames()[-1]['t'];start=time.monotonic();offset=len(g.read_log())
   for i in range(10):g.advance(2000)
   wall=time.monotonic()-start;elapsed=(g.frames()[-1]['t']-start_t)/1000
   profiles=[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[offset:].splitlines()if x.startswith('SIMULATION_PERFORMANCE ')]
   run=dict(reference=reference,simulated_seconds=elapsed,wall_seconds=wall,pace=elapsed/wall,profiles=profiles)
   r['runs'].append(run)
   check(('reference'if reference else'indexed')+' retains a fixed 10 ms simulation tick',bool(profiles)and all(x['dt_ms']=='10'for x in profiles),run)
   g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 old,new=r['runs'];before=statistics.median(float(x['mean_ms'])for x in old['profiles']);after=statistics.median(float(x['mean_ms'])for x in new['profiles'])
 # Live AI segments do not contain identical actions. Whole-step averages
 # include trajectory/AI work, so they cannot isolate a small skin-query gain.
 # Record both, assert real-time pacing, then pair each exact query with its
 # reference implementation in a separate verification run.
 check('the physical match keeps real-time pace with the unchanged tick',new['pace']>.97,dict(reference_ms=before,indexed_ms=after,reference_pace=old['pace'],indexed_pace=new['pace']))
 config.update(training_contact_reference='false',training_contact_verify='true')
 with NativeTraining(a.build,a.output/'paired',display=a.display,analog_pad=True,camera=1,config_overrides=config)as g:
  for i in range(4):g.advance(2000)
  paired=[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log().splitlines()if x.startswith('CONTACT_SKIN_PROFILE ')]
  factors=[float(x['reference_us'])/float(x['optimized_us'])for x in paired if float(x['optimized_us'])>0]
  check('paired identical skin queries are faster without a contact change',bool(factors)and statistics.median(factors)>1.5 and all(float(x['max_error'])<.00001 for x in paired),dict(profiles=paired[-8:],median_speedup=statistics.median(factors)if factors else 0))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('paired query run exits cleanly',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
