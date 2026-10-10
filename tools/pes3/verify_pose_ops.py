#!/usr/bin/env python3
"""Compare memory-independent semantic C++ pose helpers to original instructions."""
import ctypes as C
import json
import struct
import subprocess
from pathlib import Path

from savestate import digest

SOURCE = '''#include "pose_ops.hpp"
extern "C" int pose_op(unsigned op,const float* a,const float* b,float alpha,float* out) {
  if(!a || !b || !out) return 0;
  try {
    pes3_pose::Vector x{},y{};
    std::memcpy(x.data(),a,16); std::memcpy(y.data(),b,16);
    if(op==1) { const auto m=pes3_pose::matrix(x); std::memcpy(out,m.data(),64); }
    else {
      const auto v=op==0 ? pes3_pose::multiply(x,y) : op==2 ? pes3_pose::rotate(x,y) :
        op==3 ? pes3_pose::blend(x,y,alpha) : throw std::domain_error("unknown helper");
      std::memcpy(out,v.data(),16);
    }
    return 1;
  } catch(const std::exception&) { return 0; }
}
'''


def verify(state, actors, reference, math_class, image, output):
    output.mkdir(parents=True, exist_ok=False)
    header = Path(__file__).with_name('recovered') / 'pose_ops.hpp'
    (output / header.name).write_bytes(header.read_bytes())
    (output / 'pose_ops.cpp').write_text(SOURCE)
    library = output / 'libpose_ops.so'
    command = ['g++', '-std=c++17', '-O0', '-Wall', '-Wextra', '-Werror', '-fno-fast-math',
               '-ffp-contract=off', '-shared', '-fPIC', str(output / 'pose_ops.cpp'), '-o', str(library)]
    subprocess.run(command, check=True)
    native = C.CDLL(str(library.resolve()))
    native.pose_op.argtypes = [C.c_uint, C.POINTER(C.c_float), C.POINTER(C.c_float), C.c_float, C.POINTER(C.c_float)]
    native.pose_op.restype = C.c_int
    ref = reference(state.ram, state.scratch)
    a_at, b_at, out_at = 0x01fc7000, 0x01fc7010, 0x01fc7040
    fixtures, words, instructions = [], {}, 0
    def case(operation, source, a, b, alpha=0):
        nonlocal instructions
        ref.ram[a_at:a_at + 16], ref.ram[b_at:b_at + 16] = a, b
        ref.ram[out_at:out_at + 64] = bytes(64)
        entry = (0x010d3060, 0x010d2f00, 0x010d2ff0, 0x010d29b0)[operation]
        params = [out_at, a_at] if operation == 1 else [out_at, a_at, b_at]
        f32 = struct.unpack('<I', struct.pack('<f', alpha))[0]
        def observe(pc, word, registers, floats):
            nonlocal instructions
            if image.read(pc) != struct.pack('<I', word): raise ValueError('helper original alterado')
            words[pc] = word; instructions += 1
        ref.run(entry, params, math_model=math_class(ref), max_instructions=2000,
                initial_float_registers={12: f32}, instruction_observer=observe, full_quadwords=True)
        size = 64 if operation == 1 else 16
        expected = bytes(ref.ram[out_at:out_at + size])
        left, right = (C.c_float * 4).from_buffer_copy(a), (C.c_float * 4).from_buffer_copy(b)
        result = (C.c_float * 16)()
        if native.pose_op(operation, left, right, alpha, result) != 1 or bytes(result)[:size] != expected:
            actual = bytes(result)[:size]
            delta = [(i, hex(x), hex(y)) for i, (x, y) in enumerate(zip(struct.unpack('<' + 'I' * (size//4), actual),
                                                                                    struct.unpack('<' + 'I' * (size//4), expected))) if x != y]
            raise AssertionError(f'{source}: semantic pose mismatch {delta[:8]}')
        fixtures.append({'operation': operation, 'source': source,
                         'a_bits': list(struct.unpack('<4I', a)), 'b_bits': list(struct.unpack('<4I', b)),
                         'alpha_bits': f32, 'expected_bits': list(struct.unpack('<' + 'I' * (size//4), expected))})
    for actor in actors:
        for buffer, spec in enumerate(actor['buffers']):
            for index, at in enumerate(spec['nodes']):
                local = state.ram[at + 0x50:at + 0x60]
                parent = spec['parents'][index]
                parent_at = spec['nodes'][parent] if parent >= 0 else at
                composed = state.ram[parent_at + 0x60:parent_at + 0x70]
                translation = state.ram[at + 0x40:at + 0x50]
                ident = f"actor-{actor['id']}-buffer-{buffer}-bone-{index}"
                case(0, ident, composed, local)
                case(1, ident, local, translation)
                case(2, ident, composed, translation)
        for index in range(19):
            first, second = (s['nodes'][index] for s in actor['buffers'])
            a, b = state.ram[first + 0x50:first + 0x60], state.ram[second + 0x50:second + 0x60]
            for alpha in (0, .1, .25, .5, .75, .9, 1):
                case(3, f"actor-{actor['id']}-bone-{index}-alpha-{alpha}", a, b, alpha)
    fixture_file = output / 'pose-ops-vectors.json'
    fixture_file.write_text(json.dumps({'schema_version': 1, 'state_sha256': state.metadata['sha256'],
        'scope': 'Original helper calls with captured numeric operands relocated in EE RAM; selected host arithmetic, not PS2 hardware.',
        'cases': fixtures}, separators=(',', ':')) + '\n')
    report = {'result': 'passed', 'comparisons': len(fixtures), 'original_instructions': instructions,
        'instruction_words': len(words), 'by_operation': {name: sum(r['operation'] == i for r in fixtures)
            for i, name in enumerate(('quaternion_multiply', 'quaternion_matrix', 'quaternion_rotate', 'shortest_arc_nlerp'))},
        'fixture_sha256': digest(fixture_file.read_bytes()), 'compile_command': command,
        'files_sha256': {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir())},
        'scope': 'Memory-independent semantic C++ pose helpers; unchanged original helper bodies run first. No reference output substitution, mesh retargeting, contact or whole frame equivalence.'}
    (output / 'pose-ops-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
