#!/usr/bin/env python3
"""Rendered regressions for running crosses, charged shots and chest recovery."""
import argparse
import json
import math
import re
from pathlib import Path
from native_training_harness import NativeTraining

parser=argparse.ArgumentParser()
parser.add_argument('--build',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--display',default=':99')
args=parser.parse_args()
report={'result':'running','checks':[]}

def rows(text,prefix):
    return [{k:float(v)for k,v in re.findall(r'(\w+)=(-?[\d.]+)',line)}
            for line in text.splitlines()if line.startswith(prefix+' ')]

def check(name,condition,evidence):
    row={'check':name,'result':'passed'if condition else'failed','evidence':evidence}
    report['checks'].append(row);print(json.dumps(row),flush=True)

try:
    with NativeTraining(args.build,args.output/'game',display=args.display,analog_pad=True,camera=2,
            config_overrides={'context_x':'480','context_y':'270'})as game:
        game.reset();game.pad(0,-1);game.advance(1500)
        start=len(game.log.read_text());walk=game.advance(4200)
        segment=game.log.read_text()[start:];touches=rows(segment,'TRAINING_FBX_TOUCH')
        check('normal movement is slower while the simulation remains real time',
              3.4<sum(f['speed']for f in walk)/len(walk)<3.8,
              {'mean_speed_mps':sum(f['speed']for f in walk)/len(walk)})
        check('right-foot dribbling has separated physical contacts',len(touches)>=5 and
              all(t['side']==1 and -.0015<=t['gap']<=.0006 for t in touches)and
              all(b['t']-a['t']>=450 for a,b in zip(touches,touches[1:])),touches)
        game.keys(['Right','Up'],True);looking=game.advance(250);game.keys(['Right','Up'],False)
        head=rows(game.log.read_text()[start:],'TRAINING_HEAD_POSE')
        check('the rendered head follows independent camera yaw and pitch',bool(head)and
              max(abs(h['yaw'])for h in head)>.4 and max(h['pitch']for h in head)>.3 and
              max(h['alignment']for h in head)>.999,head[-8:])

        for duration in [300,900,1600,2200]:
            game.reset();game.pad(0,-1,sprint=True);game.advance(duration)
            start=len(game.log.read_text());game.pad(0,-1,sprint=True,buttons=2)
            game.advance(300);game.pad(0,-1,sprint=True);flight=game.advance(1700)
            segment=game.log.read_text()[start:]
            contact=re.findall(r'TRAINING_ACTION_TOUCH t=(\d+) part=(\w+) function=(\d+)',segment)
            check('running B cross after '+str(duration)+' ms is a real high pass',
                  any(int(kind)==6 for _,_,kind in contact)and not any(f['function']==13 for f in flight),
                  {'contacts':contact,'functions':sorted(set(f['function']for f in flight)),
                   'peak_height_m':max(f['ball'][2]for f in flight)})

        trajectories={}
        for name,hold,chip in [('quick',250,False),('full',600,False),('lob',600,True)]:
            game.reset();start=len(game.log.read_text())
            game.pad(0,0,buttons=4|((1<<9)if chip else 0));charging=game.advance(hold)
            game.pad(0,0);flight=game.advance(2800);segment=game.log.read_text()[start:]
            shot=rows(segment,'TRAINING_SHOT');frames=charging+flight
            trajectories[name]={'peak_height_m':max(f['ball'][2]for f in frames),
                                'peak_speed_mps':max(f['ball_speed']for f in frames),'shot':shot}
            check(name+' shot applies one physical kick',len(shot)==1,
                  trajectories[name])
        check('holding X reaches full power and increases height',
              bool(trajectories['full']['shot'])and trajectories['full']['shot'][0]['charge']==1 and
              trajectories['full']['peak_height_m']>trajectories['quick']['peak_height_m']+.8,
              trajectories)
        check('LB plus X delivers a slower arcing lob',
              bool(trajectories['lob']['shot'])and trajectories['lob']['shot'][0]['chip']==1 and
              trajectories['lob']['peak_height_m']>trajectories['full']['peak_height_m']and
              trajectories['lob']['peak_speed_mps']<trajectories['full']['peak_speed_mps'],trajectories)

        game.reset();start=len(game.log.read_text());origin=game.frames()[-1]['player']
        game.keys(['F5'],True);game.keys(['F5'],False);after=game.advance(3300)
        segment=game.log.read_text()[start:];states=rows(segment,'TRAINING_CHEST_STATE')
        contact=rows(segment,'TRAINING_CHEST_TOUCH')
        recovery=[f for f in after if contact and states and contact[0]['t']<f['t']<=states[-1]['t']]
        distance=math.dist(origin[:2],recovery[-1]['player'][:2])if recovery else 0
        check('chest recovery moves the actual player with the authored steps',len(contact)==1 and
              bool(states)and max(s['root_motion']for s in states)>.6 and .6<distance<1.1,
              {'contacts':contact,'maximum_root_motion_m':max((s['root_motion']for s in states),default=None),
               'actual_player_displacement_m':distance})
        game.reset();start=len(game.log.read_text());game.keys(['F5'],True)
        delivery=rows(game.log.read_text()[start:],'TRAINING_DELIVERY')[-1]['t']
        game.wait(lambda:game.frames()[-1]['t']>=delivery+600)
        game.pad(0,-1);game.keys(['F5'],False);after=game.advance(800);game.pad(0,0)
        segment=game.log.read_text()[start:];contact=rows(segment,'TRAINING_CHEST_TOUCH')
        check('forward adjustment while awaiting the ball retains a chest contact',len(contact)==1,
              {'contacts':contact,'speed_after_mps':after[-1]['speed']})
        game.reset();start=len(game.log.read_text());game.keys(['F6'],True);game.keys(['F6'],False)
        game.pad(0,0,buttons=1);game.advance(300);game.pad(0,0);game.advance(2000)
        segment=game.log.read_text()[start:]
        check('preparing a first-time header keeps the native head action',
              'TRAINING_CHEST_TOUCH'not in segment and 'part=head function=4'in segment,
              {'chest_contacts':segment.count('TRAINING_CHEST_TOUCH'),
               'body_contacts':rows(segment,'TRAINING_BODY_TOUCH')})
        game.keys(['Escape'],True);game.game.wait(timeout=15)
        check('clean exit',game.game.returncode==0,game.game.returncode)
    report['result']='passed'if all(c['result']=='passed'for c in report['checks'])else'failed'
except BaseException as error:
    report['result']='failed';report['error']=str(error);raise
finally:
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed':raise SystemExit(1)
