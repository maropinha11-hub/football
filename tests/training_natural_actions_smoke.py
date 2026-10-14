#!/usr/bin/env python3
"""Running/turning action commits must hit once, with no late foot reaching."""
import argparse,json,re,math
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':115');a=p.parse_args()
report={'result':'running','checks':[]}
def check(name,ok,evidence):
 row={'check':name,'result':'passed'if ok else'failed','evidence':evidence};report['checks'].append(row);print(json.dumps(row),flush=True)
def rows(s,prefix):
 return [{k:float(v)for k,v in re.findall(r'(\w+)=(-?[\d.]+)',l)}for l in s.splitlines()if l.startswith(prefix+' ')]
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=2,config_overrides={'context_x':'320','context_y':'180'})as g:
  for name,button,kind,hold in [('pass',1,4,120),('cross',2,6,250),('through',8,5,250),('shot',4,8,250),('full shot',4,8,600)]:
   for scenario,duration in [('run 500',500),('run 1100',1100),('run 1850',1850),('turn during run',900)]:
    g.reset();g.pad(0,-1);g.advance(900);g.pad(0,-1,sprint=True);g.advance(duration)
    start=len(g.log.read_text());stick=(1,0)if scenario=='turn during run'else(0,-1)
    g.pad(*stick,sprint=True,buttons=button);g.advance(hold);g.pad(0,-1,sprint=True);g.advance(2400)
    s=g.log.read_text()[start:];commits=rows(s,'TRAINING_ACTION_START');hits=rows(s,'TRAINING_ACTION_TOUCH')
    wanted=[r for r in hits if r['function']==kind]
    check(name+' '+scenario+' commits one reachable action',len(commits)==1 and commits[0]['function']==kind and len(wanted)==1 and
      'TRAINING_ACTION_MISS'not in s and commits[0]['foot_reach']==0,
      {'commits':commits,'contacts':wanted,'misses':rows(s,'TRAINING_ACTION_MISS')})
  poses=rows(g.log.read_text(),'TRAINING_NATIVE_POSE')
  check('contact poses retain bone lengths without large foot repositioning',bool(poses)and max(r['foot_shift']for r in poses)<=.0801 and max(r['length_error']for r in poses)<.0001,
        {'samples':len(poses),'maximum_render_adjustment_m':max((r['foot_shift']for r in poses),default=None),'maximum_length_error_m':max((r['length_error']for r in poses),default=None)})
  check('running action poses keep both shoes outside the ball',bool(poses)and min(min(r['gap_left'],r['gap_right'])for r in poses)>=-.0015,
        {'minimum_skin_gap_m':min((min(r['gap_left'],r['gap_right'])for r in poses),default=None)})
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 report['result']='passed'if all(r['result']=='passed'for r in report['checks'])else'failed'
except BaseException as e:
 report['result']='failed';report['error']=str(e);raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed':raise SystemExit(1)
