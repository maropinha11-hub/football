#!/usr/bin/env python3
"""Repeated Xbox taps must retain a first-time action until real contact."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from native_training_harness import NativeTraining

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--build',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':185')
a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence)
 r['checks'].append(row);print(json.dumps(row),flush=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,config_overrides={'context_x':320,'context_y':180,'training_physical_rig':'true','training_physical_lab':'true'})as g:
  for name,key,button,part,kind,delay in [
      ('ground pass repeated taps','F4',1,None,4,0),
      ('aerial pass repeated taps','F6',1,'head',4,0),
      ('aerial through pass repeated taps','F6',8,'head',5,0),
      ('header shot repeated taps','F6',4,'head',8,0),
      ('late header shot repeated taps','F6',4,'head',8,200),
      ('cross command repeated taps','F6',2,'head',6,0)]:
   g.reset();start=len(g.log.read_text());g.keys([key],True);g.keys([key],False)
   launch=g.frames()[-1]['t']
   if delay:g.advance(delay)
   taps=[]
   for _ in range(5):
    taps.append(g.frames()[-1]['t']-launch)
    g.pad(0,0,buttons=button);g.advance(100);g.pad(0,0);g.advance(100)
   g.advance(1800)
   hits=[dict(t=int(t),part=body,kind=int(k))for t,body,k in re.findall(r'TRAINING_ACTION_TOUCH t=(\d+) part=(\w+) function=(\d+)',g.log.read_text()[start:])]
   check(name,any(x['kind']==kind and (part is None or x['part']==part)for x in hits),dict(tap_offsets_ms=taps,touches=hits))
  g.keys(['Escape'],True);g.game.wait(timeout=15)
  check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
