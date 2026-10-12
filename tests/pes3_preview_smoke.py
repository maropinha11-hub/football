#!/usr/bin/env python3
"""Exercise the rendered PES source-rig preview through real SDL key events."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import struct
import time
import uuid

p=argparse.ArgumentParser()
p.add_argument('--build',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
args=p.parse_args();root=Path(__file__).resolve().parents[1]
args.output.mkdir(parents=True,exist_ok=False)
environment=os.environ.copy()
runtime=args.output.resolve()/'xdg-runtime';runtime.mkdir(mode=0o700)
environment.update(DISPLAY=':92',SDL_VIDEODRIVER='x11',ALSOFT_DRIVERS='null',LIBGL_ALWAYS_SOFTWARE='1',LP_NUM_THREADS='2',
                   XDG_RUNTIME_DIR=str(runtime),XDG_CACHE_HOME=str(args.output.resolve()/'xdg-cache'))
config=args.output/'preview.config'
config.write_text((root/'config/training.config').read_text()+
                  '\n"context_x" "960"\n"context_y" "540"\n"training_camera" "2"\n'+
                  '"pes3_animation_file" '+json.dumps(str(args.bundle.resolve()))+'\n'+
                  '"pes3_preview_units_per_second" "20"\n')
bundle_data=args.bundle.read_bytes()
durations=[struct.unpack_from('<f',bundle_data,32+16*i+4)[0]for i in range(1105)]
log=args.output/'preview-smoke.log';checks=[];game=None;server=None;window=None;held=set()
report={'run_id':str(uuid.uuid4()),'result':'running','study_phase_units_per_second':20,'checks':checks}
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
    with (args.output/'xvfb.log').open('w')as stream:
        server=subprocess.Popen(['Xvfb',':92','-screen','0','960x540x24','-nolisten','tcp'],stdout=stream,stderr=subprocess.STDOUT,env=environment)
    # Wait for an actual X11 connection. A fixed delay can race startup and
    # SDL may silently choose its offscreen driver, leaving no test window.
    until=time.monotonic()+10
    while True:
        if server.poll()is not None:raise RuntimeError('Xvfb exited '+str(server.returncode))
        ready=subprocess.run(['xdpyinfo'],env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if ready.returncode==0:break
        if time.monotonic()>until:raise TimeoutError('X11 server readiness')
        time.sleep(.05)
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
    tap('v');wait(lambda:'PES3_BODY_APPLY joints=13' in log.read_text())
    # Third-person view exposes the skinned native player, not just the graph.
    tap('Tab');tap('Tab')
    tap('F9');wait(lambda:states()[-1]['clip']==47)
    tap('c');wait(lambda:states()[-1]['phase']<10)
    orientation_pattern=re.compile(r'PES3_BODY_ORIENTATION knee_flex=\[([^]]+)\] chest_z=([-\d.]+) head_y=([-\d.]+) toes_y=\[([^]]+)\]')
    old_orientation_count=len(orientation_pattern.findall(log.read_text()))
    wait(lambda:len(orientation_pattern.findall(log.read_text()))>old_orientation_count)
    reference_orientation=orientation_pattern.findall(log.read_text())[-1]
    flex=[float(v)for v in reference_orientation[0].split(',')]
    toes=[float(v)for v in reference_orientation[3].split(',')]
    check('reference body faces forward with authored knee flexion',min(flex)>0 and
          float(reference_orientation[1])<0 and float(reference_orientation[2])<-.99 and max(toes)<-.99,
          {'knee_flex':flex,'chest_z':float(reference_orientation[1]),'head_y':float(reference_orientation[2]),'toes_y':toes})
    from PIL import ImageGrab
    ImageGrab.grab(xdisplay=environment['DISPLAY']).save(args.output/'native-clip-47.png')
    # Observed clip IDs, rather than fabricated names for pass/header gestures.
    for expected in (236,313,304,224,219,269,120,372,264,206,797,275,317,366):
        tap('c');wait(lambda:states()[-1]['clip']==expected)
        wait(lambda:'PES3_RENDER clip='+str(expected)+' ' in log.read_text())
        tap('F10');wait(lambda:states()[-1]['clip']==expected and states()[-1]['phase']>0)
        if expected in (236,269,797,366):
            wait(lambda:states()[-1]['phase']>=durations[expected]*.4)
            ImageGrab.grab(xdisplay=environment['DISPLAY']).save(args.output/('native-clip-'+str(expected)+'.png'))
        wait(lambda:states()[-1]['playing']==0)
        check('native body playback completes clip '+str(expected),
              abs(states()[-1]['phase']-durations[expected])<.0001,states()[-1]['phase'])
    all_states=states()
    check('observed source clips can be rendered',len({s['clip']for s in all_states})>=15,sorted({s['clip']for s in all_states}))
    check('finite source points',all(math.isfinite(v)for s in all_states for v in s['point']),len(all_states))
    body_pattern=re.compile(r'PES3_BODY_APPLY joints=13 knee=\[([^]]+)\] ankles_z=\[([^]]+)\] head_z=([-\d.]+)')
    bodies=[([float(v)for v in m[1].split(',')],[float(v)for v in m[2].split(',')],float(m[3]))for m in body_pattern.finditer(log.read_text())]
    check('source rotations reach the native player',len(bodies)>10 and len({tuple(b[0])for b in bodies})>10,len(bodies))
    check('native study rotations and positions finite',all(math.isfinite(v)for q,feet,head in bodies for v in q+feet+[head]) and
          all(abs(sum(v*v for v in q)-1)<.00002 for q,_,_ in bodies),len(bodies))
    geometry=re.findall(r'PES3_BODY_GEOMETRY direction_error=([-\d.]+) root_z=([-\d.]+)',log.read_text())
    check('physical limb directions follow source segments',len(geometry)>100 and
          all(math.isfinite(float(e))and float(e)<.00002 for e,_ in geometry),max(float(e)for e,_ in geometry))
    applied=re.findall(r'PES3_BODY_GEOMETRY[^\n]*root_z=([-\d.]+) applied_root_z=([-\d.]+) applied_fk_error=([-\d.]+)',log.read_text())
    check('applied native bones match the solved pose in actor facing',len(applied)>100 and
          all(abs(float(expected)-float(actual))<.00001 and math.isfinite(float(error))and float(error)<.00005
              for expected,actual,error in applied),max(float(error)for _,_,error in applied))
    skin=re.findall(r'PES3_BODY_SKIN vertices=(\d+) invalid=(\d+) rigid_error=([-\d.]+) foot_min_z=([-\d.]+) radius=([-\d.]+)',log.read_text())
    check('actual native skin remains finite without rigid stretching',len(skin)>100 and
          all(int(n)>500 and int(bad)==0 and math.isfinite(float(error))and float(error)<.00002 and
              math.isfinite(float(radius))and float(radius)<4 for n,bad,error,_,radius in skin),len(skin))
    check('actual foot vertices stay above the pitch',all(math.isfinite(float(z))and float(z)>=.007 for _,_,_,z,_ in skin),
          min(float(z)for _,_,_,z,_ in skin))
    # Holding a paused pose must not accumulate the pelvis height correction.
    count=len(skin);time.sleep(.5)
    paused=re.findall(r'PES3_BODY_SKIN vertices=(\d+) invalid=(\d+) rigid_error=([-\d.]+) foot_min_z=([-\d.]+) radius=([-\d.]+)',log.read_text())[count:]
    check('paused body retains stable ground support',len(paused)>2 and
          max(float(s[3])for s in paused)-min(float(s[3])for s in paused)<.00001,len(paused))
    ImageGrab.grab(xdisplay=environment['DISPLAY']).save(args.output/'preview.png')
    tap('v');before=len(body_pattern.findall(log.read_text()));time.sleep(.3)
    check('closing body study restores native animation',len(body_pattern.findall(log.read_text()))==before and
          'PES3_BODY_RESTORE native=1' in log.read_text(),before)
    tap('v');wait(lambda:len(body_pattern.findall(log.read_text()))>before)
    key('w',True);time.sleep(.3);key('w',False);time.sleep(.2)
    released=len(body_pattern.findall(log.read_text()));time.sleep(.2)
    check('movement automatically restores gameplay pose','PES3_BODY released reason=gameplay_input' in log.read_text() and
          len(body_pattern.findall(log.read_text()))==released,released)
    for action_key in ('j','k','i','l','Shift_L','space'):
        old_count=len(body_pattern.findall(log.read_text()))
        old_releases=log.read_text().count('PES3_BODY released reason=gameplay_input')
        tap('v');wait(lambda:len(body_pattern.findall(log.read_text()))>old_count)
        tap(action_key);wait(lambda:log.read_text().count('PES3_BODY released reason=gameplay_input')>old_releases)
        held_count=len(body_pattern.findall(log.read_text()));time.sleep(.2)
        check('action restores gameplay pose '+action_key,len(body_pattern.findall(log.read_text()))==held_count,held_count)
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
