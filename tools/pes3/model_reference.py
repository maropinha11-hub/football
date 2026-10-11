"""Private instruction-model extension for the reached model initializer.

Adds five packed rearrangements and full 128-bit VU transfers; does not
change the supplied reference modules or emulate PS2 timing/devices.
"""
import struct
import types
from pathlib import Path
from arithmetic import classes
from pose import REFERENCE_HASHES
from savestate import digest

MASK64=(1<<64)-1

def packed(word, registers, upper):
    rs,rt,rd,sa,fn=((word>>n)&31 for n in (21,16,11,6,0))
    fn=word&63
    def lanes(index):
        return [registers[index]&0xffffffff,registers[index]>>32&0xffffffff,
            upper[index]&0xffffffff,upper[index]>>32&0xffffffff]
    a,b=lanes(rs),lanes(rt)
    if (fn,sa)==(8,18): result=[b[0],a[0],b[1],a[1]]  # PEXTLW
    elif (fn,sa)==(40,18): result=[b[2],a[2],b[3],a[3]]  # PEXTUW
    elif (fn,sa)==(9,14): result=[b[0],b[1],a[0],a[1]]  # PCPYLD
    elif (fn,sa)==(41,14): result=[a[2],a[3],b[2],b[3]]  # PCPYUD
    elif (fn,sa)==(41,27):  # PCPYH: replicate halfwords 0 and 4 in each half.
        low=(b[0]&0xffff)*0x10001;high=(b[2]&0xffff)*0x10001
        result=[low,low,high,high]
    else: raise ValueError('packed model instruction outside selected subset: %08x'%word)
    if rd:
        registers[rd]=result[0]|result[1]<<32;upper[rd]=result[2]|result[3]<<32

def model_classes(folder, fpu='nearest', vu='nearest'):
    reference, math_class=classes(folder,fpu,vu,'nearest','nearest')
    path=Path(folder)/'mips_integer_reference.py'
    if digest(path.read_bytes()) != REFERENCE_HASHES[path.name]: raise ValueError('integer model changed')
    source=path.read_text()
    anchor="            elif op == 0x11 and math_model is not None:\n"
    if source.count(anchor)!=1: raise ValueError('extension anchor changed')
    source=source.replace(anchor,"            elif op == 0x1C:\n                self.packed(w,r,upper)\n"+anchor)
    anchor='        upper = [0] * 32\n'
    if source.count(anchor)!=1: raise ValueError('quadword anchor changed')
    source=source.replace(anchor,anchor+'        self.quad_upper = upper\n')
    module=types.ModuleType('_pes3_model_integer');module.__file__=str(path)
    exec(compile(source,str(path),'exec'),module.__dict__)
    class ModelReference(reference):
        run=module.IntegerReference.run
        def packed(self,word,registers,upper): packed(word,registers,upper)
    class ModelMath(math_class):
        def cop2(self,pc,word,registers):
            rs,ft,fs=((word>>n)&31 for n in(21,16,11))
            if rs==1:
                raw=struct.unpack('<4I',struct.pack('<4f',*self.vf[fs]))
                if ft:
                    registers[ft]=raw[0]|raw[1]<<32
                    self.ref.quad_upper[ft]=raw[2]|raw[3]<<32
                return
            if rs==5:
                low,high=registers[ft],self.ref.quad_upper[ft]
                self.vf[fs]=list(struct.unpack('<4f',struct.pack('<QQ',low&MASK64,high&MASK64)))
                return
            return super().cop2(pc,word,registers)
    return ModelReference,ModelMath
