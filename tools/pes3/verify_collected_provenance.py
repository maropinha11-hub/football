#!/usr/bin/env python3
"""Compare received motion/model resources with actual saved EE fields.

No saved float is inverted to manufacture a source value. Bind expectations
come from independently executed original routines, in explicit profiles.
Translation and mirror checks are deliberately separate: no one profile has
yet reproduced the whole captured pose.
"""
import argparse
import base64
import ctypes as C
from datetime import datetime,timezone
import json
from pathlib import Path
import struct
import uuid

from collected_assets import BANKS,animation_blocks,model_references
from import_collected_resources import validate
from pose import structures,word
from savestate import SaveState,digest
from verify_model_bind import ModelBind

def span(ram,address,size):
    if address<0 or size<0 or address+size>len(ram):
        raise ValueError('recurso salvo fora da memoria EE')
    return ram[address:address+size]

def load_bind(folder,archive_sha,state_sha):
    report=json.loads((folder/'model-bind-report.json').read_text())
    if (report['result']!='passed' or report['collector_zip_sha256']!=archive_sha
            or report['state_sha256']!=state_sha):
        raise ValueError('verificacao de bind de outra entrada ou incompleta')
    for name,expected in report['files_sha256'].items():
        if name not in ('model_bind.hpp','bind_arithmetic.hpp','pose_rig.hpp','pose_ops.hpp','model_bind.cpp',
                        'model-bind-vectors.json','model-bind-instructions.json'):
            raise ValueError('arquivo de verificacao de bind inesperado')
        if digest((folder/name).read_bytes())!=expected:
            raise ValueError('hash de verificacao de bind divergente: '+name)
    fixtures=json.loads((folder/'model-bind-vectors.json').read_text())
    if len(fixtures['cases'])!=report['comparisons']:
        raise ValueError('numero de vetores de bind divergente')
    unique={}
    for case in fixtures['cases']:
        matrix=base64.b64decode(case['matrix_base64'],validate=True)
        output=base64.b64decode(case['expected_base64'],validate=True)
        if len(matrix)!=1216 or len(output)!=C.sizeof(ModelBind) or digest(matrix)!=case['matrix_sha256']:
            raise ValueError('vetor de bind invalido')
        key=case['matrix_sha256']
        if key in unique and unique[key]['output']!=output:
            raise ValueError('matrizes iguais com saidas divergentes')
        unique.setdefault(key,{'output':output,'source_models':[]})['source_models'].append(
            {'variant':case['variant'],'model':case['model']})
    return report,unique

def investigate(archive,state,folders):
    resources,_,_=validate(archive);archive_sha=digest(archive.read_bytes())
    group={resource_id:payload for _,payload,resource_id in resources.values()}
    rows=[];start=0
    metadata_bases=[word(state.ram,0x012adef0+o)for o in(-26468,-26472,-26476)]
    for bank,(resource_id,count) in enumerate(BANKS):
        payload=group[resource_id];blocks,records,_=animation_blocks(payload,count)
        for (duration_bits,block),record in zip(blocks,records):
            clip=start+record['local_index'];motion_at=word(state.ram,0x014d7d50+4*clip)
            profile_at=word(state.ram,0x014d8fa0+4*clip)
            metadata_at=metadata_bases[bank]
            # In this idle save the first two banks are loaded; do not treat
            # an absent third bank as a successful comparison against RAM.
            loaded=bool(motion_at)
            if loaded!=bool(profile_at) or loaded!=bool(metadata_at):
                raise ValueError('banco parcialmente carregado ou ponteiros incoerentes')
            profile_size=record['motion_profile_bytes'];off=record['motion_profile_source_offset']
            profile=payload[off:off+profile_size];metadata=bytes.fromhex(record['metadata_raw_hex'])
            row={'clip':clip,'resource_id':resource_id,'loaded':loaded,'block_sha256':digest(block),
                'profile_sha256':digest(profile),'metadata_hex':metadata.hex()}
            if loaded:
                observed=(span(state.ram,motion_at,len(block)),span(state.ram,profile_at,profile_size),
                    span(state.ram,metadata_at+8*record['local_index'],8))
                if observed!=(block,profile,metadata):
                    raise ValueError('clip/perfil/metadados salvos divergem da origem: '+str(clip))
                # 01114EE0 returns header+8 as float; 0113A4C0 then
                # CVT.W.S stores an integer. Every received duration is
                # already an integral float, so no rounding tie is inferred.
                duration=struct.unpack('<f',struct.pack('<I',duration_bits))[0]
                if not duration.is_integer() or not 0<=duration<2**31:
                    raise ValueError('duracao fora dos inteiros conferidos')
                if word(state.ram,0x014d6b00+4*clip)!=int(duration):
                    raise ValueError('duracao salva diverge da origem: '+str(clip))
                row.update(motion_pointer=hex(motion_at),profile_pointer=hex(profile_at),
                    metadata_pointer=hex(metadata_at+8*record['local_index']),duration=int(duration),
                    duration_source_bits=duration_bits)
            rows.append(row)
        start+=count
    models=model_references(group['0x00470000'])
    source_hashes={model['matrix_sha256']for variant in models for model in variant['models']if model['bone_count']==19}
    actors=structures(state);captures=[]
    for actor in actors:
        for buffer,spec in enumerate(actor['buffers']):
            translation=b''.join(span(state.ram,node+0xa0,16)for node in spec['nodes'][1:])
            mirror=b''.join(span(state.ram,node+0xe0,16)for node in spec['nodes'])
            captures.append({'actor':actor['id'],'buffer':buffer,'translation':translation,'mirror':mirror})
    comparisons=[];inputs=[]
    for folder in folders:
        report,unique=load_bind(folder,archive_sha,state.metadata['sha256'])
        if set(unique)!=source_hashes:raise ValueError('matrizes de bind diferem do ZIP original')
        inputs.append({'profile':report['arithmetic_profile'],'run_id':report['run_id'],
            'report_sha256':digest((folder/'model-bind-report.json').read_bytes())})
        for matrix_sha,case in unique.items():
            bind=ModelBind.from_buffer_copy(case['output'])
            translation=b''.join(bytes(t)for t in bind.channel_translation[1:])
            mirror=b''.join(bytes(b.mirror_correction)for b in bind.pose.bones)
            comparisons.append({'profile':report['arithmetic_profile'],'matrix_sha256':matrix_sha,
                'source_models':case['source_models'],'nonroot_a_translation_sha256':digest(translation),
                'mirror_correction_sha256':digest(mirror),
                'translation_buffers_equal':sum(c['translation']==translation for c in captures),
                'translation_words_equal':sum(a==b for c in captures for a,b in zip(
                    struct.unpack('<72I',translation),struct.unpack('<72I',c['translation']))),
                'mirror_buffers_equal':sum(c['mirror']==mirror for c in captures)})
    matching=[case for case in comparisons if case['translation_buffers_equal']==len(captures)]
    if len(matching)!=1:raise ValueError('origem de translacoes nao tem correspondencia unica')
    captured=[{'actor':c['actor'],'buffer':c['buffer'],'nonroot_a_translation_sha256':digest(c['translation']),
        'mirror_correction_sha256':digest(c['mirror'])}for c in captures]
    return {'schema_version':1,'result':'passed','run_id':str(uuid.uuid4()),
        'completed_at_utc':datetime.now(timezone.utc).isoformat(),'collector_zip_sha256':archive_sha,
        'state_sha256':state.metadata['sha256'],'bind_inputs':inputs,'loaded_motion_blocks':sum(r['loaded']for r in rows),
        'loaded_metadata_records':sum(r['loaded']for r in rows),'loaded_motion_profiles':sum(r['loaded']for r in rows),
        'unloaded_clips':sum(not r['loaded']for r in rows),'motion_records':rows,'captured_buffers':captured,
        'bind_field_comparisons':comparisons,'unique_nonroot_translation_source':{
            k:matching[0][k]for k in('profile','matrix_sha256','nonroot_a_translation_sha256')},
        'translation_components':len(captures)*72,'complete_pose_equivalence':False,'runtime_enabled':False,
        'tool_sha256':digest(Path(__file__).read_bytes()),
        'scope':'Original resource bytes compared with actual saved motion blocks/profiles/metadata, and fresh original-initialization bind fields compared separately with saved nonroot A translations and mirror corrections. Root A translation is animated and excluded. These fields do not establish whole-pose arithmetic, clock/video cadence, contact events, animation choices over time, or native gameplay integration.'}

def main():
    p=argparse.ArgumentParser(description='Conferir origem dos recursos e canais de referencia salvos')
    p.add_argument('--archive',type=Path,required=True);p.add_argument('--state',type=Path,required=True)
    p.add_argument('--bind',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=investigate(a.archive,SaveState(a.state),a.bind)
    with a.output.open('x')as stream:json.dump(r,stream,indent=2);stream.write('\n')
    print(json.dumps({k:r[k]for k in('result','loaded_motion_blocks','loaded_motion_profiles',
        'loaded_metadata_records','unloaded_clips','translation_components','unique_nonroot_translation_source')},indent=2))
if __name__=='__main__':main()
