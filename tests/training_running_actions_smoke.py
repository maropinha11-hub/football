#!/usr/bin/env python3
"""Regression for directional running kicks that used to miss the ball."""
import argparse,hashlib,json,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':138');p.add_argument('--physical',action='store_true');a=p.parse_args()
r={'result':'running','physical_profile':a.physical,'checks':[],'executable_sha256':hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest()}
def events(s,prefix):return [dict(re.findall(r'(\w+)=([^\s]+)',line))for line in s.splitlines()if line.startswith(prefix+' ')]
def check(name,ok,evidence):
 row={'check':name,'result':'passed'if ok else'failed','evidence':evidence};r['checks'].append(row);print(json.dumps(row),flush=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,config_overrides={'context_x':320,'context_y':180,'training_physical_rig':'true'if a.physical else'false'})as g:
  for phase in (900,1450):
   for action,button,kind in [('shot',4,8),('cross',2,6)]:
    for direction,stick in [('forward',(0,-1)),('right',(1,0)),('diagonal',(.7071,-.7071))]:
     g.reset();g.pad(0,-1,sprint=True);g.advance(phase);start=len(g.read_log());g.pad(*stick,sprint=True,buttons=button);g.advance(300);g.pad(*stick,sprint=True);frames=g.advance(2000)
     s=g.read_log()[start:];hits=[x for x in events(s,'TRAINING_ACTION_TOUCH')if int(x['function'])==kind]
     plans=[x for x in events(s,'TRAINING_NATIVE_START')if int(x['function'])==kind]
     check(str(phase)+' ms running '+action+' toward '+direction+' makes one physical kick',len(hits)==1 and bool(plans)and max(x['ball_speed']for x in frames)>5,{'touches':hits,'native_selections':plans[-3:],'peak_ball_speed_mps':max(x['ball_speed']for x in frames)})
  log=g.read_log();hits=events(log,'TRAINING_ACTION_TOUCH');skin=[x for x in events(log,'TRAINING_SKIN_CONTACT')if x['accepted']=='1'];accepted={x['t']for x in skin}
  check('every impulse has same-tick skin contact without enlarging the contact tolerance',bool(hits)and all(x['t']in accepted for x in hits)and all(float(x['gap'])<=.00251 for x in skin),{'authored_impulses':len(hits),'maximum_accepted_gap_m':max(float(x['gap'])for x in skin)})
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r['result']='failed';r['error']=str(e);raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
