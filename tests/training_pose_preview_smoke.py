#!/usr/bin/env python3
"""Render a locally supplied native clip on the original weighted skin."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from native_training_harness import NativeTraining

p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True)
p.add_argument('--clip',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':3930');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest(),clip_sha256=hashlib.sha256(a.clip.read_bytes()).hexdigest())
def records(g,prefix):return[dict(re.findall(r'(\w+)=([^\s]+)',s))for s in g.read_log().splitlines()if s.startswith(prefix+' ')]
def check(name,ok,evidence):
    row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
try:
    for frame in [0,45,90]:
        with NativeTraining(a.build,a.output/('frame-'+str(frame)),display=a.display,camera=1,
                config_overrides=dict(context_x=960,context_y=540,training_pose_preview_file=str(a.clip.resolve()),
                    training_pose_preview_frame=frame,training_physical_rig='true',training_telemetry='true'))as g:
            g.advance(250)
            skin=records(g,'PES3_BODY_SKIN');geometry=records(g,'PES3_BODY_GEOMETRY');body=records(g,'PES3_BODY_APPLY')
            prefix='frame '+str(frame)+' '
            check(prefix+'loads only the visual preview',bool(records(g,'TRAINING_POSE_PREVIEW')),records(g,'TRAINING_POSE_PREVIEW'))
            check(prefix+'keeps the weighted skin finite and preserves rigid limb distances',bool(skin)and all(
                int(x['invalid'])==0 and float(x['rigid_error'])<.00003 for x in skin),skin[-2:])
            check(prefix+'keeps the applied bone hierarchy consistent',bool(geometry)and all(
                float(x['applied_fk_error'])<.00003 and 0<float(x['root_z'])<2 for x in geometry),geometry[-2:])
            check(prefix+'keeps the actual boot vertices above the pitch',bool(skin)and all(float(x['foot_min_z'])>-.02 for x in skin),skin[-2:])
            check(prefix+'keeps the head above the pelvis',bool(body)and all(float(x['head_z'])>1.2 for x in body),body[-2:])
            subprocess.run(['import','-window',g.window,str(a.output/('pose-'+str(frame)+'.png'))],env=g.env,check=True)
            g.keys(['Escape'],True);g.game.wait(timeout=15);check(prefix+'clean exit',g.game.returncode==0,g.game.returncode)
    r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as error:r.update(result='failed',error=str(error));raise
finally:
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
