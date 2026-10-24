"""Observe actual rendered feet/torso in a 22-player physical match."""
import argparse,hashlib,json,math,re,statistics,subprocess
from pathlib import Path
from native_training_harness import NativeTraining

p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':1810');p.add_argument('--mode',choices=['walk','receive'],required=True);a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',line))for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')]
def visible(g,start=0):
 rows=[json.loads(line[16:])for line in g.read_log()[start:].splitlines()if line.startswith('VISIBLE_PHYSICS ')]
 return list({(x['t'],x['actor']):x for x in rows}.values())
def key(g,k,mods=()):g.keys([*mods,k],True);g.advance(100);g.keys([*mods,k],False);g.advance(100)
def reset(g):g.pad(0,0);key(g,'r');g.advance(2700)
def capture(g,name):subprocess.run(['import','-window',g.window,str(a.output/name)],env=g.env,check=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=640,context_y=360,training_physical_rig='true',training_physical_lab='true',player_match='true',player_match_half_seconds=120,player_match_all_restarts='false',simulation_seed=7))as g:
  if a.mode=='walk':
   speeds=[]
   for strength in [.35,.50,.68]:
    reset(g);key(g,'F4',['h','Control_L','Shift_L']);start=len(g.read_log());yaw=g.frames()[-1]['player_yaw'];g.pad(math.cos(yaw)*strength,-math.sin(yaw)*strength);f=g.advance(5000);capture(g,'walk-'+str(strength)+'.png');g.pad(0,0)
    rows=[x for x in visible(g,start)if x['human'] and x['t']>f[0]['t']+800];tail=f[-25:]
    speed=math.dist(tail[0]['player'][:2],tail[-1]['player'][:2])/((tail[-1]['t']-tail[0]['t'])/1000);speeds.append(speed)
    walk=[x for x in rows if x['walk']>.90 and x['slow']]
    check('off-ball ordinary stick '+str(strength)+' displays a complete walking gait',bool(rows)and len(walk)/len(rows)>.75 and .25<speed<1.8,dict(speed=speed,samples=len(rows),walking=len(walk),kinds=sorted({x['kind']for x in rows})))
    heights={foot:[x[foot][2]for x in walk]for foot in ['left','right']}
    support=sum(min(x['left'][2],x['right'][2])<.16 for x in walk)/max(1,len(walk))
    slip=[]
    for previous,current in zip(walk,walk[1:]):
     dt=(current['t']-previous['t'])/1000
     if not .015<dt<.12:continue
     for foot in ['left','right']:
      if max(previous[foot][2],current[foot][2])<.12 and abs(current[foot][2]-previous[foot][2])/dt<.2:
       slip.append(math.dist(previous[foot][:2],current[foot][:2])/dt)
    check('off-ball stick '+str(strength)+' has alternating visible swing and grounded support',bool(walk)and all(max(v,default=0)-min(v,default=0)>.02 for v in heights.values())and support>.80,dict(height_ranges={k:[min(v,default=0),max(v,default=0)]for k,v in heights.items()},support_fraction=support))
    check('off-ball stick '+str(strength)+' support feet stay on the pitch rather than sliding at root speed',bool(slip)and statistics.median(slip)<.55,dict(stance_samples=len(slip),median_slip_mps=statistics.median(slip)if slip else None,root_speed=speed))
   check('walking fixture stays in play without teleporting the human',max(math.dist(x['player'][:2],y['player'][:2])for x,y in zip(f,f[1:]))<.30,dict(maximum_frame_displacement=max(math.dist(x['player'][:2],y['player'][:2])for x,y in zip(f,f[1:]))))
   check('ordinary walking pressures give progressively greater travel',speeds[0]+.06<speeds[-1],speeds)
  else:
   for cpu in [False,True]:
    for name,k,mods in [('ground','F4',[]),('side','F4',['Shift_L']),('chest','F5',[]),('belly','F5',['Control_L']),('hard','F5',['Control_L','Shift_L'])]:
     reset(g);start=len(g.read_log());key(g,k,(['h']if cpu else[])+mods);g.advance(400 if name in ['ground','side']else 250);capture(g,('cpu-'if cpu else'human-')+name+'.png');g.advance(1800 if name in ['ground','side']else 1950)
     delivery=ev(g,'TRAINING_DELIVERY',start);actor=delivery[0]['actor']if delivery else''
     contacts=[x for x in ev(g,'TRAINING_ACTION_TOUCH',start)+ev(g,'TRAINING_BODY_TOUCH',start)if x.get('actor')==actor]
     check(('CPU 'if cpu else'human ')+name+' delivery meets its intended actor on the actual skin',bool(delivery)and bool(contacts),dict(delivery=delivery,contacts=contacts))
     render=[x for x in ev(g,'PHYSICAL_SITUATION_RENDER',start)if x['actor']==actor]
     reaction=[x for x in ev(g,'PHYSICAL_BALL_REACTION',start)if x['actor']==actor]
     poses=[x for x in visible(g,start)if str(x['actor'])==actor]
     delta=max([math.dist(x['torso'],y['torso'])for x in poses for y in poses]or[0])
     moved=any(float(x['trunk'])>.04 and float(x['arms'])>.04 for x in render)
     check(('CPU 'if cpu else'human ')+name+' has a rendered upper-body response',bool(contacts)and bool(poses)and (moved or (bool(reaction)and delta>.04) or (any(x.get('part')=='trunk'for x in contacts)and delta>.08)),dict(poses=len(poses),torso_direction_range=delta,peak_trunk=max([float(x['trunk'])for x in render]or[0]),peak_arms=max([float(x['arms'])for x in render]or[0]),reaction=reaction[:6]))
     if cpu:
      muscles=[x for x in ev(g,'ML_MUSCLE',start)if x['actor']==actor and int(x['samples'])>0]
      check('CPU '+name+' receiver runs the learned angular motor rather than passive tracking',bool(muscles),dict(samples=len(muscles)))
   rows=visible(g);actors={x['id']for x in next(json.loads(line[19:])for line in g.read_log().splitlines()if line.startswith('PLAYER_MATCH_FRAME '))['players']};seen={x['actor']for x in rows};check('final rendered telemetry covers all 22 match actors',len(actors)==22 and actors<=seen,dict(match_actors=sorted(actors),rendered_actors=sorted(seen)))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
