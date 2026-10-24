#!/usr/bin/env python3
"""A real CPU hand must reach the human shirt before applying a finite hold."""
import argparse,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':286');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def ev(g,prefix):return[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log().splitlines()if x.startswith(prefix+' ')]
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides={'context_x':480,'context_y':270,'training_physical_rig':'true','training_physical_lab':'true','player_match':'true','player_match_half_seconds':120,'simulation_seed':7})as g:
  g.advance(2600);yaw=g.frames()[-1]['player_yaw'];g.keys(['b','n'],True);g.keys(['Shift_L','F2','F11'],True);g.advance(100);g.keys(['Shift_L','F2','F11'],False)
  # The standard side-by-side drill can be outside this player's anatomical
  # arm reach. Bring the carrier closer with actual analog locomotion; the
  # CPU still has to reach real skin before the unchanged .10 m grip gate.
  g.wait(lambda:ev(g,'PHYSICAL_MATCH_SETUP'));setup=ev(g,'PHYSICAL_MATCH_SETUP')[-1];opponent=int(setup['opponent'])
  def match_frames_now():return[json.loads(x[19:])for x in g.read_log().splitlines()if x.startswith('PLAYER_MATCH_FRAME ')]
  g.wait(lambda:match_frames_now()and match_frames_now()[-1]['t']>=int(setup['t']))
  match_frames=match_frames_now()
  target=next(x['p']for x in match_frames[-1]['players']if x['id']==opponent);actor=g.frames()[-1]['player']
  dx=target[0]-actor[0];dy=target[1]-actor[1];length=math.hypot(dx,dy)
  # Make one real approach to the actual opponent until its hand contacts
  # the shirt. Braking now works, so a fixed250ms step no longer coasts the
  # carrier the additional distance that the old fixture depended on.
  g.pad(.35*dx/length,-.35*dy/length)
  g.wait(lambda:any(x['state']=='begin'and x['actor']==str(opponent)for x in ev(g,'PHYSICAL_AI_GRIP')),seconds=8);g.pad(0,0)
  g.advance(1500);grips=[x for x in ev(g,'PHYSICAL_AI_GRIP')if x['actor']==str(opponent)];forces=[x for x in ev(g,'PHYSICAL_AI_GRIP_FORCE')if x['actor']==str(opponent)]
  check('CPU hand reaches the actual shirt before holding',any(x['state']=='begin'and float(x['gap'])<.10 for x in grips),grips)
  check('CPU hold transmits bounded force through a reachable hand',bool(forces)and all(math.isfinite(float(x['force']))and float(x['force'])<=180.01 and float(x['gap'])<=.23 for x in forces),forces)
  g.keys(['b','n'],False);g.advance(1800);grips=[x for x in ev(g,'PHYSICAL_AI_GRIP')if x['actor']==str(opponent)];fouls=ev(g,'PHYSICAL_FOUL')
  check('CPU grip eventually releases or is stopped by the referee',any(x['state']=='release'for x in grips)or bool(fouls),dict(grips=grips,fouls=fouls))
  frames=[json.loads(x[19:])for x in g.read_log().splitlines()if x.startswith('PLAYER_MATCH_FRAME ')]
  check('contact drill preserves the two teams and fixed human',all(len(x['players'])==22 and x['human_count']==1 and x['selected_id']==x['locked_id']for x in frames),dict(samples=len(frames)))
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
