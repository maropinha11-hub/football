#!/usr/bin/env python3
"""Run direction/dispatch/speed consecutively, with original helpers unchanged."""
import argparse
import ctypes as C
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import struct
import subprocess
import uuid
from actions import Image
from arithmetic import classes
from chain_abi import Input, Decision, SOURCE, configure
from direction_abi import Decision as DirectionDecision
from replay import PLAYER_BASE, PLAYER_STRIDE
from savestate import SaveState, digest
from selection_abi import Decision as CommonDecision
from verify_selection import FIELDS


def scenarios():
    for clip, mask, flags, restart in itertools.product((28,35,47,48,61,62,63,119,304,613,864),
            (0,1,2,8), (0,1), (0,1)):
        yield f'clip{clip}-mask{mask}-flags{flags}-restart{restart}', dict(clip=clip,
            direction_mask=mask, state_flags=flags, restart=restart)
    for clip, x, z, body in itertools.product((28,35,48,61,62,63), (0,256), (-300,0,300), (0,32768)):
        yield f'direction-clip{clip}-near{x}-far{z}-body{body}', dict(clip=clip,
            near_x=x, far_z=z, body_heading=body, movement_heading=body, ball_heading=0, direction_mask=1)
    for mask in (1,2,3,4,8,15):
        yield f'chase-{mask}', dict(clip=48, direction_mask=mask, body_heading=32768, movement_heading=32768,
            position_x=10000.0, ball_axis=3000.0)


def verify(state, image, core, output, fpu):
    output.mkdir(parents=True, exist_ok=False)
    reference, math_class = classes(core / 'reference', fpu, fpu, 'nearest', 'nearest')
    for name in ('selection','speed','direction','tables','special','prediction','variants','chain'):
        name = 'locomotion_' + name + '.hpp'
        (output / name).write_bytes((Path(__file__).with_name('recovered') / name).read_bytes())
    (output / 'chain.cpp').write_text(SOURCE)
    command = ['g++','-std=c++14','-O0','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off',
        '-shared','-fPIC',str(output / 'chain.cpp'),'-o',str(output / 'chain.so')]
    subprocess.run(command, check=True, capture_output=True)
    lib = configure(C.CDLL(str((output / 'chain.so').resolve())))
    player = PLAYER_BASE + state.ram[0x01564920 + 13] * PLAYER_STRIDE
    words, cases, instructions = {}, [], 0
    for ident, edits in scenarios():
        ref = reference(state.ram, state.scratch)
        context, ball, mode = [ref.read(a,'I') for a in (0x012a6238,0x012a6250,0x012a623c)]
        roster = 0x0155f1c0 + ref.read(player+0xd8,'B')*10880 + ref.read(player+0xd7,'B')*272
        ref.write(player+0xdc,'H',16); ref.write(player+0x2fa,'B',4); ref.write(player+0x2fe,'B',0)
        for name, value in edits.items():
            if name in FIELDS:
                off, kind = FIELDS[name]; ref.write(player+off,kind,value)
            elif name == 'direction_mask': ref.write(context+0x48,'I',value)
            elif name == 'restart': ref.write(player+0x2e0,'H',32767 if value else 0)
            elif name == 'ball_heading': ref.write(ball+0x60,'H',value)
            elif name == 'near_x': ref.write(ball+0x444,'f',ref.read(player+0x2c4,'f')+value)
            elif name == 'far_z':
                ref.write(ball+0x474,'f',ref.read(player+0x2c4,'f'))
                ref.write(ball+0xb74,'f',ref.read(player+0x2cc,'f')+value)
            elif name == 'position_x': ref.write(player+0x2c4,'f',value)
            elif name == 'ball_axis': ref.write(ball+0x2c,'f',value)
            else: raise ValueError(name)
        i = Input(); c = i.selection.common; d = i.direction; v = i.selection
        for name,(off,kind) in FIELDS.items(): setattr(c,name,ref.read(player+off,kind))
        c.direction_mask = ref.read(context+0x48,'I'); c.context_player = ref.read(context+14,'B')
        c.ball_amplitude = ref.read(ball+0x58,'i')
        for name in ('body_heading','movement_heading','turn_heading','clip','substate','direction_mask'): setattr(d,name,getattr(c,name))
        d.ball_heading = ref.read(ball+0x60,'H')
        d.player_xz[:] = [ref.read(player+off,'f') for off in (0x2c4,0x2cc)]
        d.ball_far_xz[:] = [ref.read(ball+off,'f') for off in (0x474,0xb74)]
        d.ball_near_xz[:] = [ref.read(ball+off,'f') for off in (0x444,0xb44)]
        for name,off,kind in (('flags_1b0',0x1b0,'I'),('amplitude_120',0x120,'i'),('current_frame',0x2e4,'f'),
                ('attribute_12c',0x12c,'B'),('auxiliary_105',0x105,'B'),('auxiliary_133',0x133,'B')):
            setattr(v,name,ref.read(player+off,kind))
        for name,off,kind in (('roster_ac',0xac,'H'),('roster_ae',0xae,'H'),('roster_ab',0xab,'B'),('roster_cc',0xcc,'B')):
            setattr(v,name,ref.read(roster+off,kind))
        v.configuration_step = ref.read(mode+0x4c,'f'); v.mode_phase_5 = ref.read(mode+5,'B'); v.mode_2 = ref.read(mode+2,'B')
        v.profile_flag = ref.read(0x01304034,'i'); v.timing_byte = ref.read(0x012997b0+v.profile_flag,'B')
        v.fpu_rounding = int(fpu=='chop')
        i.prediction_y_7cc = ref.read(ball+0x7cc,'f'); i.roster_a3 = ref.read(roster+0xa3,'B')
        i.speed.roster_ae = v.roster_ae; i.speed.attribute_124 = c.attribute_124
        i.speed.mode_phase_5 = v.mode_phase_5; i.speed.mode_2 = v.mode_2; i.speed.profile_flag = v.profile_flag
        expected = Decision(); action_headings, requests, refreshes, tail = [],[],[],[]; sites = set()
        def observe(pc, word, registers, floats):
            if image.read(pc) != struct.pack('<I',word): raise ValueError('original code changed')
            words[pc]=word; sites.add(pc)
            if pc == 0x01878550: action_headings.append(registers[2]&65535)
            if pc == 0x0187866c:
                expected.direction = DirectionDecision(registers[18]&0xffffffff,registers[21]&65535,
                    ref.read(player+0xea,'H'),ref.read(player+0xec,'H'),ref.read(player+0xdc,'H'),
                    registers[16]&65535,registers[20]&65535,registers[22]&65535,action_headings[0])
            if pc in (0x018790d8,0x01878998,0x01878be4,0x01879018): c.clip_restart=int(bool(registers[2]))
            if pc in (0x01879178,0x018788a0,0x01878e24): c.chase_gate=int(bool(registers[2]))
            if pc in (0x0187918c,0x018788b0,0x01878e34): c.chase_amplitude=C.c_int32(registers[2]&0xffffffff).value
            if pc == 0x017d93cc: i.cap_squared_distance=registers[2]&0xffffffff
            if pc in (0x01878754,0x018790d0): expected.animation_rate=ref.read(player+0x138,'f')
            if pc == 0x018a4720: requests.append((2,registers[5]&65535,struct.unpack('<f',struct.pack('<I',floats[12]))[0],0,0))
            if pc == 0x018a4de0: requests.append((3,registers[5]&65535,0,C.c_int32(registers[6]&0xffffffff).value,0))
            if pc == 0x011677a0 and not requests: requests.append((1,registers[5]&65535,0,0,registers[6]&0xffffffff))
            if pc == 0x0119f860: refreshes.append(registers[5]&255)
            if pc == 0x0187927c:
                expected.decision=CommonDecision(selected_amplitude=C.c_int32(registers[17]&0xffffffff).value,
                    amplitude_before_speed=ref.read(player+0xe0,'i'),substate=ref.read(player+0xdc,'H'),
                    turn_heading=ref.read(player+0xf8,'H'),auxiliary_134=ref.read(player+0x134,'B'))
                expected.flags_1a0=ref.read(player+0x1a0,'I'); expected.auxiliary_105=ref.read(player+0x105,'B')
                expected.auxiliary_133=ref.read(player+0x133,'B'); expected.phase_130=ref.read(player+0x130,'B')
                tail.append(pc)
        ref.run(0x018783b0,[],initial_registers={19:player,17:c.initial_amplitude},stop_before=0x0187930c,
            math_model=math_class(ref),instruction_observer=observe,full_quadwords=True,max_instructions=100000)
        if len(tail)!=1 or len(requests)>1: raise ValueError('unexpected chain')
        common_bits={0x018790e4:1,0x0187910c:16,0x0187926c:8,0x01879270:2,0x01879278:4,0x01878e08:16}
        for pc, bit in common_bits.items():
            if pc in sites: expected.decision.writes |= bit
        if 0x018790e4 in sites: expected.decision.frame_override=24
        if c.clip==28: expected.decision.writes|=2
        if c.clip in (28,47): expected.writes|=16
        if any(pc in sites for pc in (0x01878fe8,0x01879050,0x01878930)): expected.writes|=1
        if any(pc in sites for pc in (0x01879048,0x01878928)): expected.writes|=4
        if any(pc in sites for pc in (0x018789bc,0x01878c08)): expected.writes|=2
        if 0x01878940 in sites: expected.writes|=8
        if requests:
            kind,clip,frame,encoded,start=requests[0]
            expected.transition_kind=kind; expected.decision.change_clip=1; expected.decision.requested_clip=clip
            expected.comparison_frame=frame; expected.encoded_start=encoded; expected.decision.start_frame=start
            if kind==1:
                if refreshes != [4]: raise ValueError('plain refresh sequence changed')
                expected.decision.refresh_window=4
        expected.updated_amplitude=ref.read(player+0xe0,'i')
        actual=Decision(); status=lib.step_locomotion(C.byref(i),C.byref(actual))
        if status!=1 or bytes(actual)!=bytes(expected):
            raise AssertionError(f'{ident}: status={status}, input={bytes(i).hex()}, expected={bytes(expected).hex()}, actual={bytes(actual).hex()}')
        instructions+=ref.instructions
        cases.append({'id':ident,'input_hex':bytes(i).hex(),'expected_hex':bytes(expected).hex(),
            'instructions':ref.instructions,'edits':edits,'memory_kind':'modified_snapshot'})
    (output/'chain-vectors.json').write_text(json.dumps({'schema_version':1,'state_sha256':state.metadata['sha256'],
        'input_bytes':160,'decision_bytes':80,'cases':cases},separators=(',',':'))+'\n')
    (output/'chain-instruction-words.json').write_text(json.dumps({hex(k):v for k,v in sorted(words.items())})+'\n')
    report={'schema_version':1,'run_id':str(uuid.uuid4()),'completed_at_utc':datetime.now(timezone.utc).isoformat(),
        'result':'passed','state_sha256':state.metadata['sha256'],'sources':image.sources,'comparisons':len(cases),
        'original_instructions':instructions,'instruction_words':len(words),'entry':'0x018783b0','stop_before':'0x0187930c',
        'arithmetic':{'fpu':fpu,'division':'nearest','sqrt':'nearest'},'compile_command':command,
        'tool_sha256':{n:digest(Path(__file__).with_name(n).read_bytes()) for n in ('verify_locomotion_chain.py','chain_abi.py',
            'direction_abi.py','variant_abi.py','speed_abi.py','selection_abi.py','arithmetic.py','pose.py','savestate.py','verify_selection.py')},
        'files_sha256':{p.name:digest(p.read_bytes()) for p in sorted(output.iterdir())},
        'scope':'Consecutive original direction/selected dispatch/speed, eleven clip paths; requests/rate observed before phase/encoded helpers. Helpers execute original code and provide numeric chase/gate/restart/cap boundaries without native result injection. Modified stationary snapshot, not resumed frames. Excludes other special paths, full clock/poses/actions, contacts/physics, units/retarget and native gameplay integration.'}
    (output/'chain-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    p=argparse.ArgumentParser()
    for name in ('state','elf','over','core','output'): p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--fpu-rounding',choices=('nearest','chop'),default='nearest')
    a=p.parse_args();state=SaveState(a.state);report=verify(state,Image(a.elf,a.over),a.core,a.output,a.fpu_rounding)
    if digest(a.state.read_bytes())!=state.metadata['sha256']: raise ValueError('state changed')
    print(json.dumps({k:report[k] for k in ('result','comparisons','original_instructions','instruction_words')},indent=2))

if __name__=='__main__': main()
