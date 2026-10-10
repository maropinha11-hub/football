"""Selected pose arithmetic for original instruction probes.

The supplied v0.14 PoseMathModel must be on sys.path. This extension executes
reached VU arithmetic with host binary32, separate product/add rounding and
subnormal flushing. No timing, flags, devices or PS2 hardware equivalence.
Encoding was checked against PCSX2 v2.8.2 R5900OpcodeTables.cpp; no emulator
implementation is copied. Unsupported transfers/domains still fail.
"""
from pose_math_model import PoseMathModel
from float_vector_model import bits, signed32, vector_value


class PoseReference(PoseMathModel):
    def cop2(self, pc, word, registers):
        rs, ft, fs, fd = ((word >> n) & 31 for n in (21, 16, 11, 6))
        fn = word & 63
        if rs == 2 and fs == 22:  # Selected CFC2 Q, low scalar only.
            registers[ft] = signed32(bits(self.q)) & ((1 << 64) - 1)
            return
        if rs < 16:
            return super().cop2(pc, word, registers)
        mask = rs & 15
        source, other, old_acc = self.vf[fs][:], self.vf[ft][:], self.acc[:]
        destination, broadcast, kind, use_q = self.vf[fd], None, None, False
        if fn >= 60:
            index = (word & 3) | ((word >> 4) & 0x7c)
            if index == 56:
                numerator = vector_value(source[(word >> 21) & 3])
                denominator = vector_value(other[(word >> 23) & 3])
                if not denominator:
                    raise ValueError('VU division by zero outside pose model')
                self.q = vector_value(numerator / denominator)
                return
            if index == 58:
                import math
                numerator = vector_value(source[(word >> 21) & 3])
                denominator = vector_value(math.sqrt(abs(vector_value(other[(word >> 23) & 3]))))
                if not denominator:
                    raise ValueError('VU reciprocal sqrt outside nonzero pose domain')
                self.q = vector_value(numerator / denominator)
                return
            if index == 47:
                return  # VNOP: no timing or flags.
            if index == 46:
                if mask != 14:
                    raise ValueError('OPMULA outside selected xyz mask')
                for lane in range(3):
                    self.acc[lane] = vector_value(vector_value(source[(lane + 1) % 3])
                                                  * vector_value(other[(lane + 2) % 3]))
                return
            if 4 <= index <= 7:
                kind, broadcast, destination = 'sub', index - 4, self.acc
            elif 12 <= index <= 15:
                kind, broadcast, destination = 'msub', index - 12, self.acc
            elif index in (40, 41, 42, 44, 45):
                kind = {40: 'add', 41: 'madd', 42: 'mul', 44: 'sub', 45: 'msub'}[index]
                destination = self.acc
            else:
                return super().cop2(pc, word, registers)
        elif 12 <= fn <= 15:
            kind, broadcast = 'msub', fn - 12
        elif fn in (28, 33, 37, 40, 41, 45):
            kind = {28: 'mul', 33: 'madd', 37: 'msub', 40: 'add', 41: 'madd', 45: 'msub'}[fn]
            use_q = fn in (28, 33, 37)
        elif fn == 46:
            if mask != 14:
                raise ValueError('OPMSUB outside selected xyz mask')
            for lane in range(3):
                product = vector_value(vector_value(source[(lane + 1) % 3])
                                       * vector_value(other[(lane + 2) % 3]))
                if fd:
                    destination[lane] = vector_value(vector_value(old_acc[lane]) - product)
            self.vf[0] = [0.0, 0.0, 0.0, 1.0]
            return
        else:
            return super().cop2(pc, word, registers)
        for lane in range(4):
            if not mask & (8 >> lane):
                continue
            left = vector_value(source[lane])
            right = vector_value(self.q if use_q else other[lane if broadcast is None else broadcast])
            if kind == 'add':
                result = vector_value(left + right)
            elif kind == 'sub':
                result = vector_value(left - right)
            elif kind == 'mul':
                result = vector_value(left * right)
            else:
                product = vector_value(left * right)
                result = vector_value(vector_value(old_acc[lane]) + product if kind == 'madd'
                                      else vector_value(old_acc[lane]) - product)
            if destination is self.acc or fd:
                destination[lane] = result
        self.vf[0] = [0.0, 0.0, 0.0, 1.0]
