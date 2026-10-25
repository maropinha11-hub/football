#!/usr/bin/env python3
"""Light rear taps use a heel; charged passes turn and hit the actual ball."""
import argparse,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':173');p.add_argument('--camera',type=int,choices=[1,2],default=1);a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def events(s,prefix):return [dict(re.findall(r'(\w+)=([^\s]+)',x))for x in s.splitlines()if x.startswith(prefix+' ')]
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=a.camera,config_overrides={'context_x':480,'context_y':270,'training_physical_rig':'true','training_physical_lab':'true'})as g:
  front=(1,0)if a.camera==1 else(0,-1);rear=(-1,0)if a.camera==1 else(0,1)
  for name,stick,charge in [('straight',front,180),('light_heel',rear,80),('behind',rear,180),('strong_behind',rear,350),('behind_on_release',rear,180)]:
   g.reset();start=len(g.read_log());g.pad(*(front if name=='behind_on_release'else stick),buttons=1);g.advance(charge);release=g.frames()[-1]['t'];g.pad(*stick);f=g.advance(2500);g.pad(0,0)
   log=g.read_log()[start:];hits=[x for x in events(log,'TRAINING_ACTION_TOUCH')if x['function']=='4'];turn=events(log,'PHYSICAL_PASS_TURN')
   selected=[x for x in events(log,'TRAINING_NATIVE_START')if x['function']=='4']
   check(name+' pass completes with a real foot contact',len(hits)==1 and max(x['ball_speed']for x in f)>4,dict(hits=hits,turn=turn,peak_ball_speed=max(x['ball_speed']for x in f),selected=selected))
   contact=int(hits[0]['t'])if hits else 0
   if name=='light_heel':
    check('light rear tap selects a heel without a slow turn',bool(hits)and bool(selected)and selected[0]['heel']=='1'and not turn and 0<contact-release<750,dict(selected=selected,release_to_contact_ms=contact-release,turn=turn))
   elif name.startswith('behind')or name=='strong_behind':
    before=[x for x in g.frames()if contact-100<=x['t']<=contact]
    # player_yaw is a quantized locomotion/look heading. It is deliberately
    # clamped relative to travel and is not the physical pelvis orientation.
    poses=[json.loads(x[19:])for x in log.splitlines()if x.startswith('PHYSICAL_RIG_FRAME ')]
    poses=[x for x in poses if contact-100<=x['t']<=contact]
    facing=1
    if poses:
     qx,qy,qz,qw=poses[-1]['root_q'];forward=(2*(qw*qz-qx*qy),-1+2*(qx*qx+qz*qz))
     facing=forward[0]/max(.0001,math.hypot(*forward))
    check(name+' turns the body instead of selecting a heel',bool(selected)and all(x['heel']=='0'for x in selected)and bool(poses)and facing<-.35,dict(turn=turn,selected=selected,physical_facing_dot_original_forward=facing,semantic_heading_dot=math.cos(before[-1]['player_yaw'])if before else None,release_to_contact_ms=contact-release))
    # A direction changed on release can require the current control step
    # followed by a native pivot and the authored kicking wind-up. Measure
    # idle delay separately instead of treating all that motion as a lock.
    chosen=selected[-1]if selected else {};begin=int(chosen.get('t',0));windup=int(chosen.get('contact_frame',0))*10
    ready=[int(x['t'])for x in turn if x.get('state')=='release'and x.get('aligned')=='1'and int(x['t'])<=begin]
    aligned=ready[-1]if ready else begin
    controls=[int(x['t'])for x in events(log,'TRAINING_ACTION_TOUCH')if x['function']in ['2','3']and aligned<=int(x['t'])<=begin]
    # Alignment does not imply the shoe has brought the ball into its next
    # striking position. Count a measured intervening control as preparation;
    # retain the same latency bounds and measure idle delay after that touch.
    factual_ready=max([aligned,*controls]);handoff=begin-factual_ready
    approach=[x for x in g.frames()if release<=x['t']<=begin]
    recovery=sum(b['t']-a['t']for a,b in zip(approach,approach[1:])if math.dist(a['player'][:2],a['ball'][:2])>1.25)
    # A ball outside the native kick corridor still needs a real approach.
    # Bound that separately; keep the original response bound while reachable
    # and the unchanged120ms idle-handoff bound after actual preparation.
    check(name+' finishes its native pivot and wind-up without an extra input lock',bool(hits)and bool(selected)and 0<contact-release<=2100 and contact-release-recovery<=1400 and 0<=begin-release-recovery<=950 and abs(contact-begin-windup)<=40 and handoff<=120,dict(release_to_contact_ms=contact-release,out_of_reach_recovery_ms=recovery,reachable_to_contact_ms=contact-release-recovery,pivot_preparation_ms=begin-release,authored_windup_ms=windup,actual_windup_ms=contact-begin,aligned_handoff_ms=begin-aligned,preparation_contacts=controls,contact_handoff_ms=handoff))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
