#!/usr/bin/env python3
"""Rendered incoming deliveries, geometry and standing chest control on the native rig."""
import argparse,json,math,re,subprocess
from pathlib import Path
from native_training_harness import NativeTraining
parser=argparse.ArgumentParser()
parser.add_argument('--build',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--display',default=':96')
args=parser.parse_args();report={'result':'running','checks':[]}
def rows(text,prefix):
    return [{k:float(v)for k,v in re.findall(r'(\w+)=(-?[\d.]+)',line)}for line in text.splitlines()if line.startswith(prefix+' ')]
def check(name,ok,evidence):
    report['checks'].append({'check':name,'result':'passed'if ok else'failed','evidence':evidence})
    print(('PASS 'if ok else'FAIL ')+name+': '+str(evidence),flush=True)
try:
    with NativeTraining(args.build,args.output/'game',display=args.display,analog_pad=True,camera=1)as game:
        check('non-looping chest animation loads','TRAINING_CHEST_LOADED frames=151'in game.log.read_text(),'1.5 seconds; 151 native samples')
        for attempt in range(3):
            game.reset()
            if attempt:
                game.pad(0,1 if attempt==1 else -1);game.advance(700);game.pad(0,0);game.advance(900)
            start=len(game.log.read_text())
            game.keys(['F5'],True);game.advance(400);game.keys(['F5'],False)
            first=game.advance(450)
            subprocess.run(['ffmpeg','-nostdin','-loglevel','error','-y','-f','x11grab','-video_size','960x540',
                '-i',game.env['DISPLAY'],'-frames:v','1',str(args.output/('chest-'+str(attempt)+'.png'))],env=game.env,check=True)
            after=game.advance(2000);segment=game.log.read_text()[start:]
            delivery=rows(segment,'TRAINING_DELIVERY');touch=rows(segment,'TRAINING_CHEST_TOUCH');pose=rows(segment,'TRAINING_CHEST_POSE')
            state=[s for s in rows(segment,'TRAINING_CHEST_STATE') if s['phase']>0]
            check('chest delivery '+str(attempt)+' launches once',len(delivery)==1 and delivery[0]['error']<.005,delivery)
            starts=rows(segment,'TRAINING_CHEST_START')
            check('chest delivery '+str(attempt)+' presents the animation from its first pose',
                  len(starts)==1 and starts[0]['phase']<=0,starts)
            check('chest delivery '+str(attempt)+' makes one real body contact',len(touch)==1 and
                  abs(touch[0]['gap'])<=.0011 and touch[0]['correction']<.09,touch)
            check('chest delivery '+str(attempt)+' plays through recovery',bool(state) and
                  max(s['phase']for s in state)>140 and all(b['phase']>=a['phase']for a,b in zip(state,state[1:])),
                  {'phases':[state[0]['phase'],state[-1]['phase']]if state else [],'pose_samples':len(pose)})
            check('chest delivery '+str(attempt)+' leaves a reachable ball',math.dist(after[-1]['ball'][:2],after[-1]['player'][:2])<1.4,
                  {'distance':math.dist(after[-1]['ball'][:2],after[-1]['player'][:2]),'height':after[-1]['ball'][2]})
        game.reset();start=len(game.log.read_text());game.keys(['F4'],True);game.keys(['F4'],False);low=game.advance(2500)
        segment=game.log.read_text()[start:]
        check('ground pass uses foot reception and does not start chest control',
              'TRAINING_ACTION_TOUCH'in segment and 'TRAINING_CHEST_START'not in segment,
              {'native_touches':segment.count('TRAINING_ACTION_TOUCH'),'chest':segment.count('TRAINING_CHEST_START')})
        game.reset();start=len(game.log.read_text());game.keys(['F6'],True);game.keys(['F6'],False);high=game.advance(1300)
        segment=game.log.read_text()[start:]
        actual=rows(segment,'TRAINING_CHEST_TOUCH')
        check('high crossing travels above chest and any assisted chest reception meets real skin',
              max(f['ball'][2]for f in high)>3 and all(abs(t['gap'])<=.0011 for t in actual),
              {'maximum_height':max(f['ball'][2]for f in high),'actual_chest_contacts':actual})
        for key,part in [('F4','foot'),('F6','head')]:
            game.reset();start=len(game.log.read_text());game.keys([key],True);game.keys([key],False)
            game.pad(0,0,buttons=1);game.advance(300);game.pad(0,0);game.advance(1500)
            segment=game.log.read_text()[start:]
            contacts=re.findall(r'TRAINING_ACTION_TOUCH t=(\d+) part=(\w+) function=(\d+)',segment)
            check(key+' permits a native first-time pass',bool(contacts) and int(contacts[0][2])==4 and
                  (contacts[0][1]=='head'if part=='head'else contacts[0][1].endswith('foot')),contacts)
        game.reset();start=len(game.log.read_text());game.keys(['F5'],True)
        delivery=rows(game.log.read_text()[start:],'TRAINING_DELIVERY')[-1]['t']
        game.wait(lambda:game.frames()[-1]['t']>=delivery+600)
        move_started=game.frames()[-1]['t'];game.pad(1,0)
        game.keys(['F5'],False);moving=game.advance(700);game.pad(0,0)
        segment=game.log.read_text()[start:]
        # The original engine can receive through a controlled skin collision
        # in Movement as well as through a dedicated Trap animation.
        check('advancing before impact returns to native physical reception',
              'TRAINING_CHEST_START'in segment and 'TRAINING_CHEST_CANCEL'in segment and
              'TRAINING_CHEST_TOUCH'not in segment and
              (any(s['accepted']for s in rows(segment,'TRAINING_NATIVE_SURFACE')) or
               bool(rows(segment,'TRAINING_BODY_TOUCH'))) and
              moving[-1]['speed']>2 and
              move_started-delivery<800,
              {'speed':moving[-1]['speed'],'chest_touches':segment.count('TRAINING_CHEST_TOUCH'),
               'native_trap_selected':any(f['function']==3 for f in moving),
               'physical_body_contacts':rows(segment,'TRAINING_BODY_TOUCH'),
               'movement_after_delivery_ms':move_started-delivery})
        native=rows(game.log.read_text(),'TRAINING_NATIVE_SURFACE');accepted=[n for n in native if n['accepted']]
        check('native impulses are gated on actual skin contact',bool(accepted)and all(-.001<=n['gap']<=.0021 for n in accepted),
              {'accepted_contacts':len(accepted),'maximum_gap':max((n['gap']for n in accepted),default=None)})
        game.keys(['Escape'],True);game.game.wait(timeout=15);check('clean exit',game.game.returncode==0,game.game.returncode)
    report['result']='passed'if all(c['result']=='passed'for c in report['checks'])else'failed'
except BaseException as error:
    report['result']='failed';report['error']=str(error);raise
finally:
    args.output.mkdir(parents=True,exist_ok=True);(args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
if report['result']!='passed':raise SystemExit(1)
