#!/usr/bin/env python3
"""Compare identical native dribbles with the optional contact lift off/on."""
import argparse,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':196');a=p.parse_args()
r=dict(result='running',checks=[],trajectories={},executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,data):
 row=dict(check=name,result='passed'if ok else'failed',evidence=data);r['checks'].append(row);print(json.dumps(row),flush=True)
try:
 peaks=[]
 for hop in [0,.82]:
  with NativeTraining(a.build,a.output/str(hop),display=a.display,analog_pad=True,camera=2,
    config_overrides={'context_x':320,'context_y':180,'training_physical_rig':'true','training_physical_lab':'true','training_control_hop':hop})as g:
   g.reset();start=len(g.log.read_text());g.pad(0,-1);frames=g.advance(4500);g.pad(0,0)
   log=g.log.read_text()[start:];hits=re.findall(r'TRAINING_ACTION_TOUCH t=\d+ part=(\w+) function=2',log)
   peak=max(f['ball'][2]for f in frames);gap=max(math.dist(f['player'][:2],f['ball'][:2])for f in frames);peaks.append(peak)
   r['trajectories'][str(hop)]=dict(peak_ball_height_m=peak,maximum_ball_range_m=gap,touches=hits,frames=frames)
   check('hop '+str(hop)+' follows actual native foot controls',len(hits)>=5 and all(x in ['right_foot','left_foot']for x in hits),dict(touches=hits))
   g.keys(['Escape'],True);g.game.wait(timeout=15)
   check('hop '+str(hop)+' keeps a low playable ball and exits cleanly',gap<2 and peak<.20 and g.game.returncode==0,dict(maximum_range_m=gap,peak_ball_height_m=peak,exit_code=g.game.returncode))
 check('contact lift measurably increases the small dribble hops',peaks[1]>peaks[0]+.004,dict(native_peak_m=peaks[0],lifted_peak_m=peaks[1]))
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as error:r.update(result='failed',error=str(error));raise
finally:a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
