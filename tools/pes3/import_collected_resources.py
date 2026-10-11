#!/usr/bin/env python3
"""Validate a Windows collector ZIP and preserve verified stored/payload bytes.

Does not execute embedded instructions or enable animation import. DATA hashes
in its manifest are collector observations, not independently received files.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile
from actions import ELF_SHA, _inspector

LIMIT = 16 * 1024 * 1024
TARGETS = {
    '0x00470000': ('body_lnk.bin', [14,2,0]), '0x00470001': ('mon_lnk.bin', [14,2,1]),
    '0x00370000': ('anime2.bin', [14,0,0]), '0x00370001': ('anime3.bin', [14,0,1]),
    '0x00080000': ('anime.bin', [1,1,2,0,0]), '0x00080001': ('game.mbc', [1,1,2,0,1])}

def sha(data): return hashlib.sha256(data).hexdigest()
def hash_string(value): return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None
def integer(value): return type(value) is int and value >= 0

def validate(archive):
    if archive.stat().st_size > 32*1024*1024: raise ValueError('ZIP excede 32 MiB')
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist(); members = {}
        if len(entries) > 128: raise ValueError('ZIP tem entradas demais')
        for entry in entries:
            # .NET Framework on Windows writes backslashes into ZIP member
            # names. Normalize before validation and duplicate detection;
            # never use the original member name as an extraction path.
            name = entry.filename.replace('\\', '/')
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or str(path) != name.rstrip('/'):
                raise ValueError('caminho ZIP inseguro')
            if name in members: raise ValueError('entrada ZIP duplicada')
            if entry.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED): raise ValueError('compactacao ZIP inesperada')
            if (entry.external_attr >> 16) & 0o170000 == 0o120000: raise ValueError('link ZIP inesperado')
            if entry.is_dir():
                if name != 'recursos/': raise ValueError('diretorio ZIP inesperado')
                continue
            if entry.file_size > LIMIT: raise ValueError('entrada ZIP excede limite')
            if name != 'manifesto.json' and not re.fullmatch(r'recursos/[0-9a-f]{8}-[a-z0-9_.]+-[0-9a-f]{16}\.stored',name):
                raise ValueError('arquivo ZIP inesperado')
            members[name]=entry
        if 'manifesto.json' not in members or members['manifesto.json'].file_size > 1024*1024:
            raise ValueError('manifesto ausente ou grande demais')
        manifest=json.loads(zipped.read('manifesto.json').decode('utf-8-sig'))
        if manifest.get('schema_version') != 1 or manifest.get('descritores_sles_sha256') != ELF_SHA:
            raise ValueError('versao/descritores do coletor divergentes')
        if manifest.get('sles_sha256') not in (None,ELF_SHA): raise ValueError('revisao SLES divergente')
        rows=manifest.get('recursos')
        if not isinstance(rows,list) or not 6 <= len(rows) <= 30: raise ValueError('lista de recursos incompleta/invalida')
        resources={}; provenance=[]; ids=set()
        for row in rows:
            resource_id=row.get('ResourceId'); name=row.get('StoredFile'); claimed=row.get('StoredSha256')
            if resource_id not in TARGETS or not hash_string(claimed) or not isinstance(name,str):
                raise ValueError('identificacao/hash de recurso invalido')
            label,indices=TARGETS[resource_id]
            expected_name=resource_id[2:]+'-'+label+'-'+claimed[:16]+'.stored'
            if name != expected_name or row.get('Indices') != indices: raise ValueError('caminho de banco divergente')
            member='recursos/'+name
            if member not in members: raise ValueError('recurso nao esta no ZIP')
            if not hash_string(row.get('SourceSha256')) or not isinstance(row.get('Source'),str) or not re.fullmatch(r'DATA_[EFGIS]\.AFS',row['Source'],re.IGNORECASE):
                raise ValueError('origem declarada invalida')
            size=row.get('StoredBytes');offset=row.get('AbsoluteOffset');source_bytes=row.get('SourceBytes')
            if not all(integer(value) for value in (size,offset,source_bytes)) or size < 32 or size > LIMIT or offset+size > source_bytes:
                raise ValueError('intervalo de recurso invalido')
            if members[member].file_size != size: raise ValueError('tamanho armazenado divergente')
            if name not in resources:
                stored=zipped.read(members[member])  # zipfile checks its CRC.
                if sha(stored) != claimed: raise ValueError('SHA256 do recurso divergente')
                tag,_,unpacked_bytes=struct.unpack_from('<III',stored)
                if tag != row.get('HeaderTag') or unpacked_bytes != row.get('UnpackedBytes'):
                    raise ValueError('cabecalho diverge do manifesto')
                payload=stored[32:] if resource_id=='0x00080001' and len(stored)==1782 else _inspector.unpack_resource(stored,LIMIT)
                resources[name]=(stored,payload,resource_id)
            else:
                stored,payload,_=resources[name]
                if len(stored) != size or struct.unpack_from('<I',stored,8)[0] != row.get('UnpackedBytes') or row.get('HeaderTag') != struct.unpack_from('<I',stored)[0]:
                    raise ValueError('registros repetidos divergentes')
            ids.add(resource_id)
            provenance.append({key:row[key] for key in ('Source','SourceSha256','SourceBytes','ResourceId','Indices','AbsoluteOffset','StoredFile')})
        if ids != set(TARGETS): raise ValueError('faltam bancos necessarios')
        if set(members) != {'manifesto.json'} | {'recursos/'+name for name in resources}:
            raise ValueError('ZIP contem recursos sem registro')
        return resources,provenance,manifest

def import_archive(archive, output):
    archive,output=Path(archive),Path(output)
    if output.exists(): raise FileExistsError('saida ja existe; use uma nova pasta')
    resources,provenance,manifest=validate(archive)
    output.mkdir(parents=True)
    report={'schema_version':1,'collector_zip_sha256':sha(archive.read_bytes()),'resources':[],
        'source_records':provenance,'sles_sha256_reported':manifest.get('sles_sha256'),
        'data_source_hashes_independently_verified':False,'runtime_enabled':False,
        'scope':'Stored ZIP members and SHA256 verified; compressed wrappers have strict sizes/end/zlib checksums. Reported raw 1782-byte game.mbc preserves its header and 1750-byte payload without a zlib assertion or interpreting unknown header fields. Names/paths derived from pinned SLES descriptors and supplied study. DATA source hashes reported by collector; source archives not received. Link parsing, raw animation comparison, bind/axes/units/contact calibration and native integration remain required.'}
    for name,(stored,payload,resource_id) in sorted(resources.items()):
        (output/name).write_bytes(stored);(output/(name+'.payload')).write_bytes(payload)
        report['resources'].append({'resource_id':resource_id,'stored_file':name,'stored_bytes':len(stored),
            'stored_sha256':sha(stored),'payload_file':name+'.payload','payload_bytes':len(payload),
            'payload_sha256':sha(payload),'payload_kind':'reported_raw_game_mbc' if resource_id=='0x00080001' and len(stored)==1782 else 'verified_zlib'})
    (output/'import-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    p=argparse.ArgumentParser(description='Validar ZIP gerado pelo coletor Windows PES3')
    p.add_argument('archive',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();report=import_archive(a.archive,a.output)
    print(json.dumps({'result':'passed','resources':len(report['resources']),'output':str(a.output),'runtime_enabled':False}))

if __name__=='__main__':main()
