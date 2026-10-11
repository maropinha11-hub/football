#!/usr/bin/env python3
"""Check the actual pose-to-render matrix bridge against original calls."""
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
from model_reference import model_classes
from pose import structures,word
from savestate import SaveState,digest

SOURCE='''#include "render_pose.hpp"
static_assert(sizeof(pes3_pose::RenderMatrices)==1216,"render matrix ABI");
extern "C" int owned_render_matrices(const float* m,const float* s,unsigned count,unsigned chop,float* out) {
  if(!m||!out||count>19||chop>1)return 0;
  try {
    pes3_pose::RenderMatrices matrices;pes3_pose::RenderScales scales;
    std::memcpy(matrices.data(),m,sizeof(matrices));
    if(s)std::memcpy(scales.data(),s,sizeof(scales));
    const auto result=pes3_pose::render_matrices(matrices,s?&scales:nullptr,count,pes3_pose::BindArithmetic{bool(chop)});
    std::memcpy(out,result.data(),sizeof(result));return 1;
  }catch(const std::exception&){return 0;}
}
extern "C" int owned_render_position(const float* p,unsigned chop,float* out) {
  if(!p||!out||chop>1)return 0;
  try {
    std::array<float,3> position;std::memcpy(position.data(),p,sizeof(position));
    const auto result=pes3_pose::render_position(position,pes3_pose::BindArithmetic{bool(chop)});
    std::memcpy(out,result.data(),sizeof(result));return 1;
  }catch(const std::exception&){return 0;}
}
'''

def verify(state,image,core,output,profile):
    output.mkdir(parents=True,exist_ok=False)
    names=('render_pose.hpp','bind_arithmetic.hpp','pose_rig.hpp','pose_ops.hpp')
    for name in names:(output/name).write_bytes((Path(__file__).with_name('recovered')/name).read_bytes())
    (output/'render_pose.cpp').write_text(SOURCE)
    cmd=['g++','-std=c++14','-O0','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off',
        '-shared','-fPIC',str(output/'render_pose.cpp'),'-o',str(output/'librender_pose.so')]
    subprocess.run(cmd,check=True)
    lib=C.CDLL(str((output/'librender_pose.so').resolve()))
    ptr=C.POINTER(C.c_float)
    lib.owned_render_matrices.argtypes=[ptr,ptr,C.c_uint,C.c_uint,ptr];lib.owned_render_matrices.restype=C.c_int
    lib.owned_render_position.argtypes=[ptr,C.c_uint,ptr];lib.owned_render_position.restype=C.c_int
    reference,math_class=model_classes(core/'reference',profile,profile)
    actors=structures(state);fixtures=[];position_fixtures=[];captured_matrices=[];words={};instructions=0
    model,count_desc,destination=0x1f30000,0x1f31000,0x1f40000
    def observe(pc,w,registers,floats):
        nonlocal instructions
        if image.read(pc)!=struct.pack('<I',w):raise ValueError('original render instruction changed')
        words[pc]=w;instructions+=1
    for actor in actors:
        player=int(actor['player'],16);obj=int(actor['object'],16);scale_at=word(state.ram,obj+224)
        if scale_at!=player+848:raise ValueError('appearance scale ownership differs from original caller')
        scale_bytes=state.ram[scale_at:scale_at+304]
        for buffer,spec in enumerate(actor['buffers']):
            source=b''.join(state.ram[node:node+64]for node in spec['nodes'])
            for use_scale,count in((False,0),(False,17),(False,19),(True,0),(True,17),(True,19)):
                ref=reference(state.ram,state.scratch)
                ref.ram[destination:destination+1216]=bytes(1216)
                ref.write(model+28,'I',destination);ref.write(count_desc+12,'I',count)
                ref.run(0x1139e30,[int(spec['instance'],16),model,count_desc,scale_at if use_scale else 0],
                    math_model=math_class(ref),full_quadwords=True,instruction_observer=observe,max_instructions=10000)
                expected=bytes(ref.ram[destination:destination+1216])
                matrices=(C.c_float*304).from_buffer_copy(source)
                scales=(C.c_float*76).from_buffer_copy(scale_bytes)if use_scale else None
                actual=(C.c_float*304)()
                status=lib.owned_render_matrices(matrices,scales,count,int(profile=='chop'),actual)
                if status!=1 or bytes(actual)!=expected:
                    raise AssertionError('render bridge differs: actor %d buffer %d scale %s count %d'%(
                        actor['id'],buffer,use_scale,count))
                fixtures.append({'actor':actor['id'],'buffer':buffer,'count':count,
                    'matrices_base64':base64.b64encode(source).decode(),
                    'scales_base64':base64.b64encode(scale_bytes).decode()if use_scale else None,
                    'expected_base64':base64.b64encode(expected).decode(),'original_instructions':ref.instructions})
        # Follow the actual renderer's selected source/descriptor pair, rather
        # than assuming object+8 or a 19-bone LOD. 01139DD0..DEC supplies these
        # same pointers to 01139E30. They select 14x19 and 8x17 matrices here.
        record=word(state.ram,obj+36);pair=word(state.ram,obj+40)
        source_instance=word(state.ram,record+4)
        desc,countdesc=struct.unpack_from('<2I',state.ram,pair)
        count=word(state.ram,countdesc+12);matrices_at=word(state.ram,desc+28)
        buffers=[i for i,s in enumerate(actor['buffers'])if int(s['instance'],16)==source_instance]
        if len(buffers)!=1 or count not in(17,19):raise ValueError('renderer source/LOD differs from checked layout')
        case=next(c for c in fixtures if c['actor']==actor['id']and c['buffer']==buffers[0]
                  and c['count']==count and c['scales_base64']is not None)
        rendered=base64.b64decode(case['expected_base64'])[:count*64]
        saved=state.ram[matrices_at:matrices_at+count*64]
        if len(saved)!=count*64:raise ValueError('saved matrices outside EE')
        captured_matrices.append({'actor':actor['id'],'source_buffer':buffers[0],'count':count,
            'saved_equal':rendered==saved,'saved_sha256':digest(saved),'original_output_sha256':digest(rendered),
            'saved_equal_words':sum(a==b for a,b in zip(struct.unpack('<'+'I'*16*count,saved),
                struct.unpack('<'+'I'*16*count,rendered)))})
        position=state.ram[player+708:player+720];ref=reference(state.ram,state.scratch)
        ref.run(0x113c870,[destination],initial_float_registers={12:struct.unpack_from('<I',position,0)[0],
            13:struct.unpack_from('<I',position,4)[0],14:struct.unpack_from('<I',position,8)[0]},
            math_model=math_class(ref),instruction_observer=observe,max_instructions=100)
        expected=bytes(ref.ram[destination+192:destination+204]);actual=(C.c_float*3)()
        status=lib.owned_render_position((C.c_float*3).from_buffer_copy(position),int(profile=='chop'),actual)
        if status!=1 or bytes(actual)!=expected:raise AssertionError('render position differs')
        position_fixtures.append({'actor':actor['id'],'input_base64':base64.b64encode(position).decode(),
            'expected_base64':base64.b64encode(expected).decode(),
            'saved_render_position_equal':expected==state.ram[obj+192:obj+204]})
        print('verified render actor %d'%actor['id'],flush=True)
    (output/'render-vectors.json').write_text(json.dumps({'matrices':fixtures,'positions':position_fixtures},separators=(',',':'))+'\n')
    (output/'render-instructions.json').write_text(json.dumps({hex(k):v for k,v in sorted(words.items())})+'\n')
    report={'schema_version':1,'result':'passed','run_id':str(uuid.uuid4()),
        'completed_at_utc':datetime.now(timezone.utc).isoformat(),'state_sha256':state.metadata['sha256'],
        'sources':image.sources,'arithmetic_profile':{'fpu':profile,'vu':profile,'division':'nearest','sqrt':'nearest'},
        'matrix_comparisons':len(fixtures),'position_comparisons':len(position_fixtures),
        'saved_position_matches':sum(c['saved_render_position_equal']for c in position_fixtures),
        'saved_matrix_matches':sum(c['saved_equal']for c in captured_matrices),
        'captured_matrix_checks':captured_matrices,
        'compared_words':len(fixtures)*304+len(position_fixtures)*3,
        'original_instructions':instructions,'instruction_words':len(words),'compile_command':cmd,
        'tool_sha256':{name:digest(Path(__file__).with_name(name).read_bytes())for name in('verify_render_pose.py','model_reference.py')},
        'files_sha256':{name:digest((output/name).read_bytes())for name in names+('render_pose.cpp','render-vectors.json','render-instructions.json')},
        'runtime_enabled':False,
        'scope':'Reached pose-to-render bridge on captured 19-node buffers, copying matrices or applying actual per-column appearance scales for destination counts 0/17/19, and physics-to-render positions for all 22 actors. Separately compares actual selected descriptor matrices in the save (14x19 and 8x17) with the original-call outputs. Source pose evaluation, 17-node bind topology, render orientation, metres, video cadence, contact events and native retargeting are outside this proof.'}
    (output/'render-report.json').write_text(json.dumps(report,indent=2)+'\n');return report

def main():
    p=argparse.ArgumentParser(description='Conferir a ponte entre pose e matrizes desenhadas do PES3')
    for name in('state','elf','over','core','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--profile',choices=('nearest','chop'),default='nearest');a=p.parse_args()
    r=verify(SaveState(a.state),Image(a.elf,a.over),a.core,a.output,a.profile)
    print(json.dumps({k:r[k]for k in('result','matrix_comparisons','position_comparisons','saved_matrix_matches','saved_position_matches','original_instructions')}))
if __name__=='__main__':main()
