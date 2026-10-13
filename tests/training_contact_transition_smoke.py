#!/usr/bin/env python3
"""Use a small rendered viewport to observe the short overlapping contact/fade window."""
import argparse,json,re
from pathlib import Path
from native_training_harness import NativeTraining
parser=argparse.ArgumentParser()
parser.add_argument('--build',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--display',default=':96')
args=parser.parse_args();report={'result':'running','checks':[]}
try:
    with NativeTraining(args.build,args.output/'game',display=args.display,analog_pad=True,camera=2,
            config_overrides={'context_x':'320','context_y':'180'})as game:
        for stick,duration in [((1,0),300),((0,1),300),((-1,0),650),((0,0),250)]:
            game.reset();game.pad(0,-1);game.advance(1500)
            game.pad(*stick);game.advance(duration);game.pad(0,-1);game.advance(2800)
        poses=[{k:float(v)for k,v in re.findall(r'(\w+)=(-?[\d.]+)',line)}
            for line in game.log.read_text().splitlines()if line.startswith('TRAINING_NATIVE_POSE ')]
        overlaps=[p for p in poses if p['dribble_remaining']>.01 and p['blend']>.999]
        passed=bool(overlaps)and min(p['gap']for p in overlaps)>-.01
        report['checks'].append({'check':'visible physical contact pose overrides the overlapping dribble',
            'result':'passed'if passed else'failed','evidence':{'overlap_samples':len(overlaps),
                'minimum_rendered_gap_m':min((p['gap']for p in overlaps),default=None)}})
        print(report['checks'][-1],flush=True)
        for name,ok,evidence in [
            ('both rendered shoes stay outside the moving sphere',bool(poses)and
             min(min(p['gap_left'],p['gap_right'])for p in poses)>=-.001,
             {'samples':len(poses),'minimum_gap_m':min((min(p['gap_left'],p['gap_right'])for p in poses),default=None)}),
            ('yielding legs preserve their segment lengths',bool(poses)and
             max(p['length_error']for p in poses)<.0001,
             {'maximum_length_error_m':max((p['length_error']for p in poses),default=None)}),
            ('sub-frame corrections remain within the local reach limit',bool(poses)and
             0<max(p['foot_shift']for p in poses)<=.1801,
             {'maximum_ankle_shift_m':max((p['foot_shift']for p in poses),default=None)})]:
            report['checks'].append({'check':name,'result':'passed'if ok else'failed','evidence':evidence})
            print(report['checks'][-1],flush=True)
        game.keys(['Escape'],True);game.game.wait(timeout=15)
        report['checks'].append({'check':'clean exit','result':'passed'if game.game.returncode==0 else'failed','evidence':game.game.returncode})
    report['result']='passed'if all(c['result']=='passed'for c in report['checks'])else'failed'
except BaseException as error:
    report['result']='failed';report['error']=str(error);raise
finally:
    args.output.mkdir(parents=True,exist_ok=True);(args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed':raise SystemExit(1)
