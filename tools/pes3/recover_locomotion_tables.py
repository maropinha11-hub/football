#!/usr/bin/env python3
"""Recover the quantized locomotion tables from pinned original bytes."""
import argparse
import json
from pathlib import Path
import struct
from actions import Image
from savestate import SaveState, digest

TABLES = [('angles', 0x0129d890, 257, 'h', 'std::int16_t'),
          ('projections', 0x018eb950, 512, 'h', 'std::int16_t'),
          ('input_headings', 0x018e56d0, 16, 'H', 'std::uint16_t')]


def recover(image, state=None):
    lines = ['#pragma once', '// Quantized tables recovered from pinned SLES_519.12 and game.ovl bytes.',
             '#include <cstdint>', 'namespace pes3_motion {']
    evidence = []
    for name, address, count, kind, declaration in TABLES:
        raw = image.read(address, count * 2)
        if state is not None and state.ram[address:address + len(raw)] != raw:
            raise ValueError('loaded table differs: ' + name)
        values = struct.unpack('<' + kind * count, raw)
        lines.append(f'// {hex(address)}; SHA-256 {digest(raw)}')
        lines.append(f'static constexpr {declaration} {name}[{count}] = {{')
        for start in range(0, count, 16): lines.append('  ' + ', '.join(map(str, values[start:start + 16])) + ',')
        lines.append('};')
        evidence.append({'name': name, 'address': hex(address), 'count': count, 'sha256': digest(raw),
                         'loaded_ram_matched': state is not None})
    lines.append('} // namespace pes3_motion')
    return '\n'.join(lines) + '\n', {'schema_version': 1, 'sources': image.sources, 'tables': evidence,
        'state_sha256': state.metadata['sha256'] if state else None}


def main():
    parser = argparse.ArgumentParser(description='Recuperar tabelas de locomoção PES sem aproximação trigonométrica')
    for name in ('elf', 'over', 'output'): parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--state', type=Path); parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    text, report = recover(Image(args.elf, args.over), SaveState(args.state) if args.state else None)
    with args.output.open('x') as stream: stream.write(text)
    report['header_sha256'] = digest(args.output.read_bytes())
    with args.report.open('x') as stream: json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
