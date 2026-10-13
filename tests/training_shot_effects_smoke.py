#!/usr/bin/env python3
"""Check real strike offsets, spin variation and the resulting curved flight."""
import argparse,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
parser=argparse.ArgumentParser()
parser.add_argument('--build',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--display',default=':98')
args=parser.parse_args();report={'result':'running','checks':[]}
def check(name,condition,evidence):
    row={'check':name,'result':'passed'if condition else'failed','evidence':evidence}
    report['checks'].append(row);print(json.dumps(row),flush=True)
try:
    with NativeTraining(args.build,args.output/'game',display=args.display,analog_pad=True,camera=2,
            config_overrides={'context_x':'320','context_y':'180'})as game:
        spins=[]
        for name,stick in [('standing',(0,0)),('right approach',(.6,-.8)),('left approach',(-.6,-.8))]:
            game.reset();game.pad(*stick);game.advance(180)
            start=len(game.log.read_text());game.pad(*stick,buttons=4)
            charging=game.advance(600);game.pad(0,0);flight=game.advance(1600)
            lines=[l for l in game.log.read_text()[start:].splitlines()if l.startswith('TRAINING_SHOT ')]
            check(name+' applies a single physical shot',len(lines)==1,lines)
            if not lines:continue
            line=lines[0];t=float(re.search(r' t=([\d.]+)',line)[1])
            spin=list(map(float,re.search(r'spin=\[([^]]+)\]',line)[1].split(',')))
            lever=list(map(float,re.search(r'lever=\[([^]]+)\]',line)[1].split(',')))
            spins.append(spin)
            check(name+' measures the contact on the ball surface',
                  abs(math.sqrt(sum(v*v for v in lever))-.1105)<.003,
                  {'lever_m':lever,'angular_velocity_rad_s':spin})
            samples=[f for f in charging+flight if t+30<=f['t']<=t+1200]
            if len(samples)<5:raise RuntimeError('Insufficient trajectory samples')
            a,b=samples[0]['ball'],samples[1]['ball'];dx=b[0]-a[0];dy=b[1]-a[1]
            length=math.hypot(dx,dy);end=samples[-1]['ball']
            sideways=(dx*(end[1]-a[1])-dy*(end[0]-a[0]))/length
            check(name+' curves in the direction of measured spin',
                  abs(spin[2])>.5 and sideways*spin[2]>0 and abs(sideways)>.03,
                  {'signed_lateral_deflection_m':sideways,'spin_z_rad_s':spin[2]})
        check('different physical approaches produce different spin',len(spins)==3 and
              max(math.dist(a,b)for a in spins for b in spins)>1,spins)
        # Release both buttons together before maximum charge: preserve LB.
        game.reset();start=len(game.log.read_text());game.pad(0,0,buttons=4|(1<<9));game.advance(250)
        game.pad(0,0);game.advance(1700)
        lob=[l for l in game.log.read_text()[start:].splitlines()if l.startswith('TRAINING_SHOT ')]
        check('a short LB plus X release keeps its lob modifier',len(lob)==1 and 'chip=1'in lob[0],lob)
        game.keys(['Escape'],True);game.game.wait(timeout=15)
        check('clean exit',game.game.returncode==0,game.game.returncode)
    report['result']='passed'if all(c['result']=='passed'for c in report['checks'])else'failed'
except BaseException as error:
    report['result']='failed';report['error']=str(error);raise
finally:
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed':raise SystemExit(1)
