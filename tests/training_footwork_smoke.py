#!/usr/bin/env python3
"""Exercise RT sole work and the contact-generated dribble hop in the real game."""
import argparse, hashlib, json, math, re, subprocess
from pathlib import Path
from native_training_harness import NativeTraining

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':193');p.add_argument('--camera',type=int,choices=[1,2],default=1)
a=p.parse_args();r=dict(result='running',checks=[],scenarios={},executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def events(text,prefix):return [dict(re.findall(r'(\w+)=([^\s]+)',s))for s in text.splitlines()if s.startswith(prefix+' ')]
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def point(s):return json.loads(s)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=a.camera,
   config_overrides={'context_x':640,'context_y':360,'training_physical_rig':'true','training_physical_lab':'true'})as g:
  def pad(x,y,**kw):g.pad(*((-y,x)if a.camera==1 else(x,y)),**kw)
  bank=events(g.log.read_text(),'PHYSICAL_SITUATION_BANK')
  check('the running executable includes one thousand contextual profiles',bool(bank)and all(x['profiles']=='1000'for x in bank),bank)
  for name,stick in [('stepover',(0,0)),('sole_right',(1,0)),('sole_left',(-1,0)),('sole_pull',(0,1)),('sole_forward',(0,-1))]:
   g.reset();start=len(g.log.read_text());initial=g.frames()[-1]
   pad(*stick,close=True);g.advance(900)
   if name in ['stepover','sole_right']:
    subprocess.run(['import','-window',g.window,str(a.output/(name+'.png'))],env=g.env,check=True)
   g.wait(lambda:bool(events(g.log.read_text()[start:],'PHYSICAL_FOOTWORK_END')),seconds=18)
   pad(0,0,close=True);g.advance(350);stopped=g.frames()[-1];pad(0,0);g.advance(150);log=g.log.read_text()[start:]
   rows=events(log,'PHYSICAL_FOOTWORK');hits=events(log,'PHYSICAL_FOOTWORK_CONTACT');done=events(log,'PHYSICAL_FOOTWORK_END')
   frames=[f for f in g.frames()if f['t']>=initial['t']]
   travel=math.dist(initial['ball'][:2],stopped['ball'][:2]);root=math.dist(initial['player'][:2],stopped['player'][:2])
   feet=[point(x['ankle'])for x in rows];support=[point(x['support'])for x in rows]
   data=dict(samples=len(rows),contacts=len(hits),ball_travel_m=travel,root_travel_m=root,
     maximum_speed_mps=max(float(x['speed'])for x in rows),minimum_gap_m=min(float(x['gap'])for x in rows),
     support_drift_m=max(math.dist(support[0],s)for s in support),ankle_height_range_m=max(s[2]for s in feet)-min(s[2]for s in feet),maximum_measured_ankle_speed_mps=max(math.dist(feet[i-1],feet[i])/((int(rows[i]['t'])-int(rows[i-1]['t']))*.001)for i in range(1,len(rows))if int(rows[i]['t'])>int(rows[i-1]['t'])))
   r['scenarios'][name]=data
   check(name+' completes one bounded gesture with planted support',len(done)==1 and len(rows)>50 and root<.10 and data['support_drift_m']<.003 and data['maximum_speed_mps']<=.951 and data['ankle_height_range_m']>.08 and data['minimum_gap_m']>-.001 and data['maximum_measured_ankle_speed_mps']<1.35,data)
   if name=='stepover':check('passing the foot over the ball supplies no invisible touch',not hits and travel<.035 and data['minimum_gap_m']>-.001,data)
   else:check(name+' rolls only through measured sole contact',len(hits)>=3 and .035<travel<.40 and all(-.0011<=float(x['gap'])<=.00251 for x in hits),data)
  # The neutral RT gesture must leave native pass input available afterwards.
  g.reset();pad(0,0,buttons=1);g.advance(150);pad(0,0);start=len(g.log.read_text());g.advance(1800)
  check('a native pass remains available after RT is released',bool(events(g.log.read_text()[start:],'TRAINING_ACTION_TOUCH')),'native contact after RT exercises')
  g.reset();start=len(g.log.read_text());pad(0,0,close=True)
  g.wait(lambda:bool(events(g.log.read_text()[start:],'PHYSICAL_FOOTWORK_END')),seconds=18)
  start=len(g.log.read_text());pad(0,0,close=True,buttons=1);g.advance(150);pad(0,0,close=True);g.advance(1800)
  check('holding RT after a gesture does not block a queued native pass',any(x['function']=='4'for x in events(g.log.read_text()[start:],'TRAINING_ACTION_TOUCH')),'RT held during native pass')
  pad(0,0);g.reset();start=len(g.log.read_text());pad(0,0,close=True);g.advance(700)
  pad(0,0,close=True,buttons=1);g.advance(150);pad(0,0,close=True)
  g.wait(lambda:any(x['function']=='4'for x in events(g.log.read_text()[start:],'TRAINING_ACTION_TOUCH')),seconds=18)
  check('a queued pass interrupts sole work and completes after safe foot return',bool(events(g.log.read_text()[start:],'PHYSICAL_FOOTWORK_END')),'safe return followed by real native pass')
  pad(0,0)
  g.reset();start=len(g.log.read_text());pad(0,-1);frames=g.advance(4500);pad(0,0)
  hops=events(g.log.read_text()[start:],'PHYSICAL_CONTROL_HOP')
  check('small grounded dribble impulses produce bounded physical lift',len(hops)>=2 and all(0<float(x['vz'])<=.851 for x in hops)
    and any(.121<f['ball'][2]<.20 for f in frames),dict(hops=hops,maximum_ball_height_m=max(f['ball'][2]for f in frames)))
  check('dribble hops keep the native player attached to a playable ball',max(math.dist(f['ball'][:2],f['player'][:2])for f in frames)<2.0,'same native action/contact path')
  arms=events(g.log.read_text(),'PHYSICAL_ARM_RENDER')
  check('procedural feet and torso preserve final anatomical arm limits',len(arms)>100 and max(float(x['error'])for x in arms)<1e-5 and max(float(x['penetration'])for x in arms)<.004,dict(samples=len(arms)))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as error:r.update(result='failed',error=str(error));raise
finally:a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
