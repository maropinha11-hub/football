#!/usr/bin/env python3
"""Aimed repeated taps must redirect the real incoming ball, not only queue an action."""
import argparse,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--approved',action='store_true',help='Use the approved nonphysical training path.')
p.add_argument('--display',default=':194');p.add_argument('--camera',type=int,choices=[1,2],default=2)
a=p.parse_args();r=dict(result='running',checks=[],scenarios={},executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def angle(x,y):
 n=math.hypot(*x)*math.hypot(*y)
 return math.degrees(math.acos(max(-1,min(1,sum(i*j for i,j in zip(x,y))/n))))if n>.00001 else 180
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=a.camera,config_overrides={'context_x':320,'context_y':180,'training_physical_rig':'false'if a.approved else'true','training_physical_lab':'false'if a.approved else'true'})as g:
  for key,button,kind in [('F6',1,4),('F6',4,8),('F4',1,4)]:
   directions=[('left_diagonal',-.70710678,-.70710678),('right_diagonal',.70710678,-.70710678)]
   if key=='F6':directions += [('left',-1,0),('right',1,0)]
   for label,x,y in directions:
    name=f'{key}_{kind}_{label}';g.reset();start=len(g.read_log())
    g.keys([key],True);g.keys([key],False)
    f=g.frames()[-1];yaw=f['yaw']if a.camera==2 else f['player_yaw']
    # Aim diagonally on both sides of the player's CURRENT front. Reception
    # should still constrain the feet rather than rotate away from the ball.
    requested=(math.cos(yaw)*-y+math.sin(yaw)*x,math.sin(yaw)*-y-math.cos(yaw)*x)
    raw=(x,y)if a.camera==2 else(requested[0],-requested[1])
    for _ in range(4):
     g.pad(*raw,buttons=button);g.advance(100);g.pad(*raw);g.advance(100)
    # Centering the stick while the action is queued must retain the aim.
    g.pad(0,0);g.advance(2000)
    events=[]
    for t,k,part,tx,ty,vx,vy in re.findall(r'TRAINING_ACTION_AIM t=(\d+) function=(\d+) part=(\w+) requested=\[([^,]+),([^\]]+)\] actual=\[([^,]+),([^\]]+)\]',g.read_log()[start:]):
     if int(k)==kind:events.append(dict(t=int(t),part=part,target=[float(tx),float(ty)],velocity=[float(vx),float(vy)]))
    evidence=dict(expected_direction=requested,contacts=events)
    if events:
     e=events[0];evidence.update(target_error_deg=angle(requested,e['target']),outgoing_error_deg=angle(requested,e['velocity']))
     frames=g.frames();first=next((v for v in frames if v['t']>=e['t']),None);last=next((v for v in frames if v['t']>=e['t']+150),None)
     if first and last:
      displacement=[last['ball'][i]-first['ball'][i]for i in range(2)]
      evidence.update(ball_travel=displacement,travel_error_deg=angle(requested,displacement))
    r['scenarios'][name]=evidence
    check(name+' completes a real first-time contact',len(events)==1 and(key!='F6'or events[0]['part']=='head'),evidence)
    if key=='F6'and not a.approved:
     power=[dict(re.findall(r'(\w+)=([^\s]+)',line))for line in g.read_log()[start:].splitlines()if line.startswith('HEADER_CONTACT_POWER ')]
     check(name+' uses loaded head contact and a bounded header-specific impulse',len(power)==1 and power[0]['loaded']=='1'and 3.19<float(power[0]['speed'])<=(18.001 if kind==8 else 13.001),power)
    check(name+' retains the selected aim through repeated taps and stick release',bool(events)and evidence['target_error_deg']<20,evidence)
    check(name+' sends the actual ball toward the chosen side',bool(events)and evidence['outgoing_error_deg']<35 and evidence.get('travel_error_deg',180)<40,evidence)
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
