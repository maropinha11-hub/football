import math
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/pes3'))
from arithmetic import chop, nearest, classes
from channel_provenance import rotation_keys


def raw(number):
    return struct.unpack('<I', struct.pack('<f', number))[0]


class RoundingTests(unittest.TestCase):
    def test_signed_halfway_and_adjacent_values(self):
        midpoint = 1 + 3 * 2 ** -24
        for sign in (1, -1):
            self.assertEqual(raw(nearest(sign * midpoint)), raw(sign * (1 + 2 ** -22)))
            self.assertEqual(raw(chop(sign * midpoint)), raw(sign * (1 + 2 ** -23)))
            for delta in (-2 ** -48, 2 ** -48):
                value = sign * (midpoint + delta)
                self.assertLessEqual(abs(chop(value)), abs(value))
                self.assertGreater(abs(chop(value)) + 2 ** -23, abs(value))

    def test_signed_zero_and_subnormal_underflow(self):
        self.assertEqual(raw(chop(-0.0)), 0x80000000)
        self.assertEqual(raw(chop(0.0)), 0)
        for sign, zero in ((1, 0), (-1, 0x80000000)):
            self.assertEqual(raw(chop(sign * .75 * 2 ** -149)), zero)
            self.assertEqual(raw(nearest(sign * .75 * 2 ** -149)), zero | 1)

    def test_known_packed_rotation_products(self):
        scale = struct.unpack('<f', struct.pack('<I', 0x38000100))[0]
        for packed, expected in ((10366, 0x3ea1f943), (-19896, 0xbf1b7136), (21101, 0x3f24db49)):
            self.assertEqual(raw(chop(packed * scale)), expected)
            self.assertEqual(raw(nearest(packed * scale)), expected + 1)

    def test_nonfinite_and_unknown_profiles_rejected(self):
        for rounding in (chop, nearest):
            for value in (math.nan, math.inf, -math.inf):
                with self.assertRaises(ValueError): rounding(value)
        with self.assertRaises(ValueError): classes(Path('/missing'), 'bad', 'nearest')

    def test_packed_key_layout_skips_root_translation(self):
        block = bytearray(28 + 164)
        for bone in range(19):
            offset = 28 + bone * 8 + (12 if bone else 0)
            struct.pack_into('<4h', block, offset, 10366, -19896, 21101, 0)
        struct.pack_into('<3f', block, 36, 17, -31, 59)
        key = rotation_keys(block, 1, chop)[0]
        self.assertEqual(struct.unpack('<76I', key), (0x3ea1f943, 0xbf1b7136, 0x3f24db49, 0) * 19)


if __name__ == '__main__': unittest.main()
