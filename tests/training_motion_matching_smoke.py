#!/usr/bin/env python3
"""Rendered phase continuity, receiving preparation, shielding and CPU header."""
import argparse,hashlib,json,math,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':245');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):
 return [dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[start:].splitlines()if x.startswith(prefix+' ')]
def key(g,k,mods=()):
 names=[*mods,k];g.keys(names,True);g.advance(100);g.keys(names,False);g.advance(100)
def shot(g,name):
 subprocess.run(['import','-window',g.window,str(a.output/(name+'.png'))],env=g.env,check=True)
def config(match=False):
 return dict(context_x=640,context_y=360,training_physical_rig='true',training_physical_lab='true',
             player_match='true'if match else'false',player_match_half_seconds=120,simulation_seed=7)
try:
 with NativeTraining(a.build,a.output/'solo',display=a.display,analog_pad=True,camera=1,config_overrides=config())as g:
  g.reset();origin=g.frames()[-1];g.pad(0,-1);f=g.advance(3000);g.pad(0,0)
  phases=ev(g,'MOTION_PHASE_ENTER');queries=ev(g,'MOTION_MATCH');inertia=ev(g,'MOTION_INERTIA')
  check('motion matching searches per-frame features with the learned native metric',
        any(int(x['frames'])>100 and int(x['tested'])>1 and x['adaptive']=='1'and x['learned']=='1'for x in queries),
        dict(queries=len(queries),maximum_indexed_frames=max(int(x['frames'])for x in queries)))
  check('an interior pose retains a nonzero first physics displacement',
        bool(phases)and all(int(x['frame'])>0 and float(x['root_step'])>.001 for x in phases),phases)
  check('phase selection preserves dribble travel and ball ownership',
        math.dist(origin['player'][:2],f[-1]['player'][:2])>7 and max(math.dist(x['player'][:2],x['ball'][:2])for x in f)<2,
        dict(travel_m=math.dist(origin['player'][:2],f[-1]['player'][:2]),maximum_ball_gap_m=max(math.dist(x['player'][:2],x['ball'][:2])for x in f)))
  check('rendered transitions use finite decaying inertial offsets',
        bool(inertia)and max(float(x['offset'])for x in inertia)>.02 and all(math.isfinite(float(x['offset']))and float(x['offset'])<6.284 for x in inertia),
        dict(samples=len(inertia),maximum_rotation_offset_rad=max(float(x['offset'])for x in inertia)))
  for k,name,part in [('F4','ground','right_foot'),('F5','chest','trunk')]:
   g.reset();start=len(g.read_log());key(g,k);g.advance(280);shot(g,'anticipation-'+name);g.advance(1920)
   preparation=[x for x in ev(g,'PHYSICAL_ADAPTIVE',start)if x['receiving']=='1'and float(x['anticipate'])>.02]
   hits=ev(g,'TRAINING_ACTION_TOUCH',start)
   check(name+' arrival prepares the visible body from a future trajectory',bool(preparation),preparation[:4])
   check(name+' arrival still reaches an authored physical contact',any(x['part']==part for x in hits),hits)
  g.reset();key(g,'F10');g.keys(['n'],True);g.advance(1000);shot(g,'shielding')
  stance=ev(g,'PHYSICAL_ADAPTIVE')[-8:]
  check('shielding lowers and offsets the body under nearby pressure',any(float(x['stance'])>.025 for x in stance),stance)
  start=len(g.read_log());key(g,'F12');g.advance(400)
  check('F12 disables the new search and transition layer for comparison',
        any(x['enabled']=='0'for x in ev(g,'MOTION_MATCH_TOGGLE',start)),ev(g,'MOTION_MATCH_TOGGLE',start))
  key(g,'F12');g.advance(500);g.keys(['n'],False);key(g,'F10');g.advance(1500)
  pressure=ev(g,'PHYSICAL_BODY_DUEL')
  check('real close-range body overlap transmits bounded reciprocal pressure',
        bool(pressure)and all(x['reciprocal']=='1'and 0<float(x['normal_force'])<=260.01 and float(x['penetration'])<=.08001 for x in pressure),
        dict(samples=len(pressure),examples=pressure[:4]))
  hits=ev(g,'TRAINING_ACTION_TOUCH');skin=ev(g,'TRAINING_SKIN_CONTACT');accepted={x['t']for x in skin if x['accepted']=='1'}
  check('new movement preserves same-tick skin contact for every ball impulse',
        bool(hits)and all(x['t']in accepted for x in hits),dict(impulses=len(hits),accepted_skin_ticks=len(accepted)))
  check('body preparation and contact diagnostics remain finite',
        all(math.isfinite(float(x[k]))for x in ev(g,'PHYSICAL_ADAPTIVE')for k in ['stance','anticipate','arrival','height']),
        dict(samples=len(ev(g,'PHYSICAL_ADAPTIVE'))))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('solo clean exit',g.game.returncode==0,g.game.returncode)
 with NativeTraining(a.build,a.output/'match',display=a.display,analog_pad=True,camera=1,config_overrides=config(True))as g:
  g.advance(2700);start=len(g.read_log());key(g,'F2',['Alt_L']);g.advance(350);shot(g,'aerial-contest');g.advance(2150)
  setup=ev(g,'PHYSICAL_AERIAL_DUEL_SETUP',start);duels=ev(g,'CPU_AERIAL_DUEL',start)
  heads=[x for x in ev(g,'TRAINING_ACTION_TOUCH',start)if x['part']=='head']
  # The native controller can already request a pass or defensive header;
  # the added policy deliberately does not overwrite an existing decision.
  # Its modulo-sampled telemetry need not coincide with those short queries.
  native=[x for x in ev(g,'MOTION_MATCH',start)if setup and x['actor']==setup[0]['opponent']and x['function']in ['4','5','6','8','11']]
  check('aerial fixture asks the CPU to contest an incoming high ball',bool(setup)and bool(duels or native),dict(setup=setup,decisions=duels,native_queries=native[:6]))
  check('CPU wins a header through the native authored contact solver',
        bool(heads)and bool(setup)and any(x['actor']==setup[0]['opponent']and x['function']in ['4','5','6','8','11']for x in heads),heads)
  skin=ev(g,'TRAINING_SKIN_CONTACT',start);accepted={x['t']for x in skin if x['accepted']=='1'}
  check('CPU header has real same-tick skin contact at the unchanged tolerance',
        bool(heads)and all(x['t']in accepted for x in heads)and all(float(x['gap'])<=.00251 for x in skin if x['accepted']=='1'),skin)
  matches=[json.loads(x[19:])for x in g.read_log().splitlines()if x.startswith('PLAYER_MATCH_FRAME ')]
  check('aerial and body duels retain both teams and the single locked human',
        bool(matches)and all(len(x['players'])==22 and x['human_count']==1 and x['selected_id']==x['locked_id']for x in matches),dict(samples=len(matches)))
  pressure=ev(g,'PHYSICAL_BODY_DUEL',start)
  check('physical match uses the same reciprocal body-contact layer as training',bool(pressure),pressure[:4])
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('match clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
