#!/usr/bin/env python3
"""Compare the production source-motion path with fresh original calls.

This proves an initialized, unmirrored clip's numeric decode/local/global path
under the selected nearest model. It does not resume a frame or prove native
retarget, game action choice, source cadence, blend policy or ball contacts.
"""
import argparse
import ctypes as C
from datetime import datetime,timezone
import gzip
import json
from pathlib import Path
import re
import struct
import uuid

from actions import Image
from fpsa import read_bundle,EXPECTED_BUNDLE_SHA256
from model_reference import model_classes
from rig import read_rig
from pose import skeleton
from runtime_abi import build,Frame,Channels,Pose
from savestate import SaveState,digest

NODE,INSTANCE,BLOCK=0x01fc0000,0x01fc2000,0x01fd0000
CLIPS=(47,236,313,304,224,219,269,120,372,264,206,797,275,317,366,741,999,1104)

def verify(args):
    args.output.mkdir(parents=True,exist_ok=False)
    lib,command=build(args.output)
    data,catalogue=read_bundle(args.bundle)
    if catalogue['sha256']!=EXPECTED_BUNDLE_SHA256:raise ValueError('banco nao corresponde ao recebido')
    state=SaveState(args.state);image=Image(args.elf,args.over)
    reference,math_class=model_classes(args.core/'reference','nearest','nearest')
    ref=reference(state.ram,state.scratch)
    root=Path(__file__).resolve().parents[2]
    text=(root/'src/pes3/pes_skeleton_bind_bits.h').read_text()
    rows=re.findall(r'\{([^{}]+)\}',text.split('PES_SKELETON_TRANSLATION_BITS')[1])
    translations=[tuple(int(x.strip().rstrip('u'),0)for x in row.split(','))for row in rows]
    parents=tuple(b if b<128 else b-256 for b in image.read(0x126db20,19))
    pairs=tuple(b if b<128 else b-256 for b in image.read(0x126db40,19))
    if len(translations)!=19:raise ValueError('tabela de translacoes diferente')
    words={};instructions=0;cases=[]
    def observe(pc,word,registers,floats):
        nonlocal instructions
        if image.read(pc)!=struct.pack('<I',word):raise ValueError('instrucoes originais divergentes')
        words[pc]=word;instructions+=1
        if pc==0x1113dac: selected.append((floats[20],(registers[6]-(BLOCK+table+4))//8))
    bank=lib.bank_create()
    try:
        if lib.bank_load(bank,str(args.bundle).encode())!=1 or lib.bank_count(bank)!=1105:raise AssertionError('production bank load')
        for clip in CLIPS:
            entry=catalogue['entries'][clip];block=data[entry['bundle_offset']:entry['bundle_offset']+entry['block_bytes']]
            table=struct.unpack_from('<I',block,16)[0];duration=entry['duration_original_units']
            for phase in (-1.0,0.0,struct.unpack('<f',struct.pack('<f',duration*.431))[0],duration,duration+1):
                channels=Channels();channels.channel_count=19
                for i in range(19):
                    channels.bones[i].rotation_a[3]=channels.bones[i].rotation_b[3]=1
                    for axis in range(4):
                        value=struct.unpack('<f',struct.pack('<I',translations[i][axis]))[0]
                        channels.bones[i].translation_a[axis]=channels.bones[i].translation_b[axis]=value
                ref.ram[BLOCK:BLOCK+len(block)]=block
                ref.ram[INSTANCE:INSTANCE+32]=bytes(32)
                ref.write(INSTANCE,'I',NODE);ref.write(INSTANCE+4,'I',BLOCK)
                for i,parent in enumerate(parents):
                    at=NODE+i*0x110;ref.ram[at:at+0x110]=bytes(0x110)
                    ref.ram[at+0x80:at+0xd0]=bytes(channels.bones[i])
                    ref.write(at+0x103,'B',0 if parent>=0 else 128)
                    ref.write(at+0x104,'I',NODE+(i+1)*0x110 if i<18 else 0)
                    ref.write(at+0x108,'I',NODE+parent*0x110 if parent>=0 else 0)
                    ref.write(at+0x10c,'I',NODE+pairs[i]*0x110 if pairs[i]>=0 else 0)
                selected=[]
                ref.run(0x1113cc0,[INSTANCE,BLOCK],initial_float_registers={12:struct.unpack('<I',struct.pack('<f',phase))[0]},
                        math_model=math_class(ref),full_quadwords=True,max_instructions=20000,instruction_observer=observe)
                if len(selected)!=1:raise AssertionError('source interval selection')
                channels.clamped_time=struct.unpack('<f',struct.pack('<I',selected[0][0]))[0]
                channels.interval_index=selected[0][1]
                for i in range(19):C.memmove(C.byref(channels.bones[i]),bytes(ref.ram[NODE+i*0x110+0x80:NODE+i*0x110+0xd0]),80)
                ref.run(0x1115130,[INSTANCE],math_model=math_class(ref),full_quadwords=True,max_instructions=40000,instruction_observer=observe)
                local=b''.join(ref.ram[NODE+i*0x110+0x50:NODE+i*0x110+0x60]+ref.ram[NODE+i*0x110+0x40:NODE+i*0x110+0x50]for i in range(19))
                ref.run(0x1115ea0,[INSTANCE],math_model=math_class(ref),full_quadwords=True,max_instructions=40000,instruction_observer=observe)
                rig=read_rig(ref.ram,skeleton(ref.ram,INSTANCE))
                expected=bytes(channels)+local+bytes(rig)
                actual=Frame()
                if lib.bank_sample(bank,clip,phase,C.byref(actual))!=1:raise AssertionError(('sample',clip,phase))
                if bytes(actual)!=expected:
                    a,e=struct.unpack('<1376I',bytes(actual)),struct.unpack('<1376I',expected)
                    diff=[(i,hex(x),hex(y))for i,(x,y)in enumerate(zip(a,e))if x!=y]
                    raise AssertionError((clip,phase,diff[:16]))
                cases.append({'clip':clip,'phase':phase,'frame_sha256':digest(expected)})
            print('verified runtime clip',clip,flush=True)
        samples=0
        for entry in catalogue['entries']:
            for phase in (0,entry['duration_original_units']*.431,entry['duration_original_units']):
                out=Frame()
                if lib.bank_sample(bank,entry['clip'],phase,C.byref(out))!=1:raise AssertionError(('domain',entry['clip'],phase))
                samples+=1
        # Re-run the v0.14's sealed original decoder/evaluator fixtures against
        # the exact production sources compiled with the production flags.
        fixtures=json.loads(gzip.decompress((args.core/'tests/animation_pose_vectors.json.gz').read_bytes()))
        fixture_checks=0
        for clip,t,initial,expected,pose in fixtures['cases']:
            entry=catalogue['entries'][clip];block=data[entry['bundle_offset']:entry['bundle_offset']+entry['block_bytes']]
            b=(C.c_ubyte*len(block)).from_buffer_copy(block)
            channels=Channels.from_buffer_copy(bytes.fromhex(fixtures['initials'][initial]));out=Pose()
            if lib.pes_animation_channels_decode(b,len(b),t,C.byref(channels))!=1 or bytes(channels).hex()!=expected:
                raise AssertionError(('sealed decode fixture',clip,t))
            if lib.pes_animation_pose_evaluate(C.byref(channels),C.byref(out))!=1 or bytes(out).hex()!=pose:
                raise AssertionError(('sealed local fixture',clip,t))
            fixture_checks+=1
        for initial,expected in fixtures['captured_channels_pose']:
            channels=Channels.from_buffer_copy(bytes.fromhex(initial));out=Pose()
            if lib.pes_animation_pose_evaluate(C.byref(channels),C.byref(out))!=1 or bytes(out).hex()!=expected:
                raise AssertionError('sealed captured fixture')
            fixture_checks+=1
    finally:lib.bank_destroy(bank)
    report={'schema_version':1,'result':'passed','run_id':str(uuid.uuid4()),'completed_at_utc':datetime.now(timezone.utc).isoformat(),
            'state_sha256':state.metadata['sha256'],'bundle_sha256':catalogue['sha256'],'original_sources':image.sources,
            'fresh_original_pipeline_cases':len(cases),'compared_words_per_case':1376,'original_instructions':instructions,
            'distinct_reached_instruction_words':len(words),'all_clip_domain_samples':samples,
            'sealed_decoder_local_pose_cases':fixture_checks,'arithmetic_profile':'nearest FPU/VU; nearest division/sqrt',
            'compile_command':command,'native_gameplay_replaced':False,
            'scope':'Source-format clip decode -> local interpolation -> 19-node hierarchy/materialization under the selected instruction model. Explicit canonical initialized channels and no mirror/blend. Not a resumed PES frame or exact PS2 hardware. Native mesh, action selection, cadence, transitions and ball contacts remain outside this path.'}
    report['production_sources_sha256']={str(p.relative_to(root)):digest(p.read_bytes())for p in sorted((root/'src/pes3').glob('*'))if p.is_file()}
    (args.output/'runtime-pose-vectors.json').write_text(json.dumps(cases,indent=2)+'\n')
    (args.output/'runtime-pose-instructions.json').write_text(json.dumps({hex(k):v for k,v in sorted(words.items())})+'\n')
    (args.output/'runtime-pose-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    p=argparse.ArgumentParser(description='Conferir o sampler PES3 integrado ao jogo')
    for name in ('bundle','state','elf','over','core','output'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();report=verify(args)
    print(json.dumps({k:report[k]for k in('result','fresh_original_pipeline_cases','all_clip_domain_samples','sealed_decoder_local_pose_cases','original_instructions')},indent=2))
if __name__=='__main__':main()
