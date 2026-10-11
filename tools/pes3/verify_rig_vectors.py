#!/usr/bin/env python3
"""Recheck a numeric rig delivery without the PES binary, state or core bundle."""
import argparse
import base64
import ctypes as C
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(folder, compiler='g++'):
    report = json.loads((folder / 'rig-validation.json').read_text())
    if report['result'] != 'passed': raise ValueError('rig reference report did not pass')
    names = ('pose_ops.hpp', 'pose_rig.hpp', 'pose_rig.cpp')
    for name in names:
        if digest((folder / name).read_bytes()) != report['files_sha256'][name]:
            raise ValueError('source hash mismatch: ' + name)
    raw = gzip.decompress((folder / 'rig-vectors.json.gz').read_bytes())
    if digest(raw) != report['files_sha256']['rig-vectors.json']:
        raise ValueError('fixture hash mismatch')
    fixtures = json.loads(raw)
    if fixtures['state_sha256'] != report['state_sha256']:
        raise ValueError('fixtures from another state')
    if fixtures['abi'] != {'rig_bytes': 3360, 'bone_bytes': 176, 'endianness': 'little', 'rigs_per_case': 3}:
        raise ValueError('unsupported fixture ABI')
    with tempfile.TemporaryDirectory(prefix='pes3-rig-verify-') as temp:
        library = Path(temp) / 'rig.so'
        command = [compiler, '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror', '-fno-fast-math',
                   '-ffp-contract=off', '-shared', '-fPIC', '-I', str(folder.resolve()),
                   str((folder / 'pose_rig.cpp').resolve()), '-o', str(library)]
        subprocess.run(command, check=True, capture_output=True)
        native = C.CDLL(str(library))
        native.rig_op.argtypes = [C.c_uint, C.c_void_p, C.c_uint, C.c_uint, C.c_uint, C.c_float, C.c_int]
        native.rig_op.restype = C.c_int
        comparisons = 0
        for case in fixtures['cases']:
            before, expected = (base64.b64decode(case[k], validate=True) for k in ('input_base64', 'expected_base64'))
            if len(before) != 10080 or len(expected) != 10080: raise ValueError('invalid numeric rig length')
            work = (C.c_uint32 * 2520).from_buffer_copy(before)
            alpha = struct.unpack('<f', struct.pack('<I', case['alpha_bits']))[0]
            status = native.rig_op(case['operation'], work, case['destination'], case['source_a'], case['source_b'],
                                   alpha, int(case['translate_all']))
            if status != 1 or bytes(work) != expected:
                raise AssertionError('rig differs in fixture: ' + case['id'])
            comparisons += 1
        if comparisons != report['comparisons']: raise ValueError('comparison count differs')
    return {'result': 'passed', 'comparisons': comparisons, 'fixture_sha256': digest(raw),
            'sources_sha256': {name: digest((folder / name).read_bytes()) for name in names},
            'scope': 'Recompiled semantic numeric rig compared in bits with recorded selected-model original-call fixtures. No fresh original execution, hardware or gameplay validation.'}


def main():
    parser = argparse.ArgumentParser(description='Repetir os testes C++ do rig sem arquivos PES')
    parser.add_argument('folder', type=Path)
    parser.add_argument('--compiler', default='g++')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(args.folder, args.compiler)
    if args.output:
        with args.output.open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
