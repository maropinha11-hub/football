#!/usr/bin/env python3
"""Rendered Xbox regressions for restarting dribbles, chest handoffs and RB bursts."""
import argparse,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':121');a=p.parse_args()
report={'result':'running','checks':[]}
def rows(s,prefix):
    return [{k:float(v)for k,v in re.findall(r'(\w+)=(-?[\d.]+)',l)}for l in s.splitlines()if l.startswith(prefix+' ')]
def check(name,ok,evidence):
    row={'check':name,'result':'passed'if ok else'failed','evidence':evidence};report['checks'].append(row);print(json.dumps(row),flush=True)
def ahead(f):
    return (f['ball'][0]-f['player'][0])*math.cos(f['player_yaw'])+(f['ball'][1]-f['player'][1])*math.sin(f['player_yaw'])
try:
    with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=2,config_overrides={'context_x':'320','context_y':'180'})as g:
        for idle in [100,300,900,2000]:
            g.reset();g.pad(0,-1);g.advance(1600);g.pad(0,0);g.advance(idle)
            start=len(g.log.read_text());g.pad(0,-1);frames=g.advance(2400);s=g.log.read_text()[start:]
            distances=[math.dist(f['player'][:2],f['ball'][:2])for f in frames];values=[ahead(f)for f in frames];touches=rows(s,'TRAINING_FBX_TOUCH')
            check('resume after '+str(idle)+' ms keeps the ball ahead and advances',min(values)>.20 and max(distances)<1.5 and
                  all(f['with_ball']for f in frames)and math.dist(frames[-1]['player'][:2],frames[0]['player'][:2])>4,
                  {'minimum_ahead_m':min(values),'maximum_distance_m':max(distances),'travel_m':math.dist(frames[-1]['player'][:2],frames[0]['player'][:2]),'lost_frames':sum(not f['with_ball']for f in frames)})
            check('resume after '+str(idle)+' ms acquires actual loop foot contacts',len(touches)>=2 and all(-.0015<=t['gap']<=.00051 for t in touches),
                  {'contacts':len(touches),'contact_gaps_m':[t['gap']for t in touches]})
        for duration in [300,800,1700,3000]:
            g.reset();g.pad(0,-1);g.advance(1400);start=len(g.log.read_text());g.pad(0,-1,sprint=True);running=g.advance(duration)
            g.pad(0,-1);after=g.advance(2000);s=g.log.read_text()[start:];f=running+after
            check('RB burst '+str(duration)+' ms retains controlled spacing',math.dist(running[-1]['player'][:2],running[0]['player'][:2])>max(.3,duration*.0025)and all(x['with_ball']for x in f)and min(ahead(x)for x in f)>.20 and
                  max(math.dist(x['player'][:2],x['ball'][:2])for x in f)<1.5 and ahead(after[-1])<.9 and all(r['t']in {t['t']for t in rows(s,'TRAINING_NATIVE_SURFACE')if t['accepted']}for r in rows(s,'TRAINING_CONTROL_RELEASE')),
                  {'maximum_distance_m':max(math.dist(x['player'][:2],x['ball'][:2])for x in f),'minimum_ahead_m':min(ahead(x)for x in f),
                   'ending_ahead_m':ahead(after[-1]),'lost_frames':sum(not x['with_ball']for x in f),'follow_through_adjustments_at_real_contacts':len(rows(s,'TRAINING_CONTROL_RELEASE')),'running_travel_m':math.dist(running[-1]['player'][:2],running[0]['player'][:2])})
        for delay in [0,200,500]:
            g.reset();start=len(g.log.read_text());g.keys(['F5'],True);g.keys(['F5'],False)
            g.wait(lambda:bool(rows(g.log.read_text()[start:],'TRAINING_CHEST_TOUCH')));touch=rows(g.log.read_text()[start:],'TRAINING_CHEST_TOUCH')[0]
            if delay:g.advance(delay)
            g.pad(0,-1);frames=g.advance(2400);s=g.log.read_text()[start:];release=rows(s,'TRAINING_CHEST_RELEASE');tail=rows(s,'TRAINING_CHEST_HANDOFF')
            check('chest interruption after '+str(delay)+' ms blends through the next native clip',len(rows(s,'TRAINING_CHEST_TOUCH'))==1 and bool(release)and len(tail)>=10 and
                  tail[0]['tail']>.9 and tail[-1]['tail']<.05 and all(b['tail']<=a['tail']for a,b in zip(tail,tail[1:])),
                  {'release':release,'handoff_samples':len(tail),'initial_tail':tail[0]['tail']if tail else None,'final_tail':tail[-1]['tail']if tail else None,
                   'native_contact_during_fade':sum(t['remaining']>=0 and t['function']==2 for t in tail)})
            poses=[]
            for line in s.splitlines():
                if line.startswith('TRAINING_CONTACT_JOINTS '):
                    poses.append((int(re.search(r't=(\d+)',line)[1]),{int(k):list(map(float,v.split(',')))for k,v in re.findall(r'j(\d+)=\[([^]]+)\]',line)}))
            rates=[]
            if release:
                for first,second in zip(poses,poses[1:]):
                    dt=second[0]-first[0]
                    if 0<dt<=100 and release[0]['t']-50<=first[0]<=release[0]['t']+250:
                        rates.append(max(2*math.acos(min(1,abs(sum(x*y for x,y in zip(first[1][k],second[1][k])))))*1000/dt for k in first[1]))
            check('chest interruption after '+str(delay)+' ms has continuous rendered torso and leg rotations',len(rates)>=3 and max(rates)<20,
                  {'rendered_transition_samples':len(rates),'maximum_joint_angular_speed_rad_s':max(rates,default=None)})
            late=[x for x in frames if x['t']>touch['t']+800]
            check('chest interruption after '+str(delay)+' ms resumes forward control',bool(late)and all(x['with_ball']for x in late)and min(ahead(x)for x in late)>.20 and ahead(late[-1])<.9 and late[-1]['speed']>2,
                  {'minimum_ahead_m':min((ahead(x)for x in late),default=None),'ending_ahead_m':ahead(late[-1])if late else None,'ending_speed_mps':late[-1]['speed']if late else None})
        g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
    report['result']='passed'if all(r['result']=='passed'for r in report['checks'])else'failed'
except BaseException as e:
    report['result']='failed';report['error']=str(e);raise
finally:
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed':raise SystemExit(1)
