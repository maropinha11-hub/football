#!/usr/bin/env python3
"""Package Windows built-in PowerShell collector, with source hashes/CRLF."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

def digest(data):return hashlib.sha256(data).hexdigest()

def build(output):
    root=Path(__file__).with_name('windows');files={}
    for name in ('ColetarPES3.bat','coletar-pes3.ps1','Pes3ResourceCollector.cs','LEIA-ME.txt'):
        files[name]=root.joinpath(name).read_text().replace('\r\n','\n').replace('\n','\r\n').encode('utf-8')
    manifest={'schema_version':1,'kind':'pes3-readonly-windows-resource-collector',
        'requirements':'Windows 11 built-in Windows PowerShell 5.1 and .NET Framework; no installation',
        'resource_ids':['0x00470000','0x00470001','0x00370000','0x00370001','0x00080000','0x00080001'],
        'files_sha256':{name:digest(data) for name,data in sorted(files.items())},
        'runtime_enabled':False,'scope':'Reads local extracted ISO DATA archives, preserves selected stored bytes in new output, hashes and records origins. No source mutation, PS2 execution or network transfer; user sends generated ZIP. Names/paths from pinned SLES descriptors/study; real DATA not received yet. Collector exercised on synthetic AFS with PowerShell 7.4.6/Linux; Windows 11 GUI/batch/5.1 not executed in cloud.'}
    files['manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode('utf-8')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files.items()):
            entry=zipfile.ZipInfo(name,date_time=(2026,10,11,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o644<<16
            archive.writestr(entry,data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():raise ValueError('invalid ZIP CRC')
    return {'bytes':output.stat().st_size,'sha256':digest(output.read_bytes()),'members':len(files)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(build(a.output),indent=2))

if __name__=='__main__':main()
