#!/usr/bin/env python3
"""Exercise an early shin cushion through the real rendered skin solver."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from native_training_harness import NativeTraining

p=argparse.ArgumentParser()
p.add_argument('--build',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--display',default=':3920')
a=p.parse_args()
r=dict(result='running',checks=[],attempts=[],executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest())

def events(g,prefix,start):
    return [dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in g.read_log()[start:].splitlines() if line.startswith(prefix+' ')]

def key(g,names):
    g.keys(names,True);g.advance(100);g.keys(names,False);g.advance(100)

def check(name,ok,evidence):
    row=dict(check=name,result='passed' if ok else 'failed',evidence=evidence)
    r['checks'].append(row);print(json.dumps(row),flush=True)

try:
    with NativeTraining(a.build,a.output/'game',display=a.display,analog_pad=True,camera=1,
            config_overrides=dict(context_x=480,context_y=270,training_physical_rig='true',
                training_physical_lab='true',player_match='true',player_match_half_seconds=120,
                player_match_all_restarts='false',simulation_seed=7,training_contact_verify='true',
                training_performance='true')) as g:
        for attempt in range(12):
            g.pad(0,0);key(g,['r']);g.advance([2700,2100,3300][attempt//4])
            start=len(g.read_log())
            mods=['Shift_L'] if attempt%2==0 else ['Control_L']
            if attempt%4<2:mods.append('z')
            key(g,[*mods,'F4']);g.advance(1750)
            received=events(g,'PREPARED_BODY_RECEPTION',start)
            r['attempts'].append(dict(index=attempt,keys=mods,
                delivery=events(g,'TRAINING_DELIVERY',start),prepared=received))
            if received:break
        prepared=[event for attempt in r['attempts'] for event in attempt['prepared']]
        check('a genuine planned reception finishes on the early leg skin contact',bool(prepared),prepared)
        check('cushion contacts are actual leg surfaces and dissipate incoming pass energy',bool(prepared) and all(
            -.001<float(e['skin_gap'])<=.00051 and float(e['outgoing'])<float(e['incoming']) and
            any(part in e['part'] for part in ['thigh','knee','ankle']) for e in prepared),prepared)
        states=events(g,'PHYSICAL_ACTIVE_STATE',0)
        check('no ragdoll world is used during the reception',bool(states) and all(
            e.get('mode')=='0' and e.get('world_builds')=='0' and e.get('muscles')=='0' for e in states),len(states))
        g.keys(['Escape'],True);g.game.wait(timeout=15)
        check('clean exit',g.game.returncode==0,g.game.returncode)
    r['result']='passed' if all(c['result']=='passed' for c in r['checks']) else 'failed'
except BaseException as e:
    r.update(result='failed',error=str(e));raise
finally:
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'validation.json').write_text(json.dumps(r,indent=2)+'\n')
if r['result']!='passed':raise SystemExit(1)
