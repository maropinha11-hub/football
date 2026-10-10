import importlib.util
import io
from pathlib import Path
import struct
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/pes3'))
from savestate import SaveState, decode_zstd, MEMORY_SIZES
from lift import translate, generate
from mips import Instruction


class SaveStateTests(unittest.TestCase):
    def state(self, folder, changes=None):
        members={'PCSX2 Savestate Version.id':struct.pack('<I',1)+b'test'.ljust(16,b'\0'),
                 'PCSX2 Internal Structures.dat':b'opaque',
                 'eeMemory.bin':bytes(MEMORY_SIZES['eeMemory.bin']),
                 'Scratchpad.bin':bytes(16384)}
        members.update(changes or {})
        target=Path(folder)/'test.p2s'
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,contents in members.items():z.writestr(name,contents)
        return target

    def test_valid_archive_preserves_source(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.state(temp);before=path.read_bytes();state=SaveState(path)
            self.assertEqual(len(state.ram),32*1024*1024)
            self.assertEqual(state.cpu_metadata(),{'status':'unsupported_layout'})
            self.assertEqual(path.read_bytes(),before)

    def test_rejects_missing_scratchpad(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.state(temp)
            with zipfile.ZipFile(path) as z:items={n:z.read(n) for n in z.namelist() if n!='Scratchpad.bin'}
            with zipfile.ZipFile(path,'w') as z:
                for n,b in items.items():z.writestr(n,b)
            with self.assertRaises(ValueError):SaveState(path)

    def test_rejects_wrong_memory_size(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'memória'):
                SaveState(self.state(temp,{'eeMemory.bin':bytes(32)}))

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'nome'):
                SaveState(self.state(temp,{'../outside.bin':b'x'}))

    def test_rejects_local_header_name_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.state(temp);raw=bytearray(path.read_bytes());raw[30]=ord('X');path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'nome'):SaveState(path)

    def test_rejects_corrupt_crc(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.state(temp);raw=bytearray(path.read_bytes());at=raw.find(b'PK\x01\x02')
            struct.pack_into('<I',raw,at+16,0);path.write_bytes(raw)
            with self.assertRaises((ValueError,zipfile.BadZipFile)):SaveState(path)

    @unittest.skipUnless(importlib.util.find_spec('zstandard'),'zstandard unavailable')
    def test_zstd_size_and_trailing_data_rejected(self):
        import zstandard
        block=zstandard.ZstdCompressor().compress(b'actual bytes')
        self.assertEqual(decode_zstd(block,12),b'actual bytes')
        with self.assertRaises(ValueError):decode_zstd(block,11)
        with self.assertRaises(ValueError):decode_zstd(block+b'extra',12)

    @unittest.skipUnless(importlib.util.find_spec('zstandard'),'zstandard unavailable')
    def test_zip_method_93(self):
        import zstandard
        with tempfile.TemporaryDirectory() as temp:
            path=self.state(temp)
            with zipfile.ZipFile(path) as z:members={n:z.read(n) for n in z.namelist()}
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as z:
                for n,b in members.items():z.writestr(n,zstandard.ZstdCompressor().compress(b))
            raw=bytearray(stream.getvalue())
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                for f in z.infolist():
                    struct.pack_into('<H',raw,f.header_offset+8,93)
                    struct.pack_into('<I',raw,f.header_offset+14,zlib.crc32(members[f.filename]))
                    struct.pack_into('<I',raw,f.header_offset+22,len(members[f.filename]))
            pos=raw.find(b'PK\x01\x02')
            while raw[pos:pos+4]==b'PK\x01\x02':
                length,extra,comment=struct.unpack_from('<3H',raw,pos+28)
                name=raw[pos+46:pos+46+length].decode()
                struct.pack_into('<H',raw,pos+10,93)
                struct.pack_into('<I',raw,pos+16,zlib.crc32(members[name]))
                struct.pack_into('<I',raw,pos+24,len(members[name]))
                pos+=46+length+extra+comment
            path.write_bytes(raw)
            self.assertEqual(SaveState(path).ram,members['eeMemory.bin'])

    def test_rejects_duplicate_members(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.state(temp)
            with self.assertWarns(UserWarning):
                with zipfile.ZipFile(path,'a') as z:z.writestr('Scratchpad.bin',bytes(16384))
            with self.assertRaisesRegex(ValueError,'repetido'):SaveState(path)


class LiftTests(unittest.TestCase):
    def test_unknown_instruction_does_not_become_nop(self):
        self.assertIn('throw',translate(Instruction(0x100,0x0000000c)))

    def test_likely_branch_annuls_and_jalr_captures_target_first(self):
        likely=translate(Instruction(0x100,(20<<26)|(4<<21)|(5<<16)|2))
        self.assertIn('else c.annul = true',likely)
        jalr=translate(Instruction(0x100,(4<<21)|(4<<11)|9))
        self.assertLess(jalr.index('c.branch'),jalr.index('c.r[4] ='))

    def test_generated_code_guards_original_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            destination=Path(temp)/'native'
            generate({0x100:0},destination)
            code=(destination/'lifted_program.cpp').read_text()
            self.assertIn('c.mark(0u)',code)
            self.assertIn('untranslated path',code)
            with self.assertRaises(FileExistsError):generate({0x100:0},destination)


@unittest.skipUnless(shutil.which('g++'),'g++ unavailable')
class NativeLiftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import ctypes as C
        from replay import LiftResult
        cls.temp=tempfile.TemporaryDirectory();cls.output=Path(cls.temp.name)/'native'
        cls.words={0x100:0x2402fff9,0x104:0x24030003,
                   0x108:(2<<21)|(3<<16)|26,0x10c:(4<<11)|18,
                   0x110:(5<<11)|16,0x114:0x03e00008,0x118:0}
        generate(cls.words,cls.output)
        target=cls.output/'test.so'
        subprocess.run(['g++','-std=c++17','-O0','-fno-fast-math','-ffp-contract=off',
            '-shared','-fPIC',str(cls.output/'lifted_program.cpp'),'-o',str(target)],check=True,capture_output=True)
        cls.library=C.CDLL(str(target));cls.Result=LiftResult
        cls.library.pes3_run_lifted.argtypes=[C.POINTER(C.c_uint8),C.POINTER(C.c_uint8),C.c_uint32,
            C.POINTER(C.c_uint64),C.c_uint32,C.c_uint32,C.POINTER(LiftResult)]
        cls.library.pes3_run_lifted.restype=C.c_int

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def execute(self,entry=0x100,budget=64,mutate=False):
        import ctypes as C
        ram=bytearray(32*1024*1024);scratch=bytearray(16384)
        for at,word in self.words.items():struct.pack_into('<I',ram,at,word)
        if mutate:struct.pack_into('<I',ram,0x100,0)
        result=self.Result()
        self.library.pes3_run_lifted((C.c_uint8*len(ram)).from_buffer(ram),
            (C.c_uint8*len(scratch)).from_buffer(scratch),entry,None,0,budget,C.byref(result))
        return result

    def test_signed_division_truncates_and_returns(self):
        result=self.execute()
        self.assertEqual(result.status,0)
        self.assertEqual(result.instructions,7)
        self.assertEqual(result.registers[4],(-2)&0xffffffffffffffff)
        self.assertEqual(result.registers[5],(-1)&0xffffffffffffffff)

    def test_changed_code_and_untranslated_paths_fail(self):
        self.assertIn(b'changed',self.execute(mutate=True).error)
        self.assertIn(b'untranslated',self.execute(entry=0x120).error)

    def test_instruction_budget_is_enforced(self):
        result=self.execute(budget=2)
        self.assertEqual(result.instructions,2)
        self.assertIn(b'budget',result.error)


if __name__=='__main__':unittest.main()
