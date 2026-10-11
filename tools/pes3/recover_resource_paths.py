#!/usr/bin/env python3
"""Recover AFS parent/index/count paths from the pinned 92 ELF descriptors."""
import argparse
import json
from pathlib import Path
import struct
from actions import Image
from savestate import digest

TARGETS = {0x00470000: 'body_lnk.bin', 0x00470001: 'mon_lnk.bin',
    0x00370000: 'anime2.bin', 0x00370001: 'anime3.bin', 0x00080000: 'anime.bin', 0x00080001: 'game.mbc'}

def recover(image):
    data = image.read(0x0129d440, 92 * 12)
    descriptors = {}
    for number in range(92):
        word, resource, count = struct.unpack_from('<3I', data, number * 12)
        group, parent = word & 65535, word >> 16
        if group != number or parent != resource >> 16 or count > 100000:
            raise ValueError('descriptor layout changed')
        descriptors[group] = (parent, resource & 65535, count)
    if descriptors[0] != (0, 0, 17): raise ValueError('unexpected root')
    paths = []
    for resource, name in TARGETS.items():
        bank, item = resource >> 16, resource & 65535
        if item >= descriptors[bank][2]: raise ValueError('item outside bank')
        path, counts, group = [item], [descriptors[bank][2]], bank
        visited = set()
        while group:
            if group in visited: raise ValueError('cyclic AFS parents')
            visited.add(group)
            parent, index, _ = descriptors[group]
            if index >= descriptors[parent][2]: raise ValueError('parent index out of range')
            path.insert(0, index); counts.insert(0, descriptors[parent][2]); group = parent
        paths.append({'resource_id': hex(resource), 'reported_name': name, 'indices': path, 'container_counts': counts})
    return {'schema_version': 1, 'sources': image.sources, 'descriptor_address': '0x0129d440',
        'descriptor_count': 92, 'descriptor_bytes': len(data), 'descriptor_sha256': digest(data), 'paths': paths,
        'scope': 'Paths/counts recovered from executable. Resource names are reported by supplied study; DATA E/F/G/I/S bytes have not been received or verified. Collector checks archive counts/ranges and preserves compressed bytes for independent validation.'}

def main():
    p = argparse.ArgumentParser()
    for n in ('elf', 'over', 'output'): p.add_argument('--' + n, type=Path, required=True)
    a = p.parse_args(); report = recover(Image(a.elf, a.over))
    with a.output.open('x') as out: out.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'paths': len(report['paths']), 'descriptor_sha256': report['descriptor_sha256']}))

if __name__ == '__main__': main()
