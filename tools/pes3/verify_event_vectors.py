#!/usr/bin/env python3
"""Compile owned event code and verify sealed numeric vectors without PES files."""
import argparse
import ctypes as C
import gzip
import json
from pathlib import Path, PurePosixPath
import struct
import subprocess
import tempfile

from event_abi import Anchor741, Input, configure
from savestate import digest


def safe_member(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or str(path) != name:
        raise ValueError('unsafe package member name')
    return path


def verify(folder, compiler='g++'):
    manifest = json.loads((folder / 'manifest.json').read_text())
    if manifest.get('schema_version') != 1 or manifest.get('kind') != 'pes3-training-states-events-research':
        raise ValueError('unsupported event evidence package')
    for name, expected in manifest['files_sha256'].items():
        safe_member(name)
        if digest((folder / name).read_bytes()) != expected:
            raise ValueError('package hash differs: ' + name)
    report = json.loads((folder / 'event-report.json').read_text())
    raw = gzip.decompress((folder / 'event-vectors.json.gz').read_bytes())
    if (report['result'] != 'passed' or digest(raw) != report['files_sha256']['event-vectors.json']
            or report['state_hashes'] != manifest['state_hashes']):
        raise ValueError('event proof inputs or result differ')
    vectors = json.loads(raw)
    if (len(vectors['cases']) != report['comparisons']
            or len(vectors['anchor_741']) != report['anchor_741_comparisons']):
        raise ValueError('event vector count differs')
    with tempfile.TemporaryDirectory(prefix='pes3-event-verify-') as temporary:
        library = Path(temporary) / 'events.so'
        subprocess.run([compiler, '-std=c++14', '-O0', '-Wall', '-Wextra', '-Werror',
                        '-fno-fast-math', '-ffp-contract=off', '-shared', '-fPIC',
                        '-I', str(folder.resolve()), str((folder / 'animation_events.cpp').resolve()),
                        '-o', str(library)], check=True, capture_output=True)
        lib = configure(C.CDLL(str(library)))
        for row in vectors['cases']:
            if row['profile'] not in ('nearest', 'chop'):
                raise ValueError('unsupported event arithmetic profile')
            value = Input.from_buffer_copy(bytes.fromhex(row['input_hex']))
            result = C.c_uint(0x2A2A2A2A)
            status = lib.owned_phase_gate(C.byref(value), row['marker'],
                                         int(row['profile'] == 'chop'), C.byref(result))
            if status != 1 or result.value != row['expected']:
                raise AssertionError('recorded original temporal predicate differs')
        for row in vectors['anchor_741']:
            if row['profile'] not in ('nearest', 'chop'):
                raise ValueError('unsupported anchor arithmetic profile')
            context_y, = struct.unpack('<f', struct.pack('<I', int(row['context_y_bits'], 16)))
            result = Anchor741()
            status = lib.owned_anchor_741(context_y, int(row['profile'] == 'chop'), C.byref(result))
            if status != 1 or bytes(result).hex() != row['expected_hex']:
                raise AssertionError('recorded original context-dependent anchor differs')
    return {'result': 'passed', 'phase_gate_comparisons': len(vectors['cases']),
            'anchor_741_comparisons': len(vectors['anchor_741']),
            'scope': 'Offline regression against sealed original-call outputs. No fresh PES execution.'}


def main():
    parser = argparse.ArgumentParser(description='Repetir a prova C++ dos marcadores e do anchor 741')
    parser.add_argument('folder', type=Path)
    parser.add_argument('--compiler', default='g++')
    args = parser.parse_args()
    print(json.dumps(verify(args.folder, args.compiler), indent=2))


if __name__ == '__main__':
    main()
