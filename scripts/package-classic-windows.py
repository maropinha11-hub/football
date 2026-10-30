#!/usr/bin/env python3
"""Build the self-contained animation/IK Windows release from the linked binary."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build-windows-mingw2'
ARTIFACT=ROOT/'artifacts/football-classico-windows-x86_64.zip'
DLL_CANDIDATES=(Path('/workspace/.football-windows/sdk/bin'),
                Path('/workspace/.football-windows/vcpkg/installed/x64-mingw-dynamic/bin'))
RUNTIME_DLLS=Path(os.environ['FOOTBALL_WINDOWS_VCPKG_BIN'])if 'FOOTBALL_WINDOWS_VCPKG_BIN'in os.environ else next(
    (p for p in DLL_CANDIDATES if p.is_dir()),DLL_CANDIDATES[0])
NATIVE=Path(os.environ.get('FOOTBALL_WINDOWS_MINGW_ROOT','/workspace/.football-native/root'))


def package():
    validation=json.loads((ROOT/'docs/animation-gameplay-validation.json').read_text())
    build_hash=hashlib.sha256((BUILD/'gameplayfootball.exe').read_bytes()).hexdigest()
    if (validation.get('result')!='passed' or validation['binaries']['windows_unstripped_sha256']!=build_hash or
            {row['scenario']for row in validation['rendered']}!={'camera','central','airborne','actions'} or
            any(row['result']!='passed'for row in validation['rendered'])):
        raise RuntimeError('Final executable has no matching successful gameplay validation')
    bank_path=ROOT/'data/media/training/pes17/catalog.json'
    bank=json.loads(bank_path.read_text())
    bank_hash=hashlib.sha256(bank_path.read_bytes()).hexdigest()
    pes=validation.get('pes_action_bank',{})
    if(pes.get('result')!='passed' or pes.get('executable_sha256')!=validation['binaries']['native_sha256'] or
       pes.get('bank_catalog_sha256')!=bank_hash or pes.get('views')!=2):
        raise RuntimeError('Action bank has no matching successful two-view contact/fallback validation')
    for row in bank['actions']:
        if hashlib.sha256((bank_path.parent/row['file']).read_bytes()).hexdigest()!=row['sha256']:
            raise RuntimeError('Action bank changed after validation: '+row['file'])
    ARTIFACT.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='football-classic-',dir=ARTIFACT.parent)as temporary:
        stage=Path(temporary)/'football-classico-windows-x86_64';stage.mkdir()
        for entry in (ROOT/'data').iterdir():
            if entry.name=='pes3':continue
            if entry.is_dir():shutil.copytree(entry,stage/entry.name)
            else:shutil.copy2(entry,stage/entry.name)
        shutil.copy2(ROOT/'config/training.config',stage/'training.config')
        shutil.copy2(ROOT/'config/training.config',stage/'football.config')
        for filename in ('situational-motion-catalog.json','procedural-strikes.json','approved-base.json'):
            shutil.copy2(ROOT/'config'/filename,stage/filename)
        subprocess.run([os.environ.get('STRIP','x86_64-w64-mingw32-strip'),'--preserve-dates','--strip-debug','-o',str(stage/'gameplayfootball.exe'),str(BUILD/'gameplayfootball.exe')],check=True)
        if not RUNTIME_DLLS.is_dir():raise FileNotFoundError('Windows runtime DLL directory is unavailable: '+str(RUNTIME_DLLS))
        for dll in RUNTIME_DLLS.glob('*.dll'):shutil.copy2(dll,stage/dll.name)
        for path in (NATIVE/'usr/lib/gcc/x86_64-w64-mingw32/14-posix/libgcc_s_seh-1.dll',
                     NATIVE/'usr/lib/gcc/x86_64-w64-mingw32/14-posix/libstdc++-6.dll',
                     NATIVE/'usr/x86_64-w64-mingw32/lib/libwinpthread-1.dll'):
            shutil.copy2(path,stage/path.name)
        for filename,args in [('treino-classico.bat','--training --physical-rig'),
                              ('treinar-animacoes-pes.bat','--training --physical-rig --pes-actions'),
                              ('run-training.bat','--training --physical-rig'),
                              ('jogar-partida.bat','--player-match --physical-rig'),
                              ('run-controller-test.bat','--test-controller')]:
            (stage/filename).write_text('@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n'
                'gameplayfootball.exe --config training.config '+args+' %*\r\nif errorlevel 1 pause\r\n',encoding='ascii',newline='')
        for source,name in [('LICENSE','LICENSE'),('NOTICE','NOTICE'),('third_party/bullet/LICENSE.txt','BULLET-LICENSE.txt'),
                            ('third_party/motion-matching/LICENSE.txt','MOTION-MATCHING-LICENSE.txt'),
                            ('docs/TREINO-CLASSICO.md','LEIA-PRIMEIRO.txt'),
                            ('docs/BANCO-ANIMACOES-PES2017.md','ANIMACOES-PES2017.txt'),
                            ('docs/pes2017-action-bank-validation.json','pes2017-action-bank-validation.json'),
                            ('docs/animation-gameplay-validation.json','animation-gameplay-validation.json')]:
            shutil.copy2(ROOT/source,stage/name)
        files=sorted(p for p in stage.rglob('*')if p.is_file())
        manifest=dict(mode='native_animation_and_ik',ragdoll=False,cloth_dynamics=False,
                      original_pes_gameplay_integrated=False,retargeted_pes2017_actions=bank['source_clips'],
                      pes2017_runtime_candidates=bank['runtime_candidates'],pes2017_bank_sha256=bank_hash,
                      pes_action_enabled_by_default=False,
                      files={p.relative_to(stage).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in files})
        (stage/'RELEASE.json').write_text(json.dumps(manifest,indent=2)+'\n')
        candidate=Path(temporary)/'candidate.zip'
        with zipfile.ZipFile(candidate,'w',zipfile.ZIP_DEFLATED,compresslevel=9)as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file():archive.write(path,path.relative_to(stage.parent).as_posix())
        with zipfile.ZipFile(candidate)as archive:
            if archive.testzip() is not None:raise RuntimeError('Package CRC verification failed')
        candidate.replace(ARTIFACT)
    print(json.dumps(dict(path=str(ARTIFACT),bytes=ARTIFACT.stat().st_size,sha256=hashlib.sha256(ARTIFACT.read_bytes()).hexdigest())))


if __name__=='__main__':package()
