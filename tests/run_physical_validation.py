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
p.add_argument('--display-base',type=int,default=164)
p.add_argument('--only',nargs='+',choices=['elevated_reception','visible_walk','visible_receive','support_step','malleable_solo','malleable_match','aerial_contest','energy_solo','energy_match','keeper_central','keeper_arrivals','refinement_solo','refinement_match','approved_restore','firstperson_sync','control_hop_comparison','situational_fps','situational_external','physical_solo','physical_actions','physical_controls','physical_match','approved_gait','approved_match','physical_quality','contact_lab','pass_turn','balance_lab','aerial_taps','aerial_direction_fps','aerial_direction_external','aerial_direction_approved','anatomy_lab','stagger_lab','stagger_match','pitch_turf','pitch_receive','pitch_rules','pitch_body','pitch_tackle','cpu_grip','toggle_stress','tactical_receptions','hud_stress','restart_lifecycle','startup_cycles','pass_turn_fps'])
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
env=os.environ.copy();native=Path(env.get('FOOTBALL_NATIVE_ROOT','/workspace/.football-native'))/'root/usr'
env['PATH']=str(native/'bin')+':'+env['PATH']
env['LD_LIBRARY_PATH']=str(native/'lib/x86_64-linux-gnu')+':'+env.get('LD_LIBRARY_PATH','')
env['FOOTBALL_TEST_GL_THREADS']='1'
cases=[('elevated_reception','training_elevated_reception_smoke.py',[]),
       ('visible_walk','training_visible_motion_smoke.py',['--mode','walk']),
       ('visible_receive','training_visible_motion_smoke.py',['--mode','receive']),
       ('support_step','training_support_step_smoke.py',[]),
       ('malleable_solo','training_malleable_smoke.py',[]),
       ('malleable_match','training_malleable_smoke.py',['--match']),
       ('aerial_contest','training_aerial_contest_smoke.py',[]),
       ('energy_solo','training_energy_flight_smoke.py',[]),
       ('energy_match','training_energy_flight_smoke.py',['--match']),
       ('keeper_central','training_keeper_arrivals_smoke.py',['--central-only']),
       ('keeper_arrivals','training_keeper_arrivals_smoke.py',[]),
       ('refinement_solo','training_refinement_smoke.py',[]),
       ('refinement_match','training_refinement_smoke.py',['--match']),
       ('approved_restore','training_approved_restore_smoke.py',[]),
       ('firstperson_sync','training_firstperson_sync_smoke.py',[]),
       ('startup_cycles','training_startup_smoke.py',[]),
       ('restart_lifecycle','training_restart_lifecycle_smoke.py',[]),
       ('control_hop_comparison','training_control_hop_smoke.py',[]),
       ('situational_fps','training_situational_actions_smoke.py',[]),
       ('situational_external','training_situational_actions_smoke.py',['--camera','1']),
       ('physical_solo','training_physical_rig_smoke.py',[]),
       ('physical_actions','training_running_actions_smoke.py',['--physical']),
       ('physical_controls','training_native_controls_smoke.py',['--physical']),
       ('physical_match','training_physical_rig_smoke.py',['--match']),
       ('approved_gait','training_forward_cycle_smoke.py',[]),
       ('approved_match','player_match_smoke.py',[]),
       ('physical_quality','training_physical_quality_smoke.py',[]),
       ('contact_lab','training_contact_lab_smoke.py',[]),
       ('pass_turn','training_pass_turn_smoke.py',[]),
       ('pass_turn_fps','training_pass_turn_smoke.py',['--camera','2']),
       ('balance_lab','training_balance_control_smoke.py',[]),
       ('aerial_taps','training_aerial_taps_smoke.py',[]),
       ('aerial_direction_fps','training_aerial_direction_smoke.py',[]),
       ('aerial_direction_external','training_aerial_direction_smoke.py',['--camera','1']),
       ('aerial_direction_approved','training_aerial_direction_smoke.py',['--approved']),
       ('anatomy_lab','training_anatomy_smoke.py',[]),
       ('stagger_lab','training_stagger_smoke.py',[]),
       ('stagger_match','training_stagger_smoke.py',['--match']),
       ('pitch_turf','training_pitch_rules_smoke.py',['--mode','turf']),
       ('pitch_receive','training_pitch_rules_smoke.py',['--mode','receive']),
       ('pitch_rules','training_pitch_rules_smoke.py',['--mode','rules']),
       ('pitch_body','training_pitch_rules_smoke.py',['--mode','body']),
       ('pitch_tackle','training_pitch_rules_smoke.py',['--mode','tackle']),
       ('cpu_grip','training_cpu_grip_smoke.py',[]),
       ('toggle_stress','training_toggle_stress_smoke.py',[]),
       ('tactical_receptions','training_tactical_receptions_smoke.py',[]),
       ('hud_stress','training_hud_stress_smoke.py',[])]
if a.only:cases=sorted([c for c in cases if c[0]in a.only],key=lambda c:a.only.index(c[0]))
def run(item):
 i,(name,script,extra)=item
 with (a.output/(name+'.log')).open('w')as log:
  result=subprocess.run(['python3','tests/'+script,'--build',str(a.build),'--output',str(a.output/name),
                         '--display',':'+str(a.display_base+i),*extra],env=env,stdout=log,stderr=subprocess.STDOUT)
 report=dict(scenario=name,exit_code=result.returncode)
 path=a.output/name/'validation.json'
 if path.exists():
  data=json.loads(path.read_text());report.update(result=data['result'],checks=len(data['checks']),
      failed_checks=[c['check']for c in data['checks']if c['result']!='passed'])
 print(json.dumps(report),flush=True);return report
rows=list(concurrent.futures.ThreadPoolExecutor(max_workers=2).map(run,enumerate(cases)))
(a.output/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
raise SystemExit(1 if any(r['exit_code']for r in rows)else 0)
