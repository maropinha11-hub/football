#!/usr/bin/env python3
"""Check actual post-direction dispatch for 28/35/48/864, including helpers.

The phase/encoded requests are observed at their entry. Those original calls
still execute; their full state/pose semantics are not claimed by this API.
"""
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
from arithmetic import classes as arithmetic_classes
from pose import reference_classes
from replay import PLAYER_BASE, PLAYER_STRIDE
from savestate import SaveState, digest
from selection_abi import Decision as CommonDecision
from speed_abi import Input as SpeedInput, SOURCE as SPEED_SOURCE, configure as configure_speed
from variant_abi import Input, Decision, SOURCE, configure
from verify_selection import FIELDS


def scenarios():
    for clip, near, mask, restart in itertools.product((28, 35, 48, 864),
            (65535, 65536, 102399, 102400, 123904, 123905), (0, 1), (0, 1)):
        yield f'clip{clip}-near{near}-mask{mask}-restart{restart}', dict(clip=clip,
            near_squared_distance=near, direction_mask=mask, restart=restart)
    for clip, initial, ball in itertools.product((35, 48), (-2147483648, -1, 0, 8000, 2147483647), (4095, 4096)):
        yield f'clip{clip}-initial{initial}-ball{ball}', dict(clip=clip, initial_amplitude=initial, ball_amplitude=ball)
    for clip, flags, stat, base in itertools.product((28, 864), (0, 0x4000, 0xffffffff),
            (0, 49, 50, 51, 127), (-2147483648, 0, 8000, 2147483647)):
        yield f'clip{clip}-flags{flags}-stat{stat}-base{base}', dict(clip=clip,
            flags_1b0=flags, roster_ac=stat << 4, amplitude_120=base)
    for difference in (14, 15, 16, 65535):
        yield f'clip28-difference{difference}', dict(clip=28, direction_mask=1, body_input_difference=difference)
    for stat, phase, profile in itertools.product((0, 50, 51, 127), (0, 1), (0, 1)):
        yield f'clip28-brake-stat{stat}-phase{phase}-profile{profile}', dict(clip=28,
            roster_ae=stat << 2, mode_phase_5=phase, profile_flag=profile, current_amplitude=8000, amplitude_120=4000)
    for ab, cc, step in itertools.product((0, 40, 65, 66, 127), (0, 20, 127), (0.5, 1.0, 1.75)):
        yield f'clip28-rate-ab{ab}-cc{cc}-step{step}', dict(clip=28, roster_ab=ab << 1,
            roster_cc=cc, configuration_step=step)
    for mask, aux, current in itertools.product((0, 1), (0, 8), (7743, 7744, 8000)):
        yield f'clip48-mask{mask}-aux{aux}-current{current}', dict(clip=48,
            direction_mask=mask, auxiliary_105=aux, initial_amplitude=8000, current_amplitude=current)
    for mask in (1, 2, 3, 4, 8, 15):
        yield f'clip48-chase-mask{mask}', dict(clip=48, direction_mask=mask, body_heading=32768,
            position_x=10000.0, ball_axis=3000.0)


def verify(state, image, core, output, rounding):
    output.mkdir(parents=True, exist_ok=False)
    reference_classes(core / 'reference')  # Pins the supplied reference sources.
    reference, math_class = arithmetic_classes(core / 'reference', rounding, rounding, 'nearest', 'nearest')
    headers = ('locomotion_selection.hpp', 'locomotion_speed.hpp', 'locomotion_direction.hpp',
        'locomotion_tables.hpp', 'locomotion_special.hpp', 'locomotion_prediction.hpp', 'locomotion_variants.hpp')
    for name in headers: (output / name).write_bytes((Path(__file__).with_name('recovered') / name).read_bytes())
    (output / 'variants.cpp').write_text(SOURCE + SPEED_SOURCE)
    command = ['g++', '-std=c++14', '-O0', '-Wall', '-Wextra', '-Werror', '-fno-fast-math', '-ffp-contract=off',
        '-shared', '-fPIC', str(output / 'variants.cpp'), '-o', str(output / 'variants.so')]
    subprocess.run(command, check=True, capture_output=True)
    native = configure(C.CDLL(str((output / 'variants.so').resolve()))); configure_speed(native)
    player = PLAYER_BASE + state.ram[0x01564920 + 13] * PLAYER_STRIDE
    words, cases, instructions = {}, [], 0
    for ident, edits in scenarios():
        ref = reference(state.ram, state.scratch)
        context, ball, mode = [ref.read(a, 'I') for a in (0x012a6238, 0x012a6250, 0x012a623c)]
        roster = 0x0155f1c0 + ref.read(player + 0xd8, 'B') * 10880 + ref.read(player + 0xd7, 'B') * 272
        ref.write(player + 0x2fa, 'B', 4); ref.write(player + 0x2fe, 'B', 0)
        i = Input()
        for n, (off, kind) in FIELDS.items(): setattr(i.common, n, ref.read(player + off, kind))
        i.common.direction_mask = ref.read(context + 0x48, 'I'); i.common.context_player = ref.read(context + 14, 'B')
        i.common.ball_amplitude = ref.read(ball + 0x58, 'i')
        fields = {'flags_1b0': (player + 0x1b0, 'I'), 'amplitude_120': (player + 0x120, 'i'),
            'current_frame': (player + 0x2e4, 'f'), 'configuration_step': (mode + 0x4c, 'f'),
            'roster_ac': (roster + 0xac, 'H'), 'roster_ae': (roster + 0xae, 'H'),
            'roster_ab': (roster + 0xab, 'B'), 'roster_cc': (roster + 0xcc, 'B'),
            'attribute_12c': (player + 0x12c, 'B'), 'auxiliary_105': (player + 0x105, 'B'),
            'auxiliary_133': (player + 0x133, 'B'), 'mode_phase_5': (mode + 5, 'B'), 'mode_2': (mode + 2, 'B'),
            'profile_flag': (0x01304034, 'i')}
        for n, (address, kind) in fields.items(): setattr(i, n, ref.read(address, kind))
        i.fpu_rounding = int(rounding == 'chop')
        for n, v in edits.items():
            if n in FIELDS:
                off, kind = FIELDS[n]; ref.write(player + off, kind, v); setattr(i.common, n, v)
            elif n in fields:
                address, kind = fields[n]; ref.write(address, kind, v); setattr(i, n, v)
            elif n == 'direction_mask': ref.write(context + 0x48, 'I', v); i.common.direction_mask = v
            elif n == 'ball_amplitude': ref.write(ball + 0x58, 'i', v); i.common.ball_amplitude = v
            elif n == 'restart': ref.write(player + 0x2e0, 'H', 32767 if v else 0)
            elif n in ('near_squared_distance', 'body_input_difference'): setattr(i, n, v)
            elif n == 'position_x': ref.write(player + 0x2c4, 'f', v)
            elif n == 'ball_axis': ref.write(ball + 0x2c, 'f', v)
            else: raise ValueError(n)
        i.timing_byte = ref.read(0x012997b0 + i.profile_flag, 'B')
        expected = Decision(); requested, sites, before_tail = [], set(), []
        def observe(pc, opcode, registers, floats):
            if image.read(pc) != struct.pack('<I', opcode): raise ValueError('changed original instruction')
            words[pc] = opcode; sites.add(pc)
            if pc in (0x01878998, 0x01878be4): i.common.clip_restart = int(bool(registers[2]))
            if pc == 0x018788a0: i.common.chase_gate = int(bool(registers[2]))
            if pc == 0x018788b0: i.common.chase_amplitude = C.c_int32(registers[2] & 0xffffffff).value
            if pc == 0x01878754: expected.animation_rate = ref.read(player + 0x138, 'f')
            if pc == 0x018a4720: requested.append((1, registers[5] & 65535, struct.unpack('<f', struct.pack('<I', floats[12]))[0], 0))
            if pc == 0x018a4de0: requested.append((2, registers[5] & 65535, 0, C.c_int32(registers[6] & 0xffffffff).value))
            if pc == 0x0187927c:
                d = CommonDecision(selected_amplitude=C.c_int32(registers[17] & 0xffffffff).value,
                    amplitude_before_speed=ref.read(player + 0xe0, 'i'), substate=ref.read(player + 0xdc, 'H'),
                    turn_heading=ref.read(player + 0xf8, 'H'), auxiliary_134=ref.read(player + 0x134, 'B'))
                expected.decision = d
                expected.flags_1a0 = ref.read(player + 0x1a0, 'I')
                expected.auxiliary_105 = ref.read(player + 0x105, 'B'); expected.auxiliary_133 = ref.read(player + 0x133, 'B')
                expected.phase_130 = ref.read(player + 0x130, 'B')
                if i.common.clip == 28:
                    expected.writes |= 16; expected.decision.writes |= 2
                speed = SpeedInput(current_amplitude=d.amplitude_before_speed, selected_amplitude=d.selected_amplitude,
                    roster_ae=i.roster_ae, attribute_124=i.common.attribute_124, mode_phase_5=i.mode_phase_5,
                    mode_2=i.mode_2, profile_flag=i.profile_flag)
                before_tail.append(speed)
        ref.run(0x0187866c, [], initial_registers={19: player, 18: i.near_squared_distance,
            17: i.common.initial_amplitude, 20: i.body_input_difference}, stop_before=0x0187930c,
            math_model=math_class(ref), instruction_observer=observe, full_quadwords=True, max_instructions=50000)
        if len(before_tail) != 1 or len(requested) > 1: raise ValueError('unexpected dispatch sequence')
        if 0x018789bc in sites or 0x01878c08 in sites: expected.writes |= 2
        if 0x01878930 in sites: expected.writes |= 1
        if 0x01878928 in sites: expected.writes |= 4
        if 0x01878940 in sites: expected.writes |= 8
        if requested:
            kind, clip, frame, encoded = requested[0]
            expected.transition_kind = kind; expected.decision.change_clip = 1; expected.decision.requested_clip = clip
            expected.comparison_frame = frame; expected.encoded_start = encoded
        actual = Decision(); status = native.select_variant(C.byref(i), C.byref(actual))
        if status != 1 or bytes(actual) != bytes(expected):
            raise AssertionError(f'{ident}: status={status}, input={bytes(i).hex()}, expected={bytes(expected).hex()}, actual={bytes(actual).hex()}')
        speed = before_tail[0]; speed.current_amplitude = actual.decision.amplitude_before_speed
        speed.selected_amplitude = actual.decision.selected_amplitude
        expected_speed = ref.read(player + 0xe0, 'i')
        if native.step_speed(C.byref(speed)) != expected_speed: raise AssertionError('speed mismatch: ' + ident)
        instructions += ref.instructions
        cases.append({'id': ident, 'input_hex': bytes(i).hex(), 'expected_hex': bytes(expected).hex(),
            'speed_input_hex': bytes(speed).hex(), 'expected_speed': expected_speed, 'edits': edits,
            'instructions': ref.instructions, 'memory_kind': 'modified_snapshot'})
    (output / 'variant-vectors.json').write_text(json.dumps({'schema_version': 1,
        'state_sha256': state.metadata['sha256'], 'input_bytes': 88, 'decision_bytes': 56, 'cases': cases}, separators=(',', ':')) + '\n')
    (output / 'variant-instruction-words.json').write_text(json.dumps({hex(k): v for k, v in sorted(words.items())}) + '\n')
    report = {'schema_version': 1, 'run_id': str(uuid.uuid4()), 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
        'result': 'passed', 'state_sha256': state.metadata['sha256'], 'sources': image.sources,
        'comparisons': len(cases), 'composed_speed_comparisons': len(cases), 'original_instructions': instructions,
        'instruction_words': len(words), 'entry': '0x0187866c', 'stop_before': '0x0187930c', 'compile_command': command,
        'arithmetic': {'fpu': rounding, 'division': 'nearest', 'sqrt': 'nearest'},
        'tool_sha256': {n: digest(Path(__file__).with_name(n).read_bytes()) for n in
            ('verify_variants.py', 'variant_abi.py', 'selection_abi.py', 'speed_abi.py', 'verify_selection.py', 'arithmetic.py', 'pose.py', 'savestate.py')},
        'files_sha256': {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir())},
        'scope': 'Owned branches 28/35/48/864 with actual original dependencies running. Chase/restart boundary values observed; rate compared before the later phase helper can overwrite it; phase/encoded requests compared before original helper execution. Modified stationary snapshot and supplied near/difference registers. No full action/frame, retarget or native gameplay parity.'}
    (output / 'variant-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    p = argparse.ArgumentParser(description='Conferir clips de locomoção 28/35/48/864 PES')
    for n in ('state', 'elf', 'over', 'core', 'output'): p.add_argument('--' + n, type=Path, required=True)
    p.add_argument('--fpu-rounding', choices=('nearest', 'chop'), default='nearest')
    a = p.parse_args(); state = SaveState(a.state)
    report = verify(state, Image(a.elf, a.over), a.core, a.output, a.fpu_rounding)
    if digest(a.state.read_bytes()) != state.metadata['sha256']: raise ValueError('state changed')
    print(json.dumps({k: report[k] for k in ('result', 'comparisons', 'original_instructions', 'instruction_words')}, indent=2))

if __name__ == '__main__': main()
