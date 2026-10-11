#!/usr/bin/env python3
"""Compare a semantic common locomotion decision with actual original calls.

The original predicates/predictions/change/refresh helpers execute normally.
Helper results become explicit boundary inputs of the semantic decision;
they are not injected into the original interpreter. The complete action,
prediction helper, speed tail and poses are outside this semantic API.
"""
import argparse
from collections import Counter
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import uuid
from datetime import datetime, timezone

from actions import Image
from pose import reference_classes
from replay import PLAYER_BASE, PLAYER_STRIDE
from savestate import SaveState, digest
from selection_abi import Input, Decision, SOURCE, configure
from speed_abi import Input as SpeedInput, SOURCE as SPEED_SOURCE, configure as configure_speed

FIELDS = {'initial_amplitude': (0x11c, 'i'), 'current_amplitude': (0xe0, 'i'),
          'state_flags': (0x1a0, 'I'), 'body_heading': (0xea, 'H'), 'movement_heading': (0xec, 'H'),
          'clip': (0x2dc, 'H'), 'substate': (0xdc, 'H'), 'turn_heading': (0xf8, 'H'),
          'player_id': (0, 'B'), 'attribute_124': (0x124, 'B'), 'phase_130': (0x130, 'B'),
          'auxiliary_134': (0x134, 'B')}


def scenarios():
    yield 'captured-common-input', {}
    # Strict boundaries, exclusive flags/controller branch, and both turn sides.
    for attribute in (0, 100, 255):
        for delta in (-1, 0, 1):
            yield f'ball-threshold-{attribute}-{delta}', dict(state_flags=1, context_matches=True,
                attribute_124=attribute, ball_amplitude=5888 - 12 * attribute + delta)
    for heading in (0, 65535, 12345):
        for angle in (0, 20479, 20480, 32768):
            for side in (-1, 1):
                yield f'turn-{heading}-{angle}-{side}', dict(state_flags=0, direction_mask=1,
                    body_heading=heading, movement_heading=(heading + side * angle) & 65535, current_amplitude=2048)
    for current in (-2147483648, -1, 0, 1023, 1024, 2147483647):
        for phase in (0, 1):
            yield f'amplitude-{current}-phase-{phase}', dict(state_flags=0, direction_mask=1,
                body_heading=0, movement_heading=0, current_amplitude=current, phase_130=phase)
    for initial in (-2147483648, -8000, -1, 0, 1, 1024, 4000, 8000, 2147483647):
        yield f'chase-initial-{initial}', dict(state_flags=0, direction_mask=0, initial_amplitude=initial)
    for mask in range(1, 16):
        yield f'nonzero-direction-{mask}', dict(state_flags=0, direction_mask=mask)
    for flags in (0, 1, 2, 0xffffffff):
        for matches in (False, True):
            yield f'flags-{flags}-controller-match-{matches}', dict(state_flags=flags, context_matches=matches)
    for restart in (False, True):
        yield f'clip47-restart-{restart}', dict(clip=47, restart_counter=32767 if restart else 0,
            state_flags=0, direction_mask=1, current_amplitude=2048, body_heading=0, movement_heading=0,
            frame=0.0, clear_end_flags=True)
    # The captured stationary state never takes the nonzero-input chase gate.
    # Move the player in the copied RAM and vary actual ball fields; the
    # opponent lookup, heading lookup and gate instructions still run normally.
    for axis in (-2753.0, -2752.0, 0.0, 2752.0, 2753.0):
        for heading in (0, 32768):
            yield f'chase-gate-axis-{axis}-heading-{heading}', dict(state_flags=0,
                direction_mask=1, position_x=10000.0, ball_axis=axis,
                body_heading=heading, movement_heading=heading, current_amplitude=2048)
    for height in (-1000.0, 0.0):
        yield f'chase-gate-height-{height}', dict(state_flags=0, direction_mask=1,
            position_x=10000.0, ball_axis=0.0, ball_prediction_y=height,
            body_heading=32768, movement_heading=32768, current_amplitude=2048)


def verify(state, image, core, output):
    output.mkdir(parents=True, exist_ok=False)
    reference, math_class = reference_classes(core / 'reference')
    header = Path(__file__).with_name('recovered') / 'locomotion_selection.hpp'
    (output / header.name).write_bytes(header.read_bytes())
    speed_header = header.with_name('locomotion_speed.hpp')
    (output / speed_header.name).write_bytes(speed_header.read_bytes())
    (output / 'selector.cpp').write_text(SOURCE + SPEED_SOURCE)
    command = ['g++', '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror', '-fno-fast-math', '-ffp-contract=off',
               '-shared', '-fPIC', str(output / 'selector.cpp'), '-o', str(output / 'selector.so')]
    subprocess.run(command, check=True, capture_output=True)
    native = configure(C.CDLL(str((output / 'selector.so').resolve())))
    configure_speed(native)
    words, cases, instruction_total = {}, [], 0
    controlled = state.ram[0x01564920 + 13]
    player = PLAYER_BASE + controlled * PLAYER_STRIDE
    for ident, edits in scenarios():
        ref = reference(state.ram, state.scratch)
        context = ref.read(0x012a6238, 'I'); ball = ref.read(0x012a6250, 'I')
        initial = Input()
        for name, (offset, kind) in FIELDS.items(): setattr(initial, name, ref.read(player + offset, kind))
        initial.direction_mask = ref.read(context + 0x48, 'I')
        if initial.direction_mask > 15: raise ValueError('captured direction mask outside common domain')
        initial.context_player, initial.ball_amplitude = ref.read(context + 14, 'B'), ref.read(ball + 0x58, 'i')
        for name, value in edits.items():
            if name in FIELDS:
                offset, kind = FIELDS[name]; ref.write(player + offset, kind, value); setattr(initial, name, value)
            elif name == 'direction_mask': ref.write(context + 0x48, 'I', value); initial.direction_mask = value
            elif name == 'ball_amplitude': ref.write(ball + 0x58, 'i', value); initial.ball_amplitude = value
            elif name == 'context_matches':
                value = initial.player_id if value else (initial.player_id + 1) & 255
                ref.write(context + 14, 'B', value); initial.context_player = value
            elif name == 'restart_counter': ref.write(player + 0x2e0, 'H', value)
            elif name == 'frame': ref.write(player + 0x2e4, 'f', value)
            elif name == 'position_x': ref.write(player + 0x2c4, 'f', value)
            elif name == 'ball_axis': ref.write(ball + 0x2c, 'f', value)
            elif name == 'ball_prediction_y': ref.write(ball + 0x7b4, 'f', value)
            elif name == 'clear_end_flags':
                ref.write(player + 0x2fa, 'B', 4); ref.write(player + 0x2fe, 'B', 0)
            else: raise ValueError('unhandled scenario edit: ' + name)
        entry = 0x018790d0 if initial.clip == 47 else 0x018790e8
        transitions, refreshes, writes, dependencies, before_tail = [], [], [], [], []
        def observe(pc, opcode, registers, floats):
            if image.read(pc) != struct.pack('<I', opcode): raise ValueError('changed original instruction')
            words[pc] = opcode
            if pc == 0x018790d8:
                initial.clip_restart = int(bool(registers[2]))
                dependencies.append({'role': 'restart_predicate', 'entry': '0x0116af50', 'value': initial.clip_restart})
            if pc == 0x01879178:
                initial.chase_gate = int(bool(registers[2]))
                dependencies.append({'role': 'chase_gate', 'entry': '0x017d5990', 'value': initial.chase_gate})
            if pc == 0x0187918c:
                initial.chase_amplitude = C.c_int32(registers[2] & 0xffffffff).value
                dependencies.append({'role': 'chase_prediction', 'entry': '0x01854f20', 'value': initial.chase_amplitude})
            if pc == 0x011677a0: transitions.append([registers[5] & 65535, registers[6] & 0xffffffff])
            if pc == 0x0119f860: refreshes.append(registers[5] & 255)
            if pc in (0x018790e4, 0x0187910c, 0x0187926c, 0x01879270, 0x01879278): writes.append(pc)
            if pc == 0x0187927c:
                expected = Decision(selected_amplitude=C.c_int32(registers[17] & 0xffffffff).value,
                    amplitude_before_speed=ref.read(player + 0xe0, 'i'), substate=ref.read(player + 0xdc, 'H'),
                    turn_heading=ref.read(player + 0xf8, 'H'), auxiliary_134=ref.read(player + 0x134, 'B'))
                roster = 0x0155f1c0 + ref.read(player + 0xd8, 'B') * 10880 + ref.read(player + 0xd7, 'B') * 272
                mode = ref.read(0x012a623c, 'I')
                speed = SpeedInput(current_amplitude=expected.amplitude_before_speed,
                    selected_amplitude=expected.selected_amplitude, roster_ae=ref.read(roster + 0xae, 'H'),
                    attribute_124=initial.attribute_124, mode_phase_5=ref.read(mode + 5, 'B'),
                    mode_2=ref.read(mode + 2, 'B'), profile_flag=ref.read(0x01304034, 'i'))
                before_tail.append((expected, speed))
        ref.run(entry, [], initial_registers={17: initial.initial_amplitude, 19: player},
                stop_before=0x0187930c, math_model=math_class(ref), instruction_observer=observe,
                full_quadwords=True, max_instructions=100000)
        instruction_total += ref.instructions
        if len(before_tail) != 1: raise ValueError('common tail was not reached exactly once')
        expected, speed_input = before_tail[0]
        bits = {0x018790e4: 1, 0x0187910c: 16, 0x0187926c: 8, 0x01879270: 2, 0x01879278: 4}
        expected.writes = sum(bits[pc] for pc in set(writes))
        if 0x018790e4 in writes: expected.frame_override = 24
        if transitions:
            if len(transitions) != 1 or refreshes != [4]: raise ValueError('unexpected transition sequence')
            expected.change_clip = 1; expected.requested_clip, expected.start_frame = transitions[0]; expected.refresh_window = 4
        elif refreshes: raise ValueError('refresh without recorded change')
        actual = Decision()
        status = native.select_locomotion(C.byref(initial), C.byref(actual))
        if status != 1 or bytes(actual) != bytes(expected):
            raise AssertionError(f'{ident}: status={status}, input={bytes(initial).hex()}, actual={bytes(actual).hex()}, expected={bytes(expected).hex()}')
        actual_speed_input = SpeedInput.from_buffer_copy(bytes(speed_input))
        actual_speed_input.current_amplitude = actual.amplitude_before_speed
        actual_speed_input.selected_amplitude = actual.selected_amplitude
        expected_speed = ref.read(player + 0xe0, 'i')
        actual_speed = native.step_speed(C.byref(actual_speed_input))
        if actual_speed != expected_speed: raise AssertionError(f'{ident}: composed speed differs {actual_speed} != {expected_speed}')
        cases.append({'id': ident, 'input_hex': bytes(initial).hex(), 'expected_hex': bytes(expected).hex(),
            'speed_input_hex': bytes(speed_input).hex(), 'expected_speed': expected_speed,
            'memory_kind': 'modified_snapshot' if edits else 'captured_snapshot', 'edits': edits,
            'entry': hex(entry), 'stop_before': '0x0187930c', 'dependencies': dependencies,
            'transitions': transitions, 'refreshes': refreshes, 'instructions': ref.instructions,
            'result_ram_sha256': digest(ref.ram), 'result_scratch_sha256': digest(ref.scratch)})
    (output / 'selection-vectors.json').write_text(json.dumps({'schema_version': 1,
        'state_sha256': state.metadata['sha256'], 'input_bytes': 44, 'decision_bytes': 32,
        'speed_input_bytes': 20, 'cases': cases}, separators=(',', ':')) + '\n')
    (output / 'selection-instruction-words.json').write_text(json.dumps({hex(k): v for k, v in sorted(words.items())}) + '\n')
    report = {'schema_version': 1, 'run_id': str(uuid.uuid4()), 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
        'result': 'passed', 'state_sha256': state.metadata['sha256'], 'sources': image.sources,
        'comparisons': len(cases), 'original_instructions': instruction_total, 'instruction_words': len(words),
        'by_outcome': dict(Counter('no_change' if not c['transitions'] else 'clip_' + str(c['transitions'][0][0]) for c in cases)),
        'restart_true_cases': sum(Input.from_buffer_copy(bytes.fromhex(c['input_hex'])).clip_restart for c in cases),
        'chase_gate_true_cases': sum(Input.from_buffer_copy(bytes.fromhex(c['input_hex'])).chase_gate for c in cases),
        'helper_dependency_scope': 'Predicates, chase prediction, clip change and refresh execute unchanged in the original. Their reached dependency values are explicit semantic boundary inputs. They are not rewritten by this decision API or injected into the original.',
        'compile_command': command, 'tool_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in
            ('verify_selection.py', 'selection_abi.py', 'speed_abi.py', 'pose.py', 'pose_reference.py', 'savestate.py')},
        'files_sha256': {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir())},
        'composed_speed_comparisons': len(cases),
        'scope': 'Common locomotion decision of action 1/substate 16, clip-47 frame override and composed integer speed tail to 0187930C. Numeric owned structs, original integer units/headings. No complete action, prediction rewrite, pose retargeting, native request mapping, foot/head contact or full PES gameplay equivalence.'}
    (output / 'selection-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description='Conferir seleção semântica de locomoção PES')
    for name in ('state', 'elf', 'over', 'core', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    state = SaveState(args.state)
    report = verify(state, Image(args.elf, args.over), args.core, args.output)
    if digest(args.state.read_bytes()) != state.metadata['sha256']: raise ValueError('state changed')
    print(json.dumps({k: report[k] for k in ('result', 'comparisons', 'original_instructions', 'by_outcome', 'restart_true_cases', 'chase_gate_true_cases')}, indent=2))


if __name__ == '__main__': main()
