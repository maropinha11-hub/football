#!/usr/bin/env python3
"""Reproduce short turns followed by forward FBX dribbling with a rendered Xbox pad."""
import argparse
import json
import math
from pathlib import Path
import re
from native_training_harness import NativeTraining

parser=argparse.ArgumentParser()
parser.add_argument('--build',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--display',default=':95')
args=parser.parse_args()
report={'result':'running','checks':[]}

def check(name,ok,evidence):
    report['checks'].append({'check':name,'result':'passed' if ok else 'failed','evidence':evidence})
    print(('PASS ' if ok else 'FAIL ')+name+': '+str(evidence),flush=True)

try:
    with NativeTraining(args.build,args.output/'game',display=args.display,analog_pad=True,camera=2,
                        config_overrides={'training_fbx_dribble':'true'}) as game:
        for name,stick,duration in [
            ('short right',(1,0),300),('right',(1,0),700),
            ('short backward',(0,1),300),('backward',(0,1),700),
            ('left',(-1,0),650),('diagonal',(.707,-.707),500),
            ('stop',(0,0),250),('release RB',(0,-1),500)]:
            # Stay in midfield: field resets/net collisions cannot mask a miss.
            game.reset();game.pad(0,-1);game.advance(1500)
            game.pad(*stick,sprint=name=='release RB');game.advance(duration)
            start=len(game.log.read_text());game.pad(0,-1);forward=game.advance(2800)
            distances=[math.dist(f['player'][:2],f['ball'][:2]) for f in forward]
            segment=game.log.read_text()[start:]
            contacts=[{key:float(value) for key,value in re.findall(r'(\w+)=(-?[\d.]+)',line)}
                      for line in segment.splitlines() if line.startswith('TRAINING_FBX_TOUCH ')]
            check(name+' retains ball on resuming forward',all(f['with_ball'] for f in forward) and
                  max(distances)<2.3 and distances[-1]<1.2,
                  {'maximum_distance_m':max(distances),'ending_distance_m':distances[-1],
                   'lost_possession_frames':sum(not f['with_ball'] for f in forward)})
            check(name+' resumes visible-foot loop contacts',len(contacts)>=2 and
                  max(t['gap'] for t in contacts)<=.00051,
                  {'contacts':len(contacts),'maximum_surface_gap_m':max((t['gap'] for t in contacts),default=None),
                   'native_recovery_touches':segment.count('TRAINING_ACTION_TOUCH')})
        game.keys(['Escape'],True);game.game.wait(timeout=15)
        check('clean exit',game.game.returncode==0,game.game.returncode)
    report['result']='passed' if all(c['result']=='passed' for c in report['checks']) else 'failed'
except BaseException as error:
    report['result']='failed';report['error']=str(error);raise
finally:
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed':raise SystemExit(1)
