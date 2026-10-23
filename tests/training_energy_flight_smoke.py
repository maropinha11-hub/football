"""Rendered sprint exhaustion/recovery, contact spin, walking and CPU parity."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':1091');p.add_argument('--match',action='store_true');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):return [dict(re.findall(r'(\w+)=([^\s]+)',line))for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')]
def capture(g,name):subprocess.run(['import','-window',g.window,str(a.output/name)],env=g.env,check=True)
try:
 config=dict(context_x=480,context_y=270,training_physical_rig='true',training_physical_lab='true',simulation_seed=7)
 if a.match:config.update(player_match='true',player_match_half_seconds=120,player_match_all_restarts='false')
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=config)as g:
  if a.match:
   g.advance(16000)
   rows=ev(g,'SPRINT_ENERGY');cpu=[x for x in rows if x['human']=='0'];actors={x['actor']for x in cpu}
   check('all 21 CPU players use the same simulated reserve',len(actors)==21 and all(0<=float(x['energy'])<=1 for x in cpu),dict(actors=sorted(actors),samples=len(cpu)))
   spending=[x for x in cpu if float(x['energy'])<.95 and x['requested']=='1']
   check('CPU sprint decisions actually consume stamina',len({x['actor']for x in spending})>=2,dict(actors=sorted({x['actor']for x in spending}),minimum=min([float(x['energy'])for x in cpu]or[1])))
   flights=ev(g,'CONTACT_FLIGHT')
   check('CPU releases also derive spin from their own measured contact',any(x['function']in ['4','5','6','7']for x in flights),flights[:8])
  else:
   g.reset();g.pad(0,-.4);g.advance(3200);capture(g,'walking.png');g.pad(0,0)
   clips=ev(g,'TRAINING_NATIVE_START')
   check('light stick selects the overlapping-support native-skeleton walking cycle',any(x.get('walk_support')=='overlap'for x in clips),[x for x in clips if '_slow_'in x.get('name','')][-8:])
   g.reset();start=len(g.read_log());g.pad(0,-1,sprint=True);g.advance(22000);g.pad(0,0);capture(g,'stamina-low.png')
   rows=[x for x in ev(g,'SPRINT_ENERGY',start)if x['human']=='1'];low=min([float(x['energy'])for x in rows]or[1]);tired=[x for x in rows if x['depleted']=='1']
   check('holding RB spends reserve and reaches the depleted speed cap',low<.04 and bool(tired)and all(float(x['limit'])<=4.36 for x in tired),dict(minimum=low,depleted_samples=len(tired),tail=rows[-5:]))
   start=len(g.read_log());g.advance(4500);recovery=[x for x in ev(g,'SPRINT_ENERGY',start)if x['human']=='1']
   check('standing recovers usable reserve without a full refill',bool(recovery)and float(recovery[-1]['energy'])>float(recovery[0]['energy'])+.20 and float(recovery[-1]['energy'])<1,dict(first=recovery[:2],last=recovery[-2:]))
   g.pad(0,-1,sprint=True);g.advance(1500);g.pad(0,0);resumed=[x for x in ev(g,'SPRINT_ENERGY',start)if x['human']=='1'and x['requested']=='1']
   check('a partially recovered reserve funds another sprint',bool(resumed)and min(float(x['energy'])for x in resumed)<float(recovery[-1]['energy']),resumed[-4:])
   for label,button,hold in [('pass',1,160),('cross',2,380),('shot',4,560)]:
    g.reset();start=len(g.read_log());g.pad(0,0,buttons=button);g.advance(hold);g.pad(0,0);g.advance(2600)
    flights=ev(g,'CONTACT_FLIGHT',start);touches=ev(g,'TRAINING_ACTION_TOUCH',start)
    check(label+' uses a real native event with finite contact-dependent angular impulse',bool(flights)and bool(touches)and all('nan'not in x['spin']for x in flights),dict(flights=flights,touches=touches))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
