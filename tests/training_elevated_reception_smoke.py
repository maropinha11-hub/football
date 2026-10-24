"""Mid-height/descending arrivals must move real limbs and leave the body."""
import argparse,hashlib,json,math,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':1910');a=p.parse_args()
r=dict(result='running',checks=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())
def check(name,ok,evidence):
 row=dict(check=name,result='passed'if ok else'failed',evidence=evidence);r['checks'].append(row);print(json.dumps(row),flush=True)
def ev(g,prefix,start=0):return[dict(re.findall(r'(\w+)=([^\s]+)',line))for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')]
def records(g,prefix,start=0):return list({(x['t'],x.get('actor',-1)):x for line in g.read_log()[start:].splitlines()if line.startswith(prefix+' ')for x in [json.loads(line[len(prefix)+1:])]}.values())
def key(g,k,mods=()):g.keys([*mods,k],True);g.advance(100);g.keys([*mods,k],False);g.advance(100)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,config_overrides=dict(context_x=640,context_y=360,training_physical_rig='true',training_physical_lab='true',player_match='true',player_match_half_seconds=120,player_match_all_restarts='false',simulation_seed=7))as g:
  for cpu in [False,True]:
   for name,mods in [('shin',['7']),('thigh',['8']),('belly',['Control_L']),('descending',['9']),('back',['0'])]:
    g.pad(0,0);key(g,'r');g.advance(2700);start=len(g.read_log());key(g,'F5',(['h']if cpu else[])+mods)
    g.advance(450);subprocess.run(['import','-window',g.window,str(a.output/(('cpu-'if cpu else'human-')+name+'.png'))],env=g.env,check=True);f=g.advance(2500)
    deliveries=ev(g,'TRAINING_DELIVERY',start);actor=deliveries[0]['actor']if deliveries else'';when=int(deliveries[0]['t'])if deliveries else 0
    contacts=[x for x in ev(g,'TRAINING_ACTION_TOUCH',start)+ev(g,'TRAINING_BODY_TOUCH',start)if x.get('actor')==actor and int(x['t'])<when+1300]
    title=('CPU 'if cpu else'human ')+name
    check(title+' makes a real skin contact during the arrival',bool(deliveries)and bool(contacts),dict(delivery=deliveries,contacts=contacts))
    poses=[x for x in records(g,'VISIBLE_PHYSICS',start)if str(x['actor'])==actor and x['t']<when+1500]
    limbs=[x for x in records(g,'VISIBLE_LIMBS',start)if str(x['actor'])==actor and x['t']<when+1500]
    torso=max([math.dist(x['torso'],y['torso'])for x in poses for y in poses]or[0])
    elbows=[]
    for x in limbs:
     pose=next((y for y in poses if y['t']==x['t']),None)
     if pose:elbows.append([[v-c for v,c in zip(x[side],pose['pelvis'])]for side in ['left_elbow','right_elbow']])
    arms=max([math.dist(x[side],y[side])for x in elbows for y in elbows for side in [0,1]]or[0])
    check(title+' visibly recruits torso and arms rather than acting as an unmoving wall',torso>.08 and arms>.07,dict(render_samples=len(poses),torso_direction_range=torso,elbow_relative_range_m=arms))
    if name in ['shin','thigh']:
     knee=max([max(x[side][2]for x in limbs)-min(x[side][2]for x in limbs)for side in ['left_knee','right_knee']]or[0]);ankle=max([max(x['left'][2],x['right'][2])for x in poses]or[0])
     check(title+' actually lifts/folds a visible leg to receive the mid-height ball',knee>.05 and ankle>.13,dict(knee_height_range=knee,maximum_ankle_height=ankle,reference=ev(g,'PHYSICAL_RECEIVE_REFERENCE',start)[:5]))
    match=records(g,'PLAYER_MATCH_FRAME',start);attached=[]
    for frame in g.frames():
     if not when+1200<=frame['t']<=when+3000:continue
     nearest=min(match,key=lambda x:abs(x['t']-frame['t']),default=None)
     player=next((x for x in nearest['players']if str(x['id'])==actor),None)if nearest else None
     if player:attached.append(dict(t=frame['t'],height=frame['ball'][2],gap=math.dist(frame['ball'][:2],player['p'][:2]),stuck=frame['ball'][2]>.35 and math.dist(frame['ball'][:2],player['p'][:2])<.55))
    fraction=sum(x['stuck']for x in attached)/max(1,len(attached))
    check(title+' does not remain suspended against a back/thigh after receiving',len(attached)>8 and fraction<.25,dict(attached_fraction=fraction,late_samples=attached))
    impacts=ev(g,'TRAINING_BODY_TOUCH',start)
    check(title+' keeps finite bounded real body-contact resolution',all(math.isfinite(float(x['correction']))and float(x['correction'])<.6 for x in impacts),dict(body_contacts=len(impacts),peak_correction=max([float(x['correction'])for x in impacts]or[0])))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
