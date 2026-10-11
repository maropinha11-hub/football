#!/usr/bin/env python3
"""Compare the full direction block with original instructions and tables."""
import argparse
import ctypes as C
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import subprocess
import uuid
from actions import Image
from direction_abi import Input, Decision, SOURCE, configure
from pose import reference_classes
from recover_locomotion_tables import TABLES
from replay import PLAYER_BASE, PLAYER_STRIDE
from savestate import SaveState, digest

CLIPS = (0, 28, 29, 30, 31, 32, 33, 37, 38, 47, 48, 54, 56, 61, 62, 63,
         213, 214, 215, 216, 598, 599, 613)


def scenarios(captured):
    captured.substate = 16
    yield 'captured-direction-fields-forced-substate16', captured
    serial = 0
    for clip in CLIPS:
        for body in (0, 65535):
            for span in (0, 1, 2048, 2049, 3072, 3073, 8191, 8192, 8193, 12288, 12289, 32768, 65535):
                for movement_delta in (0, 3072, 3073):
                    value = Input(substate=16, clip=clip, body_heading=body, ball_heading=span,
                        movement_heading=(span + movement_delta) & 65535, direction_mask=serial % 16,
                        turn_heading=(serial * 311) & 65535)
                    value.player_xz[:] = (104.25, -227.75)
                    value.ball_far_xz[:] = (1128.25, -227.75)  # Exact initial angle zero.
                    value.ball_near_xz[:] = (104.75 + serial % 211, -228.25 - serial % 239)
                    yield f'direction-{serial}-clip-{clip}-span-{span}-movement-{movement_delta}', value
                    serial += 1
    for dx, dz in ((0, 0), (32767, 0), (-32767, 0), (0, 32767), (0, -32767),
                   (32767, 32767), (-32767, 32767), (32767, -32767), (-32767, -32767)):
        value = Input(substate=16, direction_mask=1)
        value.ball_far_xz[:] = (dx, dz)
        value.ball_near_xz[:] = (.75, -.75)
        yield f'direction-axes-{dx}-{dz}', value
    value = Input(substate=16)
    value.player_xz[:] = (-65536, -65536)
    value.ball_far_xz[:] = (-64512, -64512)
    value.ball_near_xz[:] = (65536, 65536)
    yield 'near-distance-wrap32', value


def verify(state, image, core, output):
    output.mkdir(parents=True, exist_ok=False)
    for name, address, count, kind, declaration in TABLES:
        if state.ram[address:address + count * 2] != image.read(address, count * 2):
            raise ValueError('loaded table differs: ' + name)
    reference, math_class = reference_classes(core / 'reference')
    for name in ('locomotion_direction.hpp', 'locomotion_tables.hpp'):
        (output / name).write_bytes((Path(__file__).with_name('recovered') / name).read_bytes())
    (output / 'direction.cpp').write_text(SOURCE)
    command = ['g++', '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror', '-fno-fast-math', '-ffp-contract=off',
               '-shared', '-fPIC', str(output / 'direction.cpp'), '-o', str(output / 'direction.so')]
    subprocess.run(command, check=True, capture_output=True)
    native = configure(C.CDLL(str((output / 'direction.so').resolve())))
    player = PLAYER_BASE + state.ram[0x01564920 + 13] * PLAYER_STRIDE
    context, ball = struct.unpack_from('<I', state.ram, 0x012a6238)[0], struct.unpack_from('<I', state.ram, 0x012a6250)[0]
    first = Input()
    for name, address in (('player_xz', player), ('ball_far_xz', ball), ('ball_near_xz', ball)):
        offsets = (0x2c4, 0x2cc) if name == 'player_xz' else (0x474, 0xb74) if name == 'ball_far_xz' else (0x444, 0xb44)
        getattr(first, name)[:] = [struct.unpack_from('<f', state.ram, address + o)[0] for o in offsets]
    for name, offset in (('body_heading', 0xea), ('movement_heading', 0xec), ('turn_heading', 0xf8), ('clip', 0x2dc)):
        setattr(first, name, struct.unpack_from('<H', state.ram, player + offset)[0])
    first.ball_heading = struct.unpack_from('<H', state.ram, ball + 0x60)[0]
    first.direction_mask = struct.unpack_from('<I', state.ram, context + 0x48)[0]
    words, cases, instructions = {}, [], 0
    for ident, value in scenarios(first):
        ref = reference(state.ram, state.scratch)
        ref.write(context + 0x48, 'I', value.direction_mask)
        for name, offset in (('body_heading', 0xea), ('movement_heading', 0xec), ('turn_heading', 0xf8), ('clip', 0x2dc), ('substate', 0xdc)):
            ref.write(player + offset, 'H', getattr(value, name))
        for name, address, offsets in (('player_xz', player, (0x2c4, 0x2cc)),
                ('ball_far_xz', ball, (0x474, 0xb74)), ('ball_near_xz', ball, (0x444, 0xb44))):
            for offset, number in zip(offsets, getattr(value, name)): ref.write(address + offset, 'f', number)
        ref.write(ball + 0x60, 'H', value.ball_heading)
        headings = []
        def observe(pc, opcode, registers, floats):
            if image.read(pc) != struct.pack('<I', opcode): raise ValueError('changed original instruction')
            words[pc] = opcode
            if pc == 0x01878550: headings.append(registers[2] & 65535)
        ref.run(0x018783b0, [], initial_registers={19: player}, stop_before=0x0187866c,
            math_model=math_class(ref), instruction_observer=observe, full_quadwords=True, max_instructions=4096)
        if len(headings) != 1: raise ValueError('original action heading was not captured')
        r = ref.last_registers
        expected = Decision(r[18] & 0xffffffff, r[21] & 65535, ref.read(player + 0xea, 'H'),
            ref.read(player + 0xec, 'H'), ref.read(player + 0xdc, 'H'), r[16] & 65535,
            r[20] & 65535, r[22] & 65535, headings[0])
        actual = Decision(); status = native.select_direction(C.byref(value), C.byref(actual))
        if status != 1 or bytes(actual) != bytes(expected):
            raise AssertionError(f'{ident}: status {status}, input {bytes(value).hex()}, expected {bytes(expected).hex()}, actual {bytes(actual).hex()}')
        instructions += ref.instructions
        cases.append({'id': ident, 'input_hex': bytes(value).hex(), 'expected_hex': bytes(expected).hex(),
            'memory_kind': 'modified_snapshot', 'instructions': ref.instructions,
            'result_player_sha256': digest(ref.ram[player:player + PLAYER_STRIDE])})
    (output / 'direction-vectors.json').write_text(json.dumps({'schema_version': 1,
        'state_sha256': state.metadata['sha256'], 'input_bytes': 40, 'decision_bytes': 20, 'cases': cases}, separators=(',', ':')) + '\n')
    (output / 'direction-instruction-words.json').write_text(json.dumps({hex(k): v for k, v in sorted(words.items())}) + '\n')
    report = {'schema_version': 1, 'run_id': str(uuid.uuid4()), 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
        'result': 'passed', 'state_sha256': state.metadata['sha256'], 'sources': image.sources,
        'comparisons': len(cases), 'original_instructions': instructions, 'instruction_words': len(words),
        'entry': '0x018783b0', 'stop_before': '0x0187866c', 'compile_command': command,
        'arithmetic_profile': 'Selected host binary32 nearest subtraction, integer conversions truncate as in pinned reference. Not a complete PS2 arithmetic model.',
        'tool_sha256': {name: digest(Path(__file__).with_name(name).read_bytes()) for name in
            ('verify_direction.py', 'direction_abi.py', 'recover_locomotion_tables.py', 'pose.py', 'pose_reference.py', 'savestate.py')},
        'files_sha256': {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir())},
        'scope': 'Owned direction block plus actual original heading/turn/angle/distance helpers and recovered quantized tables. All scenarios enter the block on modified copies of the stationary save. No full action/frame, PS2 hardware, native units, retarget/contact or complete gameplay equivalence.'}
    (output / 'direction-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description='Conferir direção de corpo/movimento PES contra instruções originais')
    for name in ('state', 'elf', 'over', 'core', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(); state = SaveState(args.state)
    report = verify(state, Image(args.elf, args.over), args.core, args.output)
    if digest(args.state.read_bytes()) != state.metadata['sha256']: raise ValueError('state changed')
    print(json.dumps({k: report[k] for k in ('result', 'comparisons', 'original_instructions', 'instruction_words')}, indent=2))


if __name__ == '__main__': main()
