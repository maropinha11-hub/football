#!/usr/bin/env python3
"""Exercise analog pressure/RB handoffs and trajectory-aware chest reception."""
import argparse,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':110');a=p.parse_args()
report={'result':'running','checks':[]}
def check(name,ok,evidence):
    row={'check':name,'result':'passed' if ok else 'failed','evidence':evidence}
    report['checks'].append(row);print(json.dumps(row),flush=True)
def rows(text,prefix):
    return [{k:float(v)for k,v in re.findall(r'(\w+)=(-?[\d.]+)',s)}for s in text.splitlines()if s.startswith(prefix+' ')]
def ahead(f):
    return (f['ball'][0]-f['player'][0])*math.cos(f['player_yaw'])+(f['ball'][1]-f['player'][1])*math.sin(f['player_yaw'])
try:
    with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=2,config_overrides={'context_x':'320','context_y':'180'})as g:
        for name,pressure,sprint in [('light stick',.3,False),('half stick',.6,False),('three-quarter stick',.8,False),('RB sprint',1,True)]:
            g.reset();g.pad(0,-1);g.advance(1800);start=len(g.log.read_text())
            g.pad(0,-pressure,sprint=sprint);frames=g.advance(1800)
            values=[ahead(f)for f in frames]
            check(name+' keeps the ball ahead of the body',min(values)>.20 and all(f['with_ball']for f in frames),
                  {'minimum_ahead_m':min(values),'maximum_distance_m':max(math.dist(f['ball'][:2],f['player'][:2])for f in frames),'lost_frames':sum(not f['with_ball']for f in frames)})
            poses=rows(g.log.read_text()[start:],'TRAINING_NATIVE_POSE')
            check(name+' keeps the rendered shoes outside the ball',not poses or all(min(s['gap_left'],s['gap_right'])>=-.0015 for s in poses),
                  {'samples':len(poses),'minimum_skin_gap_m':min((min(s['gap_left'],s['gap_right'])for s in poses),default=None)})
            if sprint:
                g.pad(0,-1);after=g.advance(2200)
                check('releasing RB resumes controlled forward dribbling',min(ahead(f)for f in after)>.20 and all(f['with_ball']for f in after),
                      {'minimum_ahead_m':min(ahead(f)for f in after),'ending_distance_m':math.dist(after[-1]['ball'][:2],after[-1]['player'][:2])})
        g.reset();start=len(g.log.read_text());g.keys(['F5'],True);g.keys(['F5'],False);frames=g.advance(3600)
        text=g.log.read_text()[start:];touch=rows(text,'TRAINING_CHEST_TOUCH');states=rows(text,'TRAINING_CHEST_STATE')
        recovery=[f for f in frames if touch and touch[0]['t']+450<f['t']<=states[-1]['t']]
        check('standing chest reception has one actual shirt contact',len(touch)==1 and abs(touch[0]['gap'])<=.0011,touch)
        check('chest steps follow the ball without walking over it',bool(recovery)and min(ahead(f)for f in recovery)>.25 and max(abs(f['ball'][1]-f['player'][1])for f in recovery)<.3,
              {'minimum_ahead_m':min((ahead(f)for f in recovery),default=None),'maximum_lateral_m':max((abs(f['ball'][1]-f['player'][1])for f in recovery),default=None),'root_motion_m':max((s['root_motion']for s in states),default=None)})
        check('chest reception leaves the ball just ahead at the handoff',bool(recovery)and .3<ahead(recovery[-1])<.9 and math.dist(recovery[-1]['ball'][:2],recovery[-1]['player'][:2])<1,
              recovery[-1]if recovery else {})
        for name,stick in [('forward',(0,-1)),('backward',(0,1))]:
            g.reset();start=len(g.log.read_text());g.keys(['F5'],True)
            delivery=rows(g.log.read_text()[start:],'TRAINING_DELIVERY')[-1]['t']
            g.wait(lambda:g.frames()[-1]['t']>=delivery+600);g.pad(*stick);g.keys(['F5'],False);after=g.advance(1600)
            text=g.log.read_text()[start:];native=rows(text,'TRAINING_NATIVE_SURFACE')
            check(name+' before impact reselects an original reception',
                  'TRAINING_CHEST_CANCEL' in text and 'TRAINING_CHEST_TOUCH' not in text and
                  (any(s['accepted']and s['function']in (2,3)for s in native)or'TRAINING_BODY_TOUCH'in text),
                  {'chest_contacts':text.count('TRAINING_CHEST_TOUCH'),'cancellations':rows(text,'TRAINING_CHEST_CANCEL'),'native_contacts':[s for s in native if s['accepted']],'body_contacts':rows(text,'TRAINING_BODY_TOUCH')})
        g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
    report['result']='passed'if all(c['result']=='passed'for c in report['checks'])else'failed'
except BaseException as error:
    report['result']='failed';report['error']=str(error);raise
finally:
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed':raise SystemExit(1)
