#!/usr/bin/env python3
"""Verify multiple captured training states and reexecute selected original calls.

Slot names are labels, not a consecutive-frame clock. The selected actor and
other actors executing gestures are tracked separately. No input fields are
edited and no unsupported call is replaced by a stub.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import struct
import subprocess
import uuid

from actions import Image, SINKS
from channel_provenance import investigate
from lift import generate
from model_reference import model_classes
from pose import word
from replay import PLAYER_BASE, PLAYER_STRIDE, compare_native, inventory, trace_word
from savestate import SaveState, digest

# These addresses are recovered functions, not invented anatomical labels.
EVENTS = {**SINKS, 0x011ACC40: 'ball_release',
          0x011AC6A0: 'ball_release_core', 0x017E0810: 'contact_geometry',
          0x0116AFE0: 'animation_phase_gate'}
PASSIVE_ACTIONS = frozenset((0, 1, 7, 11, 130, 137, 157, 255))


def actor_fields(ram, ident):
    if not 1 <= ident <= 22:
        raise ValueError('actor ID outside recovered player array')
    at = PLAYER_BASE + ident * PLAYER_STRIDE
    phase = struct.unpack_from('<f', ram, at + 0x2E4)[0]
    position = list(struct.unpack_from('<3f', ram, at + 0x2C4))
    if not all(math.isfinite(v) for v in [phase, *position]):
        raise ValueError('nonfinite captured phase or player position')
    return {'id': ident, 'address': hex(at), 'action': ram[at + 0xDA],
            'substate': struct.unpack_from('<H', ram, at + 0xDC)[0],
            'clip': struct.unpack_from('<H', ram, at + 0x2DC)[0],
            'phase': phase, 'phase_bits': hex(word(ram, at + 0x2E4)),
            'amplitude_i32': struct.unpack_from('<i', ram, at + 0xE0)[0],
            'heading_u16': struct.unpack_from('<H', ram, at + 0xEA)[0],
            'position_source': position}


def selected_actors(actors, controlled):
    """Include off-ball gesture actors, even after automatic player switching."""
    if not 1 <= controlled <= 22:
        raise ValueError('controlled actor ID outside recovered player array')
    return sorted({controlled} | {a['id'] for a in actors if a['action'] not in PASSIVE_ACTIONS})


def state_fields(ram, ids):
    ball = word(ram, 0x012A6250)
    if ball & 3 or ball + 128 > len(ram):
        raise ValueError('ball pointer outside EE RAM')
    return {'actors': [actor_fields(ram, i) for i in ids], 'ball_address': hex(ball),
            'ball_first_32_words': list(struct.unpack_from('<32I', ram, ball))}


def probe(state, ident, entry, args, reference, math_class, image, words, budget):
    ref = reference(state.ram, state.scratch)
    model = math_class(ref)
    transitions, events, branches = [], [], set()
    count, signature = 0, 14695981039346656037
    last = None

    def observe(pc, raw, registers, floats):
        nonlocal count, signature, last
        last = {'pc': hex(pc), 'word': f'{raw:08x}'}
        if image.read(pc) != struct.pack('<I', raw):
            raise ValueError(f'reached instruction differs from source at {pc:#x}')
        if pc in words and words[pc] != raw:
            raise ValueError('different instruction at previously observed address')
        words[pc] = raw
        count += 1
        signature = trace_word(signature, pc, raw)
        if pc in EVENTS:
            row = {'role': EVENTS[pc], 'entry': hex(pc),
                   'call_pc': hex((registers[31] - 8) & 0xFFFFFFFF),
                   'arguments': registers[4:8],
                   'float_arguments_bits': model.f[12:16],
                   'observed_fields': state_fields(ref.ram, [ident])}
            if pc == 0x0116AFE0:
                player = registers[4] & 0xFFFFFFFF
                if player != PLAYER_BASE + ident * PLAYER_STRIDE:
                    raise ValueError('phase gate called for an unexpected actor')
                row['phase_gate_input'] = {
                    'marker_i32': struct.unpack('<i', struct.pack('<I', registers[5] & 0xFFFFFFFF))[0],
                    'phase_bits': hex(word(ref.ram, player + 0x2E4)),
                    'step_bits': hex(word(ref.ram, player + 0x138)),
                    'blend_window': ref.ram[player + 0x2FA],
                    'blend_tick': ref.ram[player + 0x2FB],
                    'cycle_fix': ref.ram[player + 0x2FE]}
            events.append(row)
            if pc in SINKS:
                transitions.append(dict(row, clip=registers[5] & 0xFFFFFFFF,
                                        actor_address=hex(registers[4] & 0xFFFFFFFF)))
        if raw >> 26 in (1, 4, 5, 6, 7, 20, 21):
            branches.add(hex(pc))

    reason = None
    try:
        value = ref.run(entry, args, max_instructions=budget, math_model=model,
                        instruction_observer=observe, full_quadwords=True)
        status = 'completed'
    except Exception as exc:
        value, status, reason = None, 'blocked', str(exc)
    result = {'entry': hex(entry), 'args': args, 'status': status, 'reason': reason,
              'return': value, 'instructions': count, 'trace_hash': hex(signature),
              'registers': ref.last_registers if status == 'completed' else None,
              'float_registers': model.f[:] if status == 'completed' else None,
              'ram_sha256': digest(ref.ram), 'scratch_sha256': digest(ref.scratch)}
    return {'id': f'actor-{ident}-{entry:x}-' + '-'.join(str(v) for v in args[1:]),
            'actor': ident, 'input_kind': 'unmodified_snapshot', 'edits': [],
            'status': status, 'results': [result], 'last_instruction': last,
            'transitions': transitions, 'events': events,
            'branch_pcs': sorted(branches), 'output_fields': state_fields(ref.ram, [ident])}


def study(paths, image, analysis, core, output, budget=200000):
    if not paths or len(paths) > 32:
        raise ValueError('provide 1..32 states')
    if not 1 <= budget <= 1000000:
        raise ValueError('instruction budget outside 1..1000000')
    output.mkdir(parents=True, exist_ok=False)
    reference, math_class = model_classes(core / 'reference')
    words, states, hashes = {}, [], set()
    dispatch = {c['value']: c['handler'] for c in analysis['routing']['actions']['cases']}
    for number, path in enumerate(paths, 1):
        state = SaveState(path)
        if state.metadata['sha256'] in hashes:
            raise ValueError('duplicate state content in batch')
        hashes.add(state.metadata['sha256'])
        observed = inventory(state, analysis, core)
        channels = investigate(state, core)
        actors = [dict(actor_fields(state.ram, i),
                       action_handler=dispatch.get(state.ram[PLAYER_BASE + i * PLAYER_STRIDE + 0xDA]))
                  for i in range(1, 23)]
        ids = selected_actors(actors, observed['controlled_actor'])
        calls = [(ident, 0x01880490, [PLAYER_BASE + ident * PLAYER_STRIDE]) for ident in ids]
        calls += [(observed['controlled_actor'], 0x01853D30,
                   [PLAYER_BASE + observed['controlled_actor'] * PLAYER_STRIDE, mode])
                  for mode in (0, 1)]
        cases = []
        for ident, entry, args in calls:
            case = probe(state, ident, entry, args, reference, math_class, image, words, budget)
            cases.append(case)
            print(f'state {number:02d}: {case["status"]} {case["id"]}', flush=True)
        row = {'index': number, 'filename': Path(path).name, 'sha256': state.metadata['sha256'],
               'version': state.metadata.get('version'), 'cpu': state.cpu_metadata(),
               'code_words_verified': observed['code_words_verified'],
               'loaded_clips_verified': len(observed['loaded_clips']),
               'loaded_clips': [c['clip'] for c in observed['loaded_clips']],
               'controlled_actor': observed['controlled_actor'], 'probed_actors': ids,
               'actors': actors, 'captured_fields': state_fields(state.ram, ids),
               'rotation_channel_summary': channels['summary'], 'cases': cases}
        states.append(row)
        (output / f'state-{number:02d}-channels.json').write_text(json.dumps(channels, indent=2) + '\n')
        (output / f'state-{number:02d}-probes.json').write_text(json.dumps(row, indent=2) + '\n')
    lift = generate(words, output / 'native')
    library = output / 'native/libpes3_lift.so'
    command = ['g++', '-std=c++17', '-O0', '-fno-fast-math', '-ffp-contract=off',
               '-shared', '-fPIC', str(output / 'native/lifted_program.cpp'), '-o', str(library)]
    subprocess.run(command, check=True)
    comparisons = 0
    for path, row in zip(paths, states):
        comparisons += compare_native(SaveState(path), row['cases'], library, budget)
        (output / f'state-{row["index"]:02d}-probes.json').write_text(json.dumps(row, indent=2) + '\n')
    (output / 'instruction-words.json').write_text(json.dumps({hex(k): v for k, v in sorted(words.items())}) + '\n')
    cases = [c for s in states for c in s['cases']]
    report = {'schema_version': 1, 'run_id': str(uuid.uuid4()),
              'completed_at_utc': datetime.now(timezone.utc).isoformat(),
              'result': 'passed_with_blocked_paths' if any(c['status'] != 'completed' for c in cases) else 'passed',
              'sources': image.sources, 'arithmetic_profile': {'fpu': 'nearest', 'vu': 'nearest'},
              'summary': {'states': len(states), 'distinct_state_hashes': len(hashes),
                          'verified_code_words_per_state': sorted({s['code_words_verified'] for s in states}),
                          'cases': len(cases), 'native_function_comparisons': comparisons,
                          'blocked_cases': sum(c['status'] != 'completed' for c in cases),
                          'original_instructions': sum(c['results'][0]['instructions'] for c in cases),
                          'events_by_role': dict(Counter(e['role'] for c in cases for e in c['events'])),
                          'translated_instruction_words': len(words)},
              'states': states, 'lift': lift, 'compile_command': command,
              'reference_sha256': {n: digest((core / 'reference' / n).read_bytes()) for n in
                                    ('mips_integer_reference.py', 'float_vector_model.py',
                                     'pose_math_model.py', 'scratch_field_model.py')},
              'runtime_enabled': False,
              'scope': 'Independent explicit original calls on unmodified captured memory, then static C++ recompilation checked against full EE RAM, scratchpad, low GPR/FPU registers and instruction paths. Labels do not imply consecutive frames. Event arguments are observed at actual callee entries after delay slots. No resumed PCSX2 frame, complete gesture, action name guessed from an ID, hardware-exact arithmetic or native game integration.'}
    report['files_sha256'] = {p.relative_to(output).as_posix(): digest(p.read_bytes())
                              for p in output.rglob('*') if p.is_file()}
    report['tool_sha256'] = {n: digest(Path(__file__).with_name(n).read_bytes()) for n in
                             ('study_states.py', 'replay.py', 'model_reference.py', 'channel_provenance.py',
                              'savestate.py', 'lift.py', 'lift_runtime.hpp')}
    (output / 'state-study.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description='Investigar escolhas e contatos nos saves de treino PES3')
    parser.add_argument('--state', action='append', type=Path, required=True)
    for name in ('elf', 'over', 'analysis', 'core', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--budget', type=int, default=200000)
    args = parser.parse_args()
    image = Image(args.elf, args.over)
    analysis = json.loads(args.analysis.read_text())
    if analysis['sources'] != image.sources:
        raise ValueError('analysis belongs to a different PES revision')
    report = study(args.state, image, analysis, args.core, args.output, args.budget)
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    main()
