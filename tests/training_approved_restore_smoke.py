#!/usr/bin/env python3
"""The approved native gait remains connected, including off-ball side/back steps."""
import argparse, hashlib, json, math, re
from pathlib import Path
from native_training_harness import NativeTraining

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':364');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
    row=dict(check=name,result='passed'if ok else'failed',evidence=evidence)
    r['checks'].append(row);print(json.dumps(row),flush=True)
try:
    for camera in [1,2]:
        with NativeTraining(a.build,a.output/str(camera),display=a.display,analog_pad=True,camera=camera,
                config_overrides=dict(context_x=480,context_y=270,training_physical_rig='true',
                    training_physical_lab='true',training_mocap_locomotion='true',simulation_seed=7))as g:
            g.reset();origin=g.frames()[-1];g.pad(0,-1);frames=g.advance(2400)
            travel=math.dist(origin['player'][:2],frames[-1]['player'][:2])
            gap=max(math.dist(x['player'][:2],x['ball'][:2])for x in frames)
            check('camera '+str(camera)+' keeps the approved connected forward dribble',travel>4 and gap<2,
                  dict(travel=travel,maximum_ball_gap=gap))
            g.pad(0,-1,sprint=True);fast=g.advance(1500);g.pad(0,-1);slow=g.advance(1200)
            check('camera '+str(camera)+' keeps native RB run and release connected',
                  max(math.dist(x['player'][:2],x['ball'][:2])for x in fast+slow)<2.8,
                  dict(maximum_ball_gap=max(math.dist(x['player'][:2],x['ball'][:2])for x in fast+slow)))
            # Kick away before testing free movement; these are not dribbling turns.
            for name,x,y in [('side_right',1,0),('backward',0,1),('side_left',-1,0),('forward',0,-1)]:
                g.reset();g.pad(0,0,buttons=1);g.advance(80);g.pad(0,0);g.advance(1300)
                before=g.frames()[-1]
                if camera==1:desired=(x,-y)
                else:
                    yaw=before['yaw'];desired=(-y*math.cos(yaw)+x*math.sin(yaw),-y*math.sin(yaw)-x*math.cos(yaw))
                g.pad(x,y);frames=g.advance(1000);tail=frames[-3:]
                velocity=[tail[-1]['player'][i]-tail[0]['player'][i]for i in range(2)]
                alignment=sum(v*d for v,d in zip(velocity,desired))/max(.001,math.hypot(*velocity))
                check('camera '+str(camera)+' '+name+' follows the requested direction',alignment>.75 and before['with_ball']==0,
                      dict(alignment=alignment,travel=math.dist(before['player'][:2],frames[-1]['player'][:2]),with_ball=before['with_ball']))
                if camera==2 and name=='backward':
                    check('backward off-ball movement preserves forward body facing',math.cos(frames[-1]['player_yaw']-before['yaw'])>.5,dict(body_yaw=frames[-1]['player_yaw'],view_yaw=before['yaw']))
            selected=[dict(re.findall(r'(\w+)=([^\s]+)',line))for line in g.read_log().splitlines()if line.startswith('NATIVE_APPROVED_SELECT ')]
            check('camera '+str(camera)+' selects only native frame-zero clips despite an old mocap setting',
                  len(selected)>15 and all(x['entry']=='0'and x['imported']=='0'for x in selected),dict(selections=len(selected)))
            check('camera '+str(camera)+' has no uploaded phase search or frozen mixer',
                  all(token not in g.read_log()for token in ['MOTION_PHASE_ENTER','MOTION_MIXER','MOTION_INERTIA','MOCAP_ACTIVE']),None)
            g.keys(['Escape'],True);g.game.wait(timeout=15);check('camera '+str(camera)+' clean exit',g.game.returncode==0,g.game.returncode)
    r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
