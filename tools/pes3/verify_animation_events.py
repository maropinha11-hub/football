#!/usr/bin/env python3
"""Prove temporal eligibility against fresh original calls on training saves.

Boundary probes explicitly edit copied phase fields. They are not observed
game frames. No original helper results are stubbed or injected.
"""
import argparse
from datetime import datetime, timezone
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import uuid

from actions import Image
from event_abi import Anchor741, Input, SOURCE, configure
from model_reference import model_classes
from replay import PLAYER_BASE, PLAYER_STRIDE
from savestate import SaveState, digest


def neighboring_float(value, direction):
    raw = struct.unpack('<I', struct.pack('<f', value))[0]
    if value == 0:
        raw = 1 if direction > 0 else 0x80000001
    else:
        raw += direction if value > 0 else -direction
    return struct.unpack('<f', struct.pack('<I', raw))[0]


def read_input(ram, player):
    value = Input()
    value.phase, = struct.unpack_from('<f', ram, player + 0x2E4)
    value.step, = struct.unpack_from('<f', ram, player + 0x138)
    for name, offset in (('blend_window', 0x2FA), ('blend_tick', 0x2FB), ('cycle_fix', 0x2FE)):
        setattr(value, name, ram[player + offset])
    return value


def write_input(ref, player, value):
    ref.write(player + 0x2E4, 'f', value.phase)
    ref.write(player + 0x138, 'f', value.step)
    for name, offset in (('blend_window', 0x2FA), ('blend_tick', 0x2FB), ('cycle_fix', 0x2FE)):
        ref.write(player + offset, 'B', getattr(value, name))


def boundaries():
    for step in (0, 0.25, 1, 2, 3.25, -1):
        for marker in (0, 24, 48):
            for edge in (marker - step / 2, marker + step / 2):
                for phase in (neighboring_float(edge, -1), edge, neighboring_float(edge, 1)):
                    yield Input(phase=phase, step=step), marker
    for blend in (0, 1, 4, 255):
        for tick in (0, 1, 255):
            for cycle in (0, 1, 255):
                yield Input(phase=24, step=1, blend_window=blend, blend_tick=tick, cycle_fix=cycle), 24
    for marker in (-2147483648, -16777217, 16777217, 2147483647):
        yield Input(phase=float(marker), step=4), marker


def anchor_boundaries():
    values = {-8192.0, 0.0, 8192.0}
    for threshold in (-51, -16, 13, 37):
        edge = -209.0 - threshold
        values.update((edge - 1, neighboring_float(edge, -1), edge,
                       neighboring_float(edge, 1), edge + 1, edge + 0.75, edge - 0.75))
    return sorted(values)


def verify(paths, image, core, output):
    output.mkdir(parents=True, exist_ok=False)
    for name in ('animation_events.hpp', 'ball_anchor_741.hpp', 'bind_arithmetic.hpp', 'pose_rig.hpp', 'pose_ops.hpp'):
        (output / name).write_bytes((Path(__file__).with_name('recovered') / name).read_bytes())
    (output / 'animation_events.cpp').write_text(SOURCE)
    command = ['g++', '-std=c++14', '-O0', '-Wall', '-Wextra', '-Werror', '-fno-fast-math',
               '-ffp-contract=off', '-shared', '-fPIC', str(output / 'animation_events.cpp'),
               '-o', str(output / 'animation_events.so')]
    subprocess.run(command, check=True, capture_output=True)
    lib = configure(C.CDLL(str((output / 'animation_events.so').resolve())))
    words, cases, hashes, anchors, total_instructions = {}, [], [], [], 0
    source_points = image.read(0x018E0350, 30)
    if struct.unpack('<15h', source_points) != (-70, -265, -156, -55, -235, -157,
                                               -38, -209, -164, -20, -178, -173, 11, -149, -177):
        raise ValueError('anchor 741 source points differ')

    def observe(pc, raw, registers, floats):
        nonlocal total_instructions
        if image.read(pc) != struct.pack('<I', raw):
            raise ValueError('phase-gate instruction differs from source')
        words[pc] = raw
        total_instructions += 1

    for index, path in enumerate(paths):
        state = SaveState(path)
        hashes.append(state.metadata['sha256'])
        for profile in ('nearest', 'chop'):
            reference, math_class = model_classes(core / 'reference', profile, profile)
            ref = reference(state.ram, state.scratch)
            captured = [(i, read_input(state.ram, PLAYER_BASE + i * PLAYER_STRIDE), marker)
                        for i in range(1, 23) for marker in (0, 24, 48)]
            modified = [(state.ram[0x01564920 + 13], value, marker) for value, marker in boundaries()]
            for memory_kind, rows in (('captured_fields', captured), ('modified_fields', modified)):
                for ident, value, marker in rows:
                    player = PLAYER_BASE + ident * PLAYER_STRIDE
                    write_input(ref, player, value)
                    expected = ref.run(0x0116AFE0, [player, marker], math_model=math_class(ref),
                                       instruction_observer=observe, max_instructions=100,
                                       full_quadwords=True)
                    actual = C.c_uint(0x2A2A2A2A)
                    status = lib.owned_phase_gate(C.byref(value), marker, int(profile == 'chop'), C.byref(actual))
                    if status != 1 or actual.value != expected:
                        raise AssertionError(f'phase gate differs: state {index + 1}, actor {ident}, {profile}')
                    cases.append({'state_index': index + 1, 'actor': ident, 'memory_kind': memory_kind,
                                  'profile': profile, 'input_hex': bytes(value).hex(),
                                  'marker': marker, 'expected': expected})
            print(f'phase gate matched state {index + 1} profile {profile}', flush=True)
            context = struct.unpack_from('<I', state.ram, 0x012A6238)[0]
            captured_y = struct.unpack_from('<f', state.ram, context + 0x41C)[0]
            metadata = struct.unpack_from('<I', state.ram, 0x012A778C)[0]
            if state.ram[metadata + 741 * 8:metadata + 742 * 8].hex() != '0e00000088132f00':
                raise ValueError('anchor 741 loaded metadata differs')
            if state.ram[0x018E0350:0x018E0350 + 30] != source_points:
                raise ValueError('anchor 741 loaded points differ')
            duration = struct.unpack_from('<I', state.ram, 0x014D6B00 + 741 * 4)[0]
            ref = reference(state.ram, state.scratch)
            rows = [('captured_fields', captured_y)]
            if index == 0:
                rows += [('modified_fields', y) for y in anchor_boundaries()]
            for memory_kind, y in rows:
                ref.write(context + 0x41C, 'f', y)
                for sample in (0, duration // 4, duration // 2):
                    at = ref.run(0x016CF420, [741, sample, 0x01F30000], math_model=math_class(ref),
                                 instruction_observer=observe, max_instructions=8000, full_quadwords=True)
                    expected = bytes(ref.ram[at:at + 6])
                    reference_index = ref.read(0x01F30000, 'H')
                    source_offset = at - 0x018E0350
                    if source_offset not in (0, 6, 12, 18, 24):
                        raise ValueError('original anchor pointer outside the five verified rows')
                    source_choice = source_offset // 6
                    actual = Anchor741()
                    status = lib.owned_anchor_741(y, int(profile == 'chop'), C.byref(actual))
                    if (status != 1 or bytes(actual.xyz) != expected
                            or actual.reference_index != reference_index or actual.choice != source_choice):
                        raise AssertionError('context-dependent anchor 741 differs from original sampler')
                    expected_output = expected + struct.pack('<HI', reference_index, source_choice)
                    anchors.append({'state_index': index + 1, 'memory_kind': memory_kind, 'profile': profile,
                                    'context_y_bits': hex(struct.unpack('<I', struct.pack('<f', y))[0]),
                                    'sample': sample, 'expected_hex': expected_output.hex(),
                                    'original_point_address': hex(at)})
            print(f'anchor 741 matched state {index + 1} profile {profile}', flush=True)
    (output / 'event-vectors.json').write_text(json.dumps({'cases': cases, 'anchor_741': anchors}, separators=(',', ':')) + '\n')
    (output / 'event-instructions.json').write_text(json.dumps({hex(k): v for k, v in sorted(words.items())}) + '\n')
    report = {'schema_version': 1, 'run_id': str(uuid.uuid4()), 'result': 'passed',
              'completed_at_utc': datetime.now(timezone.utc).isoformat(), 'state_hashes': hashes,
              'sources': image.sources, 'comparisons': len(cases),
              'captured_field_comparisons': sum(c['memory_kind'] == 'captured_fields' for c in cases),
              'boundary_comparisons': sum(c['memory_kind'] == 'modified_fields' for c in cases),
              'anchor_741_comparisons': len(anchors),
              'anchor_741_choices': sorted({Anchor741.from_buffer_copy(bytes.fromhex(c['expected_hex'])).choice for c in anchors}),
              'anchor_741_points_sha256': digest(source_points),
              'arithmetic_profiles': ['nearest', 'chop'], 'division': 'nearest',
              'original_instructions': total_instructions, 'instruction_words': len(words),
              'compile_command': command, 'runtime_enabled': False,
              'scope': 'Entire original temporal predicate 0116AFE0..0116B078, plus the context-dependent selection of five original local points for clip 741. Fresh original sampler calls verify coordinates/reference index at three sample times for each context, retaining source coordinates and units. Readiness during blend/cycle flags, signed conversion, COP1 rounding and asymmetric phase boundaries verified. Captured inputs and synthetic boundary probes are distinguished. Does not prove geometry, anatomy, ball release, event ordering, full frame or native game integration.'}
    report['files_sha256'] = {p.name: digest(p.read_bytes()) for p in output.iterdir() if p.is_file()}
    report['tool_sha256'] = {n: digest(Path(__file__).with_name(n).read_bytes()) for n in
                             ('verify_animation_events.py', 'event_abi.py', 'model_reference.py', 'savestate.py')}
    (output / 'event-report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description='Validar a regra temporal de contato das animações PES3')
    parser.add_argument('--state', type=Path, action='append', required=True)
    for name in ('elf', 'over', 'core', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.state, Image(args.elf, args.over), args.core, args.output)
    print(json.dumps({k: result[k] for k in ('result', 'comparisons', 'captured_field_comparisons',
                                          'boundary_comparisons', 'original_instructions')}, indent=2))


if __name__ == '__main__':
    main()
