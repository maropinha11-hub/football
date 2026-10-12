#!/usr/bin/env python3
"""Snap 180-degree dribble turns, including running and held-back repetitions."""
import argparse
import json
import math
from pathlib import Path
import re
from native_training_harness import NativeTraining

parser=argparse.ArgumentParser()
parser.add_argument('--build',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--analog-pad',action='store_true',help='Use a real SDL virtual Xbox controller with stick variation')
parser.add_argument('--display',default=':94',help='Separate X11 display for a concurrent rendered run')
args=parser.parse_args();checks=[];cases=[]
report={'result':'running','checks':checks,'cases':cases,'input':'real SDL virtual Xbox pad' if args.analog_pad else 'real SDL keyboard events','gameplay':'native'}
def check(name,condition,evidence):
    checks.append({'check':name,'result':'passed'if condition else'failed','evidence':evidence})
    print(('PASS 'if condition else'FAIL ')+name+': '+str(evidence),flush=True)
try:
    with NativeTraining(args.build,args.output,display=args.display,analog_pad=args.analog_pad)as game:
        check('dominant mode starts enabled',game.frames()[-1]['dominant_control']==1,game.frames()[-1]['dominant_control'])
        if args.analog_pad:
            game.pad(0,0,buttons=1<<7) # SDL left stick click = Xbox L3
            game.wait(lambda:game.frames()[-1]['dominant_control']==0)
            held=game.advance(700)
            check('held L3 toggles once',all(f['dominant_control']==0 for f in held),len(held))
            game.pad(0,0);game.advance(200)
            game.pad(0,0,buttons=1<<7)
            game.wait(lambda:game.frames()[-1]['dominant_control']==1)
            game.pad(0,0);game.advance(200)
            check('second L3 restores dominant mode',game.frames()[-1]['dominant_control']==1,game.frames()[-1]['dominant_control'])
        foot_usage={}
        for mode in ('dominant','normal'):
            if mode=='normal':
                game.keys(['g'],True)
                game.wait(lambda:game.frames()[-1]['dominant_control']==0)
                game.keys(['g'],False)
                check('G switches to normal mode',game.frames()[-1]['dominant_control']==0,game.frames()[-1]['dominant_control'])
            game.reset();foot_start=game.frames()[-1]['t']
            if args.analog_pad:game.pad(0,-1)
            else:game.keys(['w'],True)
            running=game.advance(6500)
            if args.analog_pad:game.pad(0,0)
            else:game.keys(['w'],False)
            feet=[part for t,part,kind in re.findall(r'TRAINING_ACTION_TOUCH t=(\d+) part=(\w+) function=(\d+)',game.log.read_text())
                  if int(t)>foot_start and int(kind)==2 and part in ('left_foot','right_foot')]
            foot_usage[mode]={'right':feet.count('right_foot'),'left':feet.count('left_foot'),'total':len(feet)}
            check(mode+' straight run stays controlled',bool(feet)and all(f['with_ball']for f in running),foot_usage[mode])
            game.reset();origin=game.frames()[-1]
            if args.analog_pad:game.pad(0,1)
            else:game.keys(['s'],True)
            pivot=game.advance(500)
            displacement=[pivot[-1]['player'][i]-origin['player'][i]for i in range(2)]
            ahead=displacement[0]*math.cos(origin['yaw'])+displacement[1]*math.sin(origin['yaw'])
            sideways=displacement[0]*math.sin(origin['yaw'])-displacement[1]*math.cos(origin['yaw'])
            ball_delta=[pivot[-1]['ball'][i]-origin['ball'][i]for i in range(2)]
            pull=ball_delta[0]*math.cos(origin['yaw'])+ball_delta[1]*math.sin(origin['yaw'])
            turn=abs(math.atan2(math.sin(pivot[-1]['player_yaw']-origin['player_yaw']),
                                math.cos(pivot[-1]['player_yaw']-origin['player_yaw'])))
            check(mode+' stationary reversal starts with pull and pivot',pull<-.15 and turn>.5,
                  {'first_500ms_ball_forward':pull,'body_turn':turn,'player_forward':ahead})
            # Let the planted foot finish its pivot instead of requiring the
            # pelvis to slide backwards before the ball has cleared it.
            pivot+=game.advance(300)
            displacement=[pivot[-1]['player'][i]-origin['player'][i]for i in range(2)]
            ahead=displacement[0]*math.cos(origin['yaw'])+displacement[1]*math.sin(origin['yaw'])
            sideways=displacement[0]*math.sin(origin['yaw'])-displacement[1]*math.cos(origin['yaw'])
            check(mode+' stationary reversal moves behind after pivot',ahead<-.15 and abs(sideways)<abs(ahead),
                  {'first_800ms_forward':ahead,'first_800ms_sideways':sideways})
            check(mode+' stationary reversal keeps ball',all(f['with_ball']for f in pivot),len(pivot))
            for label,modifiers,run_time,back_time in (
                    ('walking',[],1500,2200),('sprinting',['Shift_L'],2200,2500),
                    ('close control',['space'],1800,2500),('sprint long touch',['Shift_L','space'],2200,3200),
                    ('held back repeats',[],1500,6500)):
                game.reset()
                if args.analog_pad:game.pad(0,-1,sprint='Shift_L'in modifiers,close='space'in modifiers)
                else:game.keys(['w',*modifiers],True)
                game.advance(run_time)
                origin=game.frames()[-1];start=origin['t'];forward=(math.cos(origin['yaw']),math.sin(origin['yaw']))
                # Deliver the direction change together, without a neutral-stick gap.
                if args.analog_pad:
                    for i in range(back_time//100):
                        # Small lateral changes during a held backward stick,
                        # including crossing its +pi/-pi angular seam.
                        game.pad(.14 if i%2 else-.14,1,close='space'in modifiers)
                        game.advance(100)
                    samples=[f for f in game.frames()if f['t']>start]
                else:
                    game.keys(['s'],True);game.keys(['w'],False)
                    if 'Shift_L'in modifiers:game.keys(['Shift_L'],False)
                    samples=game.advance(back_time)
                distance=[math.dist(f['player'],f['ball'])for f in samples]
                delta=[samples[-1]['ball'][i]-origin['ball'][i]for i in range(2)]
                reversed_distance=sum(delta[i]*forward[i]for i in range(2))
                minimum_travel=min(sum((f['ball'][i]-origin['ball'][i])*forward[i]for i in range(2))for f in samples)
                touches=[(int(t),part,int(kind))for t,part,kind in re.findall(
                    r'TRAINING_ACTION_TOUCH t=(\d+) part=(\w+) function=(\d+)',game.log.read_text())if int(t)>start]
                native_control=[v for v in touches if v[2]in (2,3)and v[1]in ('left_foot','right_foot')]
                evidence={'right_foot_touches':sum(t[1]=='right_foot'for t in native_control),'max_ball_distance':max(distance),'final_ball_distance':distance[-1],
                          'controlled_samples':sum(f['with_ball']for f in samples),'samples':len(samples),
                          'ball_travel_in_old_front':reversed_distance,'real_control_touches':len(native_control),
                          'minimum_ball_travel_in_old_front':minimum_travel,
                          'initial_player_speed':origin['speed'],'initial_ball_speed':origin['ball_speed']}
                cases.append({'mode':mode,'case':label,'evidence':evidence,'origin':origin,'frames':samples})
                bound=3.5 if label=='sprint long touch'else 2.3
                check(mode+' / '+label+' keeps ball in reach',max(distance)<bound,evidence)
                check(mode+' / '+label+' retains dribble mode',all(f['with_ball']for f in samples),evidence)
                check(mode+' / '+label+' pulls ball with real foot events',bool(native_control)and
                      (minimum_travel<-.3 or label in ('held back repeats','sprinting','sprint long touch')),evidence)
                if label=='held back repeats':
                    repeats=[int(t)for t in re.findall(r'TRAINING_STEER_REPEAT t=(\d+)',game.log.read_text())if int(t)>start]
                    check(mode+' held back repeats after completing real turn',bool(repeats),len(repeats))
                if args.analog_pad:game.pad(0,0)
                else:game.keys(['s',*modifiers],False)
                # Following the new front must not need a reset or returning the ball.
                if args.analog_pad:game.pad(0,-1)
                else:game.keys(['w'],True)
                continued=game.advance(1200)
                if args.analog_pad:game.pad(0,0)
                else:game.keys(['w'],False)
                check(mode+' / '+label+' continues without losing ball',all(f['with_ball']for f in continued)and
                      math.dist(continued[-1]['player'],continued[-1]['ball'])<1.2,
                      {'distance':math.dist(continued[-1]['player'],continued[-1]['ball']),'controlled':sum(f['with_ball']for f in continued)})
        report['foot_usage']=foot_usage
        fallback=sum(c['evidence']['real_control_touches']-c['evidence']['right_foot_touches']for c in cases if c['mode']=='dominant')
        check('dominant preference retains weak-foot fallback',fallback>0,fallback)
        turn_ratios={}
        for mode in ('dominant','normal'):
            turning=[c['evidence']for c in cases if c['mode']==mode]
            turn_ratios[mode]=sum(c['right_foot_touches']for c in turning)/max(1,sum(c['real_control_touches']for c in turning))
        report['turn_foot_ratios']=turn_ratios
        check('dominant foot is preferred during turns too',turn_ratios['dominant']>.6 and
              turn_ratios['dominant']>turn_ratios['normal']+.1,turn_ratios)
        right_ratio={mode:usage['right']/max(1,usage['total'])for mode,usage in foot_usage.items()}
        check('dominant foot remains preferred',right_ratio['dominant']>.6,right_ratio)
        # The native solver may also choose the right foot in a straight run.
        # Verify the toggle's actual rolling interval instead of forcing the
        # normal solver to use a less suitable left-footed animation.
        check('dominant toggle changes native dribble cadence',foot_usage['dominant']['total']<foot_usage['normal']['total'],foot_usage)
        log=game.log.read_text()
        contacts={(int(t),part)for t,part,kind in re.findall(
            r'TRAINING_ACTION_TOUCH t=(\d+) part=(\w+) function=(\d+)',log)if int(kind)in (2,3)}
        pulls=re.findall(r'TRAINING_PULLBACK t=(\d+) part=(\w+) before=\[([^]]+)\] after=\[([^]]+)\] direction=\[([^]]+)\]',log)
        aligned=[]
        for t,part,before,after,direction in pulls:
            velocity=list(map(float,after.split(',')));target=list(map(float,direction.split(',')))
            dot=sum(a*b for a,b in zip(velocity,target))/max(.0001,math.hypot(*velocity)*math.hypot(*target))
            aligned.append(dot)
        check('pullback correction occurs only at accepted foot events',bool(pulls)and
              all((int(t),part)in contacts and part in ('left_foot','right_foot')for t,part,*_ in pulls),len(pulls))
        check('final pullback impulse follows collision-safe route',bool(aligned)and min(aligned)>.999,min(aligned)if aligned else None)
        check('native launcher does not load PES study bank','PES3_BANK' not in log,'explicit study flag omitted')
        report['pullback_events']=len(pulls)
        game.keys(['Escape'],True);game.game.wait(timeout=15)
        check('clean exit',game.game.returncode==0,game.game.returncode)
    report['result']='passed'if all(c['result']=='passed'for c in checks)else'failed'
except BaseException as error:
    report['result']='failed';report['error']=str(error);raise
finally:
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed':raise SystemExit(1)
