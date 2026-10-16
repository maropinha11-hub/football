#!/usr/bin/env python3
"""Run two isolated rendered football regressions at a time and retain evidence."""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--build',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
env=os.environ.copy();native=Path(env.get('FOOTBALL_NATIVE_ROOT','/workspace/.football-native'))/'root/usr'
env['PATH']=str(native/'bin')+':'+env['PATH']
env['LD_LIBRARY_PATH']=str(native/'lib/x86_64-linux-gnu')+':'+env.get('LD_LIBRARY_PATH','')
env['FOOTBALL_TEST_GL_THREADS']='1'
cases=[('physical_solo','training_physical_rig_smoke.py',[]),
       ('physical_actions','training_running_actions_smoke.py',['--physical']),
       ('physical_controls','training_native_controls_smoke.py',['--physical']),
       ('physical_match','training_physical_rig_smoke.py',['--match']),
       ('approved_gait','training_forward_cycle_smoke.py',[]),
       ('approved_match','player_match_smoke.py',[]),
       ('physical_quality','training_physical_quality_smoke.py',[])]
def run(item):
 i,(name,script,extra)=item
 with (a.output/(name+'.log')).open('w')as log:
  result=subprocess.run(['python3','tests/'+script,'--build',str(a.build),'--output',str(a.output/name),
                         '--display',':'+str(164+i),*extra],env=env,stdout=log,stderr=subprocess.STDOUT)
 report=dict(scenario=name,exit_code=result.returncode)
 path=a.output/name/'validation.json'
 if path.exists():
  data=json.loads(path.read_text());report.update(result=data['result'],checks=len(data['checks']),
      failed_checks=[c['check']for c in data['checks']if c['result']!='passed'])
 print(json.dumps(report),flush=True);return report
rows=list(concurrent.futures.ThreadPoolExecutor(max_workers=2).map(run,enumerate(cases)))
(a.output/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
raise SystemExit(1 if any(r['exit_code']for r in rows)else 0)
