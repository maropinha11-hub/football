#!/usr/bin/env python3
"""Compare a free airborne ball's rebound with two turf restitution values."""
import argparse,json,math
from pathlib import Path
from native_training_harness import NativeTraining
parser=argparse.ArgumentParser()
parser.add_argument('--build',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--display',default=':97')
args=parser.parse_args();report={'result':'running','checks':[],'trajectories':{}}
def check(name,ok,evidence):
    report['checks'].append({'check':name,'result':'passed'if ok else'failed','evidence':evidence})
    print(('PASS 'if ok else'FAIL ')+name+': '+str(evidence),flush=True)
try:
    peaks=[]
    for bounce in (.62,.70):
        with NativeTraining(args.build,args.output/str(bounce),display=args.display,analog_pad=True,
                config_overrides={'training_ground_bounce':str(bounce)})as game:
            game.reset();start=len(game.log.read_text())
            game.keys(['F6'],True);game.keys(['F6'],False)
            game.pad(1,0,sprint=True);frames=game.advance(1200)
            game.pad(0,0);frames+=game.advance(3000)
            lows=[i for i,f in enumerate(frames)if f['ball'][2]<.30]
            landing=lows[0]if lows else len(frames)
            peak=max((f['ball'][2]for f in frames[landing:landing+15]),default=0);peaks.append(peak)
            check('free ball reaches turf with bounce '+str(bounce),bool(lows),{'first_low_frame':landing})
            check('bounce '+str(bounce)+' is not affected by player contacts','TRAINING_ACTION_TOUCH'not in game.log.read_text()[start:]
                  and 'TRAINING_CHEST_TOUCH'not in game.log.read_text()[start:],'Player moves away before arrival')
            report['trajectories'][str(bounce)]={'rebound_peak':peak,'frames':frames}
            game.keys(['Escape'],True);game.game.wait(timeout=15)
    check('new turf has a higher rebound without changing gravity',peaks[1]>peaks[0]*1.15 and peaks[1]<3,
          {'old_peak':peaks[0],'new_peak':peaks[1]})
    report['result']='passed'if all(c['result']=='passed'for c in report['checks'])else'failed'
except BaseException as error:
    report['result']='failed';report['error']=str(error);raise
finally:
    args.output.mkdir(parents=True,exist_ok=True);(args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed':raise SystemExit(1)
