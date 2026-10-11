#!/usr/bin/env python3
"""Associate reached source markers with actual clip/action contexts automatically.

These are temporal checks, including non-contact transitions. No guessed gesture
labels or native enum casts are produced.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import subprocess
import struct
import tempfile

from event_abi import Input, configure
from savestate import digest
from verify_event_vectors import safe_member


def checked_report(folder, name):
    report = json.loads((folder / name).read_text())
    if report['result'] != 'passed':
        raise ValueError('verification did not complete')
    for member, expected in report['files_sha256'].items():
        safe_member(member)
        if digest((folder / member).read_bytes()) != expected:
            raise ValueError('verified file changed: ' + member)
    return report


def build(study, events):
    report = checked_report(study, 'state-study.json')
    proof = checked_report(events, 'event-report.json')
    hashes = [row['sha256'] for row in report['states']]
    if hashes != proof['state_hashes'] or report['sources'] != proof['sources']:
        raise ValueError('state and event proofs belong to different inputs')
    source_words = json.loads((study / 'instruction-words.json').read_text())
    records = []
    with tempfile.TemporaryDirectory(prefix='pes3-event-index-') as temporary:
        library = Path(temporary) / 'events.so'
        subprocess.run(['g++', '-std=c++14', '-O0', '-fno-fast-math', '-ffp-contract=off',
                        '-shared', '-fPIC', '-I', str(events.resolve()),
                        str((events / 'animation_events.cpp').resolve()), '-o', str(library)],
                       check=True, capture_output=True)
        lib = configure(C.CDLL(str(library)))
        for state in report['states']:
            for case in state['cases']:
                if (case['status'] != 'completed'
                        or case['results'][0]['native_comparison'] != 'matched_full_ram_scratch_registers_path'):
                    raise ValueError('marker came from an incomplete or unverified original call')
                for event in case['events']:
                    if event['role'] != 'animation_phase_gate':
                        continue
                    caller = int(event['call_pc'], 16)
                    raw = source_words.get(hex(caller))
                    if raw is None or raw >> 26 != 3 or (raw & 0x03FFFFFF) << 2 != 0x0116AFE0:
                        raise ValueError('marker caller is not a verified original JAL to 0116AFE0')
                    row = event['phase_gate_input']
                    value = Input.from_buffer_copy(struct.pack('<2I4B',
                        int(row['phase_bits'], 16), int(row['step_bits'], 16),
                        row['blend_window'], row['blend_tick'], row['cycle_fix'], 0))
                    allowed = C.c_uint()
                    if lib.owned_phase_gate(C.byref(value), row['marker_i32'], 0, C.byref(allowed)) != 1:
                        raise ValueError('observed marker fields outside the verified finite API domain')
                    actor = event['observed_fields']['actors'][0]
                    records.append({'state_index': state['index'], 'state_sha256': state['sha256'],
                                    'actor': case['actor'], 'selected_actor': state['controlled_actor'],
                                    'case': case['id'], 'action': actor['action'],
                                    'substate': actor['substate'], 'clip': actor['clip'],
                                    'marker': row['marker_i32'], 'phase_at_check': value.phase,
                                    'step_at_check': value.step, 'eligible': bool(allowed.value),
                                    'original_call_site': event['call_pc'], 'input_fields': row,
                                    'meaning': 'temporal_check_unclassified'})
    clips = []
    for clip in range(1105):
        observations = [row for row in records if row['clip'] == clip]
        clips.append({'clip': clip, 'semantic_name': None,
                      'observed_markers': sorted({row['marker'] for row in observations}),
                      'observed_action_contexts': sorted({row['action'] for row in observations}),
                      'evidence': observations, 'native_import_ready': False})
    return {'schema_version': 1, 'sources': report['sources'], 'state_hashes': hashes,
            'state_report_sha256': digest((study / 'state-study.json').read_bytes()),
            'event_report_sha256': digest((events / 'event-report.json').read_bytes()),
            'rule': {'original_entry': '0x0116afe0',
                     'formula': '-step/2 < rounded(phase-rounded(int32(marker))) <= step/2',
                     'blocked_when': '(blend_window != 0 || cycle_fix != 0) && blend_tick == 0',
                     'units': 'original_animation_phase'},
            'summary': {'states': len(hashes), 'observed_temporal_checks': len(records),
                        'clips_with_observed_markers': sum(bool(c['evidence']) for c in clips)},
            'clips': clips, 'runtime_enabled': False,
            'scope': 'Automatic associations from unmodified original update calls and their post-delay-slot callee inputs, verified through reached C++ recompilation. Temporal eligibility is evaluated by the owned original predicate. A marker can be a transition or a contact check; no anatomy, gesture name, contact guarantee, native action type or whole-frame behavior is inferred.'}


def main():
    parser = argparse.ArgumentParser(description='Associar automaticamente clips e marcadores vistos nos saves')
    for name in ('study', 'events', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = build(args.study, args.events)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result['summary'], indent=2))


if __name__ == '__main__':
    main()
