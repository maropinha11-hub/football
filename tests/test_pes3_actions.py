import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/pes3'))
from actions import Image, analyze_function, guarded_jump_table
from mips import Instruction


class SyntheticImage:
    def __init__(self,words,table=None):
        self.words={0x100+i*4:word for i,word in enumerate(words)}
        self.table=table
    def instruction(self,pc):return Instruction(pc,self.words.get(pc,0))
    def bound(self,entry):return max(self.words)+4
    def contains(self,pc):return pc in self.words
    def read(self,address,size):
        if address==0x400 and self.table is not None:return struct.pack('<%dI'%len(self.table),*self.table)
        raise ValueError('sem dados')


SINK=0x0c000000|(0x011677a0>>2)


class ActionAnalysisTests(unittest.TestCase):
    def test_jump_and_signed_branch_addresses(self):
        self.assertEqual(Instruction(0x1000,SINK).target,0x011677a0)
        self.assertEqual(Instruction(0x1000,0x1000fffc).target,0xff4)
        self.assertTrue(Instruction(0,0x50000001).likely)

    def test_animation_id_is_taken_after_call_delay_slot(self):
        image=SyntheticImage([0x2405002f,SINK,0x2405003d,0x03e00008,0])
        function=analyze_function(image,0x100)
        self.assertEqual(function['calls'][0]['literal_clip_ids'],[61])
        self.assertEqual(function['calls'][0]['arguments'][1],['61'])

    def test_unknown_call_clobbers_argument_registers(self):
        image=SyntheticImage([0x2405002f,0x0c000080,0,SINK,0,0x03e00008,0])
        function=analyze_function(image,0x100)
        call=next(c for c in function['calls'] if c['role']=='animation_change')
        self.assertEqual(call['literal_clip_ids'],[])
        self.assertFalse(call['clip_argument_fully_constant'])

    def test_likely_false_branch_annuls_its_delay_slot(self):
        for opcode,expected in [(0x50c00001,[47,61]),(0x10c00001,[61])]:
            image=SyntheticImage([0x2405002f,opcode,0x2405003d,SINK,0,0x03e00008,0])
            self.assertEqual(analyze_function(image,0x100)['calls'][0]['literal_clip_ids'],expected)

    def test_dynamic_current_clip_is_not_assigned_an_invented_id(self):
        image=SyntheticImage([0x948502dc,SINK,0,0x03e00008,0])
        call=analyze_function(image,0x100)['calls'][0]
        self.assertEqual(call['arguments'][1],['arg0.u16:732'])
        self.assertEqual(call['literal_clip_ids'],[])

    def test_external_shared_return_remains_unresolved(self):
        image=SyntheticImage([0x08000080,0])
        function=analyze_function(image,0x100)
        self.assertEqual(function['unresolved_edges'],[{'pc':'0x200','reason':'edge_outside_prologue_bound'}])
        self.assertEqual(function['return_summary'],['unresolved'])

    def test_guarded_jump_table_requires_unchanged_index(self):
        words=[0x2c410002,0x1020000e,0x3c030000,0x00021080,0x24630400,
               0x00431021,0x8c420000,0x00400008]+[0]*12
        image=SyntheticImage(words,[0x130,0x134])
        table=guarded_jump_table(image,0x11c,0x100)
        self.assertEqual(table['targets'],['0x130','0x134'])
        image.words[0x108]=0x24020007
        self.assertIsNone(guarded_jump_table(image,0x11c,0x100))

    def test_unknown_binary_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            elf=Path(directory)/'SLES';over=Path(directory)/'OVER'
            elf.write_bytes(b'unknown');over.write_bytes(b'unknown')
            with self.assertRaisesRegex(ValueError,'hashes'):Image(elf,over)


if __name__=='__main__':unittest.main()
