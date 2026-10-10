"""Decode integer/control R5900 instructions for bounded static analysis.

Other instruction families remain explicit words, never invented pseudocode.
This module does not execute PS2 hardware or recover original symbol names.
"""
REGS = ("zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 "
        "s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra").split()


class Instruction:
    __slots__ = ("pc", "word")

    def __init__(self, pc, word):
        self.pc, self.word = pc, word

    @property
    def op(self): return self.word >> 26
    @property
    def rs(self): return self.word >> 21 & 31
    @property
    def rt(self): return self.word >> 16 & 31
    @property
    def rd(self): return self.word >> 11 & 31
    @property
    def sa(self): return self.word >> 6 & 31
    @property
    def fn(self): return self.word & 63
    @property
    def imm(self): return self.word & 65535
    @property
    def simm(self): return self.imm - (65536 if self.imm & 32768 else 0)
    @property
    def target(self):
        if self.op in (2, 3):
            return (self.pc + 4) & 0xf0000000 | (self.word & 0x03ffffff) << 2
        return self.pc + 4 + self.simm * 4
    @property
    def conditional(self):
        return self.op in (1, 4, 5, 6, 7, 20, 21, 22, 23) or (
            self.op in (17, 18) and self.rs == 8)
    @property
    def likely(self):
        return self.op in (20, 21, 22, 23) or (self.op == 1 and self.rt in (2, 3, 18, 19)) or (
            self.op in (17, 18) and self.rs == 8 and self.rt & 2)
    @property
    def indirect(self): return self.op == 0 and self.fn in (8, 9)
    @property
    def call(self): return self.op == 3 or (self.op == 0 and self.fn == 9)

    def text(self):
        r, t, d = REGS[self.rs], REGS[self.rt], REGS[self.rd]
        if not self.word: return "nop"
        if self.op in (2, 3): return ("j" if self.op == 2 else "jal") + f" 0x{self.target:08x}"
        if self.op == 0:
            if self.fn in (0, 2, 3, 56, 58, 59, 60, 62, 63):
                name = {0:"sll",2:"srl",3:"sra",56:"dsll",58:"dsrl",59:"dsra",
                        60:"dsll32",62:"dsrl32",63:"dsra32"}[self.fn]
                return f"{name} {d}, {t}, {self.sa}"
            if self.fn in (8, 9): return ("jr " if self.fn == 8 else f"jalr {d}, ") + r
            if self.fn in (16, 18): return ("mfhi " if self.fn == 16 else "mflo ") + d
            if self.fn in (17, 19): return ("mthi " if self.fn == 17 else "mtlo ") + r
            names={4:"sllv",6:"srlv",7:"srav",10:"movz",11:"movn",24:"mult",25:"multu",
                   26:"div",27:"divu",32:"add",33:"addu",34:"sub",35:"subu",36:"and",37:"or",
                   38:"xor",39:"nor",42:"slt",43:"sltu",44:"dadd",45:"daddu",46:"dsub",47:"dsubu"}
            if self.fn in names: return f"{names[self.fn]} {d}, {r}, {t}"
        if self.op in (4, 5, 6, 7, 20, 21, 22, 23):
            name={4:"beq",5:"bne",6:"blez",7:"bgtz",20:"beql",21:"bnel",22:"blezl",23:"bgtzl"}[self.op]
            return f"{name} {r}, {t}, 0x{self.target:08x}"
        if self.op == 1:
            name={0:"bltz",1:"bgez",2:"bltzl",3:"bgezl",16:"bltzal",17:"bgezal"}.get(self.rt)
            if name: return f"{name} {r}, 0x{self.target:08x}"
        if self.op in (8, 9, 10, 11, 12, 13, 14, 15, 24, 25):
            name={8:"addi",9:"addiu",10:"slti",11:"sltiu",12:"andi",13:"ori",14:"xori",
                  15:"lui",24:"daddi",25:"daddiu"}[self.op]
            value=self.imm if self.op in (12,13,14,15) else self.simm
            return f"{name} {t}, " + ("" if self.op==15 else r+", ") + str(value)
        memory={30:"lq",31:"sq",32:"lb",33:"lh",34:"lwl",35:"lw",36:"lbu",37:"lhu",38:"lwr",
                39:"lwu",40:"sb",41:"sh",42:"swl",43:"sw",44:"sdl",45:"sdr",46:"swr",
                49:"lwc1",54:"lqc2",55:"ld",57:"swc1",62:"sqc2",63:"sd"}
        if self.op in memory:
            register=f"f{self.rt}" if self.op in (49,57) else f"vf{self.rt}" if self.op in (54,62) else t
            return f"{memory[self.op]} {register}, {self.simm}({r})"
        if self.op == 17:
            if self.rs==8: return f"bc1{'t' if self.rt&1 else 'f'}{'l' if self.rt&2 else ''} 0x{self.target:08x}"
            if self.rs in (0,4): return f"{'mfc1' if self.rs==0 else 'mtc1'} {t}, f{self.rd}"
            names={0:"add.s",1:"sub.s",2:"mul.s",3:"div.s",4:"sqrt.s",5:"abs.s",6:"mov.s",7:"neg.s",
                   24:"adda.s",25:"suba.s",26:"mula.s",28:"madd.s",29:"msub.s",32:"cvt.s.w",36:"cvt.w.s",
                   48:"c.f.s",50:"c.eq.s",52:"c.lt.s",54:"c.le.s"}
            if self.fn in names: return f"{names[self.fn]} f{self.sa}, f{self.rd}, f{self.rt}"
        return f".word 0x{self.word:08x} /* instruction family not translated */"
