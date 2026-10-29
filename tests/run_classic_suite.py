"""Run the existing rendered gameplay regressions on one final executable."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--display-base',type=int,default=4610);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
expected=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest();rows=[]
for index,(name,script,extra)in enumerate([
    ('camera','training_firstperson_sync_smoke.py',[]),
    ('central','training_central_boundary_smoke.py',[]),
    ('airborne','training_active_reception_smoke.py',[]),
    ('actions','training_situational_actions_smoke.py',['--quick','--camera','1']),
]):
    out=a.output/name
    with (a.output/(name+'.log')).open('w')as log:
        result=subprocess.run([sys.executable,str(Path(__file__).parent/script),'--build',str(a.build),
                               '--output',str(out),'--display',':'+str(a.display_base+index),*extra],stdout=log,stderr=subprocess.STDOUT)
    report=json.loads((out/'validation.json').read_text())
    passed=result.returncode==0 and report['result']=='passed'and report['executable_sha256']==expected
    row=dict(scenario=name,result='passed'if passed else'failed',checks=len(report['checks']),executable_sha256=report['executable_sha256'])
    rows.append(row);print(json.dumps(row),flush=True)
    if not passed:break
final=dict(result='passed'if len(rows)==4 and all(r['result']=='passed'for r in rows)else'failed',scenarios=rows,executable_sha256=expected)
(a.output/'validation.json').write_text(json.dumps(final,indent=2)+'\n')
raise SystemExit(0 if final['result']=='passed'else 1)
