#!/usr/bin/env python3
"""Package current, source-checked direction/dispatch/prediction/chain evidence."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

def digest(data): return hashlib.sha256(data).hexdigest()

def build(folders,output):
    tool=Path(__file__).resolve().parent;files={};runs=[];state_sha=None;sources=None
    for label,api,folder in folders:
        report_bytes=(folder/(api+'-validation.json')).read_bytes();report=json.loads(report_bytes)
        if report['result']!='passed':raise ValueError('reference did not pass')
        if state_sha is None:state_sha=report['state_sha256'];sources=report['sources']
        if state_sha!=report['state_sha256'] or sources!=report['sources']:raise ValueError('source revisions differ')
        for name,expected in report['tool_sha256'].items():
            if digest((tool/name).read_bytes())!=expected:raise ValueError('current reference tool differs: '+name)
        for name,expected in report['files_sha256'].items():
            path=folder/name
            if digest(path.read_bytes())!=expected:raise ValueError('verified file differs: '+str(path))
            if name.endswith('.hpp'):
                data=path.read_bytes()
                if data!=(tool/'recovered'/name).read_bytes():raise ValueError('current owned source differs: '+name)
                if name in files and files[name]!=data:raise ValueError('owned sources differ between runs')
                files[name]=data
        vectors=(folder/(api+'-vectors.json')).read_bytes()
        vector_name=label+'-vectors.json.gz';files[vector_name]=gzip.compress(vectors,mtime=0)
        files[label+'-validation.json']=report_bytes
        files[label+'-instruction-words.json']=(folder/(api+'-instruction-words.json')).read_bytes()
        runs.append({'label':label,'api':api,'run_id':report['run_id'],'vectors':vector_name,
            'vectors_sha256':digest(vectors),'fresh_comparisons':report.get('comparisons',report.get('prediction_comparisons')),
            'original_instructions':report['original_instructions']})
    for name in ('direction_abi.py','prediction_abi.py','selection_abi.py','special_abi.py','speed_abi.py',
            'variant_abi.py','chain_abi.py','verify_movement_vectors.py'):
        files[name]=(tool/name).read_bytes()
    files['LEIA-ME.txt']=('PES 3 - locomoção reescrita e conferida\n\n'
        'Pesquisa de direção, perseguição, seleção de clips, velocidade e execução\n'
        'consecutiva do segmento de locomoção. Este pacote não atualiza o jogo.\n'
        'Com Python 3 e g++, execute:\n'
        'python verify_movement_vectors.py . --output resultado.json\n\n'
        'O comando recompila C++14 e compara os vetores numéricos registrados.\n'
        'Os relatórios de referência incluem hashes, escopo e instruções alcançadas.\n'
        'Não inclui executável/ISO/RAM/save do PES; o replay offline não executa MIPS.\n'
        'Os casos modificam o único save recebido (parado com bola); não representam\n'
        'novas partidas observadas. Perfis aritméticos são modelos host declarados.\n'
        'Ainda faltam outros caminhos, ações completas, relógio/poses/contatos,\n'
        'calibração de unidades/retarget e integração funcional ao Football.\n').encode('utf-8')
    manifest={'schema_version':1,'kind':'pes3-consecutive-locomotion-research','state_sha256':state_sha,
        'sources':sources,'runs':runs,'runtime_enabled':False,'files_sha256':{n:digest(d) for n,d in sorted(files.items())}}
    files['manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as zipped:
        for name,data in sorted(files.items()):
            entry=zipfile.ZipInfo(name,date_time=(2026,10,11,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o644<<16
            zipped.writestr(entry,data)
    with zipfile.ZipFile(output) as zipped:
        if zipped.testzip():raise ValueError('invalid delivery CRC')
    return {'bytes':output.stat().st_size,'sha256':digest(output.read_bytes()),'members':len(files)}

def main():
    p=argparse.ArgumentParser()
    runs=[('direction','direction'),('selection','selection'),('speed','speed'),('prediction-nearest','prediction'),
        ('prediction-chop','prediction'),('special','special'),('variant-nearest','variant'),('variant-chop','variant'),
        ('chain-nearest','chain'),('chain-chop','chain')]
    for label,_ in runs:p.add_argument('--'+label,type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(build([(label,api,getattr(a,label.replace('-','_'))) for label,api in runs],a.output),indent=2))

if __name__=='__main__':main()
