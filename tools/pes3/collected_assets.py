#!/usr/bin/env python3
"""Decode collected resources without consulting a previous clip catalogue.

Numeric motion bytes are retained, including irregular key times. Model
matrices are source references, not an animated RAM cache or an inferred
T-pose. No PES meshes/executable bytes are exported by this tool.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib

from fpsa import read_bundle, EXPECTED_BUNDLE_SHA256
from import_collected_resources import validate, TARGETS

BANKS = (('0x00080000', 875), ('0x00370000', 124), ('0x00370001', 106))
MAX_BLOCK = 16 * 1024 * 1024

def sha(data): return hashlib.sha256(data).hexdigest()

def words(data, offset, count):
    if offset < 0 or count < 0 or offset + 4 * count > len(data):
        raise ValueError('tabela fora do recurso')
    return struct.unpack_from('<' + 'I' * count, data, offset)

def sections(data, expected_count=None):
    count, table = words(data, 0, 2)
    if not 0 < count <= 2048 or table != 8 or (expected_count is not None and count != expected_count):
        raise ValueError('diretorio de recurso divergente')
    offsets = words(data, table, count)
    if offsets[0] < table + 4 * count or offsets[-1] >= len(data) or any(a >= b for a,b in zip(offsets,offsets[1:])):
        raise ValueError('intervalos de recurso invalidos')
    return [(offset, data[offset:end]) for offset,end in zip(offsets, offsets[1:] + (len(data),))]

def inner_wrapper(data, expected_tag):
    tag, size, plain = words(data, 0, 3)
    if tag != expected_tag or size > len(data)-32 or plain > MAX_BLOCK:
        raise ValueError('cabecalho de recurso interno invalido')
    decoder = zlib.decompressobj()
    try: payload = decoder.decompress(data[32:32+size], plain+1)
    except zlib.error as exc: raise ValueError('checksum/fluxo zlib interno invalido') from exc
    if len(payload) != plain or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('tamanho/final zlib interno divergente')
    return payload, {'tag': hex(tag), 'stored_bytes': 32+size, 'padding_bytes': len(data)-32-size,
        'stored_sha256': sha(data[:32+size]), 'payload_bytes': len(payload), 'payload_sha256': sha(payload)}

def animation_blocks(data, expected_count):
    outer = sections(data)
    if len(outer) not in (3,4): raise ValueError('banco de animacoes invalido')
    base, first = outer[0]
    tag, size = words(first, 0, 2)
    if tag != 0x600 or size > len(first)-32 or size < 8:
        raise ValueError('cabecalho do banco de clips invalido')
    motion = first[32:32+size]
    entries = sections(motion, expected_count)
    _, profiles = outer[1]
    profile_offsets = words(profiles,0,expected_count)
    if (profile_offsets[0] < 4*expected_count or profile_offsets[-1] >= len(profiles)
            or any(a>=b for a,b in zip(profile_offsets,profile_offsets[1:]))):
        raise ValueError('tabela de perfis de movimento invalida')
    _, metadata = outer[2]
    metadata_tag,metadata_size=words(metadata,0,2)
    if metadata_tag != 0x900 or metadata_size != 8*expected_count or len(metadata)<32+metadata_size:
        raise ValueError('registros auxiliares de animacao invalidos')
    blocks, records = [], []
    for index,(offset, padded) in enumerate(entries):
        signature, flags, duration, _, table = words(padded,0,5)
        if signature != 0x20011119 or flags != 0x20000002:
            raise ValueError('formato de clip divergente')
        count, = words(padded, table, 1)
        length = 32+172*count
        if not 0 < count <= 512 or table != 28+164*count or length > len(padded):
            raise ValueError('intervalos de chaves invalidos')
        block = padded[:length]
        blocks.append((duration,block))
        records.append({'local_index': index, 'source_offset': base+32+offset,
            'block_bytes': length, 'block_sha256': sha(block), 'padding_bytes': len(padded)-length,
            'metadata_raw_hex': metadata[32+index*8:40+index*8].hex(),
            'motion_profile_source_offset':outer[1][0]+profile_offsets[index],
            'motion_profile_bytes': (profile_offsets[index+1] if index+1<expected_count else len(profiles))-profile_offsets[index],
            'motion_profile_sha256':sha(profiles[profile_offsets[index]:profile_offsets[index+1] if index+1<expected_count else len(profiles)])})
    return blocks, records, [{'offset':off,'bytes':len(blob),'sha256':sha(blob)} for off,blob in outer[1:]]

def model_references(data):
    variants=[]; total=0
    for variant,(off,blob) in enumerate(sections(data,13)):
        decoded, wrapper = inner_wrapper(blob,0x10600); models=[]
        total += len(decoded)
        if total > 64*1024*1024: raise ValueError('orcamento de modelos excedido')
        for lod,(model_offset,model) in enumerate(sections(decoded,5)):
            tag,_,matrices_at,count,links_at=words(model,0,5)
            if tag != 0xffff0003 or count not in (17,19) or matrices_at < 128 or matrices_at+64*count > len(model) or links_at+2*count > len(model):
                raise ValueError('modelo/esqueleto fora do formato conferido')
            packed = model[matrices_at:matrices_at+64*count]
            matrices = [list(words(packed,64*i,16)) for i in range(count)]
            if not all(math.isfinite(struct.unpack('<f',struct.pack('<I',v))[0]) for row in matrices for v in row):
                raise ValueError('matriz de modelo nao finita')
            models.append({'index':lod,'source_offset':model_offset,'source_bytes':len(model),'bone_count':count,
                'matrix_offset':matrices_at,'matrix_sha256':sha(packed),'matrix_bits':matrices,
                'source_links_i16':list(struct.unpack_from('<'+'h'*count,model,links_at))})
        variants.append({'index':variant,'source_offset':off,'wrapper':wrapper,'models':models})
    return variants

def texture_inventory(data):
    entries=[]; total=0
    for index,(off,blob) in enumerate(sections(data,280)):
        decoded, wrapper=inner_wrapper(blob,0x10300);total+=len(decoded)
        if total > 64*1024*1024: raise ValueError('orcamento de recursos excedido')
        entries.append({'index':index,'source_offset':off,'wrapper':wrapper})
    return entries

def decode_archive(archive, output):
    archive,output=Path(archive),Path(output)
    if output.exists(): raise FileExistsError('saida ja existe; use outra pasta')
    resources,provenance,manifest=validate(archive)
    grouped={}
    for stored,payload,resource_id in resources.values():
        if resource_id in grouped and grouped[resource_id] != payload:
            raise ValueError('variantes de idioma com conteudo divergente')
        grouped[resource_id]=payload
    blocks=[]; sources=[]; records=[]
    for resource_id,count in BANKS:
        payload=grouped[resource_id];bank,rows,other=animation_blocks(payload,count)
        start=len(blocks)
        records.extend(dict(row,clip=start+row['local_index'],resource_id=resource_id) for row in rows)
        blocks.extend(bank)
        sources.append({'resource_id':resource_id,'name':TARGETS[resource_id][0],'bytes':len(payload),
            'sha256':sha(payload),'first_clip':start,'clips':count,'other_sections':other})
    offset=32+16*len(blocks);directory=bytearray();payload=bytearray()
    for index,(duration,block) in enumerate(blocks):
        directory.extend(struct.pack('<4I',index,duration,offset,len(block)))
        payload.extend(block);offset+=len(block)
    bundle=b'FPSANM14'+struct.pack('<6I',len(blocks),32,14,19,164,0)+directory+payload
    if sha(bundle) != EXPECTED_BUNDLE_SHA256:
        raise ValueError('os clips coletados divergem do contêiner v14 conferido')
    models=model_references(grouped['0x00470000']);textures=texture_inventory(grouped['0x00470001'])
    report={'schema_version':1,'collector_zip_sha256':sha(archive.read_bytes()),'sources':sources,
        'source_records':provenance,'bundle_sha256':sha(bundle),'bundle_bytes':len(bundle),'clips':len(blocks),
        'original_clip_records':records,'body_variants':models,'mon_entries':textures,
        'game_mbc_payload_sha256':sha(grouped['0x00080001']),
        'sles_sha256_reported':manifest.get('sles_sha256'),'data_source_hashes_independently_verified':False,
        'runtime_enabled':False,'scope':'All original motion blocks verified against FPSANM14; all body/mon nested zlib checksums and sizes verified. Model matrices retain source bits, with no bind/local/axis/unit inference. Source DATA archives were not uploaded. Complete action selection, contacts and native retarget remain required.'}
    output.mkdir(parents=True)
    bundle_path=output/'pes_animation_tracks.fpsa';bundle_path.write_bytes(bundle)
    _,catalogue=read_bundle(bundle_path)
    report['poses']=catalogue['poses']
    (output/'collected-assets.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    p=argparse.ArgumentParser(description='Conferir clips e referencias de modelo coletados do PES3')
    p.add_argument('archive',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=decode_archive(a.archive,a.output)
    print(json.dumps({'result':'passed','clips':r['clips'],'poses':r['poses'],
        'body_variants':len(r['body_variants']),'mon_entries':len(r['mon_entries']),'output':str(a.output)}))
if __name__=='__main__':main()
