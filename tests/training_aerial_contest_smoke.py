"""A contested delivery must recruit both actors, not leave the CPU inert."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':1197');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):return [dict(re.findall(r'(\w+)=([^\s]+)',line))for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')]
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=480,context_y=270,training_physical_rig='true',training_physical_lab='true',player_match='true',player_match_half_seconds=120,player_match_all_restarts='false',simulation_seed=7))as g:
  trials=[]
  # Fixed count, not retry-until-success. Body contact may make both actors
  # miss one contest; that must not manufacture a head impulse. Record every
  # outcome and require actual head contact over three independent deliveries.
  for trial in range(3):
   g.keys(['r'],True);g.advance(100);g.keys(['r'],False);g.advance(2700)
   start=len(g.read_log());g.keys(['Alt_L','F2'],True);g.wait(lambda:ev(g,'PHYSICAL_AERIAL_DUEL_SETUP',start));g.keys(['Alt_L','F2'],False)
   for i in range(4):g.pad(0,0,buttons=1);g.advance(100);g.pad(0,0);g.advance(100)
   subprocess.run(['import','-window',g.window,str(a.output/('aerial-contest-'+str(trial)+'.png'))],env=g.env,check=True);g.advance(1500)
   setup=ev(g,'PHYSICAL_AERIAL_DUEL_SETUP',start);intents=ev(g,'CPU_AERIAL_DUEL',start)
   selected=ev(g,'NATIVE_APPROVED_SELECT',start);headers=[x for x in selected if 'head'in x.get('source','')]
   touches=[x for x in ev(g,'TRAINING_ACTION_TOUCH',start)if x.get('part')=='head']
   # The ordinary native AI can already have a valid header queued; the
   # CPU_AERIAL_DUEL diagnostic only describes the additional fallback.
   check('delivery '+str(trial)+' CPU competes for the actual contested trajectory',bool(setup)and any(x['actor']==setup[0]['opponent']for x in intents+headers),dict(setup=setup,intents=intents,headers=headers))
   # The delivery targets the CPU line, not the midpoint. The human can be
   # out of reach even with a correctly queued request; human heading contact
   # and aim are covered separately by the two aerial-direction suites.
   human=[x for x in g.frames()if setup and x['t']>=int(setup[0]['t'])and x['action_mode']==2]
   check('delivery '+str(trial)+' CPU selects a native header and human input stays buffered',bool(setup)and setup[0]['opponent']in{x['actor']for x in headers}and bool(human),dict(headers=headers,human_queued_samples=len(human)))
   trials.append(dict(setup=setup,headers=headers,head_touches=touches))
  r['trials']=trials
  check('the three fixed contested deliveries include a real head contact',any(x['head_touches']for x in trials),trials)
  frames=[json.loads(x[19:])for x in g.read_log().splitlines()if x.startswith('PLAYER_MATCH_FRAME ')]
  check('aerial contest preserves 22 actors and one fixed user',bool(frames)and all(len(x['players'])==22 and x['human_count']==1 for x in frames),dict(samples=len(frames),body_contacts=ev(g,'PHYSICAL_AERIAL_CONTACT',start)))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
