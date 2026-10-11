#!/usr/bin/env python3
"""Recompile owned bind/render code against recorded original-call vectors.

Works without the collector ZIP, PES executables, RAM, save, or core bundle.
This is an offline regression check, not a fresh original-game execution.
"""
import argparse
import base64
import ctypes as C
import gzip
import hashlib
import json
from pathlib import Path,PurePosixPath
import subprocess
import tempfile

def digest(data):return hashlib.sha256(data).hexdigest()
def numeric(case,name,size):
    raw=base64.b64decode(case[name],validate=True)
    if len(raw)!=size:raise ValueError('numeric vector length differs: '+name)
    return raw

def verify(folder,compiler='g++'):
    manifest=json.loads((folder/'manifest.json').read_text())
    if manifest['schema_version']!=1 or manifest['kind']!='pes3-source-bind-render-research':
        raise ValueError('unsupported resource proof package')
    for name,expected in manifest['files_sha256'].items():
        path=PurePosixPath(name)
        if path.is_absolute()or'..'in path.parts or str(path)!=name or '\\'in name:
            raise ValueError('unsafe package member name')
        if digest((folder/name).read_bytes())!=expected:raise ValueError('package hash differs: '+name)
    counts={};words=0;ptr=C.POINTER(C.c_float)
    with tempfile.TemporaryDirectory(prefix='pes3-resource-verify-')as temp:
        for index,run in enumerate(manifest['runs']):
            report_bytes=(folder/run['report']).read_bytes();report=json.loads(report_bytes)
            if digest(report_bytes)!=run['report_sha256']:raise ValueError('reference report hash differs')
            if report['result']!='passed' or report['state_sha256']!=manifest['state_sha256']:
                raise ValueError('reference inputs differ')
            raw=gzip.decompress((folder/run['vectors']).read_bytes())
            if digest(raw)!=run['vectors_sha256']:raise ValueError('vector hash differs')
            vectors=json.loads(raw);library=Path(temp)/('proof-%d.so'%index)
            cmd=[compiler,'-std=c++14','-O0','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off',
                '-shared','-fPIC','-I',str(folder.resolve()),str((folder/run['source']).resolve()),'-o',str(library)]
            subprocess.run(cmd,check=True,capture_output=True);lib=C.CDLL(str(library))
            arithmetic=report['arithmetic_profile'];fpu=arithmetic['fpu']
            if fpu not in('nearest','chop')or arithmetic!={'fpu':fpu,'vu':fpu,'division':'nearest','sqrt':'nearest'}:
                raise ValueError('unsupported bind/render arithmetic profile')
            chop=int(fpu=='chop');comparisons=0;run_words=0
            if run['api']=='model-bind':
                parents=(C.c_int32*19)(*vectors['parents']);pairs=(C.c_int32*19)(*vectors['pairs'])
                lib.model_bind_profile.argtypes=[ptr,C.POINTER(C.c_int32),C.POINTER(C.c_int32),C.c_uint,C.c_void_p]
                lib.model_bind_profile.restype=C.c_int
                for case in vectors['cases']:
                    matrix=numeric(case,'matrix_base64',1216);expected=numeric(case,'expected_base64',3968)
                    if digest(matrix)!=case['matrix_sha256']:raise ValueError('source matrix hash differs')
                    out=(C.c_uint32*992)();status=lib.model_bind_profile((C.c_float*304).from_buffer_copy(matrix),
                        parents,pairs,chop,out)
                    if status!=1 or bytes(out)!=expected:raise AssertionError('bind vector differs')
                    comparisons+=1;run_words+=992
            elif run['api']=='render':
                lib.owned_render_matrices.argtypes=[ptr,ptr,C.c_uint,C.c_uint,ptr]
                lib.owned_render_matrices.restype=C.c_int
                lib.owned_render_position.argtypes=[ptr,C.c_uint,ptr];lib.owned_render_position.restype=C.c_int
                for case in vectors['matrices']:
                    matrices=(C.c_float*304).from_buffer_copy(numeric(case,'matrices_base64',1216))
                    scales=(C.c_float*76).from_buffer_copy(numeric(case,'scales_base64',304))if case['scales_base64']is not None else None
                    expected=numeric(case,'expected_base64',1216);out=(C.c_float*304)()
                    status=lib.owned_render_matrices(matrices,scales,case['count'],chop,out)
                    if status!=1 or bytes(out)!=expected:raise AssertionError('render matrix vector differs')
                    comparisons+=1;run_words+=304
                for case in vectors['positions']:
                    position=(C.c_float*3).from_buffer_copy(numeric(case,'input_base64',12))
                    expected=numeric(case,'expected_base64',12);out=(C.c_float*3)()
                    if lib.owned_render_position(position,chop,out)!=1 or bytes(out)!=expected:
                        raise AssertionError('render position vector differs')
                    comparisons+=1;run_words+=3
            else:raise ValueError('unsupported proof API')
            if comparisons!=run['comparisons']or run_words!=report['compared_words']:
                raise ValueError('proof count differs')
            counts[run['label']]=comparisons;words+=run_words
    return {'result':'passed','comparisons':sum(counts.values()),'compared_words':words,'by_run':counts,
        'collector_zip_sha256':manifest['collector_zip_sha256'],'runtime_enabled':False,
        'scope':'Recompiled portable C++14 compared in bits with recorded selected-model original-instruction outputs. No new original calls, emulator frames, hardware test, whole-pose equivalence or gameplay integration.'}

def main():
    p=argparse.ArgumentParser(description='Repetir as verificacoes do bind e render sem arquivos PES')
    p.add_argument('folder',type=Path);p.add_argument('--compiler',default='g++');p.add_argument('--output',type=Path)
    a=p.parse_args();r=verify(a.folder,a.compiler)
    if a.output:
        with a.output.open('x')as stream:json.dump(r,stream,indent=2);stream.write('\n')
    print(json.dumps(r,indent=2))
if __name__=='__main__':main()
