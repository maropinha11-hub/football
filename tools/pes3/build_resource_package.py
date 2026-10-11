#!/usr/bin/env python3
"""Package current owned bind/render sources and fresh original-call proofs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

def digest(data):return hashlib.sha256(data).hexdigest()

def build(folders,provenance,output):
    tool=Path(__file__).resolve().parent;files={};runs=[];state_sha=None;sources=None;collector_sha=None
    for label,api,folder in folders:
        prefix='model-bind'if api=='model-bind'else'render'
        report_bytes=(folder/(prefix+'-report.json')).read_bytes();report=json.loads(report_bytes)
        if report['result']!='passed':raise ValueError('original reference proof did not pass')
        if state_sha is None:state_sha=report['state_sha256'];sources=report['sources']
        if state_sha!=report['state_sha256']or sources!=report['sources']:raise ValueError('original input revisions differ')
        if api=='model-bind':
            if collector_sha is None:collector_sha=report['collector_zip_sha256']
            if collector_sha!=report['collector_zip_sha256']:raise ValueError('collector revisions differ')
        for name,expected in report['tool_sha256'].items():
            if digest((tool/name).read_bytes())!=expected:raise ValueError('current proof tool changed: '+name)
        for name,expected in report['files_sha256'].items():
            data=(folder/name).read_bytes()
            if digest(data)!=expected:raise ValueError('verified file changed: '+name)
            if name.endswith('.hpp'):
                if data!=(tool/'recovered'/name).read_bytes():raise ValueError('current portable source changed: '+name)
                if name in files and files[name]!=data:raise ValueError('sources differ between runs')
                files[name]=data
        source='model_bind.cpp'if api=='model-bind'else'render_pose.cpp'
        files[source]=(folder/source).read_bytes()
        vectors=(folder/(prefix+'-vectors.json')).read_bytes();vector_name=label+'-vectors.json.gz'
        files[vector_name]=gzip.compress(vectors,mtime=0)
        report_name=label+'-report.json';files[report_name]=report_bytes
        files[label+'-instructions.json']=(folder/(prefix+'-instructions.json')).read_bytes()
        comparisons=report.get('comparisons',report.get('matrix_comparisons',0)+report.get('position_comparisons',0))
        runs.append({'label':label,'api':api,'run_id':report['run_id'],'source':source,'report':report_name,
            'report_sha256':digest(report_bytes),'vectors':vector_name,'vectors_sha256':digest(vectors),
            'comparisons':comparisons,'original_instructions':report['original_instructions']})
    provenance_bytes=provenance.read_bytes();captured=json.loads(provenance_bytes)
    if (captured['result']!='passed'or captured['state_sha256']!=state_sha
            or captured['collector_zip_sha256']!=collector_sha
            or captured['tool_sha256']!=digest((tool/'verify_collected_provenance.py').read_bytes())):
        raise ValueError('captured-resource provenance is stale or incompatible')
    bind_reports={run['report_sha256']for run in runs if run['api']=='model-bind'}
    if {case['report_sha256']for case in captured['bind_inputs']}!=bind_reports:
        raise ValueError('captured bind provenance uses other original executions')
    files['collected-provenance.json']=provenance_bytes
    files['verify_resource_vectors.py']=(tool/'verify_resource_vectors.py').read_bytes()
    files['LEIA-ME.txt']=('PES 3 - recursos, inicializacao e ponte de desenho\n\n'
        'Pesquisa verificavel: este pacote nao atualiza o jogo Windows.\n'
        'Com Python 3 e g++, execute na pasta extraida:\n'
        'python verify_resource_vectors.py . --output resultado.json\n\n'
        'Recompila C++14 e compara vetores numericos contra saidas registradas\n'
        'de chamadas originais em modelos aritmeticos declarados. Nao executa\n'
        'novos quadros PS2 e nao representa gameplay completa.\n'
        'Nao inclui ISO, executavel completo, RAM/save, malhas ou clips PES.\n'
        'Conserva dados numericos de teste e palavras de instrucao alcancadas.\n'
        'collected-provenance.json compara arquivos originais recebidos com o\n'
        'save parado: 999 clips/perfis/registros, 44 buffers de referencia.\n'
        'Os 106 clips restantes nao estavam carregados no save.\n'
        'As translações de referencia e correcoes de espelhamento nao coincidem\n'
        'no mesmo perfil; nenhuma pose completa foi declarada equivalente.\n'
        'Ainda faltam adaptacao nativa, unidades/tempo, selecao completa,\n'
        'transicoes e contatos/colisoes ao longo de jogadas reais.\n').encode('utf-8')
    manifest={'schema_version':1,'kind':'pes3-source-bind-render-research','state_sha256':state_sha,
        'collector_zip_sha256':collector_sha,'sources':sources,'runs':runs,'runtime_enabled':False,
        'files_sha256':{name:digest(data)for name,data in sorted(files.items())}}
    files['manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9)as zipped:
        for name,data in sorted(files.items()):
            entry=zipfile.ZipInfo(name,date_time=(2026,10,11,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
            entry.external_attr=0o644<<16;zipped.writestr(entry,data)
    with zipfile.ZipFile(output)as zipped:
        if zipped.testzip():raise ValueError('package CRC failed')
    return {'bytes':output.stat().st_size,'members':len(files),'sha256':digest(output.read_bytes()),
        'comparisons':sum(run['comparisons']for run in runs)}

def main():
    p=argparse.ArgumentParser();runs=[('bind-nearest','model-bind'),('bind-chop','model-bind'),
        ('render-nearest','render'),('render-chop','render')]
    for label,_ in runs:p.add_argument('--'+label,type=Path,required=True)
    p.add_argument('--provenance',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(build([(label,api,getattr(a,label.replace('-','_')))for label,api in runs],a.provenance,a.output),indent=2))
if __name__=='__main__':main()
