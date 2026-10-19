#!/usr/bin/env python3
"""Verify that converted FBX clips actually run on the native model and CPU."""
import argparse,hashlib,json,math,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':249');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def ev(g,p):return[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log().splitlines()if x.startswith(p+' ')]
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
try:
 with NativeTraining(a.build,a.output/'match',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=640,context_y=360,training_physical_rig='true',training_physical_lab='true',player_match='true',player_match_half_seconds=120,simulation_seed=7))as g:
  g.advance(2800);g.pad(0,-1,sprint=True);frames=g.advance(4500);g.pad(0,0);g.advance(600)
  loaded=ev(g,'MOCAP_CLIP');active=ev(g,'MOCAP_ACTIVE')
  check('ten source cycles and native mirrors load',len({x['source']for x in loaded})==20,dict(count=len({x['source']for x in loaded})))
  check('converted captures actually execute beyond their first frame',bool(active)and any(int(x['frame'])>5 for x in active),dict(samples=len(active),sources=sorted({x['source']for x in active})))
  matches=[json.loads(x[19:])for x in g.read_log().splitlines()if x.startswith('PLAYER_MATCH_FRAME ')]
  human=matches[-1]['locked_id']
  check('CPU also executes the imported native movement bank',any(int(x['actor'])!=human for x in active),dict(actors=sorted({int(x['actor'])for x in active}),human=human))
  check('imported locomotion never supplies a ball-contact action',all(x['function']=='1'for x in active),dict(functions=sorted({x['function']for x in active})))
  check('imported upright captures keep the root at normal player height',bool(active)and all(.65<float(x['root_height'])<1.35 for x in active),dict(minimum=min((float(x['root_height'])for x in active),default=-1),maximum=max((float(x['root_height'])for x in active),default=99)))
  check('the match remains finite with exactly one locked human',all(x['human_count']==1 and x['selected_id']==human for x in matches)and all(math.isfinite(v)for x in frames for v in x['player']+x['ball']),dict(samples=len(matches)))
  subprocess.run(['import','-window',g.window,str(a.output/'converted-locomotion.png')],env=g.env,check=True)
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
