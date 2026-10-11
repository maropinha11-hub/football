#!/usr/bin/env python3
"""Verify memory-independent 19-node rig operations against original routines.

Original calls use copies of the supplied state and pinned instruction words.
Semantic code receives owned numeric structures and indices. No native result
is injected into the reference and no PS2 addresses enter the semantic API.
"""
import argparse
import base64
from collections import Counter
import ctypes as C
import json
import struct
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from actions import Image
from pose import reference_classes, structures
from savestate import SaveState, digest

class Bone(C.Structure):
    _fields_ = [('parent', C.c_int32), ('mirror', C.c_int32), ('mirror_policy', C.c_uint32),
        ('processed', C.c_uint32)] + [(name, C.c_uint32 * count) for name, count in
        [('local_translation', 4), ('local_rotation', 4), ('composed_rotation', 4),
         ('composed_translation', 4), ('matrix', 16), ('cached_rotation', 4), ('mirror_correction', 4)]]

class Rig(C.Structure):
    _fields_ = [('flags', C.c_uint32 * 4), ('bones', Bone * 19)]

assert C.sizeof(Bone) == 176 and C.sizeof(Rig) == 3360
OFFSETS = {'local_translation': 0x40, 'local_rotation': 0x50, 'composed_rotation': 0x60,
           'composed_translation': 0x70, 'matrix': 0, 'cached_rotation': 0xd0, 'mirror_correction': 0xe0}
ENTRIES = (0x01116060, 0x011157e0, 0x01115940, 0x01115c60, 0x01115c20, 0x011156b0, 0x01115ea0, 0x01115520)
NAMES = ('compose_matrices', 'ensure_composed', 'ensure_local', 'mirror_raw', 'apply_mirror', 'mirror_gate', 'materialize', 'mix')
SOURCE = '''#include "pose_rig.hpp"
static_assert(sizeof(pes3_pose::Bone)==176 && sizeof(pes3_pose::Rig)==3360,"rig ABI mismatch");
extern "C" int rig_op(unsigned op,pes3_pose::Rig* rigs,unsigned d,unsigned a,unsigned b,float alpha,int all) {
  if(!rigs || d>=3 || a>=3 || b>=3 || (all!=0 && all!=1)) return 0;
  try {
    std::array<pes3_pose::Rig,3> work{}; std::memcpy(work.data(),rigs,sizeof(work));
    for(const auto& r:work) pes3_pose::validate(r);
    auto& r=work[d];
    switch(op) {
      case 0: pes3_pose::compose_matrices(r); break;
      case 1: pes3_pose::ensure_composed(r); break;
      case 2: pes3_pose::ensure_local(r); break;
      case 3: pes3_pose::mirror_raw(r); break;
      case 4: pes3_pose::apply_mirror(r); break;
      case 5: pes3_pose::mirror_gate(r); break;
      case 6: pes3_pose::materialize(r); break;
      case 7: pes3_pose::mix(r,work[a],work[b],alpha,bool(all)); break;
      default: return 0;
    }
    for(const auto& v:work) pes3_pose::validate(v);
    std::memcpy(rigs,work.data(),sizeof(work)); return 1;
  } catch(const std::exception&) { return 0; }
}
'''

def read_rig(ram, spec):
    out = Rig()
    instance = int(spec['instance'], 16)
    out.flags[:] = ram[instance + 28:instance + 32]
    for i, at in enumerate(spec['nodes']):
        bone = out.bones[i]
        bone.parent, bone.mirror = spec['parents'][i], spec['mirror_pairs'][i]
        bone.mirror_policy, bone.processed = ram[at + 0x101:at + 0x103]
        for name, offset in OFFSETS.items():
            target = getattr(bone, name)
            target[:] = struct.unpack_from('<' + 'I' * len(target), ram, at + offset)
    return out


def verify(state, image, core, output):
    output.mkdir(parents=True, exist_ok=False)
    actors = structures(state)
    specs = [b for a in actors for b in a['buffers']]
    reference, math_class = reference_classes(core / 'reference')
    for address, numbers in ((0x01269b10, (0., 1., 0., 0.)), (0x01269b20, (-1., -1., 1., 1.)),
                             (0x01269b30, (1., 1., -1., 1.))):
        expected = struct.pack('<4f', *numbers)
        if state.ram[address:address + 16] != expected or image.read(address, 16) != expected:
            raise ValueError('mirror constants differ from pinned ELF')
    lookup = state.ram[0x01269ae0:0x01269af0]
    if image.read(0x01269ae0, 16) != lookup: raise ValueError('motion class lookup changed')
    classes = {bool(all_trans): next(i for i, v in enumerate(lookup) if bool(v) == bool(all_trans)) for all_trans in (0, 1)}
    for name in ('pose_ops.hpp', 'pose_rig.hpp'):
        (output / name).write_bytes((Path(__file__).with_name('recovered') / name).read_bytes())
    (output / 'pose_rig.cpp').write_text(SOURCE)
    library = output / 'libpose_rig.so'
    command = ['g++', '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror', '-fno-fast-math', '-ffp-contract=off',
               '-shared', '-fPIC', str(output / 'pose_rig.cpp'), '-o', str(library)]
    subprocess.run(command, check=True)
    native = C.CDLL(str(library.resolve()))
    native.rig_op.argtypes = [C.c_uint, C.POINTER(Rig), C.c_uint, C.c_uint, C.c_uint, C.c_float, C.c_int]
    native.rig_op.restype = C.c_int
    fixtures, words, instructions = [], {}, 0
    def case(name, op, indices, destination=0, alpha=0, flags=None, gates=None, synthetic_type=None):
        nonlocal instructions
        ref = reference(state.ram, state.scratch)
        chosen = [specs[i] for i in indices]
        if len({s['instance'] for s in chosen}) != 3: raise ValueError('test requires three distinct instances')
        edits = []
        for i, spec in enumerate(chosen):
            inst = int(spec['instance'], 16)
            for offset, value in ((29, None if flags is None else flags[i]), (30, None if gates is None else gates[i])):
                if value is not None:
                    ref.ram[inst + offset] = value
                    edits.append({'address': hex(inst + offset), 'format': 'B', 'value': value})
        if synthetic_type is not None:
            for i in (1, 2):
                # A complete function executes the real lookup. No stubbed return.
                address, inst = 0x01fc5000 + i * 16, int(chosen[i]['instance'], 16)
                descriptor = classes[bool(synthetic_type)] << 28
                ref.write(address + 4, 'I', descriptor)
                ref.write(inst + 4, 'I', address)
                edits += [{'address': hex(address + 4), 'format': 'I', 'value': descriptor},
                          {'address': hex(inst + 4), 'format': 'I', 'value': address}]
        all_trans = False
        if op == 7:
            for spec in chosen[1:]:
                motion = ref.read(int(spec['instance'], 16) + 4, 'I')
                all_trans |= bool(lookup[ref.read(motion + 4, 'I') >> 28])
        before = b''.join(bytes(read_rig(ref.ram, s)) for s in chosen)
        params = [int(chosen[destination]['instance'], 16)]
        if op == 3: params = [int(chosen[destination]['root'], 16)]
        if op == 7: params += [int(chosen[i]['instance'], 16) for i in (1, 2)]
        def observe(pc, word, registers, floats):
            nonlocal instructions
            if image.read(pc) != struct.pack('<I', word): raise ValueError('original code word changed')
            if pc in words and words[pc] != word: raise ValueError('nonunique original code word')
            words[pc] = word; instructions += 1
        alpha_bits = struct.unpack('<I', struct.pack('<f', alpha))[0]
        ref.run(ENTRIES[op], params, math_model=math_class(ref), max_instructions=150000,
                initial_float_registers={12: alpha_bits}, instruction_observer=observe, full_quadwords=True)
        expected = b''.join(bytes(read_rig(ref.ram, s)) for s in chosen)
        work = (Rig * 3).from_buffer_copy(before)
        result = native.rig_op(op, work, destination, 1, 2, alpha, all_trans)
        actual = bytes(work)
        if result != 1 or actual != expected:
            diffs = [(i, hex(a), hex(b)) for i, (a, b) in enumerate(zip(struct.unpack('<2520I', actual), struct.unpack('<2520I', expected))) if a != b]
            raise AssertionError(f'{name}: semantic rig mismatch status={result} first_words={diffs[:12]}')
        fixtures.append({'id': name, 'operation': op, 'rig_indices': indices, 'destination': destination,
            'source_a': 1, 'source_b': 2, 'alpha_bits': alpha_bits, 'translate_all': all_trans,
            'memory_kind': 'modified_snapshot' if edits else 'captured_snapshot', 'edits': edits,
            'input_base64': base64.b64encode(before).decode(), 'expected_base64': base64.b64encode(expected).decode(),
            'instructions': ref.instructions})
    for index in range(44):
        other = index ^ 1
        next_actor = (index + 2) % 44
        indices = [index, other, next_actor]
        for op in range(5):
            flags = [1, None, None] if op in (1, 4) else [2, None, None] if op == 2 else None
            case(f'rig-{index}-{NAMES[op]}', op, indices, flags=flags)
        for op in (1, 2, 4):
            case(f'rig-{index}-{NAMES[op]}-from-matrix', op, indices, flags=[4, None, None])
        for flags in (1, 0x41, 9, 0x49):
            for gate in (0, 1):
                case(f'rig-{index}-gate-flags-{flags}-gate-{gate}', 5, indices,
                     flags=[flags, None, None], gates=[gate, None, None])
        for flags in (1, 2, 4, 7, 0x41):
            case(f'rig-{index}-materialize-flags-{flags}', 6, indices, flags=[flags, None, None])
        if index % 2 == 0: print(f'original rig {index//2+1}/22 verified', flush=True)
    for actor in range(22):
        indices = [(actor * 2 + 2) % 44, actor * 2, actor * 2 + 1]
        for alpha in (0, .1, .25, .5, .75, .9, 1):
            for destination in range(3):
                case(f'mix-actor-{actor+1}-alpha-{alpha}-destination-{destination}', 7, indices, destination, alpha)
    for all_trans in (False, True):
        for alpha in (0, .1, .25, .5, .75, .9, 1):
            for destination in range(3):
                case(f'mix-type-{all_trans}-alpha-{alpha}-destination-{destination}', 7, [20, 18, 19], destination, alpha,
                     flags=[1, 1, 1], synthetic_type=all_trans)
    fixture_path = output / 'rig-vectors.json'
    fixture_path.write_text(json.dumps({'schema_version': 1, 'state_sha256': state.metadata['sha256'],
        'abi': {'rig_bytes': C.sizeof(Rig), 'bone_bytes': C.sizeof(Bone), 'endianness': 'little', 'rigs_per_case': 3},
        'scope': 'Owned numeric rig inputs and outputs; original function calls on state copies in selected host arithmetic.',
        'cases': fixtures}, separators=(',', ':')) + '\n')
    (output / 'rig-instruction-words.json').write_text(json.dumps({hex(k): v for k, v in sorted(words.items())}) + '\n')
    report = {'schema_version': 1, 'run_id': str(uuid.uuid4()), 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
        'result': 'passed', 'state_sha256': state.metadata['sha256'], 'sources': image.sources,
        'comparisons': len(fixtures), 'original_instructions': instructions, 'instruction_words': len(words),
        'by_operation': dict(Counter(NAMES[f['operation']] for f in fixtures)),
        'by_memory_kind': dict(Counter(f['memory_kind'] for f in fixtures)),
        'full_translation_cases': sum(f['operation'] == 7 and f['translate_all'] for f in fixtures),
        'root_only_translation_cases': sum(f['operation'] == 7 and not f['translate_all'] for f in fixtures),
        'compile_command': command, 'reference_sha256': {p.name: digest(p.read_bytes()) for p in (core / 'reference').glob('*.py') if p.name in __import__('pose').REFERENCE_HASHES},
        'tool_sha256': {n: digest(Path(__file__).with_name(n).read_bytes()) for n in ('rig.py', 'pose.py', 'pose_reference.py', 'savestate.py')},
        'files_sha256': {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir())},
        'scope': 'Eight semantic rig operations on 19-node numeric structures, including matrix-to-quaternion branches. Captured and deliberately modified inputs, destination/source aliasing, exact bit comparisons with original routines in the declared host model. Clip-decode fallback requires an external evaluator and rejects here; no resumed PS2 frame, ball contacts, retargeting or native gameplay integration.'}
    (output / 'rig-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description='Reescrever e conferir composição/espelhamento do rig PES')
    for name in ('state', 'elf', 'over', 'core', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error('choose a fresh output directory')
    state = SaveState(args.state)
    report = verify(state, Image(args.elf, args.over), args.core, args.output)
    if digest(args.state.read_bytes()) != state.metadata['sha256']: raise AssertionError('state input changed')
    print(json.dumps({k: report[k] for k in ('result', 'comparisons', 'original_instructions', 'by_operation')}, indent=2))

if __name__ == '__main__': main()
