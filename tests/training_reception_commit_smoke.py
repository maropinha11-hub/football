#!/usr/bin/env python3
"""Standing reception owns its preview/impact/recovery, with assisted alternatives."""
import argparse,json,re,math
from pathlib import Path
from native_training_harness import NativeTraining
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--display',default=':116');a=p.parse_args()
report={'result':'running','checks':[]}
def rows(text,prefix):
 return [{k:float(v)for k,v in re.findall(r'(\w+)=(-?[\d.]+)',l)}for l in text.splitlines()if l.startswith(prefix+' ')]
def check(name,ok,evidence):
 r={'check':name,'result':'passed'if ok else'failed','evidence':evidence};report['checks'].append(r);print(json.dumps(r),flush=True)
try:
 with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=2,config_overrides={'context_x':'320','context_y':'180'})as g:
  for attempt in range(6):
   g.reset()
   g.advance(attempt*70);start=len(g.log.read_text());g.keys(['F5'],True);g.keys(['F5'],False)
   frames=[]
   if attempt%3:
    look='Down'if attempt%3==1 else'Right';g.keys([look],True);frames.extend(g.advance(250));g.keys([look],False)
   frames.extend(g.advance(3400))
   text=g.log.read_text()[start:];hits=rows(text,'TRAINING_CHEST_TOUCH');states=rows(text,'TRAINING_CHEST_STATE')
   check('standing attempt '+str(attempt)+' completes one physical chest control',len(hits)==1 and abs(hits[0]['gap'])<=.0011 and states[-1]['phase']==150,
         {'contacts':hits,'final_phase':states[-1]['phase']if states else None,'accidental_contacts':rows(text,'TRAINING_BODY_TOUCH')})
   waiting=[f for f in frames if hits and f['t']<hits[0]['t']]
   check('standing attempt '+str(attempt)+' waits at the reception point',bool(waiting)and
         max(math.dist(f['player'][:2],waiting[0]['player'][:2])for f in waiting)<.04,
         {'displacement_m':max((math.dist(f['player'][:2],waiting[0]['player'][:2])for f in waiting),default=None),'waiting_commands':len(rows(text,'TRAINING_RECEPTION_WAIT'))})
  for label,stick in [('advance',(0,-1)),('retreat',(0,1)),('lateral choice',(1,0))]:
   g.reset();start=len(g.log.read_text());g.keys(['F5'],True);g.keys(['F5'],False)
   delivery=rows(g.log.read_text()[start:],'TRAINING_DELIVERY')[-1]['t'];g.wait(lambda:g.frames()[-1]['t']>=delivery+450)
   g.pad(*stick);frames=g.advance(2300);g.pad(0,0);text=g.log.read_text()[start:]
   accepted=[r for r in rows(text,'TRAINING_NATIVE_SURFACE')if r['accepted']]
   check(label+' requests a native reception with a physical contact',not rows(text,'TRAINING_CHEST_TOUCH')and bool(rows(text,'TRAINING_CHEST_CANCEL'))and
      (bool(accepted)or bool(rows(text,'TRAINING_BODY_TOUCH'))),
      {'cancellations':rows(text,'TRAINING_CHEST_CANCEL'),'native_contacts':accepted,'body_contacts':rows(text,'TRAINING_BODY_TOUCH'),
       'lateral_input_seen':any(abs(f['move'][0])>.9 for f in frames)})
   if label=='lateral choice':
    check('lateral reception input is retained by the selector',any(abs(f['move'][0])>.9 for f in frames)and
      any(abs(r['longitudinal'])<.05 and r['speed']<.2 for r in rows(text,'TRAINING_RECEPTION_WAIT')),
      rows(text,'TRAINING_RECEPTION_WAIT')[:8])
  g.reset();start=len(g.log.read_text());g.keys(['F5'],True);g.keys(['F5'],False)
  g.wait(lambda:bool(rows(g.log.read_text()[start:],'TRAINING_CHEST_TOUCH')))
  contact=rows(g.log.read_text()[start:],'TRAINING_CHEST_TOUCH')[0]['t']
  g.wait(lambda:g.frames()[-1]['t']>=contact+450);g.pad(0,-1,buttons=1);g.advance(180);g.pad(0,-1);frames=g.advance(2400)
  text=g.log.read_text()[start:]
  check('a pass after the chest impact exits before full recovery and touches the ball',
        len(rows(text,'TRAINING_CHEST_TOUCH'))==1 and any(r['function']==4 for r in rows(text,'TRAINING_ACTION_TOUCH'))and'TRAINING_ACTION_MISS'not in text,
        {'action_starts':rows(text,'TRAINING_ACTION_START'),'action_contacts':rows(text,'TRAINING_ACTION_TOUCH'),'misses':rows(text,'TRAINING_ACTION_MISS')})
  g.keys(['Escape'],True);g.game.wait(timeout=15);check('clean exit',g.game.returncode==0,g.game.returncode)
 report['result']='passed'if all(r['result']=='passed'for r in report['checks'])else'failed'
except BaseException as e:
 report['result']='failed';report['error']=str(e);raise
finally:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed':raise SystemExit(1)
