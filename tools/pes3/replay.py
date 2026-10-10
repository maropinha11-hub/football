#!/usr/bin/env python3
"""Replay selected original calls on a state and verify static C++ recompilation.

Calls use explicit arguments and normalized registers, not a resumed PS2 frame.
Artificial command/state probes are distinguished from unmodified snapshot inputs.
Original callees execute normally: no success stubs or native oracle replacement.
"""
import argparse
import ctypes as C
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from actions import Image, SINKS
from lift import generate
from savestate import SaveState, digest

PLAYER_BASE, PLAYER_STRIDE = 0x014C05E0, 0x4C0


def inventory(state, analysis, core):
    ram = state.ram
    u32 = lambda at: struct.unpack_from('<I', ram, at)[0]
    checked = {}
    for function in analysis['functions']:
        for pc, word, _ in function['listing']:
            at, original = int(pc, 16), int(word, 16)
            if u32(at) != original:
                raise ValueError(f'código carregado diverge em {pc}')
            checked[at] = original
    bundle = (core / 'data/pes_animation_tracks.fpsa').read_bytes()
    catalogue = json.loads((core / 'data/animation_pose_catalog.json').read_text())
    if digest(bundle) != catalogue['bundle_sha256']:
        raise ValueError('bundle de animações divergente')
    loaded, unloaded = [], []
    for entry in catalogue['entries']:
        clip = entry['clip']; at = u32(0x014D7D50 + clip * 4)
        if not at:
            unloaded.append(clip)
            continue
        block = bundle[entry['bundle_offset']:entry['bundle_offset'] + entry['block_bytes']]
        if at + len(block) > len(ram) or ram[at:at + len(block)] != block:
            raise ValueError(f'clip {clip} carregado não corresponde ao bundle')
        loaded.append({'clip': clip, 'address': hex(at), 'bytes': len(block),
                       'sha256': digest(block)})
    actors = []
    for ident in range(1, 23):
        at = PLAYER_BASE + ident * PLAYER_STRIDE
        actors.append({'id': ident, 'address': hex(at), 'object': hex(u32(at + 0xD0)),
          'action': ram[at + 0xDA], 'substate': struct.unpack_from('<H', ram, at + 0xDC)[0],
          'clip': struct.unpack_from('<H', ram, at + 0x2DC)[0],
          'frame_bits': hex(u32(at + 0x2E4)), 'controller_slot': ram[at + 0x10E]})
    return {'code_words_verified': len(checked), 'code_mismatches': 0,
            'bundle_sha256': digest(bundle), 'loaded_clips': loaded,
            'unloaded_clips': unloaded, 'actors': actors,
            'controlled_actor': ram[0x01564920 + 0xD],
            'global_pointers': {hex(at): hex(u32(at)) for at in (0x012A6238, 0x012A623C, 0x012A6250)}}


def scenarios(analysis, active):
    if not 1 <= active <= 22:
        raise ValueError('atleta controlado fora do domínio recuperado')
    cases = []
    def add(name, ident, calls, edits=()):
        player = PLAYER_BASE + ident * PLAYER_STRIDE
        cases.append({'id': name, 'actor': ident,
          'input_kind': 'modified_snapshot' if edits else 'unmodified_snapshot',
          'edits': [{'address': hex(player + off), 'format': fmt, 'value': val} for off, fmt, val in edits],
          'calls': [{'entry': hex(entry), 'args': [player, *args]} for entry, args in calls]})
    for ident in range(1, 23):
        add(f'update-actor-{ident}', ident, [(0x01880490, [])])
        for mode in (0, 1):
            add(f'select-actor-{ident}-mode-{mode}', ident, [(0x01853D30, [mode])])
    for case in analysis['routing']['action1_substates']['cases']:
        substate = case['value']
        add(f'action1-substate-{substate}', active, [(0x01876B50, [])], [(0xDC, 'H', substate)])
    for case in analysis['routing']['actions']['cases']:
        action = case['value']
        add(f'forced-action-{action}', active, [(0x01880490, [])], [(0xDA, 'B', action), (0xDC, 'H', 0)])
    for request in range(23):
        add(f'request-{request}-update', active, [(0x0184F5C0, [request, 0, 0]), (0x01880490, [])])
    for mask in [0, *[1 << i for i in range(16)]]:
        edits = [(0x1B0, 'I', mask), (0x1B4, 'I', mask)]
        for mode in (0, 1):
            add(f'select-mask-{mask}-mode-{mode}', active, [(0x01853D30, [mode])], edits)
        add(f'request4-mask-{mask}-update', active,
            [(0x0184F5C0, [4, 0, 0]), (0x01880490, [])], edits)
    # Original caller of player update: preparation, ball backup, active-actor
    # loop and post-update helpers. This routine is still not the whole PS2 frame.
    for count in (1,3):
        cases.append({'id':f'collective-update-{count}-calls','actor':active,
          'input_kind':'unmodified_snapshot','edits':[],
          'calls':[{'entry':'0x01881220','args':[]} for _ in range(count)]})
    for mask in [0,*[1<<i for i in range(16)]]:
        cases.append({'id':f'collective-pad-mask-{mask}','actor':active,
          'input_kind':'modified_snapshot',
          'edits':[{'address':hex(0x01304040+offset),'format':'I','value':mask} for offset in (8,12)],
          'calls':[{'entry':'0x01881220','args':[]}]})
    return cases


def reference_classes(folder):
    # Only the reviewed supplied reference modules are used. No helper stubs.
    sys.path.insert(0, str(folder.resolve()))
    from scratch_field_model import ScratchReference, ScratchFloat
    return ScratchReference, ScratchFloat


def trace_word(current, pc, word):
    for byte in struct.pack('<2I', pc, word):
        current = ((current ^ byte) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return current


def observe_case(state, case, reference, math_class, words, image, budget):
    ref = reference(state.ram, state.scratch)
    for edit in case['edits']:
        ref.write(int(edit['address'], 16), edit['format'], edit['value'])
    transitions, calls, branches, records = [], [], [], []
    last = []
    for request in case['calls']:
        count, signature = 0, 14695981039346656037
        model = math_class(ref)
        def observe(pc, word, r, f):
            nonlocal count, signature
            last[:] = [pc, word]
            if image.read(pc) != struct.pack('<I', word):
                raise ValueError(f'instrução alcançada diverge da fonte em {pc:#x}')
            if pc in words and words[pc] != word:
                raise ValueError('código mudou durante os probes')
            words[pc] = word; count += 1; signature = trace_word(signature, pc, word)
            if pc in SINKS:
                transitions.append({'role': SINKS[pc], 'entry': hex(pc),
                  'call_pc': hex((r[31] - 8) & 0xFFFFFFFF),
                  'actor_address': hex(r[4] & 0xFFFFFFFF), 'clip': r[5] & 0xFFFFFFFF,
                  'arguments': r[4:8], 'case': case['id'], 'input_kind': case['input_kind']})
            if word >> 26 == 3:
                calls.append({'pc': hex(pc), 'callee': hex(((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)),
                              'arguments_before_delay_slot': r[4:8]})
            if word >> 26 in (1, 4, 5, 6, 7, 20, 21):
                branches.append(hex(pc))
        try:
            value = ref.run(int(request['entry'],16), request['args'], max_instructions=budget,
              math_model=model, instruction_observer=observe, full_quadwords=True)
            status, reason = 'completed', None
        except Exception as exc:
            value = None; status, reason = 'blocked', str(exc)
        records.append({'entry': request['entry'], 'args': request['args'],
          'status': status, 'reason': reason, 'return': value, 'instructions': count,
          'trace_hash': hex(signature), 'registers': ref.last_registers if status == 'completed' else None,
          'float_registers': model.f[:] if status == 'completed' else None,
          'ram_sha256': digest(ref.ram), 'scratch_sha256': digest(ref.scratch)})
        if status != 'completed':
            break
    player = PLAYER_BASE + case['actor'] * PLAYER_STRIDE
    return dict(case, status=records[-1]['status'], results=records,
      last_instruction={'pc':hex(last[0]), 'word':f'{last[1]:08x}'},
      transitions=transitions, calls=calls, branch_pcs=sorted(set(branches)),
      output_actor={'action':ref.read(player+0xDA,'B'), 'substate':ref.read(player+0xDC,'H'),
                    'clip':ref.read(player+0x2DC,'H'), 'frame_bits':hex(ref.read(player+0x2E4,'I'))})


class LiftResult(C.Structure):
    _fields_ = [('status',C.c_uint32),('pc',C.c_uint32),('word',C.c_uint32),('reserved',C.c_uint32),
      ('instructions',C.c_uint64),('trace_hash',C.c_uint64),('registers',C.c_uint64*32),
      ('float_registers',C.c_uint32*32),('error',C.c_char*192)]


def compare_native(state, cases, library, budget):
    native = C.CDLL(str(library.resolve()))
    native.pes3_run_lifted.argtypes = [C.POINTER(C.c_uint8),C.POINTER(C.c_uint8),C.c_uint32,
      C.POINTER(C.c_uint64),C.c_uint32,C.c_uint32,C.POINTER(LiftResult)]
    native.pes3_run_lifted.restype = C.c_int
    comparisons = 0
    for case in cases:
        if case['status'] != 'completed':
            continue
        ram, scratch = bytearray(state.ram), bytearray(state.scratch)
        for edit in case['edits']:
            struct.pack_into('<'+edit['format'],ram,int(edit['address'],16),edit['value'])
        ram_buffer = (C.c_uint8 * len(ram)).from_buffer(ram)
        scratch_buffer = (C.c_uint8 * len(scratch)).from_buffer(scratch)
        for expected in case['results']:
            args = (C.c_uint64 * len(expected['args']))(*expected['args']); result = LiftResult()
            status = native.pes3_run_lifted(ram_buffer,scratch_buffer,int(expected['entry'],16),
              args,len(args),budget,C.byref(result))
            if status:
                raise AssertionError(f"{case['id']}: native blocked at {result.pc:#x}: {result.error.decode()}")
            actual = {'instructions':result.instructions,'trace_hash':hex(result.trace_hash),
              'registers':list(result.registers),'float_registers':list(result.float_registers),
              'ram_sha256':digest(ram),'scratch_sha256':digest(scratch)}
            for key,value in actual.items():
                if value != expected[key]:
                    raise AssertionError(f"{case['id']}: native mismatch: {key}")
            expected['native_comparison'] = 'matched_full_ram_scratch_registers_path'
            comparisons += 1
        print(f"native matched {case['id']}",flush=True)
    return comparisons


def main():
    parser = argparse.ArgumentParser(description='Reexecutar seletores e recompilar caminhos com memória real')
    for name in ('state','elf','over','analysis','core','reference','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--budget',type=int,default=200000)
    args = parser.parse_args()
    if args.output.exists():parser.error('escolha uma pasta nova')
    if not 1 <= args.budget <= 1000000:parser.error('budget fora do limite')
    state = SaveState(args.state); image = Image(args.elf,args.over)
    analysis = json.loads(args.analysis.read_text())
    if analysis['sources'] != image.sources:raise ValueError('análise é de outra versão')
    observed = inventory(state,analysis,args.core)
    refs = reference_classes(args.reference); words = {}; cases = []
    args.output.mkdir(parents=True)
    for case in scenarios(analysis,observed['controlled_actor']):
        row = observe_case(state,case,*refs,words,image,args.budget)
        cases.append(row)
        print(f"original {row['status']} {case['id']}",flush=True)
    (args.output/'instruction_words.json').write_text(json.dumps({hex(k):v for k,v in sorted(words.items())})+'\n')
    (args.output/'original_probes.json').write_text(json.dumps(cases,separators=(',',':'))+'\n')
    lift = generate(words,args.output/'native')
    library = args.output/'native/libpes3_lift.so'
    command = ['g++','-std=c++17','-O0','-fno-fast-math','-ffp-contract=off','-shared','-fPIC',
               str(args.output/'native/lifted_program.cpp'),'-o',str(library)]
    subprocess.run(command,check=True)
    native_comparisons = compare_native(state,cases,library,args.budget)
    transitions = [t for case in cases for t in case['transitions']]
    blocked = [case['id'] for case in cases if case['status'] != 'completed']
    report = {'schema_version':1,'result':'passed_with_blocked_paths' if blocked else 'passed',
      'run_id':str(uuid.uuid4()),'completed_at_utc':datetime.now(timezone.utc).isoformat(),
      'state':dict(state.metadata,cpu=state.cpu_metadata()),'sources':image.sources,
      'analysis_sha256':digest(args.analysis.read_bytes()),'inventory':observed,
      'summary':{'scenarios':len(cases),'completed_scenarios':len(cases)-len(blocked),
        'original_function_calls':sum(len(c['results']) for c in cases),
        'native_function_comparisons':native_comparisons,'blocked_scenarios':blocked,
        'original_instructions':sum(r['instructions'] for c in cases for r in c['results']),
        'observed_transition_calls':len(transitions),'observed_clips':sorted({t['clip'] for t in transitions}),
        'translated_instruction_words':len(words)},'lift':lift,'compile_command':command,
      'reference_sha256':{n:digest((args.reference/n).read_bytes()) for n in
        ('mips_integer_reference.py','float_vector_model.py','scratch_field_model.py')},
      'tool_sha256':{n:digest(Path(__file__).with_name(n).read_bytes()) for n in
        ('savestate.py','replay.py','lift.py','lift_runtime.hpp')},
      'native_files_sha256':{p.name:digest(p.read_bytes()) for p in (args.output/'native').iterdir()},
      'scenarios':cases,
      'scope':'Continuous modeled original calls and reached-path static C++ recompilation on captured/modified memory. Original helpers execute normally. Comparisons cover full EE RAM, scratchpad, low GPR/FPU registers and instruction sequence. Explicit argument calls with normalized registers; no resumed PCSX2 frame, observed consecutive frames, PS2 hardware equivalence or engine integration.'}
    (args.output/'replay-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['summary'],indent=2),flush=True)


if __name__ == '__main__':main()
