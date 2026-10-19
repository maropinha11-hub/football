#!/usr/bin/env python3
"""Measure the rendered eye/head during turns and kicks, rather than simulation poses alone."""
import argparse, hashlib, json, math, re, subprocess
from pathlib import Path
from native_training_harness import NativeTraining

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--build', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--display', default=':271')
a = p.parse_args()
r = dict(result='running', checks=[], stages=[], executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name, ok, evidence):
    row = dict(check=name, result='passed' if ok else 'failed', evidence=evidence)
    r['checks'].append(row); print(json.dumps(row), flush=True)
def records(text, prefix):
    return [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines() if line.startswith(prefix+' ')]
try:
    with NativeTraining(a.build, a.output/'game', display=a.display, analog_pad=True, camera=2,
            config_overrides=dict(context_x=640, context_y=360, training_physical_rig='true',
                training_physical_lab='true', training_motion_diagnostics='true', simulation_seed=7)) as g:
        def stage(name, duration):
            start = len(g.read_log()); g.advance(duration)
            rows = records(g.read_log()[start:], 'FIRSTPERSON_FRAME')
            check(name+' keeps the lens attached to the rendered head', len(rows)>=max(3,duration//160) and
                  max(float(x['anchor_error']) for x in rows)<.025,
                  dict(samples=len(rows), maximum_eye_displacement=max((float(x['anchor_error']) for x in rows), default=999)))
            check(name+' looks in the rendered head direction', bool(rows) and
                  min(float(x['alignment']) for x in rows)>.999,
                  dict(minimum_alignment=min((float(x['alignment']) for x in rows), default=-1)))
            positions = [json.loads(x['eye']) for x in rows]
            check(name+' keeps finite eye positions', bool(positions) and
                  all(math.isfinite(v) for x in positions for v in x), dict(samples=len(positions)))
            steps = [math.dist(x,y) for x,y in zip(positions,positions[1:])]
            r['stages'].append(dict(name=name, samples=len(rows), maximum_eye_step=max(steps,default=0)))
            subprocess.run(['import','-window',g.window,str(a.output/(name+'.png'))],env=g.env,check=True)
        g.reset();g.pad(0,-1);stage('dribble',1600)
        g.pad(1,0);stage('turn_right',1600)
        g.pad(0,1);stage('reverse',1800)
        g.pad(0,0);g.keys(['Right','Down'],True);stage('head_look',500)
        g.keys(['Right','Down'],False);stage('head_return',900)
        g.reset();g.pad(0,-1,sprint=True);g.advance(900)
        g.pad(1,0,sprint=True,buttons=1<<2);g.advance(240)
        g.pad(1,0,sprint=True);stage('running_cross',1100)
        g.pad(0,0);g.keys(['F9'],True);g.keys(['F9'],False);stage('fall',1600)
        stage('recovery',5000)
        eyes = records(g.read_log(), 'PHYSICAL_EYE')
        check('the first-person lens stays outside the rendered torso, including recovery',
              bool(eyes) and all(float(x['clearance'])>=float(x['required'])-.0005 for x in eyes),
              dict(samples=len(eyes), minimum_clearance=min((float(x['clearance']) for x in eyes),default=0)))
        g.keys(['Escape'],True);g.game.wait(timeout=15)
        check('clean exit',g.game.returncode==0,g.game.returncode)
    r['result']='passed' if all(x['result']=='passed' for x in r['checks']) else 'failed'
except BaseException as e:
    r.update(result='failed',error=str(e));raise
finally:
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
