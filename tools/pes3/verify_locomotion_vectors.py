#!/usr/bin/env python3
"""Recompile and check the numeric delivery without PES files or emulator."""
import argparse
import ctypes as C
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from selection_abi import Input, Decision, configure
from speed_abi import Input as SpeedInput, configure as configure_speed


def digest(data): return hashlib.sha256(data).hexdigest()


def verify(folder, compiler='g++'):
    manifest = json.loads((folder / 'manifest.json').read_text())
    if manifest['kind'] != 'pes3-semantic-locomotion-research': raise ValueError('unexpected package')
    for name, expected in manifest['files_sha256'].items():
        if digest((folder / name).read_bytes()) != expected: raise ValueError('package hash differs: ' + name)
    reports, fixtures = {}, {}
    for kind in ('selection', 'speed'):
        report = json.loads((folder / f'{kind}-validation.json').read_text())
        if report['result'] != 'passed' or report['state_sha256'] != manifest['state_sha256']:
            raise ValueError('reference report differs')
        raw = gzip.decompress((folder / f'{kind}-vectors.json.gz').read_bytes())
        if digest(raw) != report['files_sha256'][f'{kind}-vectors.json']: raise ValueError('numeric fixture hash differs')
        fixture = json.loads(raw)
        if fixture['state_sha256'] != report['state_sha256']: raise ValueError('fixture state differs')
        if len(fixture['cases']) != report['comparisons']: raise ValueError('fixture count differs')
        for name in (('locomotion_selection.hpp', 'locomotion_speed.hpp', 'selector.cpp') if kind == 'selection'
                     else ('locomotion_speed.hpp', 'speed.cpp')):
            if digest((folder / name).read_bytes()) != report['files_sha256'][name]: raise ValueError('verified source differs: ' + name)
        reports[kind], fixtures[kind] = report, fixture
    if (fixtures['selection']['input_bytes'], fixtures['selection']['decision_bytes'],
            fixtures['selection']['speed_input_bytes'], fixtures['speed']['input_bytes']) != (44, 32, 20, 20):
        raise ValueError('unsupported numeric ABI')
    with tempfile.TemporaryDirectory(prefix='pes3-locomotion-verify-') as temp:
        library = Path(temp) / 'selector.so'
        subprocess.run([compiler, '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
            '-I', str(folder.resolve()), str((folder / 'selector.cpp').resolve()), '-o', str(library)],
            check=True, capture_output=True)
        native = configure(C.CDLL(str(library))); configure_speed(native)
        for case in fixtures['selection']['cases']:
            value = Input.from_buffer_copy(bytes.fromhex(case['input_hex']))
            expected = bytes.fromhex(case['expected_hex'])
            if len(expected) != C.sizeof(Decision): raise ValueError('wrong decision length')
            actual = Decision()
            if native.select_locomotion(C.byref(value), C.byref(actual)) != 1 or bytes(actual) != expected:
                raise AssertionError('selection fixture differs: ' + case['id'])
            speed = SpeedInput.from_buffer_copy(bytes.fromhex(case['speed_input_hex']))
            speed.current_amplitude, speed.selected_amplitude = actual.amplitude_before_speed, actual.selected_amplitude
            if native.step_speed(C.byref(speed)) != case['expected_speed']:
                raise AssertionError('composed speed fixture differs: ' + case['id'])
        for case in fixtures['speed']['cases']:
            value = SpeedInput.from_buffer_copy(bytes.fromhex(case['input_hex']))
            if native.step_speed(C.byref(value)) != case['expected']:
                raise AssertionError('speed fixture differs: ' + case['id'])
    return {'result': 'passed', 'selection_comparisons': reports['selection']['comparisons'],
        'composed_speed_comparisons': reports['selection']['composed_speed_comparisons'],
        'speed_comparisons': reports['speed']['comparisons'],
        'selection_run_id': reports['selection']['run_id'], 'speed_run_id': reports['speed']['run_id'],
        'package_manifest_sha256': digest((folder / 'manifest.json').read_bytes()),
        'scope': 'Recompiled owned C++ decisions and integer speed compared with recorded original-instruction outputs in the declared reference model. No fresh original execution, hardware, full action/frame, imported animation or gameplay validation.'}


def main():
    parser = argparse.ArgumentParser(description='Repetir a conferência do seletor/velocidade sem arquivos PES')
    parser.add_argument('folder', type=Path)
    parser.add_argument('--compiler', default='g++'); parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = verify(args.folder, args.compiler)
    if args.output:
        with args.output.open('x') as stream: json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
