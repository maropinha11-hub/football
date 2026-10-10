#!/usr/bin/env python3
"""Compare generated routing to the original integer instruction prefixes.

The independent instruction interpreter comes from the supplied v0.14 package.
Only routing is executed, stopping before the chosen action/animation block.
"""
import argparse
import hashlib
import importlib.util
import json
import struct
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from actions import Image


def verify(image, output, reference):
    document=json.loads((output/'actions.json').read_text())
    if document['sources'] != image.sources:raise ValueError('mapa de outra versão')
    spec=importlib.util.spec_from_file_location('pes3_uploaded_integer_reference',reference)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    float_spec=importlib.util.spec_from_file_location('pes3_uploaded_float_reference',reference.with_name('float_vector_model.py'))
    float_module=importlib.util.module_from_spec(float_spec);float_spec.loader.exec_module(float_module)
    memory=bytearray(32*1024*1024)
    for base,data,_ in image.regions:memory[base:base+len(data)]=data
    oracle=module.IntegerReference(memory)
    routing=document['routing'];player=0x01f80000;expected=[];counts={}

    def selected(part,value):
        if part=='requests':
            value&=255
            targets=routing[part]['targets']
            return int(targets[value] if value<len(targets) else routing[part]['default'],16)
        current=routing[part]
        return int(next((c['block'] for c in current['cases'] if c['value']==value),current['default']),16)

    domains=[('requests',list(range(256))+[0xffffffff,0x10000,0x100ff,0x10101]),
             ('actions',range(256)),('action1_substates',range(65536))]
    for part,domain in domains:
        current=routing[part]
        targets=current['targets'] if part=='requests' else [c['block'] for c in current['cases']]
        stops={int(t,16) for t in targets}|{int(current['default'],16)}
        counts[part]=0
        for value in domain:
            registers={16:player}
            args=[player,value] if part=='requests' else []
            if part=='actions':registers[2]=value
            if part=='action1_substates':
                registers[19]=player;oracle.write(player+0xdc,'H',value)
            oracle.run(int(current['entry'],16),args,initial_registers=registers,
                       stop_before=stops,max_instructions=256)
            want=selected(part,value)
            if oracle.last_pc != want:raise AssertionError((part,value,hex(oracle.last_pc),hex(want)))
            expected.append(want);counts[part]+=1
    raw=b''.join(struct.pack('<I',n) for n in expected)
    with tempfile.TemporaryDirectory(prefix='pes3-dispatch-') as folder:
        temporary=Path(folder)
        javascript=temporary/'verify.js'
        javascript.write_text('const d=require(process.argv[2]), out=[];'
          'for(let i=0;i<256;i++)out.push(d.request(i));'
          'for(const i of [0xffffffff,0x10000,0x100ff,0x10101])out.push(d.request(i));'
          'for(let i=0;i<256;i++)out.push(d.action(i));'
          'for(let i=0;i<65536;i++)out.push(d.action1Substate(i));'
          'const data=Buffer.alloc(out.length*4);out.forEach((s,i)=>data.writeUInt32LE(Number(s),i*4));'
          'process.stdout.write(data);')
        result=subprocess.run(['node',str(javascript),str((output/'action_dispatch.js').resolve())],check=True,capture_output=True)
        if result.stdout!=raw:raise AssertionError('JavaScript diverge das instruções originais')
        cpp=temporary/'verify.cpp'
        cpp.write_text('#include "action_dispatch.hpp"\n#include <iostream>\n'
          'void emit(std::uint32_t v){for(unsigned s=0;s<32;s+=8)std::cout.put(static_cast<char>(v>>s));}\n'
          'int main(){using namespace pes3_recovered;'
          'for(unsigned i=0;i<256;i++)emit(request_block(i));'
          'for(unsigned i:{0xffffffffu,0x10000u,0x100ffu,0x10101u})emit(request_block(i));'
          'for(unsigned i=0;i<256;i++)emit(action_block(static_cast<std::uint8_t>(i)));'
          'for(unsigned i=0;i<65536;i++)emit(action1_substate_block(static_cast<std::uint16_t>(i)));}\n')
        executable=temporary/'verify'
        subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-I',str(output),str(cpp),'-o',str(executable)],check=True,capture_output=True)
        result=subprocess.run([str(executable)],check=True,capture_output=True)
        if result.stdout!=raw:raise AssertionError('C++ diverge das instruções originais')
    tables=[]
    for function in document['functions']:
        for table in function['jump_tables']:
            entry=int(table['guard_pc'],16);index=table['index_register']
            names='zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split()
            reg=names.index(index);targets=[int(t,16) for t in table['targets']];default=int(table['default'],16)
            stops=set(targets)|{default}
            cases=table['count']+2
            for value in [*range(table['count']),table['count'],-1]:
                oracle.run(entry,[],initial_registers={reg:value},stop_before=stops,max_instructions=64,
                           math_model=float_module.FloatVectorModel())
                want=targets[value] if 0<=value<table['count'] else default
                if oracle.last_pc!=want:raise AssertionError(('switch',table['jump_pc'],value,hex(oracle.last_pc),hex(want)))
            tables.append({'jump_pc':table['jump_pc'],'cases':cases,'table_sha256':table['table_sha256']})
    return {'schema_version':1,'result':'passed','run_id':str(uuid.uuid4()),
            'completed_at_utc':datetime.now(timezone.utc).isoformat(),'sources':image.sources,
            'routing_cases':counts,'original_routing_executions':len(expected),
            'javascript_comparisons':len(expected),'cpp_comparisons':len(expected),
            'routing_outputs_sha256':hashlib.sha256(raw).hexdigest(),
            'guarded_tables_verified':len(tables),'original_switch_executions':sum(t['cases'] for t in tables),
            'switch_results':tables,'reference_file_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),
            'analysis_summary':document['summary'],
            'actions_file_sha256':hashlib.sha256((output/'actions.json').read_bytes()).hexdigest(),
            'float_reference_file_sha256':hashlib.sha256(reference.with_name('float_vector_model.py').read_bytes()).hexdigest(),
            'scope':'Original integer routing prefixes compared to generated JS/C++; bounded switch prefixes executed. Stops before action bodies; no complete action, full frame, table mutation, contacts or PS2 hardware validation.'}


def main():
    parser=argparse.ArgumentParser(description='Conferir o roteamento recuperado contra as instruções do PES')
    parser.add_argument('--elf',type=Path,required=True);parser.add_argument('--over',type=Path,required=True)
    parser.add_argument('--actions',type=Path,required=True);parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('escolha um relatório novo')
    result=verify(Image(args.elf,args.over),args.actions,args.reference)
    with args.output.open('x') as out:out.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='switch_results'},indent=2))


if __name__=='__main__':main()
