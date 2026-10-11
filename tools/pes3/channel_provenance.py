#!/usr/bin/env python3
"""Match saved rotation channels to actual packed keys in their loaded clips.

Every candidate comes from source bytes, not an integer inferred from a saved
float. Duplicate keys remain ambiguous. This does not establish frame order,
the current simulation clock, interpolation accuracy or animation contacts.
"""
import argparse
import json
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path

from arithmetic import chop, nearest
from fpsa import EXPECTED_BUNDLE_SHA256, read_bundle
from pose import structures, word
from savestate import SaveState, digest


def rotation_keys(block, count, rounding):
    scale = struct.unpack('<f', struct.pack('<I', 0x38000100))[0]
    keys = []
    for key in range(count):
        values = []
        for bone in range(19):
            offset = 28 + 164 * key + bone * 8 + (12 if bone else 0)
            packed = struct.unpack_from('<4h', block, offset)
            values.extend(rounding(value * scale) for value in packed)
        keys.append(struct.pack('<76f', *values))
    return keys


def investigate(state, core):
    catalogue = json.loads((core / 'data/animation_pose_catalog.json').read_text())
    data, inventory = read_bundle(core / 'data/pes_animation_tracks.fpsa', catalogue)
    if inventory['sha256'] != EXPECTED_BUNDLE_SHA256:
        raise ValueError('different source bundle')
    clips = {}
    for entry in inventory['entries']:
        address = word(state.ram, 0x014d7d50 + 4 * entry['clip'])
        if not address: continue
        block = data[entry['bundle_offset']:entry['bundle_offset'] + entry['block_bytes']]
        if state.ram[address:address + len(block)] != block:
            raise ValueError('loaded clip differs from validated bundle')
        if address in clips: raise ValueError('ambiguous loaded clip address')
        clips[address] = (entry, block)
    rows, all_bits, nearest_bits = [], 0, 0
    for actor in structures(state):
        for buffer, spec in enumerate(actor['buffers']):
            instance = int(spec['instance'], 16)
            address = word(state.ram, instance + 4)
            if address not in clips: raise ValueError('instance motion is not a verified loaded clip')
            entry, block = clips[address]
            chopped = rotation_keys(block, entry['poses'], chop)
            rounded = rotation_keys(block, entry['poses'], nearest)
            channels = []
            for label, offset in (('a', 0x80), ('b', 0x90)):
                captured = b''.join(state.ram[node + offset:node + offset + 16] for node in spec['nodes'])
                matches = [i for i, key in enumerate(chopped) if key == captured]
                near_matches = [i for i, key in enumerate(rounded) if key == captured]
                row = {'channel': label, 'captured_sha256': digest(captured),
                       'chop_key_candidates': matches, 'nearest_key_candidates': near_matches,
                       'unique_key': len(matches) == 1}
                if matches:
                    # Equal chopped keys must not silently imply equal source packed keys.
                    # Keep nearest counts as a range when candidates differ.
                    saved_words = struct.unpack('<76I', captured)
                    counts = [sum(a == b for a, b in zip(saved_words, struct.unpack('<76I', rounded[i]))) for i in matches]
                    row['nearest_equal_components_range'] = [min(counts), max(counts)]
                    all_bits += 76
                    if min(counts) == max(counts): nearest_bits += counts[0]
                    else: raise ValueError('candidate ambiguity changes numeric comparison')
                channels.append(row)
            rows.append({'actor': actor['id'], 'buffer': buffer, 'clip': entry['clip'],
                         'block_sha256': entry['block_sha256'], 'motion_address': hex(address),
                         'instance_time_bits': hex(word(state.ram, instance + 8)), 'channels': channels})
    matching = sum(bool(c['chop_key_candidates']) for r in rows for c in r['channels'])
    return {'schema_version': 1, 'run_id': str(uuid.uuid4()),
            'completed_at_utc': datetime.now(timezone.utc).isoformat(),
            'result': 'all_rotation_channels_matched' if matching == 88 else 'partial_rotation_channel_match',
            'state_sha256': state.metadata['sha256'], 'bundle_sha256': inventory['sha256'],
            'loaded_clips_verified': len(clips), 'rotation_scale_bits': '0x38000100',
            'summary': {'channel_sets': 88, 'chop_source_key_matches': matching,
                        'matched_components': all_bits, 'nearest_equal_components': nearest_bits,
                        'nearest_different_components': all_bits - nearest_bits,
                        'unique_source_keys': sum(c['unique_key'] for r in rows for c in r['channels'])},
            'buffers': rows, 'tool_sha256': {name: digest(Path(__file__).with_name(name).read_bytes())
                for name in ('channel_provenance.py', 'arithmetic.py', 'fpsa.py', 'pose.py', 'savestate.py')},
            'scope': 'Actual packed signed-16 source keys in the clips referenced by captured instances, verified byte-for-byte against loaded RAM. Finite binary32 product rounded toward zero. Candidate key lists preserve duplicates; source-key matches do not validate the current motion clock, final pose, PS2 arithmetic as a whole, ball contacts or native integration.'}


def main():
    parser = argparse.ArgumentParser(description='Conferir a origem compactada dos canais de rotação salvos')
    for name in ('state', 'core', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    state = SaveState(args.state)
    report = investigate(state, args.core)
    if digest(args.state.read_bytes()) != state.metadata['sha256']: raise ValueError('state changed')
    with args.output.open('x') as stream: json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__': main()
