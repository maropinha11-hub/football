#!/usr/bin/env python3
"""Fresh original-instruction comparisons of the locomotion speed tail."""
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
from speed_abi import Input, SOURCE, configure


def scenarios():
    yield 'captured-speed-input', None
    pairs = ((4000, 0), (0, 4000), (4000, 8000), (8000, 4000), (4000, 4000),
             (1, -1), (-2147483648, 1), (2147483647, 2147483647))
    for roster, attribute, profile, mode, pair in itertools.product(
            (0, 200, 204, 400, 508, 65535), (0, 100, 255), (0, 1),
            ((0, 0), (1, 0), (1, 4), (1, 16)), pairs):
        current, target = pair
        yield f'roster-{roster}-attr-{attribute}-profile-{profile}-mode-{mode}-pair-{pair}', Input(
            current, target, roster, attribute, mode[0], mode[1], (C.c_uint8 * 3)(), profile)


def verify(state, image, core, output):
    output.mkdir(parents=True, exist_ok=False)
    reference, math_class = reference_classes(core / 'reference')
    header = Path(__file__).with_name('recovered') / 'locomotion_speed.hpp'
    (output / header.name).write_bytes(header.read_bytes())
    (output / 'speed.cpp').write_text(SOURCE)
    command = ['g++', '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
               str(output / 'speed.cpp'), '-o', str(output / 'speed.so')]
    subprocess.run(command, check=True, capture_output=True)
    native = configure(C.CDLL(str((output / 'speed.so').resolve())))
    player = PLAYER_BASE + state.ram[0x01564920 + 13] * PLAYER_STRIDE
    words, cases, instructions = {}, [], 0
    for ident, edits in scenarios():
        ref = reference(state.ram, state.scratch)
        mode = ref.read(0x012a623c, 'I')
        roster = 0x0155f1c0 + ref.read(player + 0xd8, 'B') * 10880 + ref.read(player + 0xd7, 'B') * 272
        value = Input(ref.read(player + 0xe0, 'i'), ref.read(player + 0x11c, 'i'),
            ref.read(roster + 0xae, 'H'), ref.read(player + 0x124, 'B'),
            ref.read(mode + 5, 'B'), ref.read(mode + 2, 'B'), (C.c_uint8 * 3)(),
            ref.read(0x01304034, 'i')) if edits is None else edits
        ref.write(player + 0xe0, 'i', value.current_amplitude)
        ref.write(roster + 0xae, 'H', value.roster_ae)
        ref.write(player + 0x124, 'B', value.attribute_124)
        ref.write(mode + 5, 'B', value.mode_phase_5); ref.write(mode + 2, 'B', value.mode_2)
        ref.write(0x01304034, 'i', value.profile_flag)
        def observe(pc, opcode, registers, floats):
            if image.read(pc) != struct.pack('<I', opcode): raise ValueError('changed original word')
            words[pc] = opcode
        ref.run(0x0187927c, [], initial_registers={17: value.selected_amplitude, 19: player},
            stop_before=0x0187930c, math_model=math_class(ref), instruction_observer=observe,
            full_quadwords=True, max_instructions=100000)
        expected = ref.read(player + 0xe0, 'i')
        actual = native.step_speed(C.byref(value))
        if actual != expected: raise AssertionError(f'{ident}: expected {expected}, actual {actual}, input {bytes(value).hex()}')
        instructions += ref.instructions
        cases.append({'id': ident, 'input_hex': bytes(value).hex(), 'expected': expected,
            'memory_kind': 'captured_snapshot' if edits is None else 'modified_snapshot',
            'instructions': ref.instructions, 'result_ram_sha256': digest(ref.ram),
            'result_scratch_sha256': digest(ref.scratch)})
    (output / 'speed-vectors.json').write_text(json.dumps({'schema_version': 1,
        'state_sha256': state.metadata['sha256'], 'input_bytes': 20, 'cases': cases}, separators=(',', ':')) + '\n')
    (output / 'speed-instruction-words.json').write_text(json.dumps({hex(k): v for k, v in sorted(words.items())}) + '\n')
    report = {'schema_version': 1, 'run_id': str(uuid.uuid4()), 'result': 'passed',
        'completed_at_utc': datetime.now(timezone.utc).isoformat(), 'state_sha256': state.metadata['sha256'],
        'sources': image.sources, 'entry': '0x0187927c', 'stop_before': '0x0187930c',
        'comparisons': len(cases), 'original_instructions': instructions, 'instruction_words': len(words),
        'compile_command': command, 'tool_sha256': {name: digest(Path(__file__).with_name(name).read_bytes())
            for name in ('verify_speed.py', 'speed_abi.py', 'pose.py', 'pose_reference.py', 'savestate.py')},
        'files_sha256': {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir())},
        'scope': 'Semantic integer speed tail including stat scale, profile, acceleration/braking and mode predicate. Original helpers execute unchanged. Owned numeric fields; no opponent/prediction stubs. Original amplitudes per call, no verified native metres/second or time conversion, position integration, complete action/frame, contact or gameplay equivalence.'}
    (output / 'speed-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description='Conferir ajuste semântico de velocidade PES')
    for name in ('state', 'elf', 'over', 'core', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    state = SaveState(args.state)
    report = verify(state, Image(args.elf, args.over), args.core, args.output)
    if digest(args.state.read_bytes()) != state.metadata['sha256']: raise ValueError('state changed')
    print(json.dumps({k: report[k] for k in ('result', 'comparisons', 'original_instructions', 'instruction_words')}, indent=2))


if __name__ == '__main__': main()
