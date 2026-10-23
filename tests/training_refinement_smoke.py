"""Rendered analog walking, charged passes, recovery, audio and live restarts."""
import argparse,hashlib,json,math,re
from pathlib import Path
import sys
from native_training_harness import NativeTraining
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/animations'))
from build_situational_catalog import parse_source
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':491');p.add_argument('--match',action='store_true');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',line))for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')]
def key(g,k,mods=[]):g.keys(mods+[k],True);g.advance(80);g.keys(mods+[k],False);g.advance(120)
def mf(g):return[json.loads(line[len('PLAYER_MATCH_FRAME '):])for line in g.read_log().splitlines()if line.startswith('PLAYER_MATCH_FRAME ')]
try:
 config=dict(context_x=480,context_y=270,training_physical_rig='true',training_physical_lab='true',simulation_seed=7)
 if a.match:config.update(player_match='true',player_match_half_seconds=120)
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1 if a.match else 2,config_overrides=config)as g:
  if not a.match:
   speeds=[]
   for strength in [.25,.55,1.]:
    g.reset();g.pad(0,-strength);frames=g.advance(5000);g.pad(0,0)
    # Average complete slow strides, including the contact/recovery phase;
    # a 500 ms tail aliases the 1.68 s walking cycle.
    tail=frames[-36:];speed=math.dist(tail[-1]['player'][:2],tail[0]['player'][:2])/max(.01,(tail[-1]['t']-tail[0]['t'])/1000);speeds.append(speed)
    gap=max(math.dist(f['player'][:2],f['ball'][:2])for f in frames)
    check('stick '+str(strength)+' moves with connected ball control',speed>.25 and gap<1.8,dict(speed=speed,ball_gap=gap))
   check('analog permits walking below the approved full-stick pace',speeds[0]+.30<speeds[1]and speeds[1]+.20<speeds[2]and 2.5<speeds[2]<4.5,speeds)
   powers=[]
   for hold in [40,150,350,750]:
    g.reset();start=len(g.read_log());g.pad(0,0,buttons=1);g.advance(hold);g.pad(0,0);g.advance(2400)
    hits=[x for x in ev(g,'TRAINING_ACTION_TOUCH',start)if x['function']=='4'];power=ev(g,'HUMAN_PASS_POWER',start)
    check(str(hold)+' ms pass makes a real, charge-dependent contact',len(hits)==1 and len(power)==1,dict(hits=hits,power=power))
    powers.append(float(power[0]['speed'])if power else 0)
   check('brief A stays gentle and longer presses progressively strengthen it',0<powers[0]<6 and powers[-1]>19 and all(b>a for a,b in zip(powers,powers[1:])),powers)
   support=ev(g,'PHYSICAL_SUPPORT_COMPLIANCE')
   check('releases visibly recruit the pelvis and knees with bounded planted-foot error',bool(support)and max(float(x['knee'])for x in support)>.002 and all(float(x['foot_error'])<.005 and float(x['sink'])<=.0221 and float(x['tilt'])<=.0451 for x in support),dict(samples=len(support),peak_knee=max([float(x['knee'])for x in support]or[0]),peak_foot_error=max([float(x['foot_error'])for x in support]or[0])))
   g.reset();start=len(g.read_log());g.pad(0,-1,sprint=True);g.advance(1700);g.pad(0,0)
   steps=ev(g,'FIELD_STEP',start);audio=ev(g,'FIELD_AUDIO',start)
   check('planted running feet trigger bounded turf sounds',len(steps)>=2 and all(0<float(x['gain'])<=1 for x in steps),steps[:12])
   check('breathing follows exertion while the ambience is active',bool(audio)and max(float(x['effort'])for x in audio)>.3 and all(0<float(x['breath'])<.4 for x in audio),audio)
   for direction in range(2):
    g.reset();key(g,'F3');start=len(g.read_log());key(g,'F9');g.advance(10000)
    handoff=ev(g,'PHYSICAL_RECOVERY_HANDOFF',start)
    check('get-up '+str(direction)+' hands back a continuous valid standing pose',bool(handoff)and all(abs(float(x['to_z'])-float(x['from_z']))<.04 for x in handoff),handoff)
    brace=[]
    for line in g.read_log()[start:].splitlines():
     if line.startswith('PHYSICAL_RIG_FRAME '):brace.append(json.loads(line[len('PHYSICAL_RIG_FRAME '):]))
    check('fall '+str(direction)+' uses active ground protection',any(x['mode']==1 and x['brace']>0 for x in brace),dict(braced_samples=sum(x['brace']>0 for x in brace)))
  else:
   g.advance(2700)
   for i,name in enumerate(['free_kick','penalty','corner','throw_in','goal_kick']):
    start=len(g.read_log());key(g,'F10');g.advance(3400)
    rows=[f for f in mf(g)if f['set_piece']and f['t']>=g.frames()[-1]['t']-1600]
    moved=[]
    if len(rows)>=2:
     first={x['id']:x for x in rows[0]['players']};last=rows[-1]
     moved=[x['id']for x in last['players']if x['id']!=last['locked_id']and math.dist(first[x['id']]['p'][:2],x['p'][:2])>.18]
    if name!='penalty':check(name+' players make real off-ball runs before release',len(moved)>=2 and bool(ev(g,'RESTART_RUN',start)),dict(moved=moved,run_samples=len(ev(g,'RESTART_RUN',start))))
    check(name+' keeps the ball waiting for the taker',not ev(g,'RESTART_RELEASED',start),ev(g,'RESTART_RELEASED',start))
   key(g,'r');g.advance(2800)
   for trial in range(7):
    key(g,'r');g.advance(2700);start=len(g.read_log());key(g,'F6',['Control_L']);g.advance(2300)
    setup=ev(g,'KEEPER_LAB_SETUP',start)[-1];keeper=setup['actor'];hits=[x for x in ev(g,'TRAINING_ACTION_TOUCH',start)if x.get('actor')==keeper]
    if 2<=trial<=4:
     decisions=[x for x in ev(g,'KEEPER_DECISION',start)if x['actor']==keeper]
     check('keeper backpass '+str(trial)+' actively intercepts with the feet',any('foot'in x.get('part','')for x in hits)and any(x['mode']=='backpass_foot'for x in decisions),dict(hits=hits,decisions=decisions[-4:]))
     check('keeper backpass '+str(trial)+' never uses hands or lets it score',all('elbow'not in x.get('part','')for x in hits)and all(f['home']==0 and f['away']==0 for f in mf(g)if f['t']>=int(setup['t'])),hits)
    if trial in [1,5,6]:
     attempts=[x for x in ev(g,'KEEPER_DIVE_ATTEMPT',start)if x['actor']==keeper]
     plans=[x for x in ev(g,'TRAINING_NATIVE_START',start)if x['function']=='9']
     check('keeper shot '+str(trial)+' attempts an authored save',bool(attempts or plans or hits),dict(attempts=attempts,plans=plans,hits=hits))
     if attempts:
      sides=[]
      for attempt in attempts:
       name=attempt['clip'];mirror=name.endswith('_mirror');path=Path('data')/(name[:-7]if mirror else name)
       _,events,_,_=parse_source(path);shoe_side=events[0][1][0]*(-1 if mirror else 1);target=float(attempt['target_side'])
       sides.append(dict(authored_side=shoe_side,target_side=target))
      check('keeper shot '+str(trial)+' dives toward the incoming side',all(abs(x['authored_side'])<=.2 or abs(x['target_side'])<=.35 or x['authored_side']*x['target_side']>0 for x in sides),sides)
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
