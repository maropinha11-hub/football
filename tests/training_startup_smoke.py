#!/usr/bin/env python3
"""Repeat rendered physical-match initialization and clean shutdown."""
import argparse,hashlib,json,math
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':348');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
try:
 for i in range(6):
  with NativeTraining(a.build,a.output/('boot-'+str(i)),display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=480,context_y=270,training_physical_rig='true',training_physical_lab='true',player_match='true',simulation_seed=7))as g:
   frames=g.advance(700)
   matches=[json.loads(x[19:])for x in g.read_log().splitlines()if x.startswith('PLAYER_MATCH_FRAME ')]
   check('boot '+str(i)+' initializes 22 physical players and a working controller',bool(matches)and all(len(x['players'])==22 and x['human_count']==1 and x['locked_id']==x['selected_id']for x in matches)and frames[-1]['controller']==1 and all(math.isfinite(v)for f in frames for v in f['player']+f['ball']),dict(samples=len(matches),time=frames[-1]['t']))
   g.keys(['Escape'],True);g.game.wait(timeout=15);check('boot '+str(i)+' closes normally',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
