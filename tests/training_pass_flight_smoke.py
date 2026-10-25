#!/usr/bin/env python3
"""Exercise actual charged crosses and through passes, with real contacts."""
import argparse,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':3910');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start):return[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[start:].splitlines()if x.startswith(prefix+' ')]
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=480,context_y=270,training_physical_rig='true',training_physical_lab='true',simulation_seed=7,training_turf_roughness=0))as g:
  for name,button,kind in [('cross',2,'6'),('through',8,'5')]:
   speeds=[];distances=[]
   for hold in [100,350,700]:
    g.reset();start=len(g.read_log());g.pad(0,0,buttons=button);g.advance(hold);g.pad(0,0);g.advance(3700)
    releases=[x for x in ev(g,'PASS_FLIGHT_RELEASE',start)if x['function']==kind]
    touches=[x for x in ev(g,'TRAINING_ACTION_TOUCH',start)if x['function']==kind]
    skins=ev(g,'TRAINING_SKIN_CONTACT',start)
    check(name+' '+str(hold)+' ms completes once on the real shoe',len(releases)==1 and len(touches)==1 and any(x['t']==touches[0]['t']and x['accepted']=='1'and float(x['gap'])<=.00251 for x in skins),dict(releases=releases,touches=touches))
    if not releases:continue
    release=releases[0];speeds.append(float(release['actual']))
    check(name+' '+str(hold)+' ms retains calibrated speed and elevation',.919<float(release['actual'])/float(release['planned'])<1.081 and 0<float(release['vz'])<15,release)
    frames=[x for x in g.frames()if x['t']>=int(release['t'])]
    distance=max([math.dist(frames[0]['ball'][:2],x['ball'][:2])for x in frames]or[0]);distances.append(distance)
    check(name+' '+str(hold)+' ms travels rather than dying at the feet',distance>2 and distance<85,dict(distance_m=distance))
   check(name+' button charge progressively increases actual launch speed',len(speeds)==3 and all(y>x+.5 for x,y in zip(speeds,speeds[1:])),dict(speeds=speeds,distances=distances))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
