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
            check('restored native selector keeps frame-zero entry and excludes imported phase matching',b'NATIVE_APPROVED_SELECT'in exe and b'MOTION_PHASE_ENTER'not in exe and b'MOTION_MIXER'not in exe and b'MOTION_INERTIA'not in exe)
            check('no uploaded locomotion clips ship in either package',not any('/animations/mocap/' in n for n in full.namelist())and not any('/animations/mocap/'in n for n in patch.namelist()))
            manifest=json.loads(full.read(prefix+'approved-base.json'))
            check('the uploaded executable is identified by its verified hash',manifest['uploaded_executable_sha256']=='23230593d0f2735381a5522e21c71abc4977f76d32352bee814ebd096b4a30a3'and manifest['base_commit'].startswith('fa0dfa6'))
            check('every original native animation is byte identical in the portable game',all(hashlib.sha256(full.read(prefix+name.removeprefix('data/'))).hexdigest()==digest for name,digest in manifest['original_animation_sha256'].items()))
            check('restoration guide and provenance accompany complete and update packages',all(full.read(prefix+name)==patch.read(name) for name in ['LEIA-BASE-APROVADA.txt','approved-base.json']))
            check('rendered head camera correction remains present',b'FIRSTPERSON_FRAME'in exe)
            check('large upload splitter accompanies both portable packages',all(full.read(prefix+name)==patch.read(name)for name in ['dividir-arquivos.bat','dividir-arquivos.ps1']))
            check('moving skin receptions and physical body duels remain present',all(token in exe for token in [b'moving_skin=1',b'PHYSICAL_BODY_DUEL',b'CPU_AERIAL_DUEL']))
            check('native restoration removes the new matching toggle',b'F12:'not in full.read(prefix+'LEIA-FISICA.txt')and b'Alt+F2:'in full.read(prefix+'LEIA-FISICA.txt')and b'training_motion_matching'not in config)
            check('MIT motion matching attribution accompanies the full and update package',
                  b'Daniel Holden'in full.read(prefix+'MOTION-MATCHING-LICENSE.txt')and
                  full.read(prefix+'MOTION-MATCHING-LICENSE.txt')==patch.read('MOTION-MATCHING-LICENSE.txt'))
            check('contact laboratory instructions include partner, grip, protection and contest', all(token in full.read(prefix+'LEIA-FISICA.txt')
                  for token in [b'F10',b'F11',b'LT/L2',b'L3 nao',b'M:']))
            check('Windows code includes the shirt constraint and rendered recovery support', all(token in exe
                  for token in [b'PHYSICAL_GRIP_FORCE',b'PHYSICAL_CLOTH',b'PHYSICAL_RENDER_SUPPORT',b'PHYSICAL_PASS_TURN',b'PHYSICAL_BALANCE_BANK',b'PHYSICAL_EYE']))
            check('Windows includes final rendered arm limits and graded unforced impact tests',all(token in exe
                  for token in [b'PHYSICAL_ARM_RENDER',b'PHYSICAL_ARM_LIMITS',b'PHYSICAL_IMPACT_TEST',b'intended_speed=',b'actual_speed=']))
            check('all three impact levels are documented in the portable game',all(token in full.read(prefix+'LEIA-FISICA.txt')
                  for token in [b'F8:',b'Shift+F8:',b'Ctrl+F8:',b'125 N.s',b'190 N.s',b'350 N.s']))
            check('Windows embeds contextual body actions and independent F1 comparison',all(token in exe
                  for token in [b'PHYSICAL_SITUATION_BANK',b'PHYSICAL_SITUATION_RENDER',b'PHYSICAL_SITUATION_TOGGLE']))
            check('F1 and honest procedural profile counts accompany both packages',all(token in full.read(prefix+'LEIA-FISICA.txt')
                  for token in [b'F1:',b'11323 perfis procedurais',b'80.118 combinacoes',b'nao sao novas capturas']))
            catalog=full.read(prefix+'situational-motion-catalog.json')
            check('packaged catalog equals generated source and update manifest', catalog == patch.read('situational-motion-catalog.json')
                  and catalog == Path('config/situational-motion-catalog.json').read_bytes())
            check('situational profiles are enabled only within the opt-in physical path',b'"training_situational_motion" "true"'in config
                  and all(b'--physical-rig'not in full.read(prefix+f)for f in ['run-training.bat','jogar-partida.bat']))
            check('RT gestures are removed while aiming telemetry and control lift are shipped',b'PHYSICAL_FOOTWORK_BEGIN'not in exe and all(token in exe for token in [b'TRAINING_ACTION_AIM',b'PHYSICAL_CONTROL_HOP']) and b'RT fica reservado no treino' in full.read(prefix+'LEIA-FISICA.txt'))
            check('irregular turf and full length human restarts are configured in the complete package',all(token in config for token in [b'"training_turf_enabled" "true"',b'"training_turf_roughness" "0.65"',b'"player_match_half_seconds" "2700"',b'"player_match_all_restarts" "true"']))
            check('Windows includes physical tackles, referee, receiver and keeper decisions',all(token in exe for token in [b'PHYSICAL_TACKLE',b'PHYSICAL_FOUL',b'TURF_FORECAST',b'TRAINING_RECEIVE_ASSIST',b'KEEPER_DECISION',b'PLAYER_MATCH_TAKER',b'PLAYER_MATCH_TACTIC',b'PHYSICAL_AI_GRIP']))
            recovery_files=['media/animations/movement_special/idle/special/000_stand_up_from_'+side+'.anim'for side in ['front','back']]
            check('both original get-up animations are included unchanged', all(full.read(prefix+path)==(Path('data')/path).read_bytes()for path in recovery_files))
            check('Windows includes recovery continuity, active leg support, silent footsteps, charge and restart diagnostics',all(token in exe for token in [b'PHYSICAL_RECOVERY_HANDOFF',b'PHYSICAL_SUPPORT_COMPLIANCE',b'footsteps=0',b'FIELD_AUDIO',b'HUMAN_PASS_POWER',b'RESTART_RUN',b'backpass_foot',b'target_side=']))
            strikes=json.loads(full.read(prefix+'procedural-strikes.json'))
            check('all 56 generated native actions accompany the complete game',strikes['generated_files']==56 and strikes['new_captures']==0 and all(full.read(prefix+row['path'].removeprefix('data/'))==(Path(row['path'])).read_bytes()for row in strikes['clips']))
            check('new action and audio assets also accompany the update',all(full.read(prefix+name)==patch.read(name)for name in [*[row['path'].removeprefix('data/')for row in strikes['clips']],*['media/sounds/'+name for name in ['turfstep0.wav','turfstep1.wav','breathing.wav','fieldair.wav']]]))
            check('new outdoor sound files are real PCM WAVE files',all(full.read(prefix+'media/sounds/'+name)[:4]==b'RIFF'for name in ['turfstep0.wav','turfstep1.wav','breathing.wav','fieldair.wav']))
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
