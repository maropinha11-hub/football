#!/usr/bin/env python3
"""Verify owned bind initialization with fresh received resources and code."""
import argparse
import base64
import ctypes as C
from datetime import datetime,timezone
import json
from pathlib import Path
import struct
import subprocess
import uuid

from actions import Image
from collected_assets import decode_archive
from model_reference import model_classes
from pose import skeleton
from rig import Rig, read_rig
from savestate import SaveState, digest

class ModelBind(C.Structure):
    _fields_=[('pose',Rig),('channel_rotation',(C.c_uint32*4)*19),('channel_translation',(C.c_uint32*4)*19)]
assert C.sizeof(ModelBind)==3968
SOURCE='''#include "model_bind.hpp"
static_assert(sizeof(pes3_pose::ModelBind)==3968,"model bind ABI");
extern "C" int model_bind_profile(const float* m,const int* p,const int* pairs,unsigned chop,pes3_pose::ModelBind* out) {
  if(!m||!p||!pairs||!out||chop>1)return 0;
  try {
    std::array<pes3_pose::Matrix,19> matrices;
    std::array<std::int32_t,19> parents,mirror;
    std::memcpy(matrices.data(),m,sizeof(matrices));
    std::memcpy(parents.data(),p,sizeof(parents));std::memcpy(mirror.data(),pairs,sizeof(mirror));
    const auto result=pes3_pose::initialize_model(matrices,parents,mirror,pes3_pose::BindArithmetic{bool(chop)});
    *out=result;return 1;
  } catch(const std::exception&) {return 0;}
}
extern "C" int model_bind(const float* m,const int* p,const int* pairs,pes3_pose::ModelBind* out) {
  return model_bind_profile(m,p,pairs,0,out);
}
'''

def verify(archive,state,image,core,output,profile='nearest'):
    output.mkdir(parents=True,exist_ok=False)
    assets=decode_archive(archive,output/'assets')
    for name in ('model_bind.hpp','bind_arithmetic.hpp','pose_rig.hpp','pose_ops.hpp'):
        (output/name).write_bytes((Path(__file__).with_name('recovered')/name).read_bytes())
    (output/'model_bind.cpp').write_text(SOURCE)
    cmd=['g++','-std=c++14','-O0','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off',
        '-shared','-fPIC',str(output/'model_bind.cpp'),'-o',str(output/'libmodel_bind.so')]
    subprocess.run(cmd,check=True)
    native=C.CDLL(str((output/'libmodel_bind.so').resolve()))
    native.model_bind_profile.argtypes=[C.POINTER(C.c_float),C.POINTER(C.c_int32),C.POINTER(C.c_int32),C.c_uint,C.POINTER(ModelBind)]
    native.model_bind_profile.restype=C.c_int
    reference,math_class=model_classes(core/'reference',profile,profile)
    parent_bytes=image.read(0x0126db20,19);pair_bytes=image.read(0x0126db40,19)
    if state.ram[0x0126db20:0x0126db20+19]!=parent_bytes or state.ram[0x0126db40:0x0126db40+19]!=pair_bytes:
        raise ValueError('hierarquia/pares diferem dos bytes originais')
    parents=tuple(b if b<128 else b-256 for b in parent_bytes)
    pairs=tuple(b if b<128 else b-256 for b in pair_bytes)
    fixtures=[];words={};instructions=0;constant_calls={}
    instance,bones,model,matrices=0x1f00000,0x1f10000,0x1f30000,0x1f40000
    for variant in assets['body_variants']:
        for source_model in variant['models']:
            if source_model['bone_count']!=19:continue
            packed=struct.pack('<304I',*(w for row in source_model['matrix_bits'] for w in row))
            ref=reference(state.ram,state.scratch)
            ref.ram[bones:bones+19*272]=bytes(19*272)
            ref.write(model+28,'I',matrices);ref.ram[matrices:matrices+19*64]=packed
            def observe(pc,word,registers,floats):
                nonlocal instructions
                if image.read(pc)!=struct.pack('<I',word):raise ValueError('instrucoes originais divergentes')
                words[pc]=word;instructions+=1
                if pc in (0x010a7af0,0x010a77c0):
                    if floats[12]!=0x3fc90fdb:raise ValueError('argumento trigonometrico inesperado')
                    constant_calls[pc]=constant_calls.get(pc,0)+1
            ref.run(0x113a1c0,[instance,bones,0x126db20,0x126db40,19,model],math_model=math_class(ref),
                full_quadwords=True,max_instructions=100000,instruction_observer=observe)
            spec=skeleton(ref.ram,instance);expected=ModelBind();expected.pose=read_rig(ref.ram,spec)
            for i,at in enumerate(spec['nodes']):
                expected.channel_rotation[i][:]=struct.unpack_from('<4I',ref.ram,at+0x80)
                expected.channel_translation[i][:]=struct.unpack_from('<4I',ref.ram,at+0xa0)
            actual=ModelBind();input_matrices=(C.c_float*304).from_buffer_copy(packed)
            status=native.model_bind_profile(input_matrices,(C.c_int32*19)(*parents),(C.c_int32*19)(*pairs),int(profile=='chop'),C.byref(actual))
            if status!=1 or bytes(actual)!=bytes(expected):
                a,e=struct.unpack('<992I',bytes(actual)),struct.unpack('<992I',bytes(expected))
                diff=[(i,hex(x),hex(y))for i,(x,y)in enumerate(zip(a,e))if x!=y]
                raise AssertionError('variant %d model %d status %d first differences %s'%(variant['index'],source_model['index'],status,diff[:12]))
            fixtures.append({'variant':variant['index'],'model':source_model['index'],'matrix_sha256':digest(packed),
                'matrix_base64':base64.b64encode(packed).decode(),'expected_base64':base64.b64encode(bytes(expected)).decode(),
                'original_instructions':ref.instructions})
            print('verified model %d/%d'%(variant['index'],source_model['index']),flush=True)
    report={'schema_version':1,'result':'passed','run_id':str(uuid.uuid4()),'completed_at_utc':datetime.now(timezone.utc).isoformat(),
        'collector_zip_sha256':assets['collector_zip_sha256'],'state_sha256':state.metadata['sha256'],
        'sources':image.sources,'parents':parents,'mirror_pairs':pairs,'comparisons':len(fixtures),
        'compared_words':len(fixtures)*992,'original_instructions':instructions,'instruction_words':len(words),
        'constant_trigonometry_calls':{hex(k):v for k,v in constant_calls.items()},'compile_command':cmd,
        'unique_matrix_sets':len({case['matrix_sha256']for case in fixtures}),
        'arithmetic_profile':{'fpu':profile,'vu':profile,'division':'nearest','sqrt':'nearest'},
        'runtime_enabled':False,'scope':'Complete reached initialization on canonical zeroed node storage with original matrices and ELF parent/mirror tables for every received 19-node model. Original instruction-model outputs, not native oracle injections or observed new PS2 frames. 17-node LODs, exact PS2 arithmetic, metres/time/axis conversion, gameplay selection and contacts are outside this verification.'}
    report['tool_sha256']={n:digest(Path(__file__).with_name(n).read_bytes())for n in('verify_model_bind.py','model_reference.py','collected_assets.py')}
    (output/'model-bind-vectors.json').write_text(json.dumps({'parents':parents,'pairs':pairs,'cases':fixtures},separators=(',',':'))+'\n')
    (output/'model-bind-instructions.json').write_text(json.dumps({hex(k):v for k,v in sorted(words.items())})+'\n')
    report['abi']={'model_bind_bytes':3968,'matrix_bytes':1216,'words_per_case':992,'endianness':'little'}
    report['files_sha256']={n:digest((output/n).read_bytes()) for n in
        ('model_bind.hpp','bind_arithmetic.hpp','pose_rig.hpp','pose_ops.hpp','model_bind.cpp',
         'model-bind-vectors.json','model-bind-instructions.json')}
    (output/'model-bind-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    p=argparse.ArgumentParser(description='Comparar inicializacao de esqueleto com PES3 original')
    p.add_argument('--archive',type=Path,required=True);p.add_argument('--state',type=Path,required=True)
    p.add_argument('--elf',type=Path,required=True);p.add_argument('--over',type=Path,required=True)
    p.add_argument('--core',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--profile',choices=('nearest','chop'),default='nearest')
    a=p.parse_args();r=verify(a.archive,SaveState(a.state),Image(a.elf,a.over),a.core,a.output,a.profile)
    print(json.dumps({'result':r['result'],'comparisons':r['comparisons'],'original_instructions':r['original_instructions']}))
if __name__=='__main__':main()
