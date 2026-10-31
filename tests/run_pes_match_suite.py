"""Validate the expanded bank with CPUs, keeper arrivals and real restarts."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);p.add_argument('--display-base',type=int,default=4200)
p.add_argument('--resume',action='store_true');a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=a.resume)
exe=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest()
bank=Path(__file__).resolve().parents[1]/'data/media/training/pes17/catalog.json'
bank_hash=hashlib.sha256(bank.read_bytes()).hexdigest()
previous={}
if a.resume:
    prior=json.loads((a.output/'validation.json').read_text())
    if prior['executable_sha256']!=exe or prior['bank_catalog_sha256']!=bank_hash:
        raise RuntimeError('Cannot reuse a suite for a different executable or bank')
    previous={r['scenario']:r for r in prior['stages']}
    serial=1
    while(a.output/('validation-previous-'+str(serial)+'.json')).exists():serial+=1
    (a.output/('validation-previous-'+str(serial)+'.json')).write_text(json.dumps(prior,indent=2)+'\n')
rows=[]
for index,(name,script)in enumerate([
    ('central','training_central_boundary_smoke.py'),('airborne','training_active_reception_smoke.py'),
    ('keepers','training_keeper_arrivals_smoke.py'),('restarts','training_restart_lifecycle_smoke.py'),
    ('autonomous_match','player_match_ai_smoke.py')]):
    out=a.output/name
    reused=name in previous and previous[name]['result']=='passed'
    if reused:out=Path(previous[name]['report']).parent
    else:
        serial=1
        while out.exists():
            serial+=1;out=a.output/(name+'-attempt'+str(serial))
        with(a.output/(out.name+'.log')).open('w')as log:
            process=subprocess.run([sys.executable,str(Path(__file__).parent/script),'--build',str(a.build),
                                    '--output',str(out),'--display',':'+str(a.display_base+index),'--pes-actions'],stdout=log,stderr=subprocess.STDOUT)
    report=json.loads((out/'validation.json').read_text())
    passed=(reused or process.returncode==0)and report['result']=='passed'and report['executable_sha256']==exe
    row=dict(scenario=name,result='passed'if passed else'failed',checks=len(report['checks']),report=str(out/'validation.json'),reused=reused)
    rows.append(row);print(json.dumps(row),flush=True)
    if not passed:break
result=dict(result='passed'if len(rows)==5 and all(r['result']=='passed'for r in rows)else'failed',
            executable_sha256=exe,bank_catalog_sha256=bank_hash,stages=rows)
(a.output/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
raise SystemExit(0 if result['result']=='passed'else 1)
