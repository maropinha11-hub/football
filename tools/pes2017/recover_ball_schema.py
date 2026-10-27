#!/usr/bin/env python3
"""Describe observed ball-parameter stores in the supplied, pinned PES 2017 build.

This is schema evidence, not a gameplay implementation or a physics-constant dump.
The original binary is an external input and is never copied into this project.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from inspect_executable import PortableExecutable

EXECUTABLE_SHA256 = '6598860f6cce192e7a7017bad451aa62fc01d9c3c76806eeebafc0691fe22a26'
RESOURCE = 'cpk_dat/common/match/constant/match/ball.json'
READER = 0x4084d64
READER_END = 0x40854f8
FACTORY = 0x4085972
CONSTRUCTOR = 0x4084b24
BINARY_READER = 0x4085502
BINARY_READER_END = 0x4085963


def instructions(objdump, executable, start=READER, end=READER_END):
    result = subprocess.run([objdump, '-D', '-M', 'intel', '--no-show-raw-insn',
                             '--start-address=' + hex(start), '--stop-address=' + hex(end),
                             str(executable)], text=True, capture_output=True, check=True)
    rows = []
    for line in result.stdout.splitlines():
        match = re.match(r'^\s*([0-9a-f]+):\s+([a-z][a-z0-9]*)\s*(.*?)\s*$', line)
        if match:
            rows.append((int(match[1], 16), match[2], match[3]))
    if not rows or rows[0][0] != start:
        raise ValueError('objdump did not decode the expected function entry')
    return rows


def describe_reader(pe, rows):
    keys = []
    for i, (address, opcode, operand) in enumerate(rows):
        match = re.fullmatch(r'0x([0-9a-f]+)', operand) if opcode == 'push' else None
        if match:
            value = int(match[1], 16)
            try:
                name = pe.string(value - pe.image_base)
            except ValueError:
                continue
            if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,95}', name):
                keys.append((i, address, value, name))
    fields = []
    for n, (index, address, key_va, name) in enumerate(keys):
        end = keys[n + 1][0] if n + 1 < len(keys) else len(rows)
        block = rows[index:end]
        stores = []
        array_store = any(opcode == 'fstp' and operand == 'DWORD PTR [eax]' for _, opcode, operand in block)
        if array_store:
            starts = []
            for pc, opcode, operand in rows[max(0, index - 8):index]:
                match = re.fullmatch(r'(?:eax|ecx|edx),\[edi\+0x([0-9a-f]+)\]', operand)
                if opcode == 'lea' and match:
                    starts.append((pc, int(match[1], 16)))
            counts = [int(match[1], 16) for _, opcode, operand in block
                      if opcode == 'cmp' and (match := re.fullmatch(r'ebx,0x([0-9a-f]+)', operand))]
            stride = any(opcode == 'add' and operand == 'eax,0x4' for _, opcode, operand in block)
            if starts and len(counts) == 1 and stride and 1 <= counts[0] <= 64:
                stores.append(dict(instruction_va=starts[-1][0], offset=starts[-1][1], bytes=counts[0] * 4,
                                   storage='float32_array', elements=counts[0]))
        fields.append(dict(name=name, name_va=key_va, name_file_offset=pe.offset(key_va - pe.image_base),
                           key_push_va=address, stores=stores, complete_for_this_key=len(stores) == 1))
    # Integer/byte returns may be stored AFTER the next key is pushed. Track
    # return-value ownership through that scheduling rather than attributing
    # every write to the most recently mentioned key.
    by_push = {f['key_push_va']: f for f in fields}
    current = floating = integer = None
    for pc, opcode, operand in rows:
        if pc in by_push:
            current = by_push[pc]
        if opcode == 'call':
            target = operand.split()[0]
            if target == '0x2b5bdb1':
                floating = current
            integer = current if target in ('0x2b5bc19', '0x2b5c092') else None
        match = re.fullmatch(r'(DWORD|WORD|BYTE) PTR \[edi\+0x([0-9a-f]+)\](?:,(eax|ax|al))?', operand)
        if match and opcode in ('fstp', 'mov'):
            owner = floating if opcode == 'fstp' else integer
            if owner is not None:
                owner['stores'].append(dict(instruction_va=pc, offset=int(match[2], 16),
                    bytes={'DWORD': 4, 'WORD': 2, 'BYTE': 1}[match[1]],
                    storage='float32' if opcode == 'fstp' else 'raw_integer_store'))
            if opcode == 'fstp':
                floating = None
        elif opcode == 'fstp':
            floating = None
    for field in fields:
        field['complete_for_this_key'] = len(field['stores']) == 1
    return fields


def binary_layout(rows, fields):
    registers = {}
    pushed = array = floating = None
    stores = {}
    source = r'(DWORD|BYTE) PTR \[(edi|eax)(?:\+0x([0-9a-f]+))?\]'
    destination = r'(DWORD|BYTE) PTR \[esi\+0x([0-9a-f]+)\]'
    for pc, opcode, operand in rows:
        if opcode == 'mov':
            match = re.fullmatch(r'(eax|ecx|edx|cl|dl),' + source, operand)
            if match and match[3] == 'edi':
                registers[match[1]] = dict(kind='scalar', offset=int(match[4] or '0', 16), bytes=4 if match[2] == 'DWORD' else 1)
        if opcode == 'push' and operand in registers:
            pushed = registers[operand]
        if opcode == 'call' and operand.split()[0] == '0x40859a8':
            array = pushed
        if opcode == 'fld':
            match = re.fullmatch(source, operand)
            if match:
                offset = int(match[3] or '0', 16)
                floating = (dict(kind='scalar', offset=offset, bytes=4) if match[2] == 'edi' else
                            dict(kind='relative_array', offset_field=array['offset'], element_offset=offset, bytes=4) if array else None)
        if opcode == 'fstp':
            match = re.fullmatch(destination, operand)
            if match and floating:
                stores[int(match[2], 16)] = dict(floating, instruction_va=pc)
            floating = None
        if opcode == 'mov':
            match = re.fullmatch(destination + r',(eax|ecx|edx|cl|dl)', operand)
            if match and match[3] in registers:
                stores[int(match[2], 16)] = dict(registers[match[3]], instruction_va=pc)
    for field in fields:
        if not field['complete_for_this_key']:
            continue
        store = field['stores'][0]
        if store['storage'] == 'float32_array':
            sources = [stores.get(store['offset'] + i * 4) for i in range(store['elements'])]
            if all(s and s['kind'] == 'relative_array' and s['element_offset'] == i * 4 for i, s in enumerate(sources)) and len({s['offset_field'] for s in sources}) == 1:
                field['binary_source'] = dict(kind='relative_float32_array', offset_field=sources[0]['offset_field'], elements=store['elements'])
        elif store['offset'] in stores:
            value = stores[store['offset']]
            if value['kind'] == 'scalar' and value['bytes'] == store['bytes']:
                field['binary_source'] = dict(kind='float32' if store['storage'] == 'float32' else 'raw_integer', offset=value['offset'], bytes=value['bytes'])
    return fields


def recover(executable, objdump):
    data = Path(executable).read_bytes()
    if hashlib.sha256(data).hexdigest() != EXECUTABLE_SHA256:
        raise ValueError('executable differs from the audited build; addresses must not be reused')
    pe = PortableExecutable(data)
    pattern = RESOURCE.encode('ascii') + b'\0'
    position = data.find(pattern)
    if position < 0 or data.find(pattern, position + 1) >= 0:
        raise ValueError('ball resource path not unique')
    fields = binary_layout(instructions(objdump, executable, BINARY_READER, BINARY_READER_END),
                           describe_reader(pe, instructions(objdump, executable)))
    region = pe.offset(READER - pe.image_base, READER_END - READER)
    return dict(schema_version=1, kind='pinned_static_ball_reader_schema', executable_sha256=EXECUTABLE_SHA256,
                resource=RESOURCE, resource_file_offset=position,
                resource_va=pe.image_base + pe.rva_at_file(position),
                reader_va=READER, factory_va=FACTORY, constructor_va=CONSTRUCTOR,
                binary_reader_va=BINARY_READER, binary_reader_end_va=BINARY_READER_END,
                reader_bytes_sha256=hashlib.sha256(data[region:region + READER_END - READER]).hexdigest(),
                observed_allocation_bytes=0x1b4, fields=fields,
                decoded_keys=len(fields), keys_with_one_store=sum(f['complete_for_this_key'] for f in fields),
                keys_with_binary_source=sum('binary_source' in f for f in fields),
                numeric_parameter_values_recovered=False, parameter_units_verified=False, runtime_load_verified=False,
                scope='Observed key names and destination stores in one static reader only. Factory/allocation and zero-initializing constructor were separately inspected. Runtime data, units, ball equations and gameplay are not recovered.',
                limitations=['Address profile is specific to the pinned executable.',
                             'Names do not establish physical units or numerical values.',
                             'Array counts are read-loop bounds, not a claim about their semantic axes.',
                             'Unrecognized destination expressions remain explicitly incomplete.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('--objdump', default=shutil.which('objdump') or shutil.which('x86_64-w64-mingw32-objdump'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.objdump:
        parser.error('GNU objdump with PE/i386 support is required')
    result = recover(args.executable, args.objdump)
    with args.output.open('x', encoding='utf-8') as target:
        json.dump(result, target, indent=2)
        target.write('\n')
    print(json.dumps(dict(result='schema_described', keys=result['decoded_keys'], mapped=result['keys_with_one_store'], values_recovered=False)))


if __name__ == '__main__':
    main()
