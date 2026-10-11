#!/usr/bin/env python3
"""Recompile owned locomotion code and replay packaged, hashed numeric vectors.

Requires Python and g++, no PES executable, RAM, save, reference model or ISO.
Does not replace fresh original-instruction execution or test native gameplay.
"""
import argparse
import ctypes as C
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import direction_abi as direction
import prediction_abi as prediction
import selection_abi as selection
import special_abi as special
import speed_abi as speed
import variant_abi as variant
import chain_abi as chain

def digest(data): return hashlib.sha256(data).hexdigest()

def verify(folder, output):
    folder=folder.resolve();manifest=json.loads((folder/'manifest.json').read_text())
    if manifest.get('kind')!='pes3-consecutive-locomotion-research' or manifest.get('runtime_enabled') is not False:
        raise ValueError('unexpected package')
    for name,expected in manifest['files_sha256'].items():
        path=folder/name
        if path.resolve().parent != folder or digest(path.read_bytes())!=expected: raise ValueError('package file differs: '+name)
    apis=(direction,prediction,selection,special,speed,variant,chain)
    for abi in apis:
        if Path(abi.__file__).read_bytes() != (folder/Path(abi.__file__).name).read_bytes():
            raise ValueError('loaded ABI differs from package')
    counts={};
    with tempfile.TemporaryDirectory(prefix='pes3-movement-replay-') as temp:
        root=Path(temp);(root/'motion.cpp').write_text(''.join(abi.SOURCE for abi in apis))
        command=['g++','-std=c++14','-O0','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off',
            '-shared','-fPIC','-I',str(folder),str(root/'motion.cpp'),'-o',str(root/'motion.so')]
        subprocess.run(command,check=True,capture_output=True)
        library=C.CDLL(str(root/'motion.so'))
        for abi in apis: abi.configure(library)
        for run in manifest['runs']:
            kind=run['api'];raw=gzip.decompress((folder/run['vectors']).read_bytes())
            if digest(raw)!=run['vectors_sha256']: raise ValueError('vectors differ')
            vectors=json.loads(raw)
            if vectors['state_sha256']!=manifest['state_sha256']: raise ValueError('state differs')
            count=0
            abi={'direction':direction,'prediction':prediction,'selection':selection,'special':special,
                'speed':speed,'variant':variant,'chain':chain}[kind]
            function={'direction':'select_direction','prediction':'predict_chase','selection':'select_locomotion',
                'special':'select_special','speed':'step_speed','variant':'select_variant','chain':'step_locomotion'}[kind]
            for case in vectors['cases']:
                i=abi.Input.from_buffer_copy(bytes.fromhex(case['input_hex']))
                if kind=='speed':
                    if library.step_speed(C.byref(i))!=case['expected']: raise AssertionError(case['id'])
                else:
                    result=abi.Decision()
                    if kind=='prediction':
                        sample_bytes=bytes.fromhex(case['samples_hex'])
                        if len(sample_bytes)%C.sizeof(prediction.Sample): raise ValueError('sample size')
                        samples=(prediction.Sample*(len(sample_bytes)//C.sizeof(prediction.Sample))).from_buffer_copy(sample_bytes)
                        status=library.predict_chase(C.byref(i),samples,len(samples),C.byref(result))
                    else: status=getattr(library,function)(C.byref(i),C.byref(result))
                    if status!=1 or bytes(result).hex()!=case['expected_hex']: raise AssertionError(case['id'])
                count+=1
                if 'speed_input_hex' in case:
                    speed_input=speed.Input.from_buffer_copy(bytes.fromhex(case['speed_input_hex']))
                    decision=result if kind=='selection' else result.decision
                    speed_input.current_amplitude=decision.amplitude_before_speed
                    speed_input.selected_amplitude=decision.selected_amplitude
                    if library.step_speed(C.byref(speed_input))!=case['expected_speed']: raise AssertionError('composed speed '+case['id'])
                    count+=1
            for case in vectors.get('gate_cases',[]):
                i=prediction.GateInput.from_buffer_copy(bytes.fromhex(case['input_hex']));out=C.c_uint8()
                if library.chase_gate(C.byref(i),C.byref(out))!=1 or out.value!=case['expected']: raise AssertionError(case['id'])
                count+=1
            counts[run['label']]=count
    report={'schema_version':1,'result':'passed','comparisons':sum(counts.values()),'by_run':counts,
        'state_sha256':manifest['state_sha256'],'runtime_enabled':False,
        'scope':'Offline replay of hashed recorded numeric fixtures against recompiled owned C++14. No original PES instructions are executed here; fresh reference reports are included separately. No native runtime, full-frame, PS2 hardware or gameplay parity assertion.'}
    with output.open('x') as stream: stream.write(json.dumps(report,indent=2)+'\n')
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(verify(a.folder,a.output),indent=2))

if __name__=='__main__':main()
