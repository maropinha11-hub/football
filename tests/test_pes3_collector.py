"""Exercise the actual PowerShell/.NET collector with synthetic AFS archives."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from test_pes3_tools import afs_fixture, wrapped_fixture

ROOT = Path(__file__).resolve().parents[1]
PWSH = os.environ.get('PES3_TEST_PWSH') or shutil.which('pwsh')
SCRIPT = ROOT / 'tools/pes3/windows/coletar-pes3.ps1'
sys.path.insert(0, str(ROOT / 'tools/pes3'))
from import_collected_resources import import_archive, validate, TARGETS, ELF_SHA


def resources_fixture(names=True, raw_mbc=False):
    payloads = {name: wrapped_fixture((name.encode('ascii') + b'\0') * 300)
        for name in ('body_lnk.bin', 'mon_lnk.bin', 'anime.bin', 'anime2.bin', 'anime3.bin', 'game.mbc')}
    if raw_mbc: payloads['game.mbc'] = struct.pack('<III',0x00010000,1750,0) + b'\0'*20 + b'm'*1750
    bank47 = afs_fixture([(n, payloads[n]) for n in ('body_lnk.bin', 'mon_lnk.bin')], names=names)
    bank55 = afs_fixture([(n, payloads[n]) for n in ('anime2.bin', 'anime3.bin')] + [('unused', b'ignored')], names=names)
    group54 = afs_fixture([('anime.afs', bank55), ('unused', b'ignored'), ('lnk.afs', bank47), ('unused', b'ignored')], names=names)
    bank8 = afs_fixture([(n, payloads[n]) for n in ('anime.bin', 'game.mbc')], names=names)
    group7 = afs_fixture([('anime.afs', bank8), ('unused', b'ignored'), ('unused', b'ignored')], names=names)
    group4 = afs_fixture([('unused', b'ignored'), ('unused', b'ignored'), ('pl.afs', group7), ('unused', b'ignored')], names=names)
    group2 = afs_fixture([('unused', b'ignored'), ('boot1.afs', group4)], names=names)
    outer = [('unused', b'ignored') for _ in range(17)]
    outer[1] = ('020boot.afs', group2); outer[14] = ('150pl.afs', group54)
    return afs_fixture(outer, names=names), payloads


@unittest.skipUnless(PWSH, 'Set PES3_TEST_PWSH or install pwsh to verify Windows collector')
class CollectorTests(unittest.TestCase):
    def invoke(self, folder, output):
        env = dict(os.environ)
        if os.name != 'nt':
            for name in ('XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME'):
                path = Path(folder).parent / ('.powershell-' + name.lower())
                path.mkdir(exist_ok=True); env[name] = str(path)
        return subprocess.run([PWSH, '-NoLogo', '-NoProfile', '-File', str(SCRIPT),
            '-PastaIso', str(folder), '-Saida', str(output)], text=True, capture_output=True, timeout=40, env=env)

    def test_named_and_nameless_languages_deduplicate_and_preserve_bytes(self):
        with tempfile.TemporaryDirectory(prefix='pes3 collect ') as folder:
            root = Path(folder); iso = root / 'ISO com espacos'; iso.mkdir(); output = root / 'coleta'
            payloads = None
            for language, names in (('F', True), ('S', False)):
                data, payloads = resources_fixture(names)
                (iso / ('DATA_' + language + '.AFS')).write_bytes(data)
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in iso.iterdir()}
            run = self.invoke(iso, output)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            manifest = json.loads((output / 'manifesto.json').read_text(encoding='utf-8-sig'))
            self.assertEqual(len(manifest['recursos']), 12)
            self.assertEqual(manifest['arquivos_nao_correspondentes'], [])
            self.assertEqual(len(list((output / 'recursos').iterdir())), 6)
            for resource in manifest['recursos']:
                stored = (output / 'recursos' / resource['StoredFile']).read_bytes()
                label = resource['StoredFile'].split('-')[1]
                self.assertEqual(stored, payloads[label])
                self.assertEqual(hashlib.sha256(stored).hexdigest(), resource['StoredSha256'])
                self.assertEqual(resource['SourceSha256'], before[resource['Source']])
                self.assertEqual(resource['StoredBytes'], len(stored))
            self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in iso.iterdir()})
            with zipfile.ZipFile(str(output) + '.zip') as archive:
                self.assertIsNone(archive.testzip()); self.assertEqual(len(archive.namelist()), 7)
                self.assertEqual(json.loads(archive.read('manifesto.json').decode('utf-8-sig')), manifest)
            imported = root / 'importados'
            report = import_archive(Path(str(output) + '.zip'), imported)
            self.assertEqual(len(report['resources']), 6)
            self.assertFalse(report['runtime_enabled'])
            for resource in report['resources']:
                self.assertEqual(hashlib.sha256((imported / resource['payload_file']).read_bytes()).hexdigest(), resource['payload_sha256'])
            previous = (output / 'manifesto.json').read_bytes()
            again = self.invoke(iso, output)
            self.assertEqual(again.returncode, 1)
            self.assertEqual((output / 'manifesto.json').read_bytes(), previous)

    def test_invalid_archive_is_reported_without_publishing_selected_resources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); iso = root / 'iso'; iso.mkdir(); output = root / 'coleta'
            data, _ = resources_fixture()
            # Root entries 0 and 1 overlap; each range otherwise stays in the file.
            struct.pack_into('<I', data, 8, struct.unpack_from('<I', data, 16)[0])
            (iso / 'DATA_G.AFS').write_bytes(data)
            run = self.invoke(iso, output)
            self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
            manifest = json.loads((output / 'manifesto.json').read_text(encoding='utf-8-sig'))
            self.assertEqual(manifest['recursos'], [])
            self.assertEqual(len(manifest['arquivos_nao_correspondentes']), 1)
            self.assertFalse((output / 'recursos').exists())
            self.assertFalse(Path(str(output) + '.zip').exists())

    def test_wrong_executable_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); iso = root / 'iso'; iso.mkdir(); output = root / 'coleta'
            data, _ = resources_fixture(); (iso / 'DATA_F.AFS').write_bytes(data)
            (iso / 'SLES_519.12').write_bytes(b'not the supplied ELF')
            run = self.invoke(iso, output)
            self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
            self.assertFalse(output.exists())

    def test_truncated_compressed_header_does_not_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); iso = root / 'iso'; iso.mkdir(); output = root / 'coleta'
            data, payloads = resources_fixture()
            offset = data.index(payloads['body_lnk.bin'])
            struct.pack_into('<I', data, offset + 4, 1)
            (iso / 'DATA_F.AFS').write_bytes(data)
            run = self.invoke(iso, output)
            self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
            manifest = json.loads((output / 'manifesto.json').read_text(encoding='utf-8-sig'))
            self.assertEqual(manifest['recursos'], [])
            self.assertFalse((output / 'recursos').exists())

    def test_reported_raw_mbc_is_preserved_and_imported_without_zlib(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);iso=root/'iso';iso.mkdir();output=root/'coleta'
            data,payloads=resources_fixture(raw_mbc=True);(iso/'DATA_F.AFS').write_bytes(data)
            run=self.invoke(iso,output)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            imported=root/'imported';report=import_archive(Path(str(output)+'.zip'),imported)
            mbc=next(r for r in report['resources'] if r['resource_id']=='0x00080001')
            self.assertEqual(mbc['payload_kind'],'reported_raw_game_mbc')
            self.assertEqual((imported/mbc['stored_file']).read_bytes(),payloads['game.mbc'])
            self.assertEqual((imported/mbc['payload_file']).read_bytes(),b'm'*1750)


class ResourceImportTests(unittest.TestCase):
    def fixture(self, path, corrupt=False, extra=None):
        rows=[];files={}
        for resource_id,(label,indices) in TARGETS.items():
            data=bytearray(wrapped_fixture((label.encode()+b'\0')*300))
            if corrupt and label=='body_lnk.bin': data[-1]^=1
            data=bytes(data);sha=hashlib.sha256(data).hexdigest()
            name=resource_id[2:]+'-'+label+'-'+sha[:16]+'.stored'
            files['recursos/'+name]=data
            rows.append(dict(Source='DATA_F.AFS',SourceSha256='1'*64,SourceBytes=1000000,ResourceId=resource_id,
                StoredFile=name,StoredSha256=sha,AbsoluteOffset=2048,StoredBytes=len(data),HeaderTag=0x10600,
                UnpackedBytes=struct.unpack_from('<I',data,8)[0],ReportedUnpackedBytes=0,Indices=indices))
        manifest=dict(schema_version=1,descritores_sles_sha256=ELF_SHA,sles_sha256=None,recursos=rows)
        files['manifesto.json']=json.dumps(manifest).encode()
        if extra:files[extra]=b'ignored'
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in files.items():archive.writestr(name,data)
        return files,manifest

    def test_valid_zip_imports_all_payloads_and_keeps_runtime_disabled(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'input.zip';self.fixture(archive)
            report=import_archive(archive,root/'out')
            self.assertEqual(len(report['resources']),6)
            self.assertFalse(report['runtime_enabled'])
            self.assertFalse(report['data_source_hashes_independently_verified'])
            for row in report['resources']:
                data=(root/'out'/row['payload_file']).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(),row['payload_sha256'])
            with self.assertRaises(FileExistsError):import_archive(archive,root/'out')

    def test_even_correct_stored_hash_cannot_mask_zlib_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'input.zip';self.fixture(archive,corrupt=True)
            with self.assertRaises(ValueError):import_archive(archive,root/'out')
            self.assertFalse((root/'out').exists())

    def test_windows_framework_backslashes_import_with_checksums(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); original=root/'original.zip'; files,_=self.fixture(original)
            archive=root/'windows.zip'
            with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as zipped:
                for name,data in files.items(): zipped.writestr(name.replace('/', '\\'),data)
            report=import_archive(archive,root/'out')
            self.assertEqual(len(report['resources']),6)
            for row in report['resources']:
                self.assertEqual(hashlib.sha256((root/'out'/row['stored_file']).read_bytes()).hexdigest(),row['stored_sha256'])

    def test_normalized_aliases_and_windows_traversal_reject_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);original=root/'original.zip';files,_=self.fixture(original)
            member=next(name for name in files if name.startswith('recursos/'))
            for index,alias in enumerate((member.replace('/', '\\'), 'recursos\\..\\escape', 'C:\\escape', '\\\\server\\share')):
                archive=root/(str(index)+'.zip')
                with zipfile.ZipFile(archive,'w') as zipped:
                    for name,data in files.items(): zipped.writestr(name,data)
                    zipped.writestr(alias,files[member])
                with self.assertRaises(ValueError): import_archive(archive,root/'out')
                self.assertFalse((root/'out').exists())

    def test_extra_files_and_traversal_are_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for n,extra in enumerate(('../escape','recursos/unused.stored','other.txt')):
                archive=root/(str(n)+'.zip');self.fixture(archive,extra=extra)
                with self.assertRaises(ValueError):import_archive(archive,root/'out')
                self.assertFalse((root/'out').exists())

    def test_missing_or_tampered_bank_metadata_rejects(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);original=root/'original.zip';files,manifest=self.fixture(original)
            manifest['recursos'][0]['Indices']=[0,0,0]
            files['manifesto.json']=json.dumps(manifest).encode();archive=root/'tampered.zip'
            with zipfile.ZipFile(archive,'w') as zipped:
                for name,data in files.items():zipped.writestr(name,data)
            with self.assertRaises(ValueError):validate(archive)

if __name__ == '__main__': unittest.main()
