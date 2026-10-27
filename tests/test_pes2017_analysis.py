"""Independent PE fixtures and trace error/invalid-measurement regressions."""
import copy
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/pes2017'))
from inspect_executable import InvalidPE, PortableExecutable
from calibration import compare, export_native, validate
from recover_ball_schema import describe_reader, binary_layout, recover, EXECUTABLE_SHA256
from decode_ball_blob import decode


def pe_fixture(bits=64):
    data = bytearray(0x600)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    size = 240 if bits == 64 else 224
    struct.pack_into('<HHIIIHH', data, 0x84, 0x8664 if bits == 64 else 0x14c, 1, 1234, 0, 0, size, 0x22)
    opt = 0x98
    struct.pack_into('<H', data, opt, 0x20b if bits == 64 else 0x10b)
    struct.pack_into('<I', data, opt + 16, 0x1000)
    struct.pack_into('<Q' if bits == 64 else '<I', data, opt + (24 if bits == 64 else 28), 0x140000000 if bits == 64 else 0x400000)
    struct.pack_into('<II', data, opt + 56, 0x2000, 0x200)
    dirs = opt + (112 if bits == 64 else 96)
    struct.pack_into('<I', data, dirs - 4, 16)
    struct.pack_into('<II', data, dirs + 8, 0x1000, 40)
    table = opt + size
    data[table:table + 8] = b'.rdata\0\0'
    struct.pack_into('<IIII', data, table + 8, 0x500, 0x1000, 0x400, 0x200)
    struct.pack_into('<I', data, table + 36, 0x40000040)
    struct.pack_into('<IIIII', data, 0x200, 0x1080, 0, 0, 0x1060, 0x10a0)
    data[0x260:0x26d] = b'KERNEL32.dll\0'
    fmt = '<QQQ' if bits == 64 else '<III'
    struct.pack_into(fmt, data, 0x280, 0x10c0, (1 << (bits - 1)) | 17, 0)
    data[0x2c2:0x2ce] = b'ExitProcess\0'
    return data


class PEInventory(unittest.TestCase):
    def test_both_architectures_names_and_ordinals(self):
        for bits in (32, 64):
            with self.subTest(bits=bits):
                data = pe_fixture(bits)
                before = bytes(data)
                report = PortableExecutable(data).report()
                self.assertEqual(report['bits'], bits)
                self.assertEqual(report['imports'], [dict(module='KERNEL32.dll', symbols=[dict(name='ExitProcess'), dict(ordinal=17)])])
                self.assertEqual(bytes(data), before)
                self.assertEqual(report['sections'][0]['raw_size'], 0x400)
                self.assertEqual(PortableExecutable(data).rva_at_file(0x260), 0x1060)
    def test_rejects_truncation_and_bad_header_ranges(self):
        fixture = pe_fixture()
        for size in (0, 30, 63, 130, 280, 510, 1400):
            with self.subTest(size=size), self.assertRaises(InvalidPE):
                PortableExecutable(fixture[:size])
        struct.pack_into('<I', fixture, 0x3c, 0xfffffff0)
        with self.assertRaises(InvalidPE):
            PortableExecutable(fixture)
    def test_rejects_virtual_only_and_overlapping_mapping(self):
        pe = PortableExecutable(pe_fixture())
        with self.assertRaises(InvalidPE):
            pe.offset(0x1450)
        pe.sections.append(copy.deepcopy(pe.sections[0]))
        with self.assertRaises(InvalidPE):
            pe.offset(0x1000)
    def test_rejects_unterminated_import_descriptors(self):
        data = pe_fixture()
        struct.pack_into('<I', data, 0x98 + 112 + 12, 20)
        with self.assertRaises(InvalidPE):
            PortableExecutable(data).report()
    def test_import_strings_must_not_escape_the_image(self):
        data = pe_fixture()
        struct.pack_into('<I', data, 0x20c, 0x13f0)
        data[-16:] = b'X' * 16
        with self.assertRaises(InvalidPE):
            PortableExecutable(data).report()


def trace():
    return dict(schema_version=1, game='pes2017', executable_sha256='a' * 64,
                units=dict(time='s', distance='m'), axes='x_forward_y_left_z_up',
                scenario='low_speed_carry', conditions=dict(case_id='test-only', player='synthetic'),
                evidence=dict(kind='synthetic', method='unit test, not PES data'),
                required_inputs=['move'], observed_inputs=['move', 'shot'],
                samples=[dict(t=i / 10, player=[i / 10, 0., 0.], ball=[i / 10 + .5, 0., .11],
                              input=dict(move=[0., -1.], shot=False)) for i in range(21)])


BUDGETS = dict(player_position_rmse_m=.15, ball_position_rmse_m=.2,
               player_speed_rmse_mps=.25, maximum_input_error=.03)


class TraceComparison(unittest.TestCase):
    def test_synthetic_equality_is_not_gameplay_certification(self):
        reference, candidate = trace(), trace()
        candidate['game'] = 'football'
        report = compare(reference, candidate, BUDGETS)
        self.assertTrue(report['within_declared_tolerances'])
        self.assertFalse(report['pes_comparison'])
        self.assertEqual(report['result'], 'self_or_synthetic_test_only')
        self.assertEqual(report['metrics']['player_position_rmse_m'], 0)
    def test_known_translation_and_velocity_errors_are_not_aligned_away(self):
        reference, candidate = trace(), trace()
        for frame in candidate['samples']:
            frame['player'][0] = frame['t'] * 2 + .5
            frame['ball'][1] += 1
        report = compare(reference, candidate, BUDGETS)
        self.assertFalse(report['within_declared_tolerances'])
        self.assertAlmostEqual(report['metrics']['ball_position_rmse_m'], 1)
        self.assertAlmostEqual(report['metrics']['player_speed_rmse_mps'], 1)
        self.assertGreater(report['metrics']['player_position_rmse_m'], .5)
    def test_mismatched_commands_fail_even_when_positions_match(self):
        reference, candidate = trace(), trace()
        candidate['samples'][10]['input']['shot'] = True
        report = compare(reference, candidate, BUDGETS)
        self.assertEqual(report['metrics']['maximum_input_error'], 1)
        self.assertFalse(report['within_declared_tolerances'])
    def test_resampling_keeps_coarse_resolution(self):
        reference, candidate = trace(), trace()
        candidate['samples'] = candidate['samples'][::2]
        report = compare(reference, candidate, BUDGETS)
        self.assertEqual(report['compared_samples'], 11)
        self.assertAlmostEqual(report['temporal_resolution_s'], .2)
    def test_no_time_warp_or_incompatible_setup(self):
        for key, value in [('scenario', 'different'), ('conditions', {'other': True}), ('required_inputs', ['shot'])]:
            candidate = trace()
            candidate[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                compare(trace(), candidate, BUDGETS)
        candidate = trace()
        for frame in candidate['samples']:
            frame['t'] *= .8
        with self.assertRaises(ValueError):
            compare(trace(), candidate, BUDGETS)
    def test_invalid_units_gaps_nan_or_missing_input_are_rejected(self):
        mutations = [lambda t: t.update(units=dict(time='ms', distance='cm')),
                     lambda t: t['samples'][5]['player'].__setitem__(0, float('nan')),
                     lambda t: t['samples'].__delitem__(slice(3, 7)),
                     lambda t: t['samples'][5]['input'].pop('move'),
                     lambda t: t.update(required_inputs=['sprint'])]
        for mutation in mutations:
            value = trace()
            mutation(value)
            with self.assertRaises((ValueError, KeyError)):
                validate(value)
    def test_no_implicit_default_tolerances(self):
        with self.assertRaises(ValueError):
            compare(trace(), trace(), {})
    def test_native_export_handles_axis_mapping_and_rejects_unobserved_gamepad_buttons(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'game.log'
            executable = Path(directory) / 'game.exe'
            executable.write_bytes(b'test fixture, never executed')
            frames = [dict(t=i * 100, player=[2., i / 10, 0.], ball=[2., i / 10 + .5, .11],
                           controller=1, move=[0., -1.], shot_active=0, keys=0, wall_ms=i * 100 + 900) for i in range(21)]
            log.write_text(''.join('TRAINING_FRAME ' + json.dumps(f) + '\n' for f in frames))
            case = dict(scenario='carry', conditions=dict(player='test'), required_inputs=['move'])
            result = export_native(log, case, executable, 0, 2000, math.pi / 2)
            self.assertAlmostEqual(result['samples'][-1]['player'][0], 2)
            self.assertAlmostEqual(result['samples'][-1]['player'][1], 0)
            self.assertEqual(result['evidence']['simulation_real_time_ratio'], 1)
            case['required_inputs'].append('sprint')
            with self.assertRaises(ValueError):
                export_native(log, case, executable, 0, 2000)
            case['required_inputs'] = ['move']
            log.write_text(log.read_text().replace('TRAINING_FRAME {"t": 1000,', 'TRAINING_RESET exercise=0\nTRAINING_FRAME {"t": 1000,'))
            with self.assertRaises(ValueError):
                export_native(log, case, executable, 0, 2000)


class BallSchema(unittest.TestCase):
    def test_recovered_layout_has_no_aliases_and_all_65_keys_decode(self):
        schema = json.loads((ROOT / 'docs/pes2017-ball-schema.json').read_text())
        self.assertEqual(len(schema['fields']), 65)
        occupied = set()
        blob = bytearray(2048)
        cursor = 256
        expected = {}
        for index, field in enumerate(schema['fields']):
            store = field['stores'][0]
            span = set(range(store['offset'], store['offset'] + store['bytes']))
            self.assertFalse(occupied & span)
            occupied |= span
            source = field['binary_source']
            if source['kind'] == 'relative_float32_array':
                value = [index + i / 4 for i in range(source['elements'])]
                struct.pack_into('<I', blob, source['offset_field'], cursor)
                struct.pack_into('<' + 'f' * len(value), blob, cursor, *value)
                cursor += len(value) * 4
            elif source['kind'] == 'float32':
                value = index + .25
                struct.pack_into('<f', blob, source['offset'], value)
            else:
                value = index
                struct.pack_into('<B' if source['bytes'] == 1 else '<I', blob, source['offset'], value)
            expected[field['name']] = value
        self.assertEqual(len(occupied), 430)
        self.assertEqual(decode(blob, schema, 0)['values'], expected)
    def test_scheduled_integer_store_belongs_to_previous_key(self):
        class Names:
            image_base = 0
            def string(self, value):
                return {0x1000: 'firstCount', 0x1010: 'secondFloat'}[value]
            def offset(self, value):
                return value
        rows = [(0x100, 'push', '0x1000'), (0x105, 'call', '0x2b5bc19'),
                (0x10a, 'push', '0x1010'), (0x10f, 'mov', 'DWORD PTR [edi+0x4],eax'),
                (0x112, 'call', '0x2b5c9a1'), (0x117, 'call', '0x2b5bdb1'),
                (0x11c, 'fstp', 'DWORD PTR [edi+0x8]')]
        fields = describe_reader(Names(), rows)
        self.assertEqual([f['stores'][0]['offset'] for f in fields], [4, 8])
        self.assertTrue(all(f['complete_for_this_key'] for f in fields))
    def test_binary_array_offsets_are_relative_to_object_not_runtime_destination(self):
        fields = [dict(name='scalar', complete_for_this_key=True, stores=[dict(offset=4, bytes=4, storage='float32')]),
                  dict(name='array', complete_for_this_key=True, stores=[dict(offset=8, bytes=8, storage='float32_array', elements=2)])]
        rows = [(1, 'fld', 'DWORD PTR [edi]'), (2, 'fstp', 'DWORD PTR [esi+0x4]'),
                (3, 'mov', 'eax,DWORD PTR [edi+0x4]'), (4, 'push', 'eax'), (5, 'call', '0x40859a8'),
                (6, 'fld', 'DWORD PTR [eax]'), (7, 'fstp', 'DWORD PTR [esi+0x8]'),
                (8, 'fld', 'DWORD PTR [eax+0x4]'), (9, 'fstp', 'DWORD PTR [esi+0xc]')]
        result = binary_layout(rows, fields)
        self.assertEqual(result[0]['binary_source']['offset'], 0)
        self.assertEqual(result[1]['binary_source']['offset_field'], 4)
        data = bytearray(40)
        struct.pack_into('<fI', data, 8, 1.25, 16)
        struct.pack_into('<ff', data, 24, 2.5, 3.75)
        decoded = decode(data, dict(executable_sha256=EXECUTABLE_SHA256, fields=result), 8)
        self.assertEqual(decoded['values'], dict(scalar=1.25, array=[2.5, 3.75]))
        self.assertFalse(decoded['active_runtime_values_verified'])
        struct.pack_into('<I', data, 12, 0xfffffff0)
        with self.assertRaises(ValueError):
            decode(data, dict(executable_sha256=EXECUTABLE_SHA256, fields=result), 8)
    def test_other_build_must_not_reuse_profile_addresses(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'other.exe'
            path.write_bytes(pe_fixture())
            with self.assertRaisesRegex(ValueError, 'differs'):
                recover(path, 'unused; must fail before invoking disassembler')


if __name__ == '__main__':
    unittest.main()
