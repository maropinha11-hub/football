#!/usr/bin/env python3
"""Opposite-direction cuts on the approved native first-person gameplay."""
import argparse,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':94');p.add_argument('--observe',action='store_true');args=p.parse_args()
checks=[];cases=[]
def check(name,ok,evidence):
 checks.append(dict(check=name,result='passed'if ok else'failed',evidence=evidence));print(('PASS 'if ok else'FAIL ')+name+': '+str(evidence),flush=True)
report=dict(result='running',checks=checks,cases=cases,input='real SDL virtual Xbox controller')
try:
 with NativeTraining(args.build,args.output,display=args.display,analog_pad=True)as game:
  for label,run,sprint,keep_sprint,close in [('standing',0,False,False,False),('walking',1500,False,False,False),
       ('sprint release',2200,True,False,False),('sprint held',2200,True,True,False),('RT control',1800,False,False,True)]:
   game.reset()
   if run:game.pad(0,-1,sprint=sprint,close=close);game.advance(run)
   origin=game.frames()[-1];start=origin['t'];heading=origin['yaw']-origin['head_yaw'];forward=(math.cos(heading),math.sin(heading))
   game.pad(0,1,sprint=keep_sprint,close=close);samples=game.advance(2200)
   seq=[origin]+samples
   steps=[sum((b['ball'][i]-a['ball'][i])*forward[i]for i in range(2))for a,b in zip(seq,seq[1:])]
   distances=[math.dist(f['player'],f['ball'])for f in samples]
   contacts=[(int(t),part,int(kind))for t,part,kind in re.findall(r'TRAINING_ACTION_TOUCH t=(\d+) part=(\w+) function=(\d+)',game.log.read_text())
             if start<int(t)<=samples[-1]['t']and int(kind)in(2,3)and part in('left_foot','right_foot')]
   first=next(f for f in samples if f['t']>=start+500)
   first_pull=sum((first['ball'][i]-origin['ball'][i])*forward[i]for i in range(2))
   evidence=dict(minimum_backward_ball_step_m=min(steps),first_500ms_ball_delta_m=first_pull,max_ball_distance_m=max(distances),
                 native_foot_contacts=len(contacts),controlled_samples=sum(f['with_ball']for f in samples),samples=len(samples),
                 added_body_contacts=samples[-1]['contacts']-origin['contacts'])
   cases.append(dict(case=label,evidence=evidence,origin=origin,frames=samples))
   check(label+' pulls at native foot contacts',bool(contacts)and min(steps)<-.04,evidence)
   if label=='standing':check('standing pull responds within 500 ms',first_pull<-.15,evidence)
   check(label+' retains the ball',all(f['with_ball']for f in samples)and max(distances)<2.3,evidence)
   game.pad(0,-1,close=close);continued=game.advance(1200);game.pad(0,0)
   check(label+' continues in the new front',all(f['with_ball']for f in continued)and
         math.dist(continued[-1]['player'],continued[-1]['ball'])<1.2 and math.dist(continued[0]['player'],continued[-1]['player'])>.5,
         dict(distance=math.dist(continued[-1]['player'],continued[-1]['ball']),travel=math.dist(continued[0]['player'],continued[-1]['player'])))
  log=game.log.read_text()
  check('native player pose remains active','PES3_BODY_APPLY'not in log,'No study pose applied to the player')
  pulls=[(int(t),part,float(x),float(y))for t,part,x,y in re.findall(
         r'TRAINING_PULLBACK t=(\d+) part=(\w+) velocity=\[([^,]+),([^]]+)\]',log)]
  events={(int(t),part)for t,part,kind in re.findall(r'TRAINING_ACTION_TOUCH t=(\d+) part=(\w+) function=(\d+)',log)if int(kind)in(2,3)}
  if not args.observe:
   check('pullback force follows accepted native foot events',bool(pulls)and all((t,part)in events for t,part,_,_ in pulls),len(pulls))
   check('pullback force stays within dribble speed',bool(pulls)and max(math.hypot(x,y)for _,_,x,y in pulls)<=2.5001,
         max((math.hypot(x,y)for _,_,x,y in pulls),default=0))
   support=[(float(before),float(after))for before,after in re.findall(
            r'TRAINING_SUPPORT_CONTACT t=\d+ before=([\d.]+) after=([\d.]+)',log)]
   check('support contacts do not add another kick',bool(support)and all(after<=before+.001 for before,after in support),
         dict(contacts=len(support),maximum_speed_gain=max((after-before for before,after in support),default=0)))
  game.keys(['Escape'],True);game.game.wait(timeout=15);check('clean exit',game.game.returncode==0,game.game.returncode)
 report['result']='passed'if all(c['result']=='passed'for c in checks)else'failed'
except BaseException as error:report['result']='failed';report['error']=str(error);raise
finally:
 args.output.mkdir(parents=True,exist_ok=True);(args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed'and not args.observe:raise SystemExit(1)
