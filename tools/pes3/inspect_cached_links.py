#!/usr/bin/env python3
"""Check whether the save retains complete initialized link resources.

Header-size matches in freed memory are candidates only. Never exports a
corrupted stream or promotes an animated model to an initialization pose.
"""
import argparse
import json
from pathlib import Path
import struct
from actions import Image, GP, _inspector
from savestate import SaveState, digest

LINKS = [('body_lnk.bin', 0x00470000, 0x011801f0, -26340, 1315982),
    ('mon_lnk.bin', 0x00470001, 0x011a2cd0, -26036, 678945)]

def inspect(state, image):
    report = {'schema_version': 1, 'state_sha256': state.metadata['sha256'],
        'ee_memory_sha256': digest(state.ram), 'sources': image.sources, 'resources': []}
    for name, resource, loader, displacement, unpacked_size in LINKS:
        # Check the resource load call and global-pointer store at each loader.
        pcs = (loader+12, loader+48) if loader == 0x011801f0 else (loader+16,loader+52)
        expected = (0x0c449974, 0xaf82991c) if loader == 0x011801f0 else (0x0c449974,0xaf829a4c)
        words = tuple(image.instruction(pc).word for pc in pcs)
        if words != expected: raise ValueError('link loader instructions changed')
        pointer_address = GP + displacement
        pointer = struct.unpack_from('<I', state.ram, pointer_address)[0]
        candidates = []; start = 0; needle = struct.pack('<I', unpacked_size)
        while True:
            at = state.ram.find(needle, start)
            if at < 0: break
            start = at + 1
            if at < 8: continue
            tag, stored_size = struct.unpack_from('<II', state.ram, at-8)
            if tag != 0x00010600 or stored_size > 16*1024*1024 or at-8+32+stored_size > len(state.ram): continue
            data = state.ram[at-8:at-8+32+stored_size]
            candidate = {'ram_address': hex(at-8), 'stored_bytes': len(data), 'stored_sha256': digest(data)}
            try:
                payload = _inspector.unpack_resource(data, 16*1024*1024)
                candidate.update(zlib_valid=True, payload_bytes=len(payload), payload_sha256=digest(payload))
            except _inspector.FormatError as exc:
                candidate.update(zlib_valid=False, reason=str(exc))
            candidates.append(candidate)
        report['resources'].append({'reported_name': name, 'resource_id': hex(resource), 'loader_entry': hex(loader),
            'checked_words': {hex(pc):hex(word) for pc,word in zip(pcs,words)},
            'global_pointer_address': hex(pointer_address), 'captured_global_pointer': hex(pointer),
            'reported_unpacked_bytes': unpacked_size, 'memory_candidates': candidates})
    report['scope'] = 'Checks actual loader resource calls/global pointer stores and captured memory. Matching reported header sizes identify candidates, not verified DATA assets. Null resource pointers and failed zlib streams cannot provide complete original link initialization data. No bind pose/axes/units assertion.'
    return report

def main():
    p = argparse.ArgumentParser()
    for name in ('state','elf','over','output'): p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args(); state=SaveState(a.state); report=inspect(state,Image(a.elf,a.over))
    with a.output.open('x') as stream: stream.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'resources':len(report['resources']), 'valid_stream_candidates':sum(c['zlib_valid'] for r in report['resources'] for c in r['memory_candidates'])}))

if __name__=='__main__': main()
