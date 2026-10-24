"""A pass, shot and cross can meet an airborne ball with an actual foot."""
import argparse,hashlib,json,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':2140');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',line))for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')]
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=640,context_y=360,training_physical_rig='true',training_physical_lab='true',simulation_seed=7))as g:
  for name,button,function in [('pass',1,'4'),('shot',4,'8'),('cross',2,'6')]:
   g.reset();start=len(g.read_log());g.keys(['8','F5'],True)
   # Buffer before the delivery's 420 ms arrival. Waiting for two X11 key
   # acknowledgements first consumed most of its flight in the old fixture.
   sent=g.frames()[-1]['t'];g.pad(0,0,buttons=button);g.advance(70);g.pad(0,0);g.keys(['8','F5'],False);g.advance(1800)
   selected=ev(g,'NATIVE_APPROVED_SELECT',start);contacts=[x for x in ev(g,'TRAINING_ACTION_TOUCH',start)if x.get('function')==function]
   check(name+' meets an airborne ball with a timed native skin action',any(float(x['z'])>.27 and 'foot'in x['part']for x in contacts),dict(selected=selected,contacts=contacts,delivery=ev(g,'TRAINING_DELIVERY',start),button_sent_ms=sent))
   accepted=[x for x in ev(g,'TRAINING_KICK_PLAN',start)if x.get('accepted')=='1']
   check(name+' retains the millimetre skin-contact plan gate',bool(accepted)and all(float(x['gap'])<=.001 for x in accepted),accepted[-5:])
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
