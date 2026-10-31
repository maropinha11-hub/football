#!/usr/bin/env python3
"""Record completed graphical suites against the binaries being packaged.

No failed/stale stage can be promoted to a successful release report.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def write(name,value):(ROOT/'docs'/name).write_text(json.dumps(value,indent=2)+'\n')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite',type=Path,required=True);p.add_argument('--match',type=Path,required=True)
    p.add_argument('--ctest-log',type=Path,required=True);p.add_argument('--python-log',type=Path,required=True)
    p.add_argument('--native',type=Path,default=ROOT/'build/gameplayfootball')
    p.add_argument('--windows',type=Path,default=ROOT/'build-windows-mingw2/gameplayfootball.exe')
    a=p.parse_args();native=digest(a.native)
    bank_path=ROOT/'data/media/training/pes17/catalog.json';bank=read(bank_path);bank_hash=digest(bank_path)
    def require(report,with_bank=False):
        if report['result']!='passed' or report['executable_sha256']!=native:
            raise ValueError('Failed or stale graphical report')
        if with_bank and report.get('bank_catalog_sha256')!=bank_hash:
            raise ValueError('Stale bank in graphical report')
        if any(row['result']!='passed'for row in report.get('checks',[])):
            raise ValueError('Failed graphical check')
    solo=read(a.suite/'validation.json');require(solo)
    if {r['scenario']for r in solo['stages']}!={'turn_external','turn_firstperson','bank_external','bank_firstperson','approved_native'}:
        raise ValueError('Missing release stage')
    stages={r['scenario']:read(Path(r['report']))for r in solo['stages']}
    for name,r in stages.items():require(r,with_bank=name!='approved_native')
    classic=stages['approved_native']
    if len(classic['scenarios'])!=4 or any(r['result']!='passed'or r['executable_sha256']!=native for r in classic['scenarios']):
        raise ValueError('Missing native regression')
    match=read(a.match/'validation.json');require(match,True)
    if {r['scenario']for r in match['stages']}!={'central','airborne','keepers','restarts','autonomous_match'}:
        raise ValueError('Missing full-match stage')
    match_reports={}
    for row in match['stages']:
        r=read(Path(row['report']));require(r);match_reports[row['scenario']]=r
    ctest=a.ctest_log.read_text();python=a.python_log.read_text()
    total=re.search(r'100% tests passed, 0 tests failed out of (\d+)',ctest)
    py_count=re.search(r'Ran (\d+) tests in ',python);skips=re.search(r'OK \(skipped=(\d+)\)',python)
    if not total or not py_count or not re.search(r'^OK(?: \(skipped=\d+\))?$',python,re.M):
        raise ValueError('Unit tests did not finish successfully')
    metric=read(ROOT/'docs/pes2017-pose-metric-validation.json')
    if metric['result']!='passed'or metric['bank_catalog_sha256']!=bank_hash or metric['header_sha256']!=digest(ROOT/'src/onthepitch/player/humanoid/learned_pes_pose_metric.hpp'):
        raise ValueError('Stale learned metric')
    date=datetime.now(timezone.utc).date().isoformat()
    views=[]
    for name,camera in [('bank_external','external'),('bank_firstperson','firstperson')]:
        r=dict(stages[name]);r['camera']=camera;views.append(r)
    turns=dict(date=date,result='passed',executable_sha256=native,bank_catalog_sha256=bank_hash,
               checks=sum(len(stages[n]['checks'])for n in ('turn_external','turn_firstperson')),
               views=[stages['turn_external'],stages['turn_firstperson']])
    action=dict(date=date,result='passed',executable_sha256=native,bank_catalog_sha256=bank_hash,
                source_clips=bank['source_clips'],runtime_candidates=bank['runtime_candidates'],
                checks=sum(len(v['checks'])for v in views),views=views,
                actual_contact_sources=solo['observed_source_clips'],observed_roles=solo['observed_roles'],
                pose_validation=dict(result='passed',source_clips=bank['source_clips'],all_keys_finite=True,
                                     fixed_native_bone_lengths=True,foot_support_checked=True,
                                     approved_pass_pose_digest_unchanged=True,packed_float32_interop='passed',
                                     command="python3 -m unittest discover -s tests -p 'test_*.py'"),
                limitations=dict(windows_gui_executed=False,original_pes_selector_recovered=False,
                                 original_pes_ball_physics_integrated=False,all_sources_contact_exercised=False,
                                 all_possible_ball_arrivals_proven=False,source_fps_assumed=30,
                                 source_angular_scale_assumed='pi/2',native_fallback_retained=True))
    match_public=dict(date=date,result='passed',executable_sha256=native,bank_catalog_sha256=bank_hash,
                      stages=[dict(scenario=name,result=r['result'],checks=r['checks'])for name,r in match_reports.items()],
                      checks=sum(len(r['checks'])for r in match_reports.values()),windows_gui_executed=False,
                      human_restart_inputs=match_reports['autonomous_match'].get('human_restart_inputs',[]),
                      fixture_note='CPU live play receives no input; automation plays only the fixed human player\'s authorized restarts.')
    skipped=int(skips[1])if skips else 0
    report=dict(date=date,result='passed',base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                scope='Native animation/IK with the expanded opt-in PES bank and learned pose-selection metric; no runtime ragdoll.',
                implemented=dict(animation_body_default=True,ragdoll_worlds=0,cloth_dynamics=False,
                                 unchanged_native_animation_bank=True,retargeted_pes_actions=bank['source_clips'],
                                 pes_runtime_candidates=bank['runtime_candidates'],pes_enabled_by_default=False,
                                 ground_bounce=.74,contact='Native planning and real weighted-skin contact; no forced attachment.'),
                binaries=dict(native_sha256=native,windows_unstripped_sha256=digest(a.windows)),
                unit_validation=dict(ctest_suites=int(total[1]),ctest_result='passed',python_tests=int(py_count[1]),
                                     python_passed=int(py_count[1])-skipped,python_skipped=skipped),
                rendered=classic['scenarios'],rendered_checks=sum(r['checks']for r in classic['scenarios']),
                pes_action_bank=dict(result='passed',checks=action['checks'],views=2,executable_sha256=native,
                                     bank_catalog_sha256=bank_hash,actual_contact_sources=len(action['actual_contact_sources']),
                                     report='docs/pes2017-action-bank-validation.json'),
                reception_turns={k:v for k,v in turns.items()if k!='views'},
                pes_match=dict(result='passed',executable_sha256=native,bank_catalog_sha256=bank_hash,
                               checks=match_public['checks'],stages=[dict(scenario=r['scenario'],result=r['result'],checks=len(r['checks']))for r in match_public['stages']],
                               report='docs/pes2017-match-validation.json'),
                learned_selection=dict(report='docs/pes2017-pose-metric-validation.json',task=metric['task'],
                                       heldout_accuracy=metric['test_pair_accuracy']['learned'],generative_motion=False),
                limitations=dict(windows_gui_executed=False,original_pes_gameplay_integrated=False,
                                 all_possible_ball_arrivals_proven=False,all_sources_contact_exercised=False,
                                 excluded_source_records=2956-bank['source_clips']),research='docs/BANCO-ANIMACOES-PES2017.md')
    write('pes2017-action-bank-validation.json',action);write('pes2017-reception-turn-validation.json',turns)
    write('pes2017-match-validation.json',match_public);write('animation-gameplay-validation.json',report)
    print(json.dumps(dict(result='passed',sources=bank['source_clips'],
                          graphical_checks=report['rendered_checks']+action['checks']+turns['checks']+match_public['checks'])))

if __name__=='__main__':main()
