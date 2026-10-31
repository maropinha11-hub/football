"""Regression for a torso reception winding backwards while the player turns."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from native_training_harness import NativeTraining
from training_pes_shortpass_smoke import events

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':4120')
    p.add_argument('--camera',type=int,default=2);p.add_argument('--classic',action='store_true');a=p.parse_args()
    report=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
    report['bank_catalog_sha256']=hashlib.sha256((Path(__file__).resolve().parents[1]/'data/media/training/pes17/catalog.json').read_bytes()).hexdigest()
    def check(name,ok,evidence):
        row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);report['checks'].append(row);print(json.dumps(row),flush=True)
    overrides=dict(context_x=640,context_y=360,training_physical_lab='true',training_motion_diagnostics='true',
                   training_pes_action_filter='trap_0_0_000_y6_breast_ver03')
    try:
        with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=a.camera,
                            config_overrides=overrides,extra_arguments=[]if a.classic else['--pes-actions'])as g:
            def move(angle):
                x,y=-math.sin(math.radians(angle)),-math.cos(math.radians(angle))
                g.pad(*((-y,x)if a.camera==1 else(x,y)))
            all_masks=[];starts=0
            for name,delay,angle in [('early_reverse',150,180),('arrival_diagonal',350,135),
                                      ('after_touch_reverse',650,180),('after_touch_side',900,90)]:
                g.reset();start=len(g.read_log());g.keys(['F5'],True);g.advance(80);g.keys(['F5'],False)
                g.advance(delay);move(angle);g.advance(1800);g.pad(0,0);g.advance(350)
                log=g.read_log()[start:];masks=events(log,'TRAINING_UPPER_MASK');all_masks+=masks
                begins=events(log,'TRAINING_UPPER_START');starts+=len(begins)
                q=events(log,'TRAINING_CONTACT_JOINTS')
                finite=all(all(math.isfinite(float(v))for v in r[k].strip('[]').split(','))for r in q for k in r if k.startswith('j'))
                check(name+' keeps the actual skeleton finite',len(q)>15 and finite,dict(samples=len(q)))
                if masks:
                    peak=max(abs(float(r['spine_twist']))for r in masks)
                    check(name+' never winds the spine around the pelvis',peak<1.15,dict(samples=len(masks),maximum_twist_rad=peak))
                    check(name+' keeps independent legs and root',all(float(r['legs_error'])<.0001 and float(r['root_error'])<.0001 for r in masks),dict(samples=len(masks)))
                # After the reception attempt, changing direction must regain
                # root travel, including when the ball was missed.
                before=g.frames()[-1]['player'];move(0);frames=g.advance(1200);g.pad(0,0)
                distance=math.dist(before[:2],frames[-1]['player'][:2])
                check(name+' releases movement after the attempt',distance>.35,dict(distance_m=distance,releases=events(log,'RECEPTION_RELEASE')))
            check('the trials exercise a real upper reception rather than only an idle pose',starts>=2 and len(all_masks)>=10,dict(starts=starts,masks=len(all_masks)))
            if a.camera==2:
                eyes=events(g.read_log(),'FIRSTPERSON_FRAME')
                check('turning receptions preserve head and eye alignment',bool(eyes)and all(float(r['anchor_error'])<.025 and float(r['alignment'])>.999 for r in eyes),dict(samples=len(eyes)))
            g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
    except Exception as error:check('the rendered regression completes',False,repr(error))
    report['result']='passed'if all(r['result']=='passed'for r in report['checks'])else'failed'
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if report['result']=='passed'else 1)

if __name__=='__main__':main()
