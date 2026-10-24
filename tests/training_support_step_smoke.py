"""Rendered automatic support steps generated from load rather than a trip clip."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':1440');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 c=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(c);print(json.dumps(c),flush=True)
def ev(g,prefix,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[start:].splitlines()if x.startswith(prefix+' ')]
def key(g,k):g.keys([k],True);g.advance(100);g.keys([k],False);g.advance(100)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=640,context_y=360,training_physical_rig='true',training_physical_lab='true',simulation_seed=7))as g:
  for direction in range(4):
   g.reset();start=len(g.read_log());key(g,'F8')
   subprocess.run(['import','-window',g.window,str(a.output/('procedural-step-'+str(direction)+'.png'))],env=g.env,check=True)
   f=g.advance(1800);steps=ev(g,'PROCEDURAL_SUPPORT_STEP',start);states=ev(g,'PHYSICAL_RIG_STATE',start)
   check('direction '+str(direction)+' generates support without selecting a whole-body trip',bool(steps)and max(float(x['lift'])for x in steps)>.035 and not ev(g,'PHYSICAL_STAGGER_CLIP',start),dict(step_samples=steps))
   check('direction '+str(direction)+' preserves a reachable support and regains control',bool(steps)and max(float(x['support_error'])for x in steps)<.06 and not any(x['to']=='1'for x in states)and f[-1]['speed']<.5,dict(states=states,final_speed=f[-1]['speed']))
   key(g,'F3')
  # The active layer reports support/arms; PHYSICAL_RIG_RENDER is emitted
  # only by the full falling/get-up renderer. Exercise that renderer rather
  # than requiring a nonexistent active-mode event.
  g.reset();start=len(g.read_log());key(g,'F8');key(g,'F9');g.advance(8000)
  states=ev(g,'PHYSICAL_RIG_STATE',start);tail=ev(g,'PROCEDURAL_SUPPORT_STEP',start)
  returned=[int(x['t'])for x in states if x['from']=='2'and x['to']=='0']
  check('a fall interrupts the generated step and get-up discards its old anchors',bool(returned)and not any(int(x['t'])>returned[-1]+100 for x in tail),dict(states=states,step_samples=len(tail)))
  rendered=ev(g,'PHYSICAL_RIG_RENDER');check('falling and get-up retain the final rendered bone lengths',bool(rendered)and max(float(x['length_error'])for x in rendered)<.0001,dict(samples=len(rendered)))
  arms=ev(g,'PHYSICAL_ARM_RENDER');check('generated balance retains anatomical rendered arms',bool(arms)and max(float(x['error'])for x in arms)<.00001 and max(float(x['penetration'])for x in arms)<.004,dict(samples=len(arms)))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
