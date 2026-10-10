#!/usr/bin/env python3
"""Trace and verify reached PES pose assembly paths on the supplied training RAM.

Inputs are explicit function calls, not resuming the PCSX2 CPU. Captured fields
and host-model outputs are kept distinct. No native oracle feeds the reference.
"""
import argparse
import ctypes as C
import json
import math
import struct
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from actions import Image
from lift import generate
from replay import PLAYER_BASE, PLAYER_STRIDE, compare_native, inventory, observe_case
from savestate import SaveState, digest

REFERENCE_HASHES = {
    'mips_integer_reference.py': '2ff253c2fddb8eae6081b80786e9a13502da24e086ce0c88dfb01b50aa77c906',
    'float_vector_model.py': '3ae41e793c4ea6cfd17fba870f3e504f2601632d6a3bd568480dd9c8c317a0eb',
    'pose_math_model.py': 'a5bfdba5d75f60ca10b20dd4eb7491c2d5897a82033cde9afdab03601383dc56',
    'scratch_field_model.py': '199846d8bf4cfe31e4bfb3cab61873830abd139334206b9e640371a5298341cc',
}


def word(ram, address):
    if address & 3 or not 0 <= address <= len(ram) - 4:
        raise ValueError('ponteiro desalinhado ou fora da memória EE')
    return struct.unpack_from('<I', ram, address)[0]


def skeleton(ram, instance):
    root = word(ram, instance)
    nodes, pointer = [], root
    while pointer:
        if pointer in nodes or len(nodes) >= 19 or pointer + 0x110 > len(ram):
            raise ValueError('cadeia de ossos inválida')
        nodes.append(pointer)
        pointer = word(ram, pointer + 0x104)
    if len(nodes) != 19:
        raise ValueError('este port exige 19 ossos')
    indices = {at: i for i, at in enumerate(nodes)}
    def index(at):
        if at == 0:
            return -1
        if at not in indices:
            raise ValueError('relação de osso fora da cadeia')
        return indices[at]
    parents = [index(word(ram, at + 0x108)) for at in nodes]
    pairs = [index(word(ram, at + 0x10c)) for at in nodes]
    if parents[0] != -1 or any(p < 0 or p >= i for i, p in enumerate(parents[1:], 1)):
        raise ValueError('hierarquia não topológica')
    if any(p >= 0 and (p == i or pairs[p] != i) for i, p in enumerate(pairs)):
        raise ValueError('par de espelhamento assimétrico')
    return {'instance': hex(instance), 'root': hex(root), 'nodes': nodes,
            'parents': parents, 'mirror_pairs': pairs}


def pose_fields(ram, spec):
    def words(offset, count):
        return [list(struct.unpack_from('<' + 'I' * count, ram, at + offset)) for at in spec['nodes']]
    # 0x40/50: local translation/rotation. 0x60/70: composed quaternion/point.
    # 0x00: 4x4 matrices. These are model fields, not calibrated pitch metres.
    fields = {'instance': spec['instance'],
        'instance_flags': list(ram[int(spec['instance'], 16) + 28:int(spec['instance'], 16) + 32]),
        'local_translation_bits': words(0x40, 4), 'local_rotation_bits': words(0x50, 4),
        'composed_rotation_bits': words(0x60, 4), 'composed_translation_bits': words(0x70, 4),
        'matrix_bits': words(0, 16), 'cached_rotation_bits': words(0xd0, 4)}
    if any(not math.isfinite(struct.unpack('<f', struct.pack('<I', b))[0])
           for key, values in fields.items() if key.endswith('_bits') for row in values for b in row):
        raise ValueError('pose não finita')
    return fields


def structures(state):
    ram = state.ram
    actors = []
    for ident in range(1, 23):
        player = PLAYER_BASE + ident * PLAYER_STRIDE
        obj = word(ram, player + 0xd0)
        model = word(ram, obj + 12)
        if ram[obj + 3] != 2 or ram[obj + 8] not in (0, 1):
            raise ValueError('layout de objeto fora do estado conferido')
        buffers = [skeleton(ram, word(ram, model + i * 8 + 4)) for i in range(2)]
        if any(word(ram, model + i * 8) != int(b['root'], 16) for i, b in enumerate(buffers)):
            raise ValueError('instância/esqueleto divergente')
        actors.append({'id': ident, 'player': hex(player), 'object': hex(obj),
                       'model': hex(model), 'selected_buffer': ram[obj + 8], 'buffers': buffers})
    parents, pairs = actors[0]['buffers'][0]['parents'], actors[0]['buffers'][0]['mirror_pairs']
    if any(b['parents'] != parents or b['mirror_pairs'] != pairs for a in actors for b in a['buffers']):
        raise ValueError('estruturas de esqueleto divergentes')
    return actors


def scenarios(actors, analysis, controlled):
    cases = []
    def call(entry, args, alpha=None):
        item = {'entry': hex(entry), 'args': args}
        if alpha is not None:
            item['float_inputs'] = {'12': struct.unpack('<I', struct.pack('<f', alpha))[0]}
        return item
    def add(name, ident, calls, edits=(), buffer=None):
        case = {'id': name, 'actor': ident, 'calls': calls, 'edits': list(edits),
                'input_kind': 'modified_snapshot' if edits else 'unmodified_snapshot'}
        if buffer is not None:
            case['buffer'] = buffer
        cases.append(case)
    for actor in actors:
        ident, player = actor['id'], int(actor['player'], 16)
        add(f'assemble-actor-{ident}', ident, [call(0x0113c8b0, [player])])
        for i, spec in enumerate(actor['buffers']):
            instance = int(spec['instance'], 16)
            add(f'cached-local-{ident}-{i}', ident, [call(0x01115130, [instance])], buffer=i)
            add(f'fresh-local-{ident}-{i}', ident, [call(0x01115130, [instance])],
                [{'address': hex(instance + 29), 'format': 'B', 'value': 0}], i)
            add(f'cached-mirror-local-{ident}-{i}', ident,
                [call(e, [instance]) for e in (0x01115130, 0x011156b0, 0x01115940)], buffer=i)
            add(f'rebuild-matrices-{ident}-{i}', ident, [call(0x01115ea0, [instance])],
                [{'address': hex(instance + 29), 'format': 'B', 'value': 1}], i)
    player = int(actors[controlled - 1]['player'], 16)
    for route in analysis['routing']['actions']['cases']:
        value = route['value']
        add(f'action-{value}-pose', controlled,
            [call(0x01880490, [player]), call(0x0113c8b0, [player])],
            [{'address': hex(player + 0xda), 'format': 'B', 'value': value},
             {'address': hex(player + 0xdc), 'format': 'H', 'value': 0}])
    for route in analysis['routing']['action1_substates']['cases']:
        value = route['value']
        add(f'substate-{value}-pose', controlled,
            [call(0x01876b50, [player]), call(0x0113c8b0, [player])],
            [{'address': hex(player + 0xdc), 'format': 'H', 'value': value}])
    for request in range(23):
        add(f'request-{request}-pose', controlled, [call(0x0184f5c0, [player, request, 0, 0]),
                                                  call(0x01880490, [player]), call(0x0113c8b0, [player])])
    for count in (1, 3):
        add(f'collective-{count}-pose', controlled,
            [call(0x01881220, []) for _ in range(count)] + [call(0x0113c8b0, [player])])
    first, second = [int(s['instance'], 16) for s in actors[controlled - 1]['buffers']]
    for alpha in (0, .1, .25, .5, .75, .9, 1):
        add(f'blend-weight-{alpha}', controlled, [call(0x01115520, [second, first, second], alpha),
                                                call(0x01115ea0, [second])], buffer=1)
    # The action/assembly helper leaves representations dirty. Complete the
    # original representation conversion before exposing composed points; do
    # not draw stale 0x70 caches as a newly assembled pose. Both object buffers
    # are finalized because transition helpers can change the selected buffer.
    for case in cases:
        for spec in actors[case['actor'] - 1]['buffers']:
            instance = int(spec['instance'], 16)
            if case['calls'][-1] != call(0x01115ea0, [instance]):
                case['calls'].append(call(0x01115ea0, [instance]))
    return cases


def reference_classes(folder):
    for name, expected in REFERENCE_HASHES.items():
        actual = digest((folder / name).read_bytes())
        if expected and actual != expected:
            raise ValueError('modelo de referência de outra revisão: ' + name)
    sys.path.insert(0, str(folder.resolve()))
    from scratch_field_model import ScratchReference, ScratchFloat
    from pose_reference import PoseReference
    class ScratchPose(PoseReference, ScratchFloat):
        def __init__(self, ref): self.ref = ref
    return ScratchReference, ScratchPose


def main():
    parser = argparse.ArgumentParser(description='Conferir montagem, cache, mistura e espelhamento de poses PES 3')
    for name in ('state', 'elf', 'over', 'analysis', 'core', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error('escolha uma pasta nova')
    state, image = SaveState(args.state), Image(args.elf, args.over)
    analysis = json.loads(args.analysis.read_text())
    if analysis['sources'] != image.sources: raise ValueError('análise de outra versão')
    observed = inventory(state, analysis, args.core)
    actors = structures(state)
    reference, math_class = reference_classes(args.core / 'reference')
    def capture(ref, case):
        actor = actors[case['actor'] - 1]
        return {'selected_buffer': case.get('buffer', ref.ram[int(actor['object'], 16) + 8]),
                'buffers': [pose_fields(ref.ram, spec) for spec in actor['buffers']]}
    args.output.mkdir(parents=True)
    words, rows = {}, []
    for case in scenarios(actors, analysis, observed['controlled_actor']):
        row = observe_case(state, case, reference, math_class, words, image, 300000, capture,
                           capture_each_return=case['id'].startswith('fresh-local-'))
        rows.append(row)
        print(f"original {row['status']} {row['id']}", flush=True)
    (args.output / 'instruction_words.json').write_text(json.dumps({hex(k): v for k, v in sorted(words.items())}) + '\n')
    lift = generate(words, args.output / 'native')
    library = args.output / 'native/libpes3_pose_lift.so'
    command = ['g++', '-std=c++17', '-O0', '-fno-fast-math', '-ffp-contract=off', '-shared', '-fPIC',
               str(args.output / 'native/lifted_program.cpp'), '-o', str(library)]
    subprocess.run(command, check=True)
    comparisons = compare_native(state, rows, library, 300000)
    (args.output / 'original_probes.json').write_text(json.dumps(rows, separators=(',', ':')) + '\n')
    # Independent semantic v0.14 local evaluator; never used by the original probe.
    sys.path.insert(0, str(args.core.resolve()))
    from verify_animation_pose import Channels, Pose, configure
    local_library = C.CDLL(str((args.core / 'build/libpes_core.so').resolve())); configure(local_library)
    fresh, captured_differences = [], []
    for actor in actors:
        for index, spec in enumerate(actor['buffers']):
            channels = b''.join(state.ram[at + 0x80:at + 0xd0] for at in spec['nodes'])
            source = Channels.from_buffer_copy(struct.pack('<4I', 0, 0, 19, 0) + channels)
            output = Pose()
            if local_library.pes_animation_pose_evaluate(C.byref(source), C.byref(output)) != 1:
                raise ValueError('canais capturados fora do domínio do avaliador local')
            row = next(r for r in rows if r['id'] == f"fresh-local-{actor['id']}-{index}")
            # Evaluate is checked at its own return boundary: subsequent
            # representation conversion can overwrite the root's fourth lane.
            actual = row['results'][0]['pose_output']['buffers'][index]
            packed = b''.join(struct.pack('<8I', *(q + t)) for q, t in zip(
                actual['local_rotation_bits'], actual['local_translation_bits']))
            if bytes(output) != packed: raise AssertionError('avaliador local diverge das instruções originais')
            fresh.append(row['id'])
            original = b''.join(state.ram[at + 0x50:at + 0x60] + state.ram[at + 0x40:at + 0x50] for at in spec['nodes'])
            native_floats, saved_floats = struct.unpack('<152f', bytes(output)), struct.unpack('<152f', original)
            captured_differences.append({'actor': actor['id'], 'buffer': index,
                'whole_pose_equal': bytes(output) == original,
                'max_absolute_delta': max(abs(a - b) for a, b in zip(native_floats, saved_floats))})
    evidence = {'schema_version': 1, 'state_sha256': state.metadata['sha256'],
        'parents': actors[0]['buffers'][0]['parents'], 'mirror_pairs': actors[0]['buffers'][0]['mirror_pairs'],
        'captured_actors': [{'actor': a['id'], 'selected_buffer': a['selected_buffer'],
                             'buffers': [pose_fields(state.ram, s) for s in a['buffers']]} for a in actors],
        'scenarios': [{k: r[k] for k in ('id', 'actor', 'input_kind', 'edits', 'status', 'output_actor')}
                      | {'function_calls': [{k: v[k] for k in ('entry', 'args', 'float_inputs') if k in v}
                                            for v in r['results']]}
                      | ({'pose_output': r['pose_output']} if 'pose_output' in r else {}) for r in rows],
        'scope': 'Captured pose fields and function-return host-model outputs. No resumed PCSX2 frame, pitch metre calibration, mesh, ball contact or native game integration.'}
    (args.output / 'pose-evidence.json').write_text(json.dumps(evidence, separators=(',', ':')) + '\n')
    from verify_pose_ops import verify
    semantic = verify(state, actors, reference, math_class, image, args.output / 'semantic')
    blocked = [r['id'] for r in rows if r['status'] != 'completed']
    report = {'schema_version': 1, 'run_id': str(uuid.uuid4()), 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
        'result': 'passed_with_blocked_paths' if blocked else 'passed', 'state': state.metadata,
        'sources': image.sources, 'analysis_sha256': digest(args.analysis.read_bytes()),
        'summary': {'scenarios': len(rows), 'completed_scenarios': len(rows) - len(blocked),
            'original_function_calls': sum(len(r['results']) for r in rows),
            'native_function_comparisons': comparisons, 'original_instructions': sum(v['instructions'] for r in rows for v in r['results']),
            'translated_instruction_words': len(words), 'fresh_local_semantic_comparisons': len(fresh),
            'semantic_pose_operation_comparisons': semantic['comparisons'],
            'captured_pose_matches': sum(d['whole_pose_equal'] for d in captured_differences), 'captured_pose_comparisons': len(captured_differences),
            'blocked_scenarios': blocked},
        'captured_pose_comparison': captured_differences, 'actors': actors, 'lift': lift,
        'semantic_pose_operations': semantic,
        'compile_command': command, 'reference_sha256': {n: digest((args.core / 'reference' / n).read_bytes()) for n in REFERENCE_HASHES},
        'local_semantic_library_sha256': digest((args.core / 'build/libpes_core.so').read_bytes()),
        'native_files_sha256': {p.name: digest(p.read_bytes()) for p in sorted((args.output / 'native').iterdir())},
        'tool_sha256': {n: digest(Path(__file__).with_name(n).read_bytes()) for n in
                       ('pose.py', 'pose_reference.py', 'verify_pose_ops.py', 'replay.py', 'lift.py', 'lift_runtime.hpp', 'savestate.py')},
        'pose_evidence_sha256': digest((args.output / 'pose-evidence.json').read_bytes()),
        'scope': evidence['scope'], 'scenarios': rows}
    (args.output / 'pose-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    if digest(args.state.read_bytes()) != state.metadata['sha256']: raise AssertionError('entrada foi alterada')
    print(json.dumps(report['summary'], indent=2))
    if blocked: raise SystemExit(1)


if __name__ == '__main__':
    main()
