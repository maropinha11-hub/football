#!/usr/bin/env python3
"""Verify the actual portable Windows binary, transitive imports and media."""
import argparse,hashlib,io,json,os,re,subprocess,tempfile,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--archive',type=Path,default=Path('artifacts/football-training-windows-x86_64.zip'))
p.add_argument('--build',type=Path,default=Path('build-windows-mingw2'))
p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=dict(result='running',checks=[],archive_sha256=hashlib.sha256(a.archive.read_bytes()).hexdigest())
def check(name,ok,evidence=None):
 r['checks'].append(dict(check=name,result='passed'if ok else'failed',evidence=evidence))
def normalized_pe(data):
 data=bytearray(data);pe=int.from_bytes(data[60:64],'little')
 data[pe+8:pe+12]=bytes(4);data[pe+88:pe+92]=bytes(4);return data
try:
 with zipfile.ZipFile(a.archive)as z,tempfile.TemporaryDirectory(prefix='football-portable-',dir='/tmp')as temporary:
  prefix='football-training-windows-x86_64/';names=z.namelist()
  check('CRC and unique archive paths',z.testzip()is None and len(names)==len(set(names)),len(names))
  check('all files have one portable root',all(n.startswith(prefix)and '..'not in Path(n).parts for n in names))
  z.extractall(temporary);stage=Path(temporary)/prefix
  exe=z.read(prefix+'gameplayfootball.exe');pe=int.from_bytes(exe[60:64],'little')
  check('PE is Windows x64',exe[:2]==b'MZ'and exe[pe:pe+4]==b'PE\0\0'and int.from_bytes(exe[pe+4:pe+6],'little')==0x8664)
  fresh=Path(temporary)/'fresh-stripped.exe'
  subprocess.run([os.environ.get('STRIP','x86_64-w64-mingw32-strip'),'--strip-debug','-o',str(fresh),str(a.build/'gameplayfootball.exe')],check=True)
  check('packaged executable equals the fresh linked build',normalized_pe(exe)==normalized_pe(fresh.read_bytes()))
  check('new stagger and match implementation is embedded',all(s in exe for s in [b'PHYSICAL_STAGGER_CLIP',b'PHYSICAL_STAGGER_REQUEST',b'PHYSICAL_MATCH_ACTOR',b'PHYSICAL_MATCH_CONTEST',b'PHYSICAL_MATCH_GRIP_FORCE',b'PHYSICAL_SUPPORT']))
  old=subprocess.check_output(['git','show','56a65972d60ba288648fe171e39d45436ed02bc9:artifacts/football-training-windows-x86_64.zip'])
  with zipfile.ZipFile(io.BytesIO(old))as original:
   for name in ['run-training.bat','jogar-partida.bat','run-controller-test.bat']:
    check('approved launcher unchanged: '+name,z.read(prefix+name)==original.read(prefix+name))
  media=[]
  for f in Path('data').rglob('*'):
   if f.is_file()and 'pes3'not in f.relative_to('data').parts:
    n=prefix+f.relative_to('data').as_posix();media.append(n in names and z.read(n)==f.read_bytes())
  check('all bundled game assets equal the source data',all(media),dict(files=len(media)))
  check('JPEG background and decoder accompany the game',prefix+'media/menu/backgrounds/megabackground01.jpg'in names and any('jpeg'in n.lower()and n.endswith('.dll')for n in names))
  config=z.read(prefix+'training.config')
  check('approved modes keep physics opt-in',b'"training_physical_rig" "false"'in config and b'"training_physical_lab" "false"'in config)
  guide=z.read(prefix+'LEIA-FISICA.txt')
  check('directions and full match laboratory are documented',all(x in guide for x in [b'F3:',b'F2 na partida:',b'22 jogadores',b'LT/L2',b'Shift+F8:',b'Ctrl+F8:']))
  files={f.name.lower()for f in stage.glob('*.dll')}
  system={'kernel32.dll','msvcrt.dll','user32.dll','gdi32.dll','advapi32.dll','shell32.dll','ole32.dll','oleaut32.dll','winmm.dll','ws2_32.dll','imm32.dll','setupapi.dll','version.dll','shlwapi.dll','dinput8.dll','xinput9_1_0.dll','opengl32.dll','comdlg32.dll','bcrypt.dll','ntdll.dll','winpthread.dll','crypt32.dll','secur32.dll','powrprof.dll','avrt.dll','cfgmgr32.dll','dwmapi.dll','ucrtbase.dll'}
  for f in [stage/'gameplayfootball.exe',*sorted(stage.glob('*.dll'))]:
   output=subprocess.check_output(['x86_64-w64-mingw32-objdump','-p',str(f)],text=True)
   imports=re.findall(r'DLL Name:\s*([^\s]+)',output)
   missing=[n for n in imports if n.lower()not in files|system and not n.lower().startswith(('api-ms-win-','ext-ms-win-'))]
   check('all non-system DLL imports present: '+f.name,not missing,dict(imports=imports,missing=missing))
  r.update(executable_sha256=hashlib.sha256(exe).hexdigest(),entries=len(names),dlls=len(files),bytes=a.archive.stat().st_size)
 r['result']='passed'if all(c['result']=='passed'for c in r['checks'])else'failed'
except BaseException as e:r.update(result='failed',error=str(e));raise
finally:a.output.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(result=r['result'],checks=len(r['checks']),failed=[x['check']for x in r['checks']if x['result']!='passed'])),flush=True)
raise SystemExit(0 if r['result']=='passed'else 1)
