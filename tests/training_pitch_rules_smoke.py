#!/usr/bin/env python3
"""Rendered turf, offset reception, restart and tackle regressions."""
import argparse,hashlib,json,math,re
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':199');p.add_argument('--mode',choices=['turf','receive','rules','body','tackle'],default='turf');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def ev(g,p,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in g.read_log()[start:].splitlines()if x.startswith(p+' ')]
def mf(g):return[json.loads(x[19:])for x in g.read_log().splitlines()if x.startswith('PLAYER_MATCH_FRAME ')]
def key(g,k,mods=[]):
 g.keys(mods+[k],True);g.advance(120);g.keys(mods+[k],False);g.advance(100)
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def config(match=False):return dict(context_x=480,context_y=270,training_physical_rig='true',training_physical_lab='true',player_match='true'if match else'false',player_match_half_seconds=120,simulation_seed=7)
try:
 if a.mode=='turf':
  heights=[]
  for rough in [0,.65]:
   with NativeTraining(a.build,a.output/('rough-'+str(rough)),display=a.display,analog_pad=True,config_overrides={**config(),'training_turf_roughness':rough})as g:
    g.reset();g.pad(0,0,buttons=1);g.advance(180);g.pad(0,0);g.wait(lambda:bool(ev(g,'TRAINING_ACTION_TOUCH')));g.advance(150);start=len(g.read_log());begin=g.frames()[-1]['t'];f=g.advance(2600)
    log=g.read_log()[start:];contacts=ev(g,'TURF_CONTACT',start)
    check('free delivery remains independent of foot contacts rough='+str(rough),not ev(g,'TRAINING_ACTION_TOUCH',start),dict(contacts=ev(g,'TRAINING_ACTION_TOUCH',start)))
    heights.append([x['ball'][2]for x in f]);check('free trajectory is finite rough='+str(rough),all(math.isfinite(v)for x in f for v in x['ball']),dict(samples=len(f)))
    forecasts=[]
    for line in log.splitlines():
     m=re.search(r'TURF_FORECAST t=(\d+).*position=\[([^]]+)\] future500=\[([^]]+)\]',line)
     if m:forecasts.append((int(m[1]),[float(x)for x in m[2].split(',')],[float(x)for x in m[3].split(',')]))
    actual={t:p for t,p,_ in forecasts};errors=[math.dist(future,actual[t+500])for t,p,future in forecasts if t+500 in actual and t>begin+50]
    check('500ms forecast matches committed free-ball trajectory rough='+str(rough),bool(errors)and max(errors)<.035,dict(samples=len(errors),maximum_error=max(errors,default=999)))
    if rough:
     check('rough turf applies dissipative spatial normal contacts',len(contacts)>5 and all(float(x['energy_after'])<=float(x['energy_before'])+.001 for x in contacts),dict(samples=len(contacts),examples=contacts[:4]))
     key(g,'g');check('G toggles the same surface used for prediction',bool(ev(g,'TURF_TOGGLE')),ev(g,'TURF_TOGGLE'))
  check('roughness changes the rolling vertical trajectory',max(heights[1])-min(heights[1])>.002 and min(heights[1])>.109,dict(flat_range=[min(heights[0]),max(heights[0])],rough_range=[min(heights[1]),max(heights[1])]))
 elif a.mode=='receive':
  for match in [False,True]:
   with NativeTraining(a.build,a.output/('match'if match else'solo'),display=a.display,analog_pad=True,config_overrides=config(match))as g:
    if match:g.advance(2600)
    for mod in ['Shift_L','Control_L']:
     if not match:g.reset()
     else:key(g,'r');g.advance(2700)
     start=len(g.read_log());key(g,'F4',[mod]);f=g.advance(2600)
     touches=ev(g,'TRAINING_ACTION_TOUCH',start);assist=ev(g,'TRAINING_RECEIVE_ASSIST',start)
     if match:touches=[x for x in touches if x.get('actor')==str(mf(g)[-1]['locked_id'])]
     check(('match 'if match else'solo ')+mod+' offset pass is acquired by the receiver',bool(touches),dict(touches=touches,assist=assist[:4],delivery=ev(g,'TRAINING_DELIVERY',start)))
    if match:
     actors=ev(g,'PHYSICAL_MATCH_ACTOR');check('all 22 physical actors use weighted skin contacts',len({x['actor']for x in actors if x['skin_contacts']=='1'}|{str(mf(g)[-1]['locked_id'])})==22,actors)
     keepers=ev(g,'KEEPER_DECISION');check('both goalkeepers evaluate bounded positioning',len({x['actor']for x in keepers})==2,keepers[:4])
 elif a.mode=='body':
  for match in [False,True]:
   with NativeTraining(a.build,a.output/('match'if match else'solo'),display=a.display,analog_pad=True,config_overrides=config(match))as g:
    if match:g.advance(2600)
    for name,mods in [('chest',[]),('belly',['Control_L']),('driven_chest',['Shift_L'])]:
     if not match:g.reset()
     else:key(g,'r');g.advance(2700)
     start=len(g.read_log());key(g,'F5',mods);g.advance(1900)
     body=ev(g,'TRAINING_BODY_TOUCH',start);actions=ev(g,'TRAINING_ACTION_TOUCH',start)
     # In a live match an opponent may intercept the delivery. Its real skin contact counts too.
     check(('match 'if match else'solo ')+name+' ball meets an actual skin contact',bool(body or actions),dict(body=body,actions=actions))
     check(('match 'if match else'solo ')+name+' body resolution remains finite and sweep bounded',all(math.isfinite(float(x['correction'])) and float(x['correction'])<.6 for x in body),body)
     check(('match 'if match else'solo ')+name+' uses the moving skin sweep for accidental contacts',
       (match or name!='driven_chest' or bool(body)) and all(x.get('moving_skin')=='1' and 8<=int(x['samples'])<=24
         and math.isfinite(float(x['skin_speed'])) and 0<=float(x['skin_speed'])<=18.001 for x in body),body)
 elif a.mode in ['rules','tackle']:
  with NativeTraining(a.build,a.output/'match',display=a.display,analog_pad=True,camera=1,config_overrides=config(True))as g:
   g.advance(2600);locked=mf(g)[-1]['locked_id']
   for index in range(5 if a.mode=='rules'else 0):
    start=len(g.read_log());key(g,'F10');g.advance(1500)
    takers=ev(g,'PLAYER_MATCH_TAKER',start)
    check('restart '+str(index)+' selects the fixed human taker',any(x['actor']==str(locked)and x['team']=='0'for x in takers),takers)
    taken=g.frames()[-1]['t'];aim=(0,1)if index==3 else(-.2,1)if index==2 else(1,0);g.pad(*aim,buttons=4 if index==1 else 1);g.advance(250);g.pad(*aim);g.advance(2200);g.pad(0,0)
    check('restart '+str(index)+' can be taken through normal controls',any(x['actor']==str(locked) and int(x['t'])>taken and x['action']in ['4','5','6','8'] for x in ev(g,'PLAYER_MATCH_ACTION',start)),dict(actions=ev(g,'PLAYER_MATCH_ACTION',start),state={k:v for k,v in mf(g)[-1].items()if k!='players'}))
   # Real native action requests and geometric leg contacts; laboratory only
   # arranges an opponent and possession, never awards a tackle or foul.
   evidence=[]
   for button in ([1,2]if a.mode=='tackle'else[]):
    key(g,'r');g.advance(2700);yaw=g.frames()[-1]['player_yaw'];g.pad(math.cos(yaw),-math.sin(yaw),sprint=True);g.advance(650 if button==2 else 0);yaw=g.frames()[-1]['player_yaw'];pre=[]
    if button==2:
     # B is a cross while in possession. Assign the opponent the ball before
     # requesting the slide, then place it again with the final contact
     # fixture. Otherwise the test can queue a cross before changing sides.
     key(g,'F11');g.advance(100)
     g.pad(math.cos(yaw),-math.sin(yaw),buttons=button,sprint=True);pre=g.advance(100)
    # Capture before setup: telemetry acknowledgement may span a 100ms frame,
    # during which the already-running native slide can legitimately hit.
    start=len(g.read_log());g.keys(['Control_L','F2','F11'],True);g.advance(20);g.keys(['Control_L','F2','F11'],False)
    g.pad(math.cos(yaw),-math.sin(yaw),buttons=button,sprint=True);attempt=pre+g.advance(1000);g.pad(0,0);g.advance(700);check(('standing bote'if button==1 else'sliding tackle')+' selects a native defensive motion',any(x['function']==(11 if button==1 else 13) for x in attempt),dict(functions=sorted({x['function']for x in attempt})))
    evidence+=ev(g,'PHYSICAL_TACKLE',start)
   if a.mode=='tackle':
    check('a late sliding contact trips an opponent through the articulated body',any(x['sliding']=='1' and x['fall']=='1' for x in evidence) and any(x['to']=='1' for x in ev(g,'PHYSICAL_RIG_STATE')),dict(tackles=evidence,states=ev(g,'PHYSICAL_RIG_STATE')))
    check('late real leg contacts are passed to the referee',any(x['foul']=='1'for x in evidence)and bool(ev(g,'PHYSICAL_FOUL')),dict(tackles=evidence,fouls=ev(g,'PHYSICAL_FOUL')))
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
