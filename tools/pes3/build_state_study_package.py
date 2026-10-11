#!/usr/bin/env python3
"""Package event evidence and reached C++ paths, without saves or PES binaries."""
import argparse
import gzip
import json
from pathlib import Path
import zipfile

from savestate import digest


def build(study, events, output, index=None):
    if output.exists():
        raise FileExistsError('choose a new output path')
    state_report = json.loads((study / 'state-study.json').read_text())
    event_report = json.loads((events / 'event-report.json').read_text())
    if state_report['result'] != 'passed' or event_report['result'] != 'passed':
        raise ValueError('incomplete state/event verification')
    hashes = [s['sha256'] for s in state_report['states']]
    if hashes != event_report['state_hashes'] or len(set(hashes)) != len(hashes):
        raise ValueError('state/event inputs differ or duplicate')
    if state_report['sources'] != event_report['sources']:
        raise ValueError('different PES revision in state/event proofs')
    for folder, report in ((study, state_report), (events, event_report)):
        for name, expected in report['files_sha256'].items():
            from verify_event_vectors import safe_member
            safe_member(name)
            if digest((folder / name).read_bytes()) != expected:
                raise ValueError('changed verified input: ' + name)
    files = {}
    if index is not None:
        raw = index.read_bytes()
        association = json.loads(raw)
        if (association['state_report_sha256'] != digest((study / 'state-study.json').read_bytes())
                or association['event_report_sha256'] != digest((events / 'event-report.json').read_bytes())
                or association['state_hashes'] != hashes or association['runtime_enabled']):
            raise ValueError('event index belongs to different proof inputs')
        files['animation-event-index.json.gz'] = gzip.compress(raw, mtime=0)
    for name in ('animation_events.hpp', 'ball_anchor_741.hpp', 'bind_arithmetic.hpp',
                 'pose_rig.hpp', 'pose_ops.hpp', 'animation_events.cpp', 'event-report.json', 'event-instructions.json'):
        files[name] = (events / name).read_bytes()
    files['event-vectors.json.gz'] = gzip.compress((events / 'event-vectors.json').read_bytes(), mtime=0)
    files['state-study.json.gz'] = gzip.compress((study / 'state-study.json').read_bytes(), mtime=0)
    files['state-instructions.json.gz'] = gzip.compress((study / 'instruction-words.json').read_bytes(), mtime=0)
    for path in (study / 'native').iterdir():
        if path.suffix in ('.cpp', '.hpp'):
            files['recompiled/' + path.name] = path.read_bytes()
    for name in ('verify_event_vectors.py', 'event_abi.py', 'savestate.py'):
        files[name] = Path(__file__).with_name(name).read_bytes()
    files['LEIA-ME.txt'] = (
        'PES 3: dez estados de treino, caminhos recompilados e regras temporais\n\n'
        'Este pacote documenta pesquisa e provas numéricas. Não atualiza o jogo Windows.\n'
        'Não contém ISO, saves, executáveis ou meshes originais.\n'
        '35 chamadas originais alcançadas passaram na recompilação C++, comparando RAM,\n'
        'scratchpad, registradores e caminho de instruções. Não são quadros PS2 completos.\n'
        'animation_events.hpp reproduz 0116AFE0; ball_anchor_741.hpp conserva a escolha\n'
        'dependente do contexto, que não pode ser reduzida a um track estático.\n'
        'Os slots são capturas independentes. Não implicam frames consecutivos.\n\n'
        'Para repetir a prova dos módulos próprios: com Python 3 e g++ disponíveis,\n'
        'python verify_event_vectors.py .\n'
        'A prova offline recompila C++14 e usa saídas gravadas; não executa o PES.\n'
    ).encode('utf-8')
    manifest = {'schema_version': 1, 'kind': 'pes3-training-states-events-research',
                'state_hashes': hashes, 'sources': state_report['sources'],
                'state_summary': state_report['summary'],
                'phase_gate_comparisons': event_report['comparisons'],
                'anchor_741_comparisons': event_report['anchor_741_comparisons'],
                'runtime_enabled': False, 'files_sha256': {n: digest(b) for n, b in files.items()}}
    files['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted(files.items()):
            member = zipfile.ZipInfo(name, date_time=(2026, 10, 11, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o644 << 16
            archive.writestr(member, payload)
    return {'bytes': output.stat().st_size, 'members': len(files), 'sha256': digest(output.read_bytes())}


def main():
    parser = argparse.ArgumentParser(description='Empacotar estudo e provas dos dez saves de treino')
    for name in ('study', 'events', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--index', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.study, args.events, args.output, args.index), indent=2))


if __name__ == '__main__':
    main()
