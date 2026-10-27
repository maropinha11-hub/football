#!/usr/bin/env python3
"""Decode an explicitly located serialized ball object; no archive/offset guessing."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

from recover_ball_schema import EXECUTABLE_SHA256


def decode(data, schema, base):
    if schema.get('executable_sha256') != EXECUTABLE_SHA256 or not isinstance(base, int) or base < 0:
        raise ValueError('wrong schema revision or negative explicit object offset')
    def read(offset, fmt):
        width = struct.calcsize('<' + fmt)
        if offset < 0 or base + offset + width > len(data):
            raise ValueError('serialized value outside supplied resource')
        value = struct.unpack_from('<' + fmt, data, base + offset)[0]
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('non-finite serialized parameter')
        return value
    values = {}
    for field in schema['fields']:
        source = field.get('binary_source')
        if not source or field['name'] in values:
            raise ValueError('missing source mapping or duplicate field')
        if source['kind'] == 'relative_float32_array':
            count = source['elements']
            if not isinstance(count, int) or not 1 <= count <= 64:
                raise ValueError('unbounded array')
            relative = read(source['offset_field'], 'I')
            if relative == 0:
                raise ValueError('null relative array pointer')
            value = [read(relative + i * 4, 'f') for i in range(count)]
        elif source['kind'] == 'float32':
            value = read(source['offset'], 'f')
        elif source['kind'] == 'raw_integer' and source['bytes'] in (1, 2, 4):
            value = read(source['offset'], {1: 'B', 2: 'H', 4: 'I'}[source['bytes']])
        else:
            raise ValueError('unknown serialized storage')
        values[field['name']] = value
    return dict(schema_version=1, kind='decoded_explicit_ball_object', executable_schema_sha256=EXECUTABLE_SHA256,
                resource_sha256=hashlib.sha256(data).hexdigest(), explicit_object_offset=base,
                values=values, units_verified=False, active_runtime_values_verified=False,
                scope='Values at an explicitly selected serialized object offset. Correct object identification, archive provenance, physical units and live loading must be separately verified. Not installed in Football.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resource', type=Path)
    parser.add_argument('--schema', type=Path, required=True)
    parser.add_argument('--offset', type=lambda value: int(value, 0), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    schema_data = args.schema.read_bytes()
    result = decode(args.resource.read_bytes(), json.loads(schema_data), args.offset)
    result['schema_file_sha256'] = hashlib.sha256(schema_data).hexdigest()
    with args.output.open('x', encoding='utf-8') as target:
        json.dump(result, target, indent=2, allow_nan=False)
        target.write('\n')
    print(json.dumps(dict(result='decoded_at_supplied_offset', fields=len(result['values']), units_verified=False)))


if __name__ == '__main__':
    main()
