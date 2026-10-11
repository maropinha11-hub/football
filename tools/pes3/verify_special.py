#!/usr/bin/env python3
"""Execute the actual 61/62/63 dispatch, original helpers and speed tail."""
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
from pose import reference_classes
from replay import PLAYER_BASE, PLAYER_STRIDE
from savestate import SaveState, digest
from selection_abi import Input as CommonInput, Decision as CommonDecision
from special_abi import Input, Decision, SOURCE, configure
from speed_abi import Input as SpeedInput, SOURCE as SPEED_SOURCE, configure as configure_speed
from verify_selection import FIELDS


def scenarios():
    for clip, flags, near, initial, ball in itertools.product((62, 63), (0, 1),
            (82943, 82944), (-2147483648, -1, 0, 8000, 2147483647), (0, 4000)):
        yield f'clip{clip}-flags{flags}-near{near}-initial{initial}-ball{ball}', dict(
            clip=clip, state_flags=flags, near=near, initial_amplitude=initial, ball_amplitude=ball)
    for clip in (61,):
        for current, ball, cap, flags, restart in itertools.product((0, 2975, 4000, 5025, 2147483647),
                (0, 4000), (0, 136, 137), (0, 1), (False, True)):
            yield f'clip61-current{current}-ball{ball}-cap{cap}-flags{flags}-restart{restart}', dict(
                clip=clip, current_amplitude=current, ball_amplitude=ball, state_flags=flags,
                cap_delta=cap, restart=restart, direction_mask=0)
    for height in (-74.0, -73.0, -72.0, 0.0):
        yield f'clip61-height-{height}', dict(clip=61, prediction_y_7cc=height, roster_a3=255, state_flags=0)
    for mask in (1, 2, 3, 4, 8, 15):
        yield f'clip61-direction-{mask}', dict(clip=61, direction_mask=mask, body_heading=32768,
            position_x=10000.0, ball_axis=3000.0, state_flags=1)


def verify(state, image, core, output):
    output.mkdir(parents=True, exist_ok=False)
    reference, math_class = reference_classes(core / 'reference')
    for name in ('locomotion_selection.hpp', 'locomotion_speed.hpp', 'locomotion_direction.hpp',
                 'locomotion_tables.hpp', 'locomotion_special.hpp'):
        (output / name).write_bytes((Path(__file__).with_name('recovered') / name).read_bytes())
    (output / 'special.cpp').write_text(SOURCE + SPEED_SOURCE)
    command = ['g++', '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror', '-fno-fast-math', '-ffp-contract=off',
               '-shared', '-fPIC', str(output / 'special.cpp'), '-o', str(output / 'special.so')]
    subprocess.run(command, check=True, capture_output=True)
    native = configure(C.CDLL(str((output / 'special.so').resolve()))); configure_speed(native)
    player = PLAYER_BASE + state.ram[0x01564920 + 13] * PLAYER_STRIDE
    words, cases, instructions = {}, [], 0
    for ident, edits in scenarios():
        ref = reference(state.ram, state.scratch)
        context, ball, mode = [ref.read(address, 'I') for address in (0x012a6238, 0x012a6250, 0x012a623c)]
        roster = 0x0155f1c0 + ref.read(player + 0xd8, 'B') * 10880 + ref.read(player + 0xd7, 'B') * 272
        ref.write(player + 0x2fa, 'B', 4); ref.write(player + 0x2fe, 'B', 0)
        value = Input()
        for name, (offset, kind) in FIELDS.items(): setattr(value.common, name, ref.read(player + offset, kind))
        value.common.direction_mask = ref.read(context + 0x48, 'I')
        value.common.context_player = ref.read(context + 14, 'B'); value.common.ball_amplitude = ref.read(ball + 0x58, 'i')
        value.prediction_y_7cc = ref.read(ball + 0x7cc, 'f'); value.roster_a3 = ref.read(roster + 0xa3, 'B')
        value.auxiliary_105 = ref.read(player + 0x105, 'B')
        value.timing_byte = ref.read(0x012997b0 + ref.read(0x01304034, 'i'), 'B')
        near = 0
        for name, item in edits.items():
            if name in FIELDS:
                offset, kind = FIELDS[name]; ref.write(player + offset, kind, item); setattr(value.common, name, item)
            elif name == 'ball_amplitude': ref.write(ball + 0x58, 'i', item); value.common.ball_amplitude = item
            elif name == 'direction_mask': ref.write(context + 0x48, 'I', item); value.common.direction_mask = item
            elif name == 'near': near = item
            elif name == 'restart': ref.write(player + 0x2e0, 'H', 32767 if item else 0)
            elif name == 'position_x': ref.write(player + 0x2c4, 'f', item)
            elif name == 'ball_axis': ref.write(ball + 0x2c, 'f', item)
            elif name == 'prediction_y_7cc': ref.write(ball + 0x7cc, 'f', item); value.prediction_y_7cc = item
            elif name == 'roster_a3': ref.write(roster + 0xa3, 'B', item); value.roster_a3 = item
            elif name == 'cap_delta':
                ref.write(ball + 0x434, 'f', ref.read(player + 0x2c4, 'f') + item)
                ref.write(ball + 0xb34, 'f', ref.read(player + 0x2cc, 'f'))
            else: raise ValueError('unhandled edit: ' + name)
        value.near_squared_distance = near
        transitions, refreshes, dependencies, before_tail, write_sites = [], [], [], [], []
        def observe(pc, opcode, registers, floats):
            if image.read(pc) != struct.pack('<I', opcode): raise ValueError('changed original instruction')
            words[pc] = opcode
            if pc == 0x01878e24:
                value.common.chase_gate = int(bool(registers[2])); dependencies.append(['chase_gate', value.common.chase_gate])
            if pc == 0x01878e34:
                value.common.chase_amplitude = C.c_int32(registers[2] & 0xffffffff).value
                dependencies.append(['chase_prediction', value.common.chase_amplitude])
            if pc == 0x017d93cc: value.cap_squared_distance = registers[2] & 0xffffffff
            if pc == 0x01879018:
                value.common.clip_restart = int(bool(registers[2])); dependencies.append(['restart', value.common.clip_restart])
            if pc == 0x011677a0: transitions.append([registers[5] & 65535, registers[6] & 0xffffffff])
            if pc == 0x0119f860: refreshes.append(registers[5] & 255)
            if pc in (0x01878e08, 0x01878fe8, 0x01879048, 0x01879050): write_sites.append(pc)
            if pc == 0x0187927c:
                d = CommonDecision(selected_amplitude=C.c_int32(registers[17] & 0xffffffff).value,
                    amplitude_before_speed=ref.read(player + 0xe0, 'i'), substate=ref.read(player + 0xdc, 'H'),
                    turn_heading=ref.read(player + 0xf8, 'H'), auxiliary_134=ref.read(player + 0x134, 'B'))
                expected = Decision(decision=d, auxiliary_105=ref.read(player + 0x105, 'B'), phase_130=ref.read(player + 0x130, 'B'))
                speed = SpeedInput(current_amplitude=d.amplitude_before_speed, selected_amplitude=d.selected_amplitude,
                    roster_ae=ref.read(roster + 0xae, 'H'), attribute_124=value.common.attribute_124,
                    mode_phase_5=ref.read(mode + 5, 'B'), mode_2=ref.read(mode + 2, 'B'), profile_flag=ref.read(0x01304034, 'i'))
                before_tail.append((expected, speed))
        ref.run(0x0187866c, [], initial_registers={19: player, 18: near, 17: value.common.initial_amplitude},
            stop_before=0x0187930c, math_model=math_class(ref), instruction_observer=observe, full_quadwords=True, max_instructions=50000)
        if len(before_tail) != 1: raise ValueError('speed tail not reached once')
        expected, speed = before_tail[0]
        if 0x01878e08 in write_sites: expected.decision.writes |= 16
        if any(p in write_sites for p in (0x01878fe8, 0x01879050)): expected.writes |= 1
        if 0x01879048 in write_sites: expected.writes |= 2
        if transitions:
            if len(transitions) != 1 or refreshes != [4]: raise ValueError('unexpected transition')
            expected.decision.requested_clip, expected.decision.start_frame = transitions[0]
            expected.decision.change_clip = 1; expected.decision.refresh_window = 4
        elif refreshes: raise ValueError('refresh without transition')
        actual = Decision(); status = native.select_special(C.byref(value), C.byref(actual))
        if status != 1 or bytes(actual) != bytes(expected):
            raise AssertionError(f'{ident}: status {status}, input {bytes(value).hex()}, expected {bytes(expected).hex()}, actual {bytes(actual).hex()}')
        speed.current_amplitude = actual.decision.amplitude_before_speed; speed.selected_amplitude = actual.decision.selected_amplitude
        expected_speed = ref.read(player + 0xe0, 'i')
        if native.step_speed(C.byref(speed)) != expected_speed: raise AssertionError('composed speed differs: ' + ident)
        instructions += ref.instructions
        cases.append({'id': ident, 'input_hex': bytes(value).hex(), 'expected_hex': bytes(expected).hex(),
            'speed_input_hex': bytes(speed).hex(), 'expected_speed': expected_speed, 'edits': edits,
            'dependencies': dependencies, 'transitions': transitions, 'instructions': ref.instructions,
            'memory_kind': 'modified_snapshot', 'result_player_sha256': digest(ref.ram[player:player + PLAYER_STRIDE])})
    (output / 'special-vectors.json').write_text(json.dumps({'schema_version': 1, 'state_sha256': state.metadata['sha256'],
        'input_bytes': 60, 'decision_bytes': 36, 'cases': cases}, separators=(',', ':')) + '\n')
    (output / 'special-instruction-words.json').write_text(json.dumps({hex(k): v for k, v in sorted(words.items())}) + '\n')
    report = {'schema_version': 1, 'run_id': str(uuid.uuid4()), 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
        'result': 'passed', 'state_sha256': state.metadata['sha256'], 'sources': image.sources,
        'comparisons': len(cases), 'composed_speed_comparisons': len(cases), 'original_instructions': instructions,
        'instruction_words': len(words), 'entry': '0x0187866c', 'stop_before': '0x0187930c',
        'compile_command': command,
        'tool_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in
            ('verify_special.py', 'special_abi.py', 'selection_abi.py', 'speed_abi.py', 'verify_selection.py',
             'pose.py', 'pose_reference.py', 'savestate.py')},
        'files_sha256': {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir())},
        'scope': 'Owned 61/62/63 post-direction decisions plus composed integer speed; reached original gate/prediction/restart helpers supply explicit numeric boundary inputs and run unchanged. Modified copies of stationary save with explicit near-distance register. No full action/frame, all clips, contact retarget, native units or complete gameplay equivalence.'}
    (output / 'special-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description='Conferir caminhos de locomoção dos clips 61/62/63 PES')
    for name in ('state', 'elf', 'over', 'core', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(); state = SaveState(args.state)
    report = verify(state, Image(args.elf, args.over), args.core, args.output)
    if digest(args.state.read_bytes()) != state.metadata['sha256']: raise ValueError('state changed')
    print(json.dumps({k: report[k] for k in ('result', 'comparisons', 'original_instructions', 'instruction_words')}, indent=2))


if __name__ == '__main__': main()
