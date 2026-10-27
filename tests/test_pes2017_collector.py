"""Run the actual C# CPK reader against independently built synthetic containers."""
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LOCAL = Path('/workspace/.football-csharp/root')
MONO = os.environ.get('PES2017_TEST_MONO') or shutil.which('mono') or (str(LOCAL / 'usr/bin/mono-sgen') if (LOCAL / 'usr/bin/mono-sgen').exists() else None)
MCS = os.environ.get('PES2017_TEST_MCS') or (str(LOCAL / 'usr/lib/mono/4.5/mcs.exe') if (LOCAL / 'usr/lib/mono/4.5/mcs.exe').exists() else None)


def utf(columns, rows, table='test', expanded=False):
    strings = bytearray()
    offsets = {}
    def string(value):
        if value not in offsets:
            offsets[value] = len(strings)
            strings.extend(value.encode('utf-8') + b'\0')
        return offsets[value]
    formats = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i', 6: 'Q', 7: 'q', 8: 'f', 9: 'd'}
    def value(kind, item):
        if kind == 10:
            return struct.pack('>I', string(item))
        return struct.pack('>' + formats[kind], item)
    table_name = string(table)
    schema = bytearray()
    row_width = 0
    for name, kind, storage, constant in columns:
        schema.extend((b'\0' * 4 if expanded else b'') + bytes([storage | kind]) + struct.pack('>I', string(name)))
        if storage & 0x20:
            schema.extend(value(kind, constant))
        elif storage & 0x40:
            row_width += 4 if kind == 10 else struct.calcsize(formats[kind])
    cells = bytearray()
    for row in rows:
        for name, kind, storage, _ in columns:
            if storage & 0x40 and not storage & 0x20:
                cells.extend(value(kind, row[name]))
    row_offset = 32 + len(schema)
    string_offset = row_offset + len(cells)
    data_offset = string_offset + len(strings)
    header = struct.pack('>4sIHHIIIHHI', b'@UTF', data_offset - 8, 0, row_offset - 8,
                         string_offset - 8, data_offset - 8, table_name, len(columns), row_width, len(rows))
    return header + schema + cells + strings


def mask(packet):
    key = 0x655f
    output = bytearray()
    for byte in packet:
        output.append(byte ^ (key & 255))
        key = key * 0x4115 & 0xffffffff
    return bytes(output)


def cpk(entries, masked=False, late_toc=False, expanded=False, row_patch=None):
    toc_offset, content = (0x3000, 0x800) if late_toc else (0x800, 0x1000)
    base = min(toc_offset, content)
    at = content
    rows = []
    payloads = []
    for directory, filename, payload, extracted in entries:
        rows.append(dict(DirName=directory, FileName=filename, FileSize=len(payload), ExtractSize=extracted, FileOffset=at-base))
        payloads.append((at, payload))
        at += (len(payload) + 15) // 16 * 16
    if row_patch:
        row_patch(rows)
    columns = [(name, kind, 0x50, None) for name, kind in [('DirName', 10), ('FileName', 10), ('FileSize', 4), ('ExtractSize', 4), ('FileOffset', 6)]]
    columns.extend([('ID', 4, 0x10, None), ('UserString', 10, 0x30, 'shared')])
    toc = utf(columns, rows, 'CpkTocInfo', expanded)
    header = utf([('ContentOffset', 6, 0x30, content), ('TocOffset', 6, 0x50, None),
                  ('Files', 4, 0x50, None), ('EnabledPackedSize', 6, 0x10, None)],
                 [dict(TocOffset=toc_offset, Files=len(rows))], 'CpkHeader', expanded)
    if masked:
        header, toc = mask(header), mask(toc)
    packet = lambda tag, payload: struct.pack('<4sIQ', tag, 0, len(payload)) + payload
    result = bytearray(max(at, toc_offset + len(toc) + 16, len(header) + 16))
    result[:len(header) + 16] = packet(b'CPK ', header)
    result[toc_offset:toc_offset + len(toc) + 16] = packet(b'TOC ', toc)
    for offset, payload in payloads:
        result[offset:offset + len(payload)] = payload
    return result


HARNESS = r'''
using System;
using System.Text;
using FPSoccer.Pes2017;
class Run {
  static int Main(string[] args) {
    try {
      if(args.Length==4) {
        Resource r=Collector.CollectLoose(args[0],"configured-root-1",args[3],args[1],long.Parse(args[2]));
        Console.WriteLine("LOOSE\t"+r.Path+"\t"+r.StoredSha256);return 0;
      }
      Scan s=Collector.Collect(args[0],"Data/test.cpk",args[1],long.Parse(args[2]));
      Console.WriteLine("SCAN\t"+s.EntryCount+"\t"+s.ExportedBytes+"\t"+s.SourceSha256+"\t"+s.HeaderMasked+"\t"+s.TocMasked);
      foreach(Resource r in s.Resources)Console.WriteLine("RES\t"+Convert.ToBase64String(Encoding.UTF8.GetBytes(r.Path))+"\t"+r.Offset+"\t"+r.StoredBytes+"\t"+r.DeclaredExtractBytes+"\t"+r.StoredFile+"\t"+r.Encoding);
      foreach(string skip in s.Skipped)Console.WriteLine("SKIP\t"+skip);
      return 0;
    } catch(Exception e) { Console.Error.WriteLine(e.Message);return 3; }
  }
}
'''


@unittest.skipUnless(MONO and MCS, 'C# runtime/compiler needed for actual CPK reader checks')
class CpkCollector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='pes17-reader-build-')
        cls.directory = Path(cls.temp.name)
        harness = cls.directory / 'Run.cs'
        harness.write_text(HARNESS)
        cls.exe = cls.directory / 'Run.exe'
        cls.env = dict(os.environ)
        if str(LOCAL) in MONO:
            cls.env['MONO_CFG_DIR'] = str(LOCAL / 'etc')
        command = [MONO, MCS, '-out:' + str(cls.exe), str(ROOT / 'tools/pes2017/windows/Pes2017ResourceCollector.cs'), str(harness)]
        subprocess.run(command, check=True, capture_output=True, text=True, env=cls.env)
    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
    def invoke(self, data, directory, budget=128*1024*1024):
        source = directory / 'archive with spaces.cpk'
        source.write_bytes(data)
        run = subprocess.run([MONO, str(self.exe), str(source), str(directory / 'resources'), str(budget)],
                             env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(source.read_bytes(), data)
        return run
    def test_plain_and_masked_tables_preserve_selected_bytes_and_ignore_appearance(self):
        for masked in (False, True):
            with self.subTest(masked=masked), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                data = cpk([('cpk_dat/common/match/constant', 'constant_match.bin', b'match-value', 11),
                            ('common/anime/AnimeTable/bin', 'Movetable.bin', b'CRILAYLA' + b'fixture', 1000),
                            ('common/appearance', 'face.bin', b'not-selected', 12)], masked=masked)
                run = self.invoke(data, root)
                self.assertEqual(run.returncode, 0, run.stderr)
                files = sorted((root / 'resources').iterdir())
                self.assertEqual({p.read_bytes() for p in files}, {b'match-value', b'CRILAYLAfixture'})
                self.assertIn(hashlib.sha256(data).hexdigest(), run.stdout)
                self.assertIn('CRILAYLA-preserved', run.stdout)
                self.assertEqual(len(files), 2)
                self.assertIn(('True\tTrue' if masked else 'False\tFalse'), run.stdout)
    def test_standard_mask_matches_real_inventory_prefix(self):
        self.assertEqual(mask(b'@UTF').hex(), '1f9ef3f5')
    def test_toc_after_content_uses_content_base(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = cpk([('common/match/constant', 'constant_player.bin', b'late-toc', 8)], late_toc=True)
            run = self.invoke(data, root)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(next((root / 'resources').iterdir()).read_bytes(), b'late-toc')
    def test_extended_flags_and_empty_archives(self):
        for entries in ([], [('common/match/constant', 'empty.json', b'{}', 2)]):
            with self.subTest(entries=len(entries)), tempfile.TemporaryDirectory() as directory:
                run = self.invoke(cpk(entries, expanded=True), Path(directory))
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertIn('SCAN\t' + str(len(entries)), run.stdout)
    def test_full_index_is_validated_before_any_resource_is_exported(self):
        entries = [('common/match/constant', 'good.bin', b'good-value', 10), ('elsewhere', 'bad.bin', b'bad-value', 9)]
        changes = [lambda rows: rows[1].update(FileOffset=0xfffffffffffffff0),
                   lambda rows: rows[1].update(FileOffset=rows[0]['FileOffset']+1),
                   lambda rows: rows[1].update(DirName='../outside'),
                   lambda rows: rows[1].update(DirName=rows[0]['DirName'],FileName=rows[0]['FileName'])]
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                run = self.invoke(cpk(entries, row_patch=change), root)
                self.assertNotEqual(run.returncode, 0)
                self.assertFalse((root / 'resources').exists())
    def test_budget_and_truncation_do_not_publish_partial_archive(self):
        data = cpk([('common/match/constant', 'constant_match.bin', b'0123456789', 10)])
        for payload, budget in [(data, 9), (data[:0x1000 + 9], 100)]:
            with self.subTest(budget=budget), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                run = self.invoke(payload, root, budget)
                self.assertNotEqual(run.returncode, 0)
                self.assertFalse((root / 'resources').exists())
    def test_aliases_deduplicate_exact_bytes_without_losing_source_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = cpk([('common/match/constant', 'one.bin', b'same', 4), ('common/match/constant', 'two.bin', b'same', 4)])
            run = self.invoke(data, root)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(len(list((root / 'resources').iterdir())), 1)
            self.assertEqual(run.stdout.count('RES\t'), 2)
    def test_true_shared_payload_ranges_are_valid_but_unrecognized_utf_is_not(self):
        entries = [('common/match/constant', 'one.bin', b'same', 4), ('common/match/constant', 'two.bin', b'same', 4)]
        with tempfile.TemporaryDirectory() as directory:
            data = cpk(entries, row_patch=lambda rows: rows[1].update(FileOffset=rows[0]['FileOffset']))
            run = self.invoke(data, Path(directory))
            self.assertEqual(run.returncode, 0, run.stderr)
        with tempfile.TemporaryDirectory() as directory:
            data = cpk(entries)
            data[16:20] = b'BAD!'
            run = self.invoke(data, Path(directory))
            self.assertNotEqual(run.returncode, 0)
            self.assertFalse((Path(directory) / 'resources').exists())
    def test_loose_parameter_files_preserve_bytes_and_refuse_unrelated_paths_or_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'parameter.bin'
            source.write_bytes(b'parameter fixture')
            def run(path, virtual, output):
                return subprocess.run([MONO, str(self.exe), str(path), str(output), '1024', virtual],
                                      env=self.env, capture_output=True, text=True, timeout=15)
            good = run(source, r'cpk_dat\common\match\constant\constant_player.bin', root / 'good')
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(next((root / 'good').iterdir()).read_bytes(), source.read_bytes())
            self.assertNotEqual(run(source, 'common/appearance/face.bin', root / 'unrelated').returncode, 0)
            self.assertFalse((root / 'unrelated').exists())
            link = root / 'link.bin'
            link.symlink_to(source)
            self.assertNotEqual(run(link, 'common/match/constant/constant_player.bin', root / 'linked').returncode, 0)
            self.assertFalse((root / 'linked').exists())


if __name__ == '__main__':
    unittest.main()
