"""Delivered original-call vectors and failure before stale evidence is used."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/pes3'))
from verify_resource_vectors import verify

@unittest.skipUnless(shutil.which('g++'),'g++ unavailable')
class ResourcePackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='pes3-resource-package-');self.folder=Path(self.temp.name)
        with zipfile.ZipFile(ROOT/'artifacts/pes3-model-resources-research.zip')as archive:
            self.assertIsNone(archive.testzip());archive.extractall(self.folder)
        self.manifest=json.loads((self.folder/'manifest.json').read_text())
    def tearDown(self):self.temp.cleanup()
    def rehash(self,name,data):
        (self.folder/name).write_bytes(data)
        self.manifest['files_sha256'][name]=hashlib.sha256(data).hexdigest()
        (self.folder/'manifest.json').write_text(json.dumps(self.manifest))
    def test_delivered_original_call_vectors_recompile_and_match(self):
        result=verify(self.folder)
        self.assertEqual(result['result'],'passed');self.assertEqual(result['comparisons'],624)
        self.assertEqual(result['compared_words'],212228)
        self.assertEqual(result['by_run'],{'bind-nearest':26,'bind-chop':26,'render-nearest':286,'render-chop':286})
        self.assertFalse(result['runtime_enabled'])
    def test_modified_header_is_rejected_before_compiling(self):
        with (self.folder/'model_bind.hpp').open('ab')as stream:stream.write(b'\n// changed\n')
        with patch('verify_resource_vectors.subprocess.run')as compiler:
            with self.assertRaisesRegex(ValueError,'package hash differs'):verify(self.folder)
            compiler.assert_not_called()
    def test_numeric_corruption_still_fails_when_compressed_file_hash_is_updated(self):
        run=self.manifest['runs'][0];vectors=json.loads(gzip.decompress((self.folder/run['vectors']).read_bytes()))
        raw=bytearray(base64.b64decode(vectors['cases'][0]['expected_base64']));raw[20]^=1
        vectors['cases'][0]['expected_base64']=base64.b64encode(raw).decode()
        self.rehash(run['vectors'],gzip.compress(json.dumps(vectors).encode(),mtime=0))
        with self.assertRaisesRegex(ValueError,'vector hash differs'):verify(self.folder)
    def test_unsupported_profile_does_not_silently_select_nearest(self):
        run=self.manifest['runs'][0];report=json.loads((self.folder/run['report']).read_text())
        report['arithmetic_profile']['fpu']='unsupported'
        raw=json.dumps(report).encode();run['report_sha256']=hashlib.sha256(raw).hexdigest()
        self.rehash(run['report'],raw)
        with self.assertRaisesRegex(ValueError,'unsupported bind/render arithmetic profile'):verify(self.folder)

if __name__=='__main__':unittest.main()
