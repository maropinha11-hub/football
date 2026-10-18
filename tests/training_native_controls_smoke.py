#!/usr/bin/env python3
"""Preserve the approved FP camera, reserved RT, shot modifiers and reception actions."""
import argparse,json,hashlib,math,re,statistics
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':134');p.add_argument('--physical',action='store_true');a=p.parse_args()
r={'result':'running','physical_profile':a.physical,'checks':[],'executable_sha256':hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest()}
def check(name,ok,evidence):
 row={'check':name,'result':'passed'if ok else'failed','evidence':evidence};r['checks'].append(row);print(json.dumps(row),flush=True)
def touches(s):return [(int(t),part,int(kind))for t,part,kind in re.findall(r'TRAINING_ACTION_TOUCH t=(\d+) part=(\w+) function=(\d+)',s)]
try:
 # Compare RT from independent, identically seeded starting states. Reusing
 # a live gait after several resets changes animation phase and RNG history;
 # rough turf also changes the subsequent ball-control cadence. Those are
 # covered separately, rather than being mistaken for an RT speed modifier.
 for sprint in [False,True]:
  speeds=[];footwork=False
  for rt in [False,True]:
   with NativeTraining(a.build,a.output/('rt-'+str(int(sprint))+'-'+str(int(rt))),display=a.display,analog_pad=True,
     config_overrides={'context_x':'320','context_y':'180','simulation_seed':7,'training_turf_roughness':0,
                       'training_physical_rig':'true'if a.physical else'false'})as trial:
    trial.reset();trial.pad(0,-1,sprint=sprint,close=rt);trial.advance(1500);f=trial.advance(1400)
    speeds.append(statistics.median(x['speed']for x in f));footwork|='PHYSICAL_FOOTWORK_BEGIN'in trial.read_log()
  check('RT preserves native movement with RB '+str(sprint),abs(speeds[0]-speeds[1])<.2 and not footwork,
        dict(speeds=speeds,seed=7,roughness=0,independent_starting_states=True))
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,config_overrides={'context_x':'320','context_y':'180','training_physical_rig':'true'if a.physical else'false'})as g:
  g.reset();g.pad(0,-1);g.advance(500);g.keys(['Right'],True);f=g.advance(450);g.keys(['Right'],False)
  check('right stick/head look is independent from forward body travel',abs(f[-1]['head_yaw'])>.5 and abs(f[-1]['player_yaw'])<.2,f[-1])
  f=g.advance(2300);check('head recenters gradually',abs(f[-1]['head_yaw'])<.2,f[-1]['head_yaw'])
  for name,buttons,chip in [('full shot',4,0),('lob',4|(1<<9),1)]:
   g.reset();start=len(g.read_log());g.pad(0,0,buttons=buttons);g.advance(600);g.pad(0,0);f=g.advance(1700)
   s=g.read_log()[start:];rows=[x for x in s.splitlines()if x.startswith('TRAINING_SHOT ')]
   check(name+' retains charge/elevation modifier',len(rows)==1 and 'chip='+str(chip)in rows[0]and max(x['ball'][2]for x in f)>1,rows)
  # Additional receptions complete their one-shot before a new action.
  g.reset();start=len(g.read_log());g.keys(['F5'],True);g.keys(['F5'],False)
  g.wait(lambda:any(k==3 for _,_,k in touches(g.read_log()[start:])));g.advance(1500)
  start=len(g.read_log());g.pad(0,0,buttons=1);g.advance(180);g.pad(0,0);g.advance(2200)
  hits=touches(g.read_log()[start:]);check('pass works after the completed chest reception',sum(k==4 for _,_,k in hits)==1,hits)
  for name,key,button,kind in [('one-touch pass','F4',1,4),('header shot','F6',4,8),('header shot after 100 ms','F6',4,8),('header shot after 180 ms','F6',4,8)]:
   g.reset();start=len(g.read_log());g.keys([key],True);g.keys([key],False)
   if 'after' in name:g.advance(int(name.split()[-2]))
   g.pad(0,0,buttons=button);g.advance(300);g.pad(0,0);g.advance(2400)
   hits=touches(g.read_log()[start:]);check(name+' uses original buffered action',any(k==kind and (part=='head'if name.startswith('header shot')else True)for _,part,k in hits),hits)
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r['result']='failed';r['error']=str(e);raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
