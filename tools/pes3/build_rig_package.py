#!/usr/bin/env python3
"""Package verified semantic rig code and numeric evidence, without game files."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build(rig, channels, profiles, output):
    if output.exists(): raise ValueError('choose a new output file')
    tool = Path(__file__).resolve().parent
    report = json.loads((rig / 'rig-validation.json').read_text())
    if report['result'] != 'passed': raise ValueError('rig validation did not pass')
    files = {}
    for name in ('pose_ops.hpp', 'pose_rig.hpp', 'pose_rig.cpp', 'rig-vectors.json', 'rig-instruction-words.json'):
        data = (rig / name).read_bytes()
        if digest(data) != report['files_sha256'][name]: raise ValueError('rig file differs: ' + name)
        if name.endswith('.hpp') and data != (tool / 'recovered' / name).read_bytes():
            raise ValueError('verified semantic header is not current: ' + name)
        files['rig-vectors.json.gz' if name == 'rig-vectors.json' else name] = gzip.compress(data, mtime=0) if name == 'rig-vectors.json' else data
    files['rig-validation.json'] = (rig / 'rig-validation.json').read_bytes()
    provenance = json.loads(channels.read_text())
    if provenance['result'] != 'all_rotation_channels_matched' or provenance['state_sha256'] != report['state_sha256']:
        raise ValueError('channel provenance not complete or from another state')
    for name, expected in provenance['tool_sha256'].items():
        if digest((tool / name).read_bytes()) != expected: raise ValueError('channel tool differs: ' + name)
    files['channel-provenance.json'] = channels.read_bytes()
    profile_summary = []
    seen = set()
    for path in profiles:
        probe = json.loads(path.read_text())
        if probe['result'] != 'investigated_equivalence_open' or probe['state_sha256'] != report['state_sha256'] or probe['sources'] != report['sources']:
            raise ValueError('profile report is not the same investigation')
        for name, expected in probe['tool_sha256'].items():
            if digest((tool / name).read_bytes()) != expected: raise ValueError('profile tool differs: ' + name)
        profile = probe['arithmetic_profile']
        key = tuple(profile[n] for n in ('fpu', 'vu', 'division', 'square_root'))
        if key in seen: raise ValueError('duplicate arithmetic profile')
        seen.add(key)
        name = 'profiles/' + '-'.join(key) + '.json'
        files[name] = path.read_bytes()
        profile_summary.append({'file': name, 'sha256': digest(files[name]), 'run_id': probe['run_id'],
                                'arithmetic_profile': profile, 'summary': probe['summary']})
    for name in ('verify_rig_vectors.py', 'arithmetic.py', 'channel_provenance.py', 'pose_differences.py', 'rig.py'):
        files[name if name == 'verify_rig_vectors.py' else 'research-tools/' + name] = (tool / name).read_bytes()
    instructions = (
        'PES 3 — reescrita do rig e investigação numérica\n\n'
        'Este pacote contém código C++ e evidência numérica. Não é uma atualização do jogo Windows.\n'
        'Abra os relatórios JSON ou leia o código. Não precisa reinstalar o Windows.\n\n'
        'Com Python 3 e g++ disponíveis, repita as 1.428 comparações em qualquer pasta:\n'
        'python verify_rig_vectors.py . --output resultado-local.json\n\n'
        'Esse comando recompila o código e compara todos os bits com as saídas originais registradas\n'
        'no modelo declarado. Não precisa da ISO, do save, de RAM ou de executáveis PES.\n'
        'As ferramentas de pesquisa em research-tools requerem o repositório e os arquivos de entrada\n'
        'para novas execuções das rotinas originais. As chaves duplicadas permaneceriam ambíguas;\n'
        'neste estado, as 88 séries A/B possuem correspondências únicas nos clips carregados.\n\n'
        'O rig recebe 19 ossos numéricos, índices de pais/pares, representações e flags próprias.\n'
        'Os 1.428 testes verificam o modelo host binary32 anterior, não todo o PS2.\n'
        'Os cinco perfis de arredondamento são experimentos separados contra os campos capturados.\n'
        'Diferenças em bits continuam registradas. Campos locais podem estar desatualizados após\n'
        'espelhamento; recompor esse local indevidamente modifica os pontos finais.\n'
        'Eixos, referência de ossos, escala, seleção completa e contatos para o jogador nativo\n'
        'precisam ser validados antes da integração. Nenhuma aproximação foi declarada equivalência.\n'
    )
    files['LEIA-ME.txt'] = instructions.encode('utf-8')
    manifest = {'schema_version': 1, 'kind': 'pes3-semantic-rig-research',
        'state_sha256': report['state_sha256'], 'rig_run_id': report['run_id'],
        'rig_comparisons': report['comparisons'], 'channel_summary': provenance['summary'],
        'arithmetic_profiles': profile_summary, 'runtime_enabled': False,
        'files_sha256': {name: digest(data) for name, data in sorted(files.items())},
        'scope': 'Numeric semantic rig and original-call evidence in declared models. Original-call profiles remain numerically different from captured complete poses. No proprietary executables, save, memory image, ISO, mesh, fresh PS2 frame or native gameplay integration.'}
    files['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 10, 11, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None: raise ValueError('bad delivery CRC')
        members = len(archive.namelist())
    return {'bytes': output.stat().st_size, 'sha256': digest(output.read_bytes()), 'members': members, 'manifest': manifest}


def main():
    parser = argparse.ArgumentParser(description='Empacotar a reescrita conferida do rig PES')
    for name in ('rig', 'channels', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--profiles', type=Path, nargs='+', required=True)
    args = parser.parse_args()
    result = build(args.rig, args.channels, args.profiles, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != 'manifest'}, indent=2))


if __name__ == '__main__': main()
