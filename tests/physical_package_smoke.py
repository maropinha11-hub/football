#!/usr/bin/env python3
"""Check that the portable Windows experiment is explicitly opt-in."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, default=Path('artifacts'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    archive = args.artifacts / 'football-training-windows-x86_64.zip'
    update = args.artifacts / 'football-windows-teste-animacao-fbx.zip'
    report = dict(result='running', checks=[], archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())

    def check(name, ok):
        report['checks'].append(dict(check=name, result='passed' if ok else 'failed'))

    try:
        with zipfile.ZipFile(archive) as full, zipfile.ZipFile(update) as patch:
            prefix = 'football-training-windows-x86_64/'
            check('complete archive CRC', full.testzip() is None)
            check('update archive CRC', patch.testzip() is None)
            for filename, mode in [('treino-fisico.bat', '--training'),
                                   ('partida-fisica.bat', '--player-match')]:
                expected = ('@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n'
                            'gameplayfootball.exe --config training.config ' + mode +
                            ' --physical-rig %*\r\nif errorlevel 1 pause\r\n').encode('ascii')
                check(filename + ' runs from its own folder with physical mode', full.read(prefix + filename) == expected)
                check(filename + ' matches between packages', patch.read(filename) == expected)
            config = full.read(prefix + 'training.config')
            check('approved training defaults to physical layer off', b'"training_physical_rig" "false"' in config
                  and b'"training_physical_lab" "false"' in config)
            check('approved launchers do not activate the experiment', all(b'--physical-rig' not in full.read(prefix + f)
                  for f in ['run-training.bat', 'jogar-partida.bat']))
            check('physical instructions accompany both packages', full.read(prefix + 'LEIA-FISICA.txt') == patch.read('LEIA-FISICA.txt'))
            exe = full.read(prefix + 'gameplayfootball.exe')
            check('packaged executable implements physical CLI and solver telemetry', all(token in exe
                  for token in [b'--physical-rig', b'PHYSICAL_RIG_STATE', b'PHYSICAL_RIG_RECOVERED', b'PHYSICAL_RIG_FRAME']))
            check('full and update use the same executable', exe == patch.read('gameplayfootball.exe'))
            license_text=full.read(prefix+'BULLET-LICENSE.txt')
            check('Bullet license accompanies the complete and update packages', license_text==patch.read('BULLET-LICENSE.txt')
                  and b'zlib license' in license_text)
            check('camera uses the approved increased sensitivity', b'"firstperson_look_speed" "3.8"' in config)
            check('packaged code implements constrained motion matching', b'MOTION_MATCH t=' in exe)
            check('contact laboratory instructions include partner, grip, protection and contest', all(token in full.read(prefix+'LEIA-FISICA.txt')
                  for token in [b'F10',b'H ou L3',b'N ou LT',b'M:']))
            check('Windows code includes the shirt constraint and rendered recovery support', all(token in exe
                  for token in [b'PHYSICAL_GRIP_FORCE',b'PHYSICAL_CLOTH',b'PHYSICAL_RENDER_SUPPORT',b'PHYSICAL_PASS_TURN']))
            recovery_files=['media/animations/movement_special/idle/special/000_stand_up_from_'+side+'.anim'for side in ['front','back']]
            check('both original get-up animations are included unchanged', all(full.read(prefix+path)==(Path('data')/path).read_bytes()for path in recovery_files))
            report.update(entries=len(full.namelist()), dlls=sum(n.lower().endswith('.dll') for n in full.namelist()),
                          bytes=archive.stat().st_size, executable_sha256=hashlib.sha256(exe).hexdigest())
        report['result'] = 'passed' if all(c['result'] == 'passed' for c in report['checks']) else 'failed'
    finally:
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))
    if report['result'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
