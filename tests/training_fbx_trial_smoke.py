#!/usr/bin/env python3
"""Rendered FBX A/B trial through real Xbox and keyboard input."""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
from native_training_harness import NativeTraining

parser=argparse.ArgumentParser()
parser.add_argument('--build',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--display',default=':94')
args=parser.parse_args()
report={'result':'running','checks':[]}
def check(name,ok,evidence):
    report['checks'].append({'check':name,'result':'passed'if ok else'failed','evidence':evidence})
    print(('PASS 'if ok else'FAIL ')+name+': '+str(evidence),flush=True)
def poses(text):
    result=[]
    for line in text.splitlines():
        if line.startswith('TRAINING_FBX_POSE '):
            result.append({key:float(value)for key,value in re.findall(r'(\w+)=(-?[\d.]+)',line)})
    return result
def retain(name,samples):
    distances=[math.dist(f['player'][:2],f['ball'][:2])for f in samples]
    check(name,all(f['with_ball']for f in samples)and max(distances)<2.3 and distances[-1]<1.2,
          {'maximum':max(distances),'ending':distances[-1],'samples':len(samples)})
try:
    with NativeTraining(args.build,args.output/'game',display=args.display,analog_pad=True,camera=1)as game:
        check('converted FBX is loaded','TRAINING_FBX_LOADED frames=71'in game.log.read_text(),'71 native pose samples')
        game.reset();game.pad(1,0);original=game.advance(3000)
        retain('original forward dribble',original)
        check('original is the default','TRAINING_FBX_POSE'not in game.log.read_text(),'No imported pose before toggle')
        def screenshot(name):
            path=args.output/name
            subprocess.run(['ffmpeg','-nostdin','-loglevel','error','-y','-f','x11grab','-video_size','960x540',
                            '-i',game.env['DISPLAY'],'-frames:v','1',str(path)],env=game.env,check=True)
        screenshot('original.png')
        old=game.log.read_text().count('TRAINING_FBX_TOGGLE')
        game.pad(1,0,buttons=1<<7);game.advance(500);game.pad(1,0)
        game.wait(lambda:game.log.read_text().count('TRAINING_FBX_TOGGLE')>old)
        check('held L3 toggles once',game.log.read_text().count('TRAINING_FBX_TOGGLE')==old+1,'Held 500 ms')
        start=len(game.log.read_text());new=game.advance(3500);active=poses(game.log.read_text()[start:])
        skin=[{key:float(value) for key,value in re.findall(r'(\w+)=(-?[\d.]+)',line)}
              for line in game.log.read_text()[start:].splitlines() if line.startswith('TRAINING_FBX_SKIN ')]
        retain('new forward dribble retains native ball control',new)
        check('new pose visibly replaces the native gait',bool(active)and max(p['blend']for p in active)>.99 and
              max(p['change']for p in active)>.2,{'pose_samples':len(active),'maximum_change':max((p['change']for p in active),default=0)})
        check('pose cycle advances',bool(active)and max(p['phase']for p in active)-min(p['phase']for p in active)>50,
              {'phase_range':[min((p['phase']for p in active),default=0),max((p['phase']for p in active),default=0)]})
        check('native joint lengths are preserved',bool(active)and max(p['length_error']for p in active)<.0001,
              max((p['length_error']for p in active),default=0))
        check('native shoe volumes stay above the pitch',bool(active)and min(p['sole_z']for p in active)>=.0079,
              min((p['sole_z']for p in active),default=0))
        check('body proportions remain bounded',bool(active)and max(p['radius']for p in active)<1.2,
              max((p['radius']for p in active),default=0))
        check('rendered mesh stays finite and preserves rigid lengths',bool(skin)and
              all(s['vertices']>=500 and s['invalid']==0 and s['rigid_error']<.0002 for s in skin),
              {'samples':len(skin),'unique_vertices':sorted(set(s['vertices']for s in skin)),
               'maximum_error':max((s['rigid_error']for s in skin),default=0)})
        check('rendered shoe vertices stay above the pitch',bool(skin)and min(s['foot_min_z']for s in skin)>=-.02,
              min((s['foot_min_z']for s in skin),default=0))
        check('native contacts retain their original lower-body pose',any(p['blend']>.99 and p['legs']<.001 for p in active),
              sum(p['legs']<.001 for p in active))
        for i in range(4):screenshot('new-'+str(i)+'.png');game.advance(200)
        game.pad(1,0,sprint=True);sprint=game.advance(1200);retain('RB remains native',sprint)
        start=len(game.log.read_text());game.advance(500)
        check('FBX yields to native sprint',not poses(game.log.read_text()[start:]),'No imported pose after transition')
        game.pad(1,0);retain('release RB retains ball',game.advance(1800))
        game.keys(['Tab'],True);game.keys(['Tab'],False)
        game.wait(lambda:game.frames()[-1]['camera']==2)
        game.pad(1,0);turn=game.advance(1400);retain('FP turn uses approved gameplay',turn)
        start=len(game.log.read_text());game.advance(300)
        check('FBX yields to the native FP turn',not poses(game.log.read_text()[start:]),'Side stick is not the forward trial')
        game.pad(0,-1);game.advance(1600)
        start=len(game.log.read_text());game.advance(500)
        check('FBX resumes in the new front',bool(poses(game.log.read_text()[start:])), 'Forward input after turning')
        # T must return to the untouched native pose without restarting.
        game.keys(['t'],True);game.keys(['t'],False);game.advance(500)
        start=len(game.log.read_text());game.advance(400)
        check('T switches back to original',not poses(game.log.read_text()[start:])and
              'TRAINING_FBX_TOGGLE enabled=0'in game.log.read_text(),'No imported pose after blend-out')
        game.keys(['t'],True);game.keys(['t'],False);game.advance(500)
        game.pad(0,-1,buttons=1<<0);game.advance(250);game.pad(0,-1)
        passing=game.advance(1200)
        check('A still selects a native pass',any(f['function']==4 for f in passing)and max(f['ball_speed']for f in passing)>5,
              {'functions':sorted(set(f['function']for f in passing))})
        start=len(game.log.read_text());game.pad(0,0);game.advance(500)
        check('FBX stops off the ball',not poses(game.log.read_text()[start:]),'No dribble trial during pass/off-ball movement')
        check('no PES pose is involved','PES3_BODY_APPLY'not in game.log.read_text(),'User FBX, native rig and native ball events')
        game.keys(['Escape'],True);game.game.wait(timeout=15)
        check('clean exit',game.game.returncode==0,game.game.returncode)
    report['result']='passed'if all(c['result']=='passed'for c in report['checks'])else'failed'
except BaseException as error:
    report['result']='failed';report['error']=str(error);raise
finally:
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed':raise SystemExit(1)
