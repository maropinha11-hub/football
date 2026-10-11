#!/usr/bin/env python3
"""Exercise the rendered PES source-rig preview through real SDL key events."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

p=argparse.ArgumentParser()
p.add_argument('--build',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
args=p.parse_args();root=Path(__file__).resolve().parents[1]
args.output.mkdir(parents=True,exist_ok=False)
environment=os.environ.copy()
environment.update(DISPLAY=':92',ALSOFT_DRIVERS='null',LIBGL_ALWAYS_SOFTWARE='1',LP_NUM_THREADS='2')
config=args.output/'preview.config'
config.write_text((root/'config/training.config').read_text()+
                  '\n"context_x" "960"\n"context_y" "540"\n"training_camera" "2"\n'+
                  '"pes3_animation_file" '+json.dumps(str(args.bundle.resolve()))+'\n')
log=args.output/'preview-smoke.log';checks=[];game=None;server=None;window=None;held=set()
report={'run_id':str(uuid.uuid4()),'result':'running','checks':checks}
pattern=re.compile(r'PES3_PREVIEW clip=(\d+) phase=([-\d.]+) playing=(\d) revision=(\d+) point16=\[([^]]+)\]')

def states():
    result=[]
    for m in pattern.finditer(log.read_text(errors='replace')):
        result.append({'clip':int(m[1]),'phase':float(m[2]),'playing':int(m[3]),
                       'revision':int(m[4]),'point':[float(v)for v in m[5].split(',')]})
    return result
def wait(predicate,seconds=30):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if game and game.poll() is not None:raise RuntimeError('game exited '+str(game.returncode))
        found=predicate()
        if found:return found
        time.sleep(.05)
    raise TimeoutError('rendered preview readiness/action')
def key(name,down):
    subprocess.run(['xdotool','keydown' if down else 'keyup','--window',window,name],env=environment,check=True)
    if down:held.add(name)
    else:held.discard(name)
def tap(name):
    key(name,True);time.sleep(.12);key(name,False);time.sleep(.12)
def check(name,condition,evidence):
    if not condition:raise AssertionError(name+': '+str(evidence))
    checks.append({'check':name,'result':'passed','evidence':evidence});print('PASS',name,evidence,flush=True)

try:
    server=subprocess.Popen(['Xvfb',':92','-screen','0','960x540x24','-nolisten','tcp'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=environment)
    time.sleep(.3)
    with log.open('w') as stream:
        game=subprocess.Popen([str(args.build.resolve()/'gameplayfootball'),'--training','--pes3-preview','--telemetry','--config',str(config.resolve())],
                              cwd=args.build.resolve(),env=environment,stdout=stream,stderr=subprocess.STDOUT)
    def find_window():
        result=subprocess.run(['xdotool','search','--name','Gameplay'],env=environment,stdout=subprocess.PIPE,text=True)
        return result.stdout.splitlines()
    window=wait(find_window)[-1]
    wait(lambda:'PES3_RENDER clip=47' in log.read_text(errors='replace'))
    check('source bank loaded in native game','PES3_BANK ready clips=1105 bones=19 gameplay_replaced=0' in log.read_text(),1105)
    wait(lambda:states() and states()[-1]['playing']==0)
    samples=states()
    check('19-bone source geometry rendered','bones=19 vertices=888' in log.read_text(),888)
    check('clip advances then clamps',len(samples)>3 and samples[-1]['phase']>0 and
          all(b['phase']>a['phase']for a,b in zip(samples,samples[1:])),samples[-1])
    last=samples[-1]['revision'];time.sleep(.3)
    check('endpoint remains stopped',states()[-1]['revision']==last,last)
    tap('F8');wait(lambda:states()[-1]['clip']==48)
    check('browsing paused clips preserves phase zero',states()[-1]['phase']==0 and states()[-1]['playing']==0,states()[-1])
    tap('F10');wait(lambda:states()[-1]['playing']==1 and states()[-1]['phase']>1)
    tap('F10');wait(lambda:states()[-1]['playing']==0)
    before=states()[-1];time.sleep(.2)
    check('pause holds source phase',states()[-1]['revision']==before['revision'],before)
    tap('F11');wait(lambda:states()[-1]['revision']>before['revision'])
    after=states()[-1]
    check('single source-phase step',after['playing']==0 and abs(after['phase']-before['phase']-1)<.00001,after)
    tap('F9');wait(lambda:states()[-1]['clip']==47)
    tap('c');wait(lambda:states()[-1]['phase']<10)
    # Observed clip IDs, rather than fabricated names for pass/header gestures.
    for expected in (236,313,304,224,219,269,120,372,264,206,797,275,317,366):
        tap('c');wait(lambda:states()[-1]['clip']==expected)
        wait(lambda:'PES3_RENDER clip='+str(expected)+' ' in log.read_text())
    all_states=states()
    check('observed source clips can be rendered',len({s['clip']for s in all_states})>=15,sorted({s['clip']for s in all_states}))
    check('finite source points',all(math.isfinite(v)for s in all_states for v in s['point']),len(all_states))
    tap('F10')
    from PIL import ImageGrab
    ImageGrab.grab(xdisplay=environment['DISPLAY']).save(args.output/'preview.png')
    tap('F7');before=len(states());time.sleep(.3)
    check('closing preview stops source work',len(states())==before,before)
    frames=[json.loads(line[len('TRAINING_FRAME '):])for line in log.read_text().splitlines()if line.startswith('TRAINING_FRAME ')]
    origin=frames[-1]['player']
    key('w',True);time.sleep(1);key('w',False);time.sleep(.2)
    frames=[json.loads(line[len('TRAINING_FRAME '):])for line in log.read_text().splitlines()if line.startswith('TRAINING_FRAME ')]
    check('native training controls remain functional',math.dist(origin,frames[-1]['player'])>.1,frames[-1]['player'])
    key('Escape',True);game.wait(timeout=15)
    check('clean game exit',game.returncode==0,game.returncode)
    report['result']='passed'
except Exception as e:
    report['result']='failed';report['error']=str(e)
    raise
finally:
    if window and game and game.poll() is None:
        for name in list(held):key(name,False)
        game.terminate()
        try:game.wait(timeout=5)
        except subprocess.TimeoutExpired:game.kill();game.wait(timeout=5)
    if server:
        server.terminate()
        try:server.wait(timeout=5)
        except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
    (args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
