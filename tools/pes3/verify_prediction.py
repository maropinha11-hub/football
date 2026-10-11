#!/usr/bin/env python3
"""Fresh original chase/gate comparisons in isolated arithmetic profiles."""
import argparse
import ctypes as C
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import subprocess
import uuid
from actions import Image
from arithmetic import classes
from prediction_abi import Input, Sample, Decision, GateInput, SOURCE, configure
from replay import PLAYER_BASE, PLAYER_STRIDE
from savestate import SaveState, digest


def forecasts():
    for horizon in range(1, 129):
        for variant in range(3):
            roster = (horizon * 19 + variant * 41) & 255
            value = Input(position_divisor=(1.0, 256.0, 512.0)[variant], roster_a3=roster)
            value.player_xz[:] = (variant * 113.25, -variant * 227.5)
            cutoff = int(-144 * ((roster >> 2) + 148) / 183)
            samples = (Sample * 129)()
            for i, sample in enumerate(samples):
                sample.xyz[:] = (float(variant * 73 + i * 5) - 2048.25, float(cutoff - 1), float(i * 3 - variant * 61) + 127.75)
                sample.validity = -1 if (i + variant) % 2 else 0
            if horizon < 128:
                samples[horizon].validity = variant
                samples[horizon].xyz[1] = float(cutoff) + (0, .25, 1)[variant]
            yield f'horizon-{horizon}-variant-{variant}', value, samples
    for roster in range(256):
        value = Input(position_divisor=256, roster_a3=roster)
        value.player_xz[:] = (4096.25, -2048.5)
        samples = (Sample * 129)()
        cutoff = int(-144 * ((roster >> 2) + 148) / 183)
        for i, sample in enumerate(samples):
            sample.xyz[:] = (i * 31.25, cutoff - 1, -i * 17.5); sample.validity = -1
        samples[16].validity = 0; samples[16].xyz[1] = cutoff
        yield f'packed-height-{roster}', value, samples
    for distance in (0, 95.75, 96.0, 96.75, 97.0, 97.75):
        value = Input(position_divisor=256)
        samples = (Sample * 129)()
        for sample in samples: sample.xyz[:] = (distance, 0, 0)
        yield f'distance-deadzone-{distance}', value, samples


def gates():
    for mask in (0, 1, 2, 3, 4, 8, 15):
        for heading in (0, 12543, 12544, 32768, 65535):
            for axis, height in ((2752.75, 0.0), (2753.0, 0.0), (-2753.0, 0.0), (0.0, -1000.0)):
                yield f'gate-mask{mask}-body{heading}-axis{axis}-height{height}', dict(
                    mask=mask, heading=heading, axis=axis, height=height, position_x=10000.0)
    yield 'captured-gate', {}


def verify(state, image, core, output, fpu):
    output.mkdir(parents=True, exist_ok=False)
    reference, math_class = classes(core / 'reference', fpu, fpu, 'nearest', 'nearest')
    for name in ('locomotion_prediction.hpp', 'locomotion_direction.hpp', 'locomotion_tables.hpp', 'locomotion_speed.hpp'):
        (output / name).write_bytes((Path(__file__).with_name('recovered') / name).read_bytes())
    (output / 'prediction.cpp').write_text(SOURCE)
    command = ['g++', '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror', '-fno-fast-math', '-ffp-contract=off',
               '-shared', '-fPIC', str(output / 'prediction.cpp'), '-o', str(output / 'prediction.so')]
    subprocess.run(command, check=True, capture_output=True)
    native = configure(C.CDLL(str((output / 'prediction.so').resolve())))
    player = PLAYER_BASE + state.ram[0x01564920 + 13] * PLAYER_STRIDE
    words, cases, gate_cases, instructions = {}, [], [], 0
    for ident, value, samples in forecasts():
        value.fpu_rounding = int(fpu == 'chop')
        ref = reference(state.ram, state.scratch)
        ball, mode = ref.read(0x012a6250, 'I'), ref.read(0x012a623c, 'I')
        roster = 0x0155f1c0 + ref.read(player + 0xd8, 'B') * 10880 + ref.read(player + 0xd7, 'B') * 272
        ref.write(roster + 0xa3, 'B', value.roster_a3); ref.write(mode + 0x48, 'f', value.position_divisor)
        for offset, number in zip((0x2c4, 0x2cc), value.player_xz): ref.write(player + offset, 'f', number)
        for i, sample in enumerate(samples):
            for offset, number in zip((0x434, 0x7b4, 0xb34), sample.xyz): ref.write(ball + offset + i * 4, 'f', number)
            ref.write(ball + 0x1074 + i * 4, 'i', sample.validity)
        boundary = []
        def observe(pc, opcode, registers, floats):
            if image.read(pc) != struct.pack('<I', opcode): raise ValueError('changed original instruction')
            words[pc] = opcode
            if pc == 0x01855038: boundary.append((registers[16] & 65535, C.c_int32(registers[2] & 0xffffffff).value))
        ref.run(0x01854f20, [player], math_model=math_class(ref), instruction_observer=observe, full_quadwords=True, max_instructions=12000)
        if len(boundary) != 1: raise ValueError('distance boundary not reached exactly once')
        expected = Decision(C.c_int32(ref.last_registers[2] & 0xffffffff).value, boundary[0][0], 0, boundary[0][1])
        actual = Decision(); status = native.predict_chase(C.byref(value), samples, 129, C.byref(actual))
        if status != 1 or bytes(actual) != bytes(expected):
            raise AssertionError(f'{ident}: status {status}, input {bytes(value).hex()}, expected {bytes(expected).hex()}, actual {bytes(actual).hex()}')
        instructions += ref.instructions
        cases.append({'id': ident, 'input_hex': bytes(value).hex(), 'samples_hex': bytes(samples).hex(),
            'expected_hex': bytes(expected).hex(), 'instructions': ref.instructions, 'memory_kind': 'modified_snapshot'})
    for ident, edits in gates():
        ref = reference(state.ram, state.scratch)
        context, ball = ref.read(0x012a6238, 'I'), ref.read(0x012a6250, 'I')
        roster = 0x0155f1c0 + ref.read(player + 0xd8, 'B') * 10880 + ref.read(player + 0xd7, 'B') * 272
        if edits:
            ref.write(context + 0x48, 'I', edits['mask']); ref.write(player + 0xea, 'H', edits['heading'])
            ref.write(ball + 0x2c, 'f', edits['axis']); ref.write(ball + 0x7b4, 'f', edits['height'])
            ref.write(player + 0x2c4, 'f', edits['position_x'])
        value = GateInput(ball_axis_2c=ref.read(ball + 0x2c, 'f'), prediction_y_7b4=ref.read(ball + 0x7b4, 'f'),
            body_heading=ref.read(player + 0xea, 'H'), roster_a3=ref.read(roster + 0xa3, 'B'))
        def observe(pc, opcode, registers, floats):
            if image.read(pc) != struct.pack('<I', opcode): raise ValueError('changed original instruction')
            words[pc] = opcode
            if pc == 0x017d59a4: value.other_squared_distance = registers[2] & 0xffffffff
            if pc == 0x017d5a90: value.action_input_heading = registers[2] & 65535
        ref.run(0x017d5990, [player], math_model=math_class(ref), instruction_observer=observe, full_quadwords=True, max_instructions=4096)
        expected = ref.last_registers[2] & 0xffffffff
        actual = C.c_uint8(42); status = native.chase_gate(C.byref(value), C.byref(actual))
        if status != 1 or actual.value != expected: raise AssertionError(f'{ident}: gate differs {actual.value} != {expected}')
        instructions += ref.instructions
        gate_cases.append({'id': ident, 'input_hex': bytes(value).hex(), 'expected': expected,
            'edits': edits, 'memory_kind': 'modified_snapshot' if edits else 'captured_snapshot', 'instructions': ref.instructions})
    (output / 'prediction-vectors.json').write_text(json.dumps({'schema_version': 1, 'state_sha256': state.metadata['sha256'],
        'input_bytes': 16, 'sample_bytes': 16, 'decision_bytes': 12, 'gate_input_bytes': 20,
        'cases': cases, 'gate_cases': gate_cases}, separators=(',', ':')) + '\n')
    (output / 'prediction-instruction-words.json').write_text(json.dumps({hex(k): v for k, v in sorted(words.items())}) + '\n')
    report = {'schema_version': 1, 'run_id': str(uuid.uuid4()), 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
        'result': 'passed', 'state_sha256': state.metadata['sha256'], 'sources': image.sources,
        'prediction_comparisons': len(cases), 'gate_comparisons': len(gate_cases),
        'gate_true_cases': sum(c['expected'] for c in gate_cases), 'original_instructions': instructions, 'instruction_words': len(words),
        'arithmetic_profile': {'fpu': fpu, 'division': 'nearest', 'sqrt': 'nearest'}, 'compile_command': command,
        'tool_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in
            ('verify_prediction.py', 'prediction_abi.py', 'arithmetic.py', 'pose.py', 'pose_reference.py', 'savestate.py')},
        'files_sha256': {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir())},
        'scope': 'Owned chase prediction from an existing 129-sample forecast and gate predicate from reached original selected-other-player distance. Full original helpers execute unchanged on copied stationary RAM. No forecast generation, opponent lookup rewrite, full action/frame, hardware equivalence, native unit conversion or gameplay integration.'}
    (output / 'prediction-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description='Conferir predição/gate de perseguição PES em perfis isolados')
    for name in ('state', 'elf', 'over', 'core', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--fpu-rounding', choices=('nearest', 'chop'), default='nearest')
    args = parser.parse_args(); state = SaveState(args.state)
    report = verify(state, Image(args.elf, args.over), args.core, args.output, args.fpu_rounding)
    if digest(args.state.read_bytes()) != state.metadata['sha256']: raise ValueError('state changed')
    print(json.dumps({k: report[k] for k in ('result', 'prediction_comparisons', 'gate_comparisons', 'gate_true_cases', 'original_instructions')}, indent=2))


if __name__ == '__main__': main()
