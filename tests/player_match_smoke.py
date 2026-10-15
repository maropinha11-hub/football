#!/usr/bin/env python3
"""Rendered 11v11 test: locked player, CPU pass requests, halves and restart."""
import argparse,hashlib,json,math,re,subprocess,time
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':154');a=p.parse_args()
r={'result':'running','checks':[],'executable_sha256':hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest()}
def ev(s,p):return[dict(re.findall(r'(\w+)=([^\s]+)',x))for x in s.splitlines()if x.startswith(p+' ')]
def mf(g):return[json.loads(x[19:])for x in g.log.read_text().splitlines()if x.startswith('PLAYER_MATCH_FRAME ')]
def check(name,ok,evidence):
 x={'check':name,'result':'passed'if ok else'failed','evidence':evidence};r['checks'].append(x);print(json.dumps(x),flush=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,config_overrides={'context_x':320,'context_y':180,'player_match':'true','player_match_half_seconds':8,'simulation_seed':7})as g:
  locked=mf(g)[-1]['locked_id'];g.advance(2500)
  check('native CPU kickoff starts normal play',mf(g)[-1]['in_play']==1 and mf(g)[-1]['set_piece']==0,mf(g)[-1])
  start=len(g.log.read_text());g.pad(0,0,close=True);g.advance(600)
  check('RT requests a pass through raw Xbox trigger input',len(ev(g.log.read_text()[start:],'PLAYER_MATCH_PASS_REQUEST'))==1,ev(g.log.read_text()[start:],'PLAYER_MATCH_PASS_REQUEST'))
  g.advance(600);check('holding RT does not repeat pass requests',len(ev(g.log.read_text()[start:],'PLAYER_MATCH_PASS_REQUEST'))==1,{})
  g.pad(0,0);g.wait(lambda:any(x['requested']=='1'for x in ev(g.log.read_text()[start:],'PLAYER_MATCH_ACTION')),seconds=15)
  passes=[x for x in ev(g.log.read_text()[start:],'PLAYER_MATCH_ACTION')if x['requested']=='1']
  check('CPU physically executes the requested native pass to the locked player',len(passes)==1 and int(passes[0]['actor'])!=locked and int(passes[0]['target'])==locked and passes[0]['team']=='0'and passes[0]['action']in('4','5','6'),passes)
  # LB must not switch the player, including after possession changed.
  g.pad(0,-1,buttons=1<<9);origin=g.frames()[-1];f=g.advance(550);g.pad(0,0)
  check('locked player still responds to the approved movement input',math.dist(origin['player'][:2],f[-1]['player'][:2])>.12,{'travel_m':math.dist(origin['player'][:2],f[-1]['player'][:2])})
  g.keys(['Tab'],True);g.keys(['Tab'],False);g.advance(150);g.keys(['Tab'],True);g.keys(['Tab'],False);g.advance(200)
  check('external camera can inspect the same player',g.frames()[-1]['camera']==1,g.frames()[-1]['camera'])
  subprocess.run(['import','-window',g.window,str(a.output/'match-11v11.png')],env=g.env,check=True)
  g.wait(lambda:'PLAYER_MATCH_END 'in g.log.read_text(),seconds=75)
  frames=mf(g);actions=ev(g.log.read_text(),'PLAYER_MATCH_ACTION');ends=ev(g.log.read_text(),'PLAYER_MATCH_END')
  check('all match frames contain two teams of eleven',bool(frames)and all(sum(p['team']==side for p in x['players'])==11 for x in frames for side in(0,1)),{'frames':len(frames)})
  check('one and the same player remains human controlled through both halves',all(x['human_count']==1 and x['selected_id']==x['locked_id']==locked and[p['id']for p in x['players']if p['human']]==[locked]for x in frames),{'locked_id':locked,'frames':len(frames)})
  for side in (0,1):
   speeds=[p['speed']for x in frames for p in x['players']if p['team']==side and not p['human']]
   check('team '+str(side)+' uses active CPU movement and ball actions',max(speeds)>3 and any(int(x['team'])==side for x in actions),{'peak_speed_mps':max(speeds),'actions':sum(int(x['team'])==side for x in actions)})
  check('both halves complete without a menu or automatic player switch',{1,2}<={x['phase']for x in frames}and len(ends)==1 and max(x['clock']for x in frames)>=5400000,{'phases':sorted({x['phase']for x in frames}),'end':ends,'clock_ms':max(x['clock']for x in frames)})
  # The stopped clock must not advance after full time; R restarts this match.
  clock=mf(g)[-1]['clock'];time.sleep(.25);check('full-time clock stops',mf(g)[-1]['clock']==clock,clock)
  g.keys(['r'],True);g.keys(['r'],False);g.advance(500)
  check('R restarts kickoff and score while retaining the controlled player',bool(ev(g.log.read_text(),'PLAYER_MATCH_RESTART'))and mf(g)[-1]['locked_id']==locked and mf(g)[-1]['home']==mf(g)[-1]['away']==0 and mf(g)[-1]['clock']<2700000,mf(g)[-1])
  # E is the keyboard alternative; wait for the restarted CPU kickoff.
  g.advance(2300);start=len(g.log.read_text());g.keys(['e'],True);g.keys(['e'],False);g.advance(200)
  check('E provides the same pass request on the keyboard',bool(ev(g.log.read_text()[start:],'PLAYER_MATCH_PASS_REQUEST')),ev(g.log.read_text()[start:],'PLAYER_MATCH_PASS_REQUEST'))
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit with both complete teams',g.game.returncode==0,g.game.returncode)
 r['result']='passed'if all(x['result']=='passed'for x in r['checks'])else'failed'
except BaseException as e:r['result']='failed';r['error']=str(e);raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
