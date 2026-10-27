#!/usr/bin/env python3
"""Bounded, read-only PE inventory. Never loads or executes the inspected file."""
import argparse
import hashlib
import json
import mmap
from pathlib import Path
import struct


class InvalidPE(ValueError):
    pass


class PortableExecutable:
    def __init__(self, data):
        self.data = data
        if self.read(0, 2) != b'MZ':
            raise InvalidPE('missing DOS MZ signature')
        self.pe = self.number(0x3c, 'I')
        if self.read(self.pe, 4) != b'PE\0\0':
            raise InvalidPE('missing PE signature')
        coff = self.pe + 4
        self.machine, count, self.timestamp = self.unpack(coff, 'HHI')
        optional_size, self.characteristics = self.unpack(coff + 16, 'HH')
        if not 1 <= count <= 96:
            raise InvalidPE('invalid section count')
        self.optional = coff + 20
        self.read(self.optional, optional_size)
        magic = self.number(self.optional, 'H')
        if magic not in (0x10b, 0x20b):
            raise InvalidPE('unsupported optional header')
        self.bits = 64 if magic == 0x20b else 32
        minimum, directory_offset = (112, 112) if self.bits == 64 else (96, 96)
        if optional_size < minimum:
            raise InvalidPE('truncated optional header')
        self.image_base = self.number(self.optional + (24 if self.bits == 64 else 28), 'Q' if self.bits == 64 else 'I')
        self.entry = self.number(self.optional + 16, 'I')
        self.image_size = self.number(self.optional + 56, 'I')
        self.header_size = self.number(self.optional + 60, 'I')
        self.directory_count = min(self.number(self.optional + directory_offset - 4, 'I'), 16)
        if directory_offset + self.directory_count * 8 > optional_size:
            raise InvalidPE('data directories exceed optional header')
        self.directories = [self.unpack(self.optional + directory_offset + i * 8, 'II') for i in range(self.directory_count)]
        self.sections = []
        table = self.optional + optional_size
        for i in range(count):
            offset = table + i * 40
            name = self.read(offset, 8).split(b'\0', 1)[0].decode('ascii', 'replace')
            virtual_size, rva, raw_size, raw_offset = self.unpack(offset + 8, 'IIII')
            flags = self.number(offset + 36, 'I')
            raw = self.read(raw_offset, raw_size) if raw_size else b''
            self.sections.append(dict(name=name, rva=rva, virtual_size=virtual_size,
                                      raw_offset=raw_offset, raw_size=raw_size,
                                      characteristics=flags, sha256=hashlib.sha256(raw).hexdigest()))

    def read(self, offset, size):
        if offset < 0 or size < 0 or offset + size > len(self.data):
            raise InvalidPE('file range outside the image')
        return self.data[offset:offset + size]

    def unpack(self, offset, fmt):
        return struct.unpack('<' + fmt, self.read(offset, struct.calcsize('<' + fmt)))

    def number(self, offset, fmt):
        return self.unpack(offset, fmt)[0]

    def offset(self, rva, size=1):
        if rva < self.header_size and rva + size <= self.header_size:
            self.read(rva, size)
            return rva
        candidates = [s for s in self.sections if s['rva'] <= rva and rva + size <= s['rva'] + s['raw_size']]
        if len(candidates) != 1:
            raise InvalidPE('RVA is unmapped, ambiguous, or in virtual-only storage')
        result = candidates[0]['raw_offset'] + rva - candidates[0]['rva']
        self.read(result, size)
        return result

    def rva_at_file(self, offset):
        candidates = [s for s in self.sections if s['raw_offset'] <= offset < s['raw_offset'] + s['raw_size']]
        if len(candidates) != 1:
            raise InvalidPE('file offset is unmapped or ambiguous')
        return candidates[0]['rva'] + offset - candidates[0]['raw_offset']

    def string(self, rva):
        characters = bytearray()
        for i in range(1024):
            value = self.read(self.offset(rva + i), 1)
            if value == b'\0':
                return characters.decode('ascii', 'replace')
            characters.extend(value)
        raise InvalidPE('unterminated import name')

    def imports(self):
        if len(self.directories) < 2 or not self.directories[1][0]:
            return []
        rva, size = self.directories[1]
        modules = []
        for index in range(min(size // 20, 1024)):
            record = self.unpack(self.offset(rva + index * 20, 20), 'IIIII')
            if not any(record):
                return modules
            lookup, _, _, name, address = record
            stride = self.bits // 8
            entries = []
            for item in range(16384):
                thunk = self.number(self.offset((lookup or address) + item * stride, stride), 'Q' if stride == 8 else 'I')
                if not thunk:
                    break
                if thunk & (1 << (self.bits - 1)):
                    entries.append(dict(ordinal=thunk & 0xffff))
                else:
                    entries.append(dict(name=self.string(thunk + 2)))
            else:
                raise InvalidPE('import thunk table exceeds bound')
            modules.append(dict(module=self.string(name), symbols=entries))
        raise InvalidPE('import descriptor table has no terminator within its declared size')

    def report(self):
        return dict(schema_version=1, kind='static_pe_inventory',
                    bytes=len(self.data), sha256=hashlib.sha256(self.data).hexdigest(),
                    architecture={0x14c: 'x86', 0x8664: 'x86_64', 0xaa64: 'arm64'}.get(self.machine, hex(self.machine)),
                    bits=self.bits, machine=self.machine, image_base=self.image_base,
                    entry_rva=self.entry, image_size=self.image_size,
                    coff_timestamp_raw=self.timestamp, sections=self.sections, imports=self.imports(),
                    directories=[dict(index=i, rva_or_file_offset=v[0], bytes=v[1]) for i, v in enumerate(self.directories)],
                    scope='Headers, section hashes and declared static imports only. No recovered gameplay functions, constants, licensing determination or runtime equivalence.',
                    limitations=['Delayed and dynamically resolved imports are not decoded.',
                                 'PE timestamp is not a verified build date.',
                                 'No executable code, DLL or game asset is exported.'])


def inspect(path):
    path = Path(path)
    with path.open('rb') as source:
        if path.stat().st_size < 64:
            raise InvalidPE('file too short')
        with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
            report = PortableExecutable(data).report()
    report['file'] = path.name
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.executable)
    with args.output.open('x', encoding='utf-8') as target:
        json.dump(report, target, indent=2)
        target.write('\n')
    print(json.dumps(dict(result='inspected', file=report['file'], architecture=report['architecture'],
                          sha256=report['sha256'], modules=len(report['imports']))))


if __name__ == '__main__':
    main()
