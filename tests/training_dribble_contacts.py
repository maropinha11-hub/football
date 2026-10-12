#!/usr/bin/env python3
"""Measure actual foot intervals and unintended leg impulses in rendered training."""
import argparse,json,math,re,statistics
from pathlib import Path
from native_training_harness import NativeTraining

p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--observe',action='store_true');args=p.parse_args();checks=[];cases=[]
def check(name,passed,evidence):
 checks.append({'check':name,'result':'passed'if passed else'failed','evidence':evidence})
 print(('PASS 'if passed else'FAIL ')+name+': '+str(evidence),flush=True)
def contacts(log,start,end):
 return [(int(t),part)for t,part,kind in re.findall(r'TRAINING_ACTION_TOUCH t=(\d+) part=(\w+) function=(\d+)',log)
         if start<int(t)<=end and int(kind)in (2,3)and part in ('left_foot','right_foot')]
report={'result':'running','checks':checks,'cases':cases,'input':'SDL virtual Xbox controller'}
try:
 with NativeTraining(args.build,args.output,analog_pad=True)as game:
  for mode in ('dominant','normal'):
   if mode=='normal':
    game.keys(['g'],True);game.wait(lambda:game.frames()[-1]['dominant_control']==0);game.keys(['g'],False)
   for name,amount,sprint,close in [('slow',.5,False,False),('jog',1,False,False),('sprint',1,True,False),('close',1,False,True)]:
    game.reset();game.pad(0,-amount,sprint=sprint,close=close);game.advance(1600)
    start=game.frames()[-1]['t'];samples=game.advance(6000);end=samples[-1]['t'];game.pad(0,0)
    touches=contacts(game.log.read_text(),start,end);gaps=[b[0]-a[0]for a,b in zip(touches,touches[1:])]
    evidence={'touches':len(touches),'right':sum(part=='right_foot'for _,part in touches),
              'gaps_ms':gaps,'min_gap_ms':min(gaps)if gaps else None,'median_gap_ms':statistics.median(gaps)if gaps else None,
              'max_distance':max(math.dist(f['player'],f['ball'])for f in samples),'controlled':sum(f['with_ball']for f in samples),
              'samples':len(samples),'median_player_speed':statistics.median(f['speed']for f in samples)}
    cases.append({'mode':mode,'case':name,'evidence':evidence})
    check(mode+' '+name+' stays controlled',all(f['with_ball']for f in samples)and evidence['max_distance']<2.3,evidence)
    if mode=='dominant':
     minimum=400 if close else 450
     check(name+' dominant foot has time between contacts',bool(gaps)and min(gaps)>=minimum,evidence)
     check(name+' dominant foot still preferred',evidence['right']/max(1,len(touches))>.6,evidence)
   for name,sprint,close in [('cuts',False,False),('sprint cuts',True,False),('RT cuts',False,True),('RB RT cuts',True,True)]:
    game.reset();game.pad(0,-1,sprint=sprint,close=close);game.advance(1700);start=game.frames()[-1]['t']
    for x,y,hold in [(0,1,750),(1,0,550),(0,-1,500),(-1,0,600),(0,1,900),(.75,.65,550),(0,-1,650)]:
     game.pad(x,y,sprint=sprint,close=close);game.advance(hold)
    samples=[f for f in game.frames()if f['t']>start];game.pad(0,0)
    log=game.log.read_text();events=[(int(t),int(leg),int(controlled),float(before),float(after))for t,leg,controlled,before,after in
     re.findall(r'TRAINING_COLLISION t=(\d+) leg=(\d+) controlled=(\d+) before=([\d.]+) after=([\d.]+)',log)if start<int(t)<=samples[-1]['t']]
    self_hits=[v for v in events if v[1]and v[2]]
    evidence={'max_distance':max(math.dist(f['player'],f['ball'])for f in samples),'controlled':sum(f['with_ball']for f in samples),
              'samples':len(samples),'leg_contacts':len(self_hits),'largest_leg_speed_gain':max((after-before for _,_,_,before,after in self_hits),default=0),
              'final_distance':math.dist(samples[-1]['player'],samples[-1]['ball'])}
    cases.append({'mode':mode,'case':name,'evidence':evidence})
    # RB+RT is an authored knock-on: allow its longer forward roll using
    # the same reach bound as training_reversal_smoke. Then release the
    # RT while retaining sprint, as in the native knock-on exercise, and
    # verify an actual return to normal dribbling distance.
    bound=3.5 if sprint and close else 2.3
    evidence['reach_bound']=bound
    check(mode+' '+name+' keeps ball through turns',all(f['with_ball']for f in samples)and
          evidence['max_distance']<bound,evidence)
    check(mode+' '+name+' support leg does not kick ball away',evidence['largest_leg_speed_gain']<=.001,evidence)
    game.pad(0,-1,sprint=sprint);recovery=game.advance(1500);game.pad(0,0)
    recovered=math.dist(recovery[-1]['player'],recovery[-1]['ball'])
    evidence['recovered_distance']=recovered
    check(mode+' '+name+' returns to normal dribbling after cuts',
          all(f['with_ball']for f in recovery)and recovered<1.2,{'distance':recovered,'samples':len(recovery)})
  game.keys(['Escape'],True);game.game.wait(timeout=15);check('clean exit',game.game.returncode==0,game.game.returncode)
  speeds={c['case']:c['evidence']['median_player_speed']for c in cases if c['mode']=='dominant'and 'median_player_speed'in c['evidence']}
  check('RT retains slower close-control movement',speeds['close']<speeds['jog']-.5,speeds)
  check('partial stick stays slower than full forward',speeds['slow']<speeds['jog']-.5,speeds)
  hits=sum(c['evidence'].get('leg_contacts',0)for c in cases)
  check('support response was exercised by actual leg contacts',hits>0,hits)
 report['result']='passed'if all(c['result']=='passed'for c in checks)else'failed'
except BaseException as error:
 report['result']='failed';report['error']=str(error);raise
finally:
 args.output.mkdir(parents=True,exist_ok=True);(args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed'and not args.observe:raise SystemExit(1)
