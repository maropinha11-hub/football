"""Run the new action bank and approved gameplay checks sequentially."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--display-base',type=int,default=4020)
p.add_argument('--resume',action='store_true',help='Reuse completed stages only when executable and bank hashes still match')
a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=a.resume)
exe=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest()
rows=[]
for name,script,extra in [
    ('turn_external','training_reception_turn_smoke.py',['--camera','1','--display',':'+str(a.display_base+2)]),
    ('turn_firstperson','training_reception_turn_smoke.py',['--camera','2','--display',':'+str(a.display_base+3)]),
    ('bank_external','training_pes_bank_smoke.py',['--camera','1','--display',':'+str(a.display_base)]),
    ('bank_firstperson','training_pes_bank_smoke.py',['--camera','2','--display',':'+str(a.display_base+1)]),
    ('approved_native','run_classic_suite.py',['--display-base',str(a.display_base+10)]),
]:
    out=a.output/name
    existing=out/'validation.json'
    reused=False
    if a.resume and existing.exists():
        previous=json.loads(existing.read_text())
        bank=Path(__file__).resolve().parents[1]/'data/media/training/pes17/catalog.json'
        reused=previous.get('result')=='passed'and previous.get('executable_sha256')==exe and (
            name=='approved_native' or previous.get('bank_catalog_sha256')==hashlib.sha256(bank.read_bytes()).hexdigest())
        if not reused:raise RuntimeError('Existing stage is failed or stale; use a new output directory: '+name)
    if not reused:
        with (a.output/(name+'.log')).open('w')as log:
            process=subprocess.run([sys.executable,str(Path(__file__).parent/script),'--build',str(a.build),
                                    '--output',str(out),*extra],stdout=log,stderr=subprocess.STDOUT)
    report=json.loads((out/'validation.json').read_text())
    passed=(reused or process.returncode==0)and report['result']=='passed'and report['executable_sha256']==exe
    row=dict(scenario=name,result='passed'if passed else'failed',report=str(out/'validation.json'),reused=reused)
    rows.append(row);print(json.dumps(row),flush=True)
    if not passed:break
coverage=set()
for name in ('bank_external','bank_firstperson'):
    path=a.output/name/'validation.json'
    if path.exists():
        coverage.update(json.loads(path.read_text()).get('observed_source_clips',[]))
# A single arrival may correctly fall back to native movement. The combined
# release still has to demonstrate all five families and the running kick.
bank=json.loads((Path(__file__).resolve().parents[1]/'data/media/training/pes17/catalog.json').read_text())
roles={r['role']for r in bank['actions']if r['source']in coverage}
coverage_ok=({'pass','shot','cross','header','reception'}<=roles and
             any(n.startswith(('kick_long_3_','kick_long_4_'))for n in coverage)and
             any(n.startswith(('kick_short_3_','kick_short_4_'))for n in coverage))
report=dict(result='passed'if len(rows)==5 and all(r['result']=='passed'for r in rows)and coverage_ok else'failed',
            executable_sha256=exe,stages=rows,observed_source_clips=sorted(coverage),
            observed_roles=sorted(roles),coverage_result='passed'if coverage_ok else'failed')
(a.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['result']=='passed'else 1)
