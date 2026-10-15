#!/usr/bin/env python3
"""Rendered Xbox regressions: added poses must leave native ball actions responsive."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from native_training_harness import NativeTraining

p=argparse.ArgumentParser()
p.add_argument('--build',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':132')
p.add_argument('--native-only',action='store_true')
a=p.parse_args()
report={'result':'running','fbx_visual':not a.native_only,'checks':[],'cases':[]}
def check(name,ok,evidence):
    row={'check':name,'result':'passed'if ok else'failed','evidence':evidence}
    report['checks'].append(row);print(json.dumps(row),flush=True)
def events(text,prefix):
    return [{k:float(v)for k,v in re.findall(r'(\w+)=(-?[\d.]+)',line)}
            for line in text.splitlines()if line.startswith(prefix+' ')]
def retained(name,frames):
    distances=[math.dist(f['player'][:2],f['ball'][:2])for f in frames]
    evidence={'maximum_distance_m':max(distances),'ending_distance_m':distances[-1],
              'ending_speed_mps':frames[-1]['speed'],'controlled_samples':sum(f['with_ball']for f in frames),'samples':len(frames)}
    check(name,max(distances)<2.3 and distances[-1]<1.4 and all(f['with_ball']for f in frames),evidence)
    report['cases'].append({'case':name,'frames':frames})
try:
    report['executable_sha256']=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest()
    with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,
            config_overrides={'context_x':'320','context_y':'180','training_fbx_dribble':'false'if a.native_only else'true'})as g:
        check('standing chest is added without removing native receptions',
              'TRAINING_CHEST_CANDIDATE'in g.log.read_text()and'native_preserved=1'in g.log.read_text(),
              [l for l in g.log.read_text().splitlines()if 'CHEST_CANDIDATE'in l])
        for pause in (0,400,1400):
            g.reset()
            if pause:g.advance(pause)
            origin=g.frames()[-1];start=len(g.log.read_text());g.pad(0,-1)
            frames=g.advance(2300);s=g.log.read_text()[start:]
            retained('start from resting ball after '+str(pause)+' ms',frames)
            check('resting start '+str(pause)+' responds and uses native touches',
                  math.dist(origin['player'][:2],frames[3]['player'][:2])>.08 and
                  math.dist(origin['player'][:2],frames[-1]['player'][:2])>3 and
                  bool(events(s,'TRAINING_ACTION_TOUCH')),
                  {'travel_m':math.dist(origin['player'][:2],frames[-1]['player'][:2]),'native_touches':events(s,'TRAINING_ACTION_TOUCH')})
        for name,stick,duration in [('right',(1,0),350),('reverse',(0,1),300),('long reverse',(0,1),650),('stop',(0,0),600)]:
            g.reset();g.pad(0,-1);g.advance(1300)
            g.pad(*stick);turn=g.advance(duration);g.pad(0,-1);resumed=g.advance(2000)
            retained(name+' then forward retains native ball control',turn+resumed)
            check(name+' resumes movement without ownership wait',resumed[-1]['speed']>2,
                  {'ending_speed_mps':resumed[-1]['speed']})
        g.reset();frames=[]
        for _ in range(3):
            g.pad(0,-1,sprint=True);frames+=g.advance(900)
            g.pad(0,-1);frames+=g.advance(1400)
        retained('three RB bursts and releases',frames)
        for name,button,kind in [('pass',1,4),('cross',2,6),('shot',4,8)]:
            g.reset();g.pad(0,-1,sprint=True);g.advance(1100);start=len(g.log.read_text())
            g.pad(0,-1,sprint=True,buttons=button);g.advance(300);g.pad(0,-1,sprint=True);frames=g.advance(2200)
            touches=[r for r in events(g.log.read_text()[start:],'TRAINING_ACTION_TOUCH')if r['function']==kind]
            check('running '+name+' touches ball once',len(touches)==1 and max(f['ball_speed']for f in frames)>5,
                  {'touches':touches,'peak_ball_speed_mps':max(f['ball_speed']for f in frames)})
        for delay in (0,200,500):
            g.reset();start=len(g.log.read_text());g.keys(['F5'],True);g.keys(['F5'],False)
            g.wait(lambda:any(r['function']==3 for r in events(g.log.read_text()[start:],'TRAINING_ACTION_TOUCH')))
            hits=events(g.log.read_text()[start:],'TRAINING_ACTION_TOUCH');touch=next(r for r in hits if r['function']==3)
            if delay:g.advance(delay)
            g.pad(0,-1)
            # Measure from the frame where SDL acknowledges this input, not
            # from an older 100 ms telemetry sample before the pad file write.
            g.wait(lambda:g.frames()[-1]['move_active']==1)
            origin=g.frames()[-1];frames=g.advance(2400)
            movement=[f for f in frames if f['t']<=origin['t']+500]
            check('chest layer with input after '+str(delay)+' ms allows immediate locomotion',
                  math.dist(origin['player'][:2],movement[-1]['player'][:2])>.12 and max(f['speed']for f in frames if f['t']>=frames[-1]['t']-500)>1,
                  {'touch':touch,'input_ack_t':origin['t'],'travel_in_500ms_m':math.dist(origin['player'][:2],movement[-1]['player'][:2]),'last_500ms_peak_speed_mps':max(f['speed']for f in frames if f['t']>=frames[-1]['t']-500),'ending_speed_mps':frames[-1]['speed']})
            retained('completed chest with input after '+str(delay)+' ms keeps the ball',frames)
        # Held lateral/back input turns relative to each new front. Judge
        # response and travelled path; a turn can naturally brake at the last sample.
        for name,stick in [('forward',(0,-1)),('backward',(0,1)),('lateral',(1,0))]:
            g.reset();start=len(g.log.read_text());g.keys(['F5'],True);g.keys(['F5'],False);g.advance(350)
            g.pad(*stick);frames=g.advance(1800)
            check('input during incoming chest ball: '+name+' moves freely under the upper layer',
                  max(f['speed']for f in frames[:6])>.5 and frames[-1]['function']!=3 and sum(math.dist(x['player'][:2],y['player'][:2])for x,y in zip(frames,frames[1:]))>.5,
                  {'ending_speed_mps':frames[-1]['speed'],'ending_function':frames[-1]['function'],'initial_peak_speed_mps':max(f['speed']for f in frames[:6]),'path_length_m':sum(math.dist(x['player'][:2],y['player'][:2])for x,y in zip(frames,frames[1:])),'touches':events(g.log.read_text()[start:],'TRAINING_ACTION_TOUCH'),
                   'body_contacts':events(g.log.read_text()[start:],'TRAINING_BODY_TOUCH')})
        log=g.log.read_text();poses=events(log,'TRAINING_NATIVE_DRIBBLE_POSE')
        if not a.native_only:
            check('additional chest clip is selected as a free upper-body layer',bool(events(log,'TRAINING_UPPER_START')),events(log,'TRAINING_NATIVE_START')[-12:])
        check('imported forward gait uses native animation selection and actions',
              (bool(poses)if not a.native_only else not poses)and
              'TRAINING_FBX_TOUCH'not in log and 'TRAINING_CHEST_START'not in log,
              {'rendered_imported_samples':len(poses),'native_contacts':len(events(log,'TRAINING_ACTION_TOUCH'))})
        g.keys(['Escape'],True);g.game.wait(timeout=15)
        check('clean exit',g.game.returncode==0,g.game.returncode)
    report['result']='passed'if all(r['result']=='passed'for r in report['checks'])else'failed'
except BaseException as error:
    report['result']='failed';report['error']=str(error);raise
finally:
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed':raise SystemExit(1)
