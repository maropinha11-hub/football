#!/usr/bin/env python3
"""Preserve the approved FP camera, reserved RT, shot modifiers and reception actions."""
import argparse,json,hashlib,math,re,statistics
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':134');a=p.parse_args()
r={'result':'running','checks':[],'executable_sha256':hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest()}
def check(name,ok,evidence):
 row={'check':name,'result':'passed'if ok else'failed','evidence':evidence};r['checks'].append(row);print(json.dumps(row),flush=True)
def touches(s):return [(int(t),part,int(kind))for t,part,kind in re.findall(r'TRAINING_ACTION_TOUCH t=(\d+) part=(\w+) function=(\d+)',s)]
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,config_overrides={'context_x':'320','context_y':'180'})as g:
  for sprint in [False,True]:
   speeds=[]
   for rt in [False,True]:
    g.reset();g.pad(0,-1,sprint=sprint,close=rt);g.advance(1500);f=g.advance(1400)
    speeds.append(statistics.median(x['speed']for x in f))
   check('RT remains reserved with RB '+str(sprint),abs(speeds[0]-speeds[1])<.2,speeds)
  g.reset();g.pad(0,-1);g.advance(500);g.keys(['Right'],True);f=g.advance(450);g.keys(['Right'],False)
  check('right stick/head look is independent from forward body travel',abs(f[-1]['head_yaw'])>.5 and abs(f[-1]['player_yaw'])<.2,f[-1])
  f=g.advance(2300);check('head recenters gradually',abs(f[-1]['head_yaw'])<.2,f[-1]['head_yaw'])
  for name,buttons,chip in [('full shot',4,0),('lob',4|(1<<9),1)]:
   g.reset();start=len(g.log.read_text());g.pad(0,0,buttons=buttons);g.advance(600);g.pad(0,0);f=g.advance(1700)
   s=g.log.read_text()[start:];rows=[x for x in s.splitlines()if x.startswith('TRAINING_SHOT ')]
   check(name+' retains charge/elevation modifier',len(rows)==1 and 'chip='+str(chip)in rows[0]and max(x['ball'][2]for x in f)>1,rows)
  # Additional receptions complete their one-shot before a new action.
  g.reset();start=len(g.log.read_text());g.keys(['F5'],True);g.keys(['F5'],False)
  g.wait(lambda:any(k==3 for _,_,k in touches(g.log.read_text()[start:])));g.advance(1500)
  start=len(g.log.read_text());g.pad(0,0,buttons=1);g.advance(180);g.pad(0,0);g.advance(2200)
  hits=touches(g.log.read_text()[start:]);check('pass works after the completed chest reception',sum(k==4 for _,_,k in hits)==1,hits)
  for name,key,button,kind in [('one-touch pass','F4',1,4),('header shot','F6',4,8)]:
   g.reset();start=len(g.log.read_text());g.keys([key],True);g.keys([key],False)
   g.pad(0,0,buttons=button);g.advance(300);g.pad(0,0);g.advance(2400)
   hits=touches(g.log.read_text()[start:]);check(name+' uses original buffered action',any(k==kind and (part=='head'if name=='header shot'else True)for _,part,k in hits),hits)
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r['result']='failed';r['error']=str(e);raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
