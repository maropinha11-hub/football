#!/usr/bin/env python3
"""Exercise actual receptions, cut loading, impact response and keeper decisions."""
import argparse,hashlib,json,math,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':314');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 c=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(c);print(json.dumps(c),flush=True)
def ev(g,prefix,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[start:].splitlines()if x.startswith(prefix+' ')]
def key(g,key,mods=[]):g.keys(mods+[key],True);g.advance(100);g.keys(mods+[key],False);g.advance(100)
def mf(g):return[json.loads(x[19:])for x in g.read_log().splitlines()if x.startswith('PLAYER_MATCH_FRAME ')]
def capture(g,name):subprocess.run(['import','-window',g.window,str(a.output/name)],env=g.env,check=True)
try:
 with NativeTraining(a.build,a.output/'solo',display=a.display,analog_pad=True,camera=1,config_overrides={'context_x':480,'context_y':270,'training_physical_rig':'true','training_physical_lab':'true','simulation_seed':7})as g:
  for name,k,mods in [('feet','F4',[]),('chest','F5',[]),('belly','F5',['Control_L'])]:
   g.reset();start=len(g.read_log());key(g,k,mods);g.advance(2200)
   requests=ev(g,'RECEPTION_REQUEST',start);native=ev(g,'TRAINING_NATIVE_START',start);touches=ev(g,'TRAINING_ACTION_TOUCH',start)
   upper=ev(g,'TRAINING_UPPER_PLAN',start)
   upper_contact=any(x.get('upper_layer')=='1'and x.get('part')=='trunk'and x.get('function')=='3'for x in touches)
   # The approved chest overlay leaves the native legs free. It therefore
   # does not emit a full-body TRAINING_NATIVE_START, but must still plan an
   # accepted skin contact and actually complete it at the trunk.
   prepared=bool(requests or touches)and any(x.get('function')in ['2','3']for x in native)
   prepared=prepared or (upper_contact and any(x.get('accepted')=='1'for x in upper))
   check(name+' arrival actively prepares a native reception',prepared,dict(requests=requests[:4],native=native[:8],touches=touches,upper_plan=upper[:4]))
  g.reset();start=len(g.read_log());key(g,'F5',['Shift_L','Control_L']);g.advance(180);capture(g,'body-impact.png');g.advance(1020)
  reacts=ev(g,'PHYSICAL_BALL_REACTION',start)
  check('a driven body hit produces a bounded physical reaction',any(x['hard']=='1'and float(x['impulse'])>0 for x in reacts),reacts)
  g.reset();g.pad(1,0,sprint=True);g.advance(1600);start=len(g.read_log());g.pad(-1,0,sprint=True);g.advance(1600);g.pad(0,0)
  cuts=ev(g,'PHYSICAL_CUT',start);steps=ev(g,'PHYSICAL_STAGGER_CLIP',start)
  check('a sprint reversal loads balance and plays a protective step',bool(cuts)and bool(steps),dict(cuts=cuts,steps=steps))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('solo exits cleanly',g.game.returncode==0,g.game.returncode)
 with NativeTraining(a.build,a.output/'match',display=a.display,analog_pad=True,camera=1,config_overrides={'context_x':480,'context_y':270,'training_physical_rig':'true','training_physical_lab':'true','player_match':'true','player_match_half_seconds':120,'player_match_all_restarts':'false','simulation_seed':7})as g:
  g.advance(2700);start=len(g.read_log());key(g,'F6',['Control_L']);setup=ev(g,'KEEPER_LAB_SETUP',start)[-1];keeper=setup['actor'];side=float(setup['side'])
  g.pad(side,0,sprint=True);g.advance(1100);g.pad(0,0)
  decisions=[x for x in ev(g,'KEEPER_DECISION',start)if x['actor']==keeper]
  check('uncovered goalkeeper advances to close the one-on-one angle',any(x['mode']in ['close_angle','smother']for x in decisions),decisions[-8:])
  key(g,'r');g.advance(2700);start=len(g.read_log());key(g,'F6',['Control_L']);g.advance(80);capture(g,'keeper-attempt.png');g.advance(920)
  dives=ev(g,'KEEPER_DIVE_ATTEMPT',start)
  check('an unreachable goal-bound corner shot still produces a real dive attempt',bool(dives)and all(x['contact']=='0'for x in dives),dives)
  key(g,'r');g.advance(2700);start=len(g.read_log());key(g,'F6',['Control_L']);setup=ev(g,'KEEPER_LAB_SETUP',start)[-1];keeper=setup['actor'];side=float(setup['side']);g.advance(1900)
  touches=[x for x in ev(g,'TRAINING_ACTION_TOUCH',start)if x.get('actor')==keeper]
  arrival=[f for f in mf(g)if f['t']>=int(setup['t'])]
  decisions=[x for x in ev(g,'KEEPER_DECISION',start)if x['actor']==keeper]
  emergency=[]
  for touch in touches:
   if touch.get('function')!='11'or 'foot'not in touch.get('part',''):continue
   before=[f for f in arrival if f['t']<=int(touch['t'])];after=[f for f in arrival if f['t']>=int(touch['t'])+300]
   if before and after and after[-1]['ball'][0]*side<before[-1]['ball'][0]*side-.4 and any(x['bound']=='1'and int(x['t'])<=int(touch['t'])for x in decisions):emergency.append(touch)
  controlled=any(x.get('function')in ['2','3','4','5','6']and 'foot'in x.get('part','')for x in touches)
  check('keeper intercepts an intentional backpass with an authored foot contact and prevents an own goal',
        bool(arrival)and all(f['home']==0 and f['away']==0 for f in arrival)and (controlled or bool(emergency)),dict(touches=touches,emergency_clearances=emergency,scores=[[f['home'],f['away']]for f in arrival]))
  check('keeper never invents a hand catch on that backpass',all('elbow'not in x.get('part','')and 'hand'not in x.get('part','')for x in touches),touches)
  frames=mf(g);check('all goalkeeper drills retain 22 players and one fixed human',bool(frames)and all(len(x['players'])==22 and x['selected_id']==x['locked_id']and x['human_count']==1 for x in frames),dict(frames=len(frames)))
  key(g,'r');g.advance(2700);start=len(g.read_log())
  # This unattended AI observation uses native CPU restarts; shipped manual
  # human restarts are exercised independently by the pitch_rules suite.
  for _ in range(3):g.advance(15000)
  tactics=ev(g,'PLAYER_MATCH_TACTIC',start);choices=sorted({x['choice']for x in tactics});r['observed_tactics']=choices
  # An arbitrary match segment may legitimately contain only blocked lanes.
  # Also exercise a prepared open outlet without forcing any AI decision.
  key(g,'r');g.advance(2700);start=len(g.read_log());key(g,'F6',['Control_L','Shift_L']);g.advance(5000)
  setup=ev(g,'CIRCULATION_LAB_SETUP',start);open_tactics=ev(g,'PLAYER_MATCH_TACTIC',start);actions=ev(g,'PLAYER_MATCH_ACTION',start)
  choices=sorted(set(choices)|{x['choice']for x in open_tactics});r['observed_tactics']=choices
  # A quick original CPU pass can start before the additional tactical
  # classifier sees settled possession. Verify that executed outlet directly
  # instead of requiring a particular diagnostic label from the extra layer.
  safe_outlets=[]
  if setup:
   frames=[f for f in mf(g)if f['t']>=int(setup[-1]['t'])]
   for action in actions:
    if action['action']not in ['4','5']or action['actor']!=setup[-1]['actor']or not frames:continue
    frame=min(frames,key=lambda f:abs(f['t']-int(action['t'])))
    actors={str(p['id']):p for p in frame['players']}
    source=actors.get(action['actor']);target=actors.get(action['target'])
    if not source or not target or source['human']or source['team']!=target['team']:continue
    a2=source['p'][:2];b2=target['p'][:2];delta=[b2[i]-a2[i]for i in range(2)]
    square=sum(x*x for x in delta);clearance=1000.
    for opponent in frame['players']:
     if opponent['team']==source['team']:continue
     u=max(0.,min(1.,sum((opponent['p'][i]-a2[i])*delta[i]for i in range(2))/max(square,.001)))
     clearance=min(clearance,math.dist(opponent['p'][:2],[a2[i]+u*delta[i]for i in range(2)]))
    forward=-float(setup[-1]['side'])*delta[0]
    if 4<math.sqrt(square)<35 and clearance>2 and forward>1:
     safe_outlets.append(dict(actor=action['actor'],target=action['target'],range=math.sqrt(square),lane_clearance=clearance,progress=forward))
  classified=any(x['choice']in ['buildout','circulate']and float(x['outlet'])>.70 and int(x['options'])>0 for x in open_tactics)
  check('an open defensive outlet produces a safe contextual choice and a real CPU pass',bool(setup)and (classified or bool(safe_outlets))and any(x['action']in ['4','5']for x in actions),dict(choices=choices,unattended_samples=tactics[:16],open_tactics=open_tactics[:16],safe_executed_outlets=safe_outlets,actions=actions))
  check('rendered match remains finite',all(math.isfinite(v)for x in g.frames()for k in ['player','ball']for v in x[k]),dict(samples=len(g.frames())))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('match exits cleanly',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
