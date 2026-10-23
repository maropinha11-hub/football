"""Rendered medium-stick walk, real RB spending and learned CPU muscles."""
import argparse,hashlib,json,math,re,statistics,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':1220');p.add_argument('--match',action='store_true');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',line))for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')]
def capture(g,name):subprocess.run(['import','-window',g.window,str(a.output/name)],env=g.env,check=True)
try:
 config=dict(context_x=480,context_y=270,training_physical_rig='true',training_physical_lab='true',simulation_seed=7)
 if a.match:config.update(player_match='true',player_match_half_seconds=120,player_match_all_restarts='false')
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=config)as g:
  if not a.match:
   speeds=[]
   for strength in [.35,.50,.68]:
    g.reset();start=len(g.read_log());g.pad(0,-strength);frames=g.advance(5000);capture(g,'walk-'+str(strength)+'.png');g.pad(0,0)
    tail=frames[-30:];speed=math.dist(tail[-1]['player'][:2],tail[0]['player'][:2])/((tail[-1]['t']-tail[0]['t'])/1000);speeds.append(speed)
    gap=max(math.dist(f['player'][:2],f['ball'][:2])for f in frames)
    peak=max(f['speed']for f in tail);moving=sum(f['speed']>.20 for f in tail)/len(tail)
    retreat=max([max(0,a['player'][1]-b['player'][1])for a,b in zip(tail,tail[1:])]or[0])
    check('stick '+str(strength)+' walks continuously with its ball rather than a brief jog burst',.25<speed<1.8 and peak<2.2 and moving>.75 and gap<1.8 and retreat<.015,dict(mean_speed=speed,peak_speed=peak,moving_fraction=moving,maximum_ball_gap=gap,maximum_backward_step=retreat))
    energy=[x for x in ev(g,'SPRINT_ENERGY',start)if x['human']=='1']
    check('stick '+str(strength)+' spends no sprint energy without RB',bool(energy)and all(x['requested']=='0'and float(x['energy'])>.999 for x in energy),energy[-3:])
   check('the walking range responds progressively to ordinary stick pressure',speeds[0]+.06<speeds[-1],speeds)
   g.reset();start=len(g.read_log());g.pad(0,-1);g.advance(3000)
   normal=[x for x in ev(g,'SPRINT_ENERGY',start)if x['human']=='1'];check('full normal movement also preserves the reserve without RB',bool(normal)and all(x['requested']=='0'and float(x['energy'])>.999 for x in normal),normal[-4:])
   start=len(g.read_log());g.pad(0,-1,sprint=True);g.advance(2200);sprint=[x for x in ev(g,'SPRINT_ENERGY',start)if x['human']=='1'];g.pad(0,-.6);start=len(g.read_log());g.advance(3000);released=[x for x in ev(g,'SPRINT_ENERGY',start)if x['human']=='1']
   check('RB alone spends reserve and releasing it stops spending during the current clip',bool(sprint)and min(float(x['energy'])for x in sprint)<.97 and bool(released)and all(x['requested']=='0'for x in released)and all(float(b['energy'])>=float(a['energy'])-.00002 for a,b in zip(released,released[1:])),dict(sprint=sprint[-4:],released=released[:3]+released[-3:]))
   muscles=[x for x in ev(g,'ML_MUSCLE')if x['human']=='1'and int(x['samples'])>0]
   check('the human rig actually runs the trained bounded motor during gameplay',bool(muscles)and all(math.isfinite(float(x['error']))and float(x['acceleration'])<=140.001 for x in muscles),dict(samples=len(muscles),peak_error=max([float(x['error'])for x in muscles]or[0])))
  else:
   g.advance(12000);banks=ev(g,'PHYSICAL_CPU_BALANCE_BANK');muscles=[x for x in ev(g,'ML_MUSCLE')if x['human']=='0'and int(x['samples'])>0]
   check('all 21 CPU actors share the actual protective-motion bank',len({x['actor']for x in banks})==21 and all(int(x['variants'])>=160 and x['shared']=='1'for x in banks),dict(actors=sorted({x['actor']for x in banks})))
   check('moving CPU actors run learned muscles rather than passive static tracking',len({x['actor']for x in muscles})>=16 and all(float(x['acceleration'])<=140.001 for x in muscles),dict(actors=sorted({x['actor']for x in muscles}),samples=len(muscles)))
   orient=ev(g,'CPU_RECEIVE_ORIENT');check('CPU receivers actively orient toward forecast arrivals',bool(orient),orient[:8])
   # A normal match may have reached a throw-in after the observation run;
   # this optional fixture is correctly unavailable while play is stopped.
   g.keys(['r'],True);g.advance(100);g.keys(['r'],False);g.advance(2700)
   start=len(g.read_log());g.keys(['F2'],True);g.wait(lambda:ev(g,'PHYSICAL_MATCH_SETUP',start));g.keys(['F2'],False)
   start=len(g.read_log());g.keys(['m'],True);g.wait(lambda:ev(g,'PHYSICAL_MATCH_CONTEST',start));g.keys(['m'],False);g.advance(350);capture(g,'cpu-recovery.png');g.advance(1700)
   contest=ev(g,'PHYSICAL_MATCH_CONTEST',start);opponent=contest[0]['opponent']if contest else''
   balance=[x for x in ev(g,'PHYSICAL_BALANCE',start)if x['actor']==opponent]
   check('a disturbed CPU loads its balance and selects a real protective response from the shared bank',bool(contest)and any(int(x['choice'])>=0 and float(x['risk'])>.10 for x in balance),dict(contest=contest,balance=balance[:8]))
   frames=[json.loads(x[19:])for x in g.read_log().splitlines()if x.startswith('PLAYER_MATCH_FRAME ')]
   check('the physical match retains 22 finite actors and one fixed user',bool(frames)and all(len(x['players'])==22 and x['human_count']==1 and all(all(math.isfinite(v)for v in actor['p'])for actor in x['players'])for x in frames),dict(samples=len(frames)))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
