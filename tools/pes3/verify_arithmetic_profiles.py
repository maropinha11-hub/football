#!/usr/bin/env python3
"""Check isolated rounding policies with selected synthetic instructions."""
import argparse
import json
import math
from pathlib import Path
import struct
import sys

from arithmetic import classes, chop, nearest
from pose import reference_classes
from savestate import digest

PROFILES = (('nearest', 'nearest', 'nearest', 'nearest'), ('nearest', 'chop', 'nearest', 'nearest'),
            ('chop', 'nearest', 'chop', 'chop'), ('chop', 'chop', 'chop', 'chop'),
            ('chop', 'chop', 'nearest', 'nearest'))


def verify(folder):
    bits = lambda x: struct.unpack('<I', struct.pack('<f', x))[0]
    value = lambda x: struct.unpack('<f', struct.pack('<I', x))[0]
    word = lambda fn: (17 << 26) | (16 << 21) | (13 << 16) | (12 << 11) | (14 << 6) | fn
    reference_classes(folder)
    public = sys.modules['float_vector_model']
    old_round, old_vector = public.rounded, public.vector_value
    instances, rows = [], []
    for fpu, vu, division, square_root in PROFILES:
        _, model = classes(folder, fpu, vu, division, square_root)
        m = model(None); m.reset([0] * 32)
        m.f[12], m.f[13] = bits(10366), 0x38000100
        m.cop1(0, word(2), [0] * 32)
        if m.f[14] != bits((chop if fpu == 'chop' else nearest)(10366 * value(0x38000100))):
            raise AssertionError('FPU multiply profile differs')
        m.f[12], m.f[13] = bits(1), bits(10)
        m.cop1(0, word(3), [0] * 32)
        if m.f[14] != bits((chop if division == 'chop' else nearest)(.1)):
            raise AssertionError('FPU division policy differs')
        m.f[12] = bits(5)
        m.cop1(0, (17 << 26) | (16 << 21) | (12 << 16) | (12 << 11) | (14 << 6) | 4, [0] * 32)
        if m.f[14] != bits((chop if square_root == 'chop' else nearest)(math.sqrt(5))):
            raise AssertionError('FPU sqrt policy differs')
        m.f[12] = bits(-1.75); m.cop1(0, word(0x24), [0] * 32)
        if m.f[14] != 0xffffffff: raise AssertionError('conversion instruction decoded as division/sqrt')
        m.vf[12], m.vf[13] = [10366.] * 4, [value(0x38000100)] * 4
        m.cop2(0, (18 << 26) | (31 << 21) | (13 << 16) | (12 << 11) | (14 << 6) | 42, [0] * 32)
        if [bits(x) for x in m.vf[14]] != [bits((chop if vu == 'chop' else nearest)(10366 * value(0x38000100)))] * 4:
            raise AssertionError('VU multiply profile differs')
        instances.append(m)
        rows.append({'profile': dict(zip(('fpu', 'vu', 'division', 'sqrt'), (fpu, vu, division, square_root))), 'checks': 5})
    if public.rounded is not old_round or public.vector_value is not old_vector:
        raise AssertionError('public reference was modified')
    for m, (fpu, _, _, _) in zip(instances, PROFILES):
        m.f[12], m.f[13] = bits(10366), 0x38000100
        m.cop1(0, word(2), [0] * 32)
        if m.f[14] != bits((chop if fpu == 'chop' else nearest)(10366 * value(0x38000100))):
            raise AssertionError('profile instance affected by later imports')
    return {'result': 'passed', 'profiles': rows, 'checks': 30, 'public_reference_unchanged': True,
            'instances_remain_independent': True,
            'tool_sha256': {name: digest(Path(__file__).with_name(name).read_bytes())
                            for name in ('verify_arithmetic_profiles.py', 'arithmetic.py', 'pose_reference.py')},
            'scope': 'Selected synthetic instructions verify profile separation, division/sqrt policy and conversion opcode width. No original game frame or hardware claim.'}


def main():
    parser = argparse.ArgumentParser(description='Conferir separação dos perfis aritméticos')
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.core / 'reference')
    with args.output.open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
