#!/usr/bin/env python3
"""Package verified owned locomotion code, fixtures and native contract."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import zipfile


def digest(data): return hashlib.sha256(data).hexdigest()


def build(selection, speed, bridge_path, output):
    if output.exists(): raise ValueError('choose a new output file')
    tool = Path(__file__).resolve().parent
    reports, files = {}, {}
    for kind, folder in (('selection', selection), ('speed', speed)):
        report = json.loads((folder / f'{kind}-validation.json').read_text())
        if report['result'] != 'passed': raise ValueError('reference did not pass: ' + kind)
        for name, expected in report['tool_sha256'].items():
            if digest((tool / name).read_bytes()) != expected: raise ValueError('verified tool differs: ' + name)
        names = ('locomotion_selection.hpp', 'locomotion_speed.hpp', 'selector.cpp') if kind == 'selection' else ('locomotion_speed.hpp', 'speed.cpp')
        for name in names + (f'{kind}-vectors.json', f'{kind}-instruction-words.json'):
            data = (folder / name).read_bytes()
            if digest(data) != report['files_sha256'][name]: raise ValueError('verified file differs: ' + name)
            if name.endswith('.hpp') and data != (tool / 'recovered' / name).read_bytes():
                raise ValueError('current semantic source differs: ' + name)
            if name in files and files[name] != data: raise ValueError('source revisions differ')
            files[name + '.gz' if name.endswith('-vectors.json') else name] = gzip.compress(data, mtime=0) if name.endswith('-vectors.json') else data
        files[f'{kind}-validation.json'] = (folder / f'{kind}-validation.json').read_bytes()
        reports[kind] = report
    if reports['selection']['state_sha256'] != reports['speed']['state_sha256'] or reports['selection']['sources'] != reports['speed']['sources']:
        raise ValueError('original inputs differ')
    bridge = json.loads(bridge_path.read_text())
    if bridge['selection_run_id'] != reports['selection']['run_id'] or bridge['selection_report_sha256'] != digest(files['selection-validation.json']):
        raise ValueError('bridge from another run')
    if bridge['runtime_enabled'] is not False: raise ValueError('unexpected enabled import')
    for name, expected in bridge['tool_sha256'].items():
        if digest((tool / name).read_bytes()) != expected: raise ValueError('bridge tool differs: ' + name)
    repo = tool.parents[1]
    for source in bridge['native_sources']:
        if digest((repo / source['path']).read_bytes()) != source['sha256']: raise ValueError('native source differs')
    for animation in bridge['native_catalogue']['animations']:
        if digest((repo / 'data/media/animations' / animation['path']).read_bytes()) != animation['sha256']:
            raise ValueError('native animation differs')
    files['selection-bridge.json'] = bridge_path.read_bytes()
    for name in ('selection_abi.py', 'speed_abi.py', 'verify_locomotion_vectors.py'):
        files[name] = (tool / name).read_bytes()
    for name in ('verify_selection.py', 'verify_speed.py', 'selection_bridge.py'):
        files['research-tools/' + name] = (tool / name).read_bytes()
    readme = (
        'PES 3 — seleção de locomoção e ajuste de velocidade\n\n'
        'Código C++ reescrito e conferido contra instruções dos arquivos fornecidos.\n'
        'Este pacote é de pesquisa e desenvolvimento; não é um novo executável Windows.\n\n'
        'Foram conferidos 92 cenários de escolha de clip + velocidade em sequência e\n'
        '1.153 cenários independentes de velocidade. Não é a gameplay completa.\n'
        'selection-bridge.json associa automaticamente os clips às condições recuperadas\n'
        'e reúne o catálogo de 293 arquivos do Football e seus requisitos de seleção.\n'
        'Ele distingue pedidos/ações PES dos tipos nativos; nomes de gestos não foram adivinhados.\n\n'
        'Para recompilar e repetir as comparações registradas, com Python 3 e g++:\n'
        'python verify_locomotion_vectors.py . --output resultado-local.json\n\n'
        'Não precisa da ISO, de RAM, do save ou dos binários do PES para esse comando.\n'
        'As ferramentas de research-tools exigem o repositório, os arquivos de entrada e\n'
        'o pacote v0.14 para uma nova execução das instruções originais.\n'
        'Predição/perseguição/reinício ainda fornecem valores explícitos ao seletor.\n'
        'Velocidade zero nessa rotina conserva a amplitude atual. As unidades por chamada\n'
        'não foram convertidas para metros/segundo ou para o passo de 10 ms do nosso jogo.\n'
        'A seleção final exige predição, apoio, alcance, contato, transições e ossos calibrados.\n'
        'O save foi informado pelo usuário como jogador parado com bola; os demais\n'
        'cenários modificam cópias da memória, sem representar novas jogadas capturadas.\n'
        'A comparação usa o modelo declarado; não retoma um quadro completo no PS2/PCSX2.\n'
    )
    files['LEIA-ME.txt'] = readme.encode('utf-8')
    manifest = {'schema_version': 1, 'kind': 'pes3-semantic-locomotion-research',
        'state_sha256': reports['selection']['state_sha256'],
        'selection_run_id': reports['selection']['run_id'], 'speed_run_id': reports['speed']['run_id'],
        'selection_comparisons': reports['selection']['comparisons'],
        'composed_speed_comparisons': reports['selection']['composed_speed_comparisons'],
        'speed_comparisons': reports['speed']['comparisons'], 'runtime_enabled': False,
        'files_sha256': {name: digest(data) for name, data in sorted(files.items())},
        'scope': 'Owned common locomotion selector and integer speed tail, recorded original-instruction evidence, automatic condition index and native source contract. No proprietary executable/save/RAM, complete action/gameplay, calibrated import, final native selector or Windows gameplay update.'}
    files['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 10, 11, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED; entry.external_attr = 0o644 << 16
            archive.writestr(entry, data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None: raise ValueError('bad delivery CRC')
        members = len(archive.namelist())
    return {'bytes': output.stat().st_size, 'sha256': digest(output.read_bytes()), 'members': members}


def main():
    parser = argparse.ArgumentParser(description='Empacotar seletor e velocidade PES conferidos')
    for name in ('selection', 'speed', 'bridge', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.selection, args.speed, args.bridge, args.output), indent=2))


if __name__ == '__main__': main()
