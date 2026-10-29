"""Validate the actual self-contained animation/IK Windows release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,default=Path('artifacts/football-classico-windows-x86_64.zip'))
p.add_argument('--build',type=Path,default=Path('build-windows-mingw2'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=dict(result='running',checks=[],archive_sha256=hashlib.sha256(a.archive.read_bytes()).hexdigest())
def check(name,ok,evidence=None):r['checks'].append(dict(check=name,result='passed'if ok else'failed',evidence=evidence))
with zipfile.ZipFile(a.archive)as z,tempfile.TemporaryDirectory()as temporary:
    prefix='football-classico-windows-x86_64/';names=z.namelist()
    check('archive CRC, unique paths and a single portable root',z.testzip()is None and len(names)==len(set(names))and all(n.startswith(prefix)and '..'not in Path(n).parts for n in names))
    check('legacy dynamic-code launchers and scripts are absent',not any(n.lower().endswith(('.ps1','.cs','.vbs'))for n in names))
    z.extractall(temporary);root=Path(temporary)/prefix;manifest=json.loads((root/'RELEASE.json').read_text())
    check('every released payload matches its content hash',all(hashlib.sha256((root/n).read_bytes()).hexdigest()==h for n,h in manifest['files'].items()))
    check('the release explicitly uses animation/IK without ragdoll or original PES integration',manifest['mode']=='native_animation_and_ik'and manifest['ragdoll']is False and manifest['cloth_dynamics']is False and manifest['original_pes_gameplay_integrated']is False)
    cfg=(root/'training.config').read_text();check('new and direct-executable launch use the same approved settings',(root/'football.config').read_text()==cfg==Path('config/training.config').read_text())
    check('animation mode, skin contacts and no cloth are the defaults',all(x in cfg for x in ['"training_animation_body" "true"','"training_physical_rig" "true"','"training_shirt_cloth" "false"','"training_body_controller" "0"']))
    check('ball rebound uses the reviewed shared setting','"training_ground_bounce" "0.74"'in cfg)
    for filename,args in [('treino-classico.bat','--training --physical-rig'),('run-training.bat','--training --physical-rig'),('jogar-partida.bat','--player-match --physical-rig'),('run-controller-test.bat','--test-controller')]:
        bat=(root/filename).read_bytes();check('portable native launcher: '+filename,b'cd /d "%~dp0"'in bat and args.encode()in bat and b'powershell'not in bat.lower())
    exe=(root/'gameplayfootball.exe').read_bytes();pe=int.from_bytes(exe[60:64],'little')
    check('native executable is Windows x64',exe[:2]==b'MZ'and exe[pe:pe+4]==b'PE\0\0'and int.from_bytes(exe[pe+4:pe+6],'little')==0x8664)
    fresh=Path(temporary)/'fresh.exe';subprocess.run([os.environ.get('STRIP','x86_64-w64-mingw32-strip'),'--preserve-dates','--strip-debug','-o',str(fresh),str(a.build/'gameplayfootball.exe')],check=True)
    check('archive executable equals the freshly linked and stripped build',exe==fresh.read_bytes())
    check('no-ragdoll mode and real contact gates are present',all(s in exe for s in [b'ANIMATION_BODY actor=',b'ragdoll=0 cloth=0 contacts=skin',b'TRAINING_SKIN_CONTACT',b'FIRSTPERSON_FRAME']))
    check('native media and database are preserved',all((root/f.relative_to('data')).read_bytes()==f.read_bytes()for f in Path('data').rglob('*')if f.is_file()and 'pes3'not in f.relative_to('data').parts and f.name!='football.config'))
    check('the new game guide is bundled',(root/'LEIA-PRIMEIRO.txt').read_bytes()==Path('docs/TREINO-CLASSICO.md').read_bytes())
    system={'kernel32.dll','msvcrt.dll','user32.dll','gdi32.dll','advapi32.dll','shell32.dll','ole32.dll','oleaut32.dll','winmm.dll','ws2_32.dll','imm32.dll','setupapi.dll','version.dll','shlwapi.dll','dinput8.dll','xinput9_1_0.dll','opengl32.dll','comdlg32.dll','bcrypt.dll','ntdll.dll','winpthread.dll','crypt32.dll','secur32.dll','powrprof.dll','avrt.dll','cfgmgr32.dll','dwmapi.dll','ucrtbase.dll'}
    dlls={x.name.lower()for x in root.glob('*.dll')}
    for f in [root/'gameplayfootball.exe',*sorted(root.glob('*.dll'))]:
        imports=re.findall(r'DLL Name:\s*([^\s]+)',subprocess.check_output(['x86_64-w64-mingw32-objdump','-p',str(f)],text=True))
        missing=[n for n in imports if n.lower()not in dlls|system and not n.lower().startswith(('api-ms-win-','ext-ms-win-'))]
        check('DLL dependencies: '+f.name,not missing,missing)
    r.update(executable_sha256=hashlib.sha256(exe).hexdigest(),bytes=a.archive.stat().st_size,windows_gui_executed=False)
r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed';a.output.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(result=r['result'],checks=len(r['checks']),failed=[c['check']for c in r['checks']if c['result']!='passed'])))
raise SystemExit(0 if r['result']=='passed'else 1)
