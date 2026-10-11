#!/usr/bin/env python3
"""Characterize raw evaluation versus processed captured pose fields.

This is an investigation, not an equivalence pass: all bit differences remain
in the report. It neither adjusts output values nor claims a resumed frame.
"""
import argparse
import json
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path

from actions import Image
from pose import structures
from rig import read_rig
from savestate import SaveState, digest

PHASES = ('raw_fresh', 'processed_fresh', 'processed_cached', 'materialized_fresh', 'materialized_cached')

def metrics(actual, captured, field):
    pairs = [(x, y) for a, b in zip(actual.bones, captured.bones)
             for x, y in zip(getattr(a, field), getattr(b, field))]
    number = lambda x: struct.unpack('<f', struct.pack('<I', x))[0]
    values = [abs(number(x) - number(y)) for x, y in pairs]
    return {'components': len(pairs), 'exact_bit_components': sum(x == y for x, y in pairs),
            'max_absolute_delta': max(values), 'different_bits': sum(x != y for x, y in pairs)}


def investigate(state, image, core, output, fpu='nearest', vu='nearest', division=None, square_root=None):
    from arithmetic import classes
    reference, math_class = classes(core / 'reference', fpu, vu, division, square_root)
    actors = structures(state)
    rows, words, total = [], {}, 0
    for actor in actors:
        for buffer, spec in enumerate(actor['buffers']):
            captured = read_rig(state.ram, spec)
            inst = int(spec['instance'], 16)
            for phase in PHASES:
                ref = reference(state.ram, state.scratch)
                initial_flags = 0 if phase == 'raw_fresh' else captured.flags[1] & (0xc0 if phase.endswith('_cached') else 0x40)
                ref.write(inst + 29, 'B', initial_flags)
                calls = (0x01115130,) if phase == 'raw_fresh' else (0x01115130, 0x011156b0, 0x01115940, 0x01116060)
                if phase.startswith('materialized_'): calls = (0x01115130, 0x01115ea0)
                boundaries = []
                for entry in calls:
                    def observe(pc, word, registers, floats):
                        if image.read(pc) != struct.pack('<I', word): raise ValueError('changed original instruction')
                        words[pc] = word
                    ref.run(entry, [inst], math_model=math_class(ref), max_instructions=150000,
                            instruction_observer=observe, full_quadwords=True)
                    total += ref.instructions
                    boundaries.append({'entry': hex(entry), 'instructions': ref.instructions,
                                       'ram_sha256': digest(ref.ram), 'flags': list(ref.ram[inst + 28:inst + 32])})
                result = read_rig(ref.ram, spec)
                fields = {name: metrics(result, captured, name) for name in
                          ('local_rotation', 'local_translation', 'composed_rotation', 'composed_translation', 'matrix')}
                rows.append({'actor': actor['id'], 'buffer': buffer, 'phase': phase, 'initial_flags': initial_flags,
                             'captured_flags': list(captured.flags), 'result_flags': list(result.flags),
                             'captured_local_marked_valid': bool(captured.flags[1] & 1),
                             'result_local_marked_valid': bool(result.flags[1] & 1),
                             'composed_fields_written': phase != 'raw_fresh',
                             'calls': boundaries, 'fields': fields,
                             'local_pose_bit_equal': all(fields[n]['different_bits'] == 0 for n in ('local_rotation', 'local_translation')),
                             'result_rig_sha256': digest(bytes(result))})
    summary = {}
    for phase in PHASES:
        selected = [r for r in rows if r['phase'] == phase]
        summary[phase] = {'poses': len(selected), 'exact_local_pose_matches': sum(r['local_pose_bit_equal'] for r in selected),
            'exact_composed_pose_matches': sum(all(r['fields'][n]['different_bits'] == 0 for n in
                 ('composed_rotation', 'composed_translation', 'matrix')) for r in selected) if phase != 'raw_fresh' else None,
            'captured_local_valid_poses': sum(r['captured_local_marked_valid'] for r in selected),
            'result_local_valid_poses': sum(r['result_local_marked_valid'] for r in selected),
            'composed_fields_written': phase != 'raw_fresh',
            'fields': {field: {'exact_bit_components': sum(r['fields'][field]['exact_bit_components'] for r in selected),
                              'components': sum(r['fields'][field]['components'] for r in selected),
                              'max_absolute_delta': max(r['fields'][field]['max_absolute_delta'] for r in selected)}
                       for field in selected[0]['fields']}}
    report = {'schema_version': 1, 'run_id': str(uuid.uuid4()), 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
              'result': 'investigated_equivalence_open', 'state_sha256': state.metadata['sha256'], 'sources': image.sources,
              'arithmetic_profile': {'fpu': fpu, 'vu': vu, 'division': division or fpu, 'square_root': square_root or fpu},
              'original_calls': sum(len(r['calls']) for r in rows), 'original_instructions': total,
              'instruction_words': len(words), 'summary': summary, 'comparisons': rows,
              'tool_sha256': {n: digest(Path(__file__).with_name(n).read_bytes()) for n in ('pose_differences.py', 'arithmetic.py', 'rig.py', 'pose.py', 'pose_reference.py')},
              'scope': 'Reevaluation of captured channels with explicit cache/mirror flags and function sequences. No motion clock update, clip resampling, native-output substitution or resumed PCSX2 frame. Deltas are model units, not metres. Bit differences remain open; arithmetic and actual frame ordering require external validation.'}
    with output.open('x') as stream: json.dump(report, stream, indent=2); stream.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description='Separar diferenças da avaliação local e da pose processada')
    for name in ('state', 'elf', 'over', 'core', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--fpu-rounding', choices=('nearest', 'chop'), default='nearest')
    parser.add_argument('--vu-rounding', choices=('nearest', 'chop'), default='nearest')
    parser.add_argument('--division-rounding', choices=('nearest', 'chop'))
    parser.add_argument('--sqrt-rounding', choices=('nearest', 'chop'))
    args = parser.parse_args()
    state = SaveState(args.state)
    report = investigate(state, Image(args.elf, args.over), args.core, args.output, args.fpu_rounding, args.vu_rounding,
                         args.division_rounding, args.sqrt_rounding)
    if digest(args.state.read_bytes()) != state.metadata['sha256']: raise AssertionError('state input changed')
    print(json.dumps(report['summary'], indent=2))

if __name__ == '__main__': main()
