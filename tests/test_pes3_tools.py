#!/usr/bin/env python3
"""Structural fixtures, independent of any proprietary PES files."""
import hashlib
import importlib.util
import io
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_tool(name):
    spec = importlib.util.spec_from_file_location("pes3_" + name, ROOT / "tools/pes3" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inspector = load_tool("inspect")
catalogue = load_tool("catalogue")
fpsa = load_tool("fpsa")


def afs_fixture(resources, names=True):
    count = len(resources)
    data = bytearray(2048)
    struct.pack_into("<4sI", data, 0, b"AFS\0", count)
    for index, (name, payload) in enumerate(resources):
        offset = len(data)
        struct.pack_into("<II", data, 8 + index * 8, offset, len(payload))
        data.extend(payload)
        data.extend(b"\0" * ((-len(data)) % 2048))
    if names:
        directory = len(data)
        for name, payload in resources:
            encoded = name.encode("ascii")
            data.extend(encoded.ljust(32, b"\0") + b"\0" * 12 + struct.pack("<I", len(payload)))
        struct.pack_into("<II", data, 8 + count * 8, directory, count * 48)
    return data


def wrapped_fixture(payload):
    stored = zlib.compress(payload)
    return struct.pack("<III", 0x00010600, len(stored), len(payload)) + b"\0" * 20 + stored


def elf_fixture():
    data = bytearray(160)
    data[:16] = b"\x7fELF\x01\x01\x01" + b"\0" * 9
    struct.pack_into("<HHIIIIIHHHHHH", data, 16,
                     2, 8, 1, 0x1000, 52, 0, 0, 52, 32, 2, 40, 0, 0)
    struct.pack_into("<8I", data, 52, 1, 128, 0x1000, 0x1000, 32, 64, 5, 16)
    struct.pack_into("<8I", data, 84, 1, 0, 0x2000, 0x2000, 0, 128, 6, 16)
    return data


class AFSTests(unittest.TestCase):
    def test_names_and_numeric_offsets(self):
        data = afs_fixture([("anime.bin", b"abc"), ("unused", b"defgh")])
        entries, directory = inspector.read_afs(io.BytesIO(data), 0, len(data))
        self.assertEqual([e["name"] for e in entries], ["anime.bin", "unused"])
        self.assertEqual([e["offset"] for e in entries], [2048, 4096])
        self.assertEqual(directory, {"offset": 6144, "size": 96})

    def test_nameless_archive(self):
        data = afs_fixture([("ignored", b"123")], names=False)
        entries, directory = inspector.read_afs(io.BytesIO(data), 0, len(data))
        self.assertIsNone(entries[0]["name"])
        self.assertIsNone(directory)

    def test_empty_entries(self):
        data = afs_fixture([("empty", b""), ("full", b"123")])
        entries, _ = inspector.read_afs(io.BytesIO(data), 0, len(data))
        self.assertEqual(entries[0]["size"], 0)

    def test_bad_tables_and_regions(self):
        original = afs_fixture([("one", b"123"), ("two", b"456")])
        cases = [b"AFS\0", b"bad\0" + b"\0" * 4]
        for offset, value in [(4, inspector.MAX_ENTRIES + 1), (8, 12),
                              (8, len(original)), (16, 2048),
                              (24, len(original)), (28, 1), (24, 2048)]:
            mutated = bytearray(original)
            struct.pack_into("<I", mutated, offset, value)
            cases.append(mutated)
        for case in cases:
            with self.subTest(case=bytes(case[:32])):
                with self.assertRaises(inspector.FormatError):
                    inspector.read_afs(io.BytesIO(case), 0, len(case))

    def test_nested_extraction_preserves_input_and_payload(self):
        payload = b"animation sample" * 200
        stored = wrapped_fixture(payload)
        inner = afs_fixture([("anime.bin", stored), ("unrelated.bin", b"no export")])
        outer = afs_fixture([("boot.afs", inner)])
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "DATA_F.AFS"
            source.write_bytes(outer)
            before = inspector.digest_file(source)
            result = inspector.inspect_file(source, Path(folder) / "out")
            self.assertEqual(inspector.digest_file(source), before)
            self.assertEqual(len(result["containers"]), 2)
            self.assertEqual(len(result["resources"]), 2)
            self.assertEqual(result["selected_resource_count"], 1)
            self.assertEqual(result["resources"][0]["indices"], [0, 0])
            self.assertEqual(result["resources"][0]["absolute_offset"], 4096)
            export = result["exports"][0]
            self.assertEqual((Path(folder) / "out" / export["stored_file"]).read_bytes(), stored)
            self.assertEqual((Path(folder) / "out" / export["payload_file"]).read_bytes(), payload)
            self.assertEqual(export["payload_sha256"], hashlib.sha256(payload).hexdigest())
            with self.assertRaises(FileExistsError):
                inspector.inspect_file(source, Path(folder) / "out")

    def test_embedded_invalid_afs_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "bad.afs"
            source.write_bytes(afs_fixture([("inner.afs", b"AFS\0")]))
            with self.assertRaises(inspector.FormatError):
                inspector.inspect_file(source)

    def test_depth_is_bounded(self):
        data = afs_fixture([])
        for _ in range(inspector.MAX_DEPTH + 1):
            data = afs_fixture([("nested.afs", data)])
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "deep.afs"
            source.write_bytes(data)
            with self.assertRaises(inspector.FormatError):
                inspector.inspect_file(source)

    def test_overlay_name_without_directory(self):
        overlay = b"MWo3" + b"\0" * 12 + b"game.ovl\0" + b"\0" * 64
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "OVER.AFS"
            source.write_bytes(afs_fixture([("unused", overlay)], names=False))
            result = inspector.inspect_file(source, Path(folder) / "out")
            self.assertEqual(result["resources"][0]["overlay_name"], "game.ovl")
            self.assertEqual(len(result["exports"]), 1)

    def test_path_labels_cannot_escape_export_directory(self):
        for name in ["../../game.ovl", "C:\\Users\\file", ".", "", "evil\nname"]:
            label = inspector.safe_label(name)
            self.assertTrue(label)
            self.assertNotIn("/", label)
            self.assertNotIn("\\", label)
            self.assertFalse(label.startswith("."))


class CompressionTests(unittest.TestCase):
    def test_strict_zlib_roundtrip(self):
        for payload in [b"", b"abcd", bytes(range(256)) * 50]:
            self.assertEqual(inspector.unpack_resource(wrapped_fixture(payload), 16384), payload)

    def test_truncation_trailing_bytes_and_wrong_lengths(self):
        original = wrapped_fixture(b"abcd" * 200)
        cases = [original[:20], original[:-1], original + b"\0"]
        for word_offset, value in [(0, 0x00010300), (4, 1), (8, 799), (8, 801)]:
            modified = bytearray(original)
            struct.pack_into("<I", modified, word_offset, value)
            cases.append(modified)
        trailing = bytearray(original + b"trailing")
        struct.pack_into("<I", trailing, 4, len(trailing) - 32)
        cases.append(trailing)
        for case in cases:
            with self.subTest(case=bytes(case[:12])):
                with self.assertRaises(inspector.FormatError):
                    inspector.unpack_resource(case, 16384)

    def test_checksum_corruption_is_rejected(self):
        corrupted = bytearray(wrapped_fixture(b"abcd" * 200))
        corrupted[-1] ^= 1
        with self.assertRaises(inspector.FormatError):
            inspector.unpack_resource(corrupted, 16384)

    def test_output_limit_prevents_large_decompression(self):
        with self.assertRaises(inspector.FormatError):
            inspector.unpack_resource(wrapped_fixture(b"x" * 100000), 1024)
        forged = bytearray(wrapped_fixture(b"x" * 100000))
        struct.pack_into("<I", forged, 8, 10)
        with self.assertRaises(inspector.FormatError):
            inspector.unpack_resource(forged, 1024)


class ELFTests(unittest.TestCase):
    def test_file_mapping_and_zero_file_segment(self):
        data = elf_fixture()
        parsed = inspector.read_elf(io.BytesIO(data), len(data))
        self.assertEqual(parsed["kind"], "elf32-mips")
        self.assertEqual(inspector.virtual_to_offset(parsed["segments"], 0x1008, 4), 136)
        for address in [0x1020, 0x2000, 0xFFFF]:
            with self.assertRaises(inspector.FormatError):
                inspector.virtual_to_offset(parsed["segments"], address)

    def test_ambiguous_mapping_is_rejected(self):
        data = elf_fixture()
        parsed = inspector.read_elf(io.BytesIO(data), len(data))
        with self.assertRaises(inspector.FormatError):
            inspector.virtual_to_offset(parsed["segments"] * 2, 0x1000)

    def test_bad_elf_headers_and_segments(self):
        original = elf_fixture()
        for offset, fmt, value in [(4, "B", 2), (5, "B", 2), (18, "H", 62),
                                   (42, "H", 16), (56, "I", 150), (68, "I", 100),
                                   (72, "I", 16), (60, "I", 0xFFFFFFF0)]:
            data = bytearray(original)
            struct.pack_into("<" + fmt, data, offset, value)
            with self.subTest(offset=offset):
                with self.assertRaises(inspector.FormatError):
                    inspector.read_elf(io.BytesIO(data), len(data))


class CatalogueTests(unittest.TestCase):
    def test_actual_authored_animation_inventory(self):
        result = catalogue.build_catalogue(ROOT / "data/media/animations")
        self.assertEqual(result["animation_count"], 293)
        self.assertEqual(result["errors"], [])
        header = next(a for a in result["animations"] if a["path"] == "pass/idle/nonbase/000_header.anim")
        self.assertEqual(header["type"], "shortpass")
        self.assertEqual(header["authored_contacts"][0]["frame"], 25)
        self.assertAlmostEqual(header["authored_contacts"][0]["position_m"][2], 1.649999)
        self.assertFalse(result["runtime_generated_clips_and_contacts_included"])

    def test_invalid_animation_is_reported(self):
        bad_samples = [
            "player,0,nan,0,0\n<type>movement</type>",
            "player,0,0,0\n<type>movement</type>",
            "player,1,0,0,0,0,0,0,0\n<type>movement</type>",
            "player,0,0,0,0\nextension,football,2,0,0,0\n<type>shortpass</type>",
            "player,0,0,0,0\n<type>movement",
        ]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for index, sample in enumerate(bad_samples):
                (root / ("bad%d.anim" % index)).write_text(sample)
            result = catalogue.build_catalogue(root)
            self.assertEqual(len(result["errors"]), len(bad_samples))
            self.assertEqual(result["animation_count"], 0)

    def test_empty_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                catalogue.build_catalogue(Path(folder))


class CLITests(unittest.TestCase):
    def test_inspector_exit_status_and_no_report_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "truncated.afs"
            source.write_bytes(b"AFS\0")
            output = Path(folder) / "report.json"
            command = [sys.executable, str(ROOT / "tools/pes3/inspect.py"), str(source), "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            report_bytes = output.read_bytes()
            self.assertEqual(len(json.loads(report_bytes)["errors"]), 1)
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), report_bytes)


def fpsa_fixture():
    rotations = [0, 0, 0, 32767] * 18
    records = b"".join(struct.pack("<4h3f72h", 0, 0, 0, 32767, float(i), -400, 0, *rotations)
                       for i in range(2))
    block = (struct.pack("<7I", 0x20011119, 0x20000002, 0x40000000, 60, 356, 0, 0)
             + records + struct.pack("<IfIfI", 2, 2.0, 28, 0.0, 192))
    return (b"FPSANM14" + struct.pack("<6I", 1, 32, 14, 19, 164, 0)
            + struct.pack("<4I", 0, 0x40000000, 48, len(block)) + block)


class FPSATests(unittest.TestCase):
    def parse(self, data, metadata=None):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.fpsa"
            path.write_bytes(data)
            return fpsa.read_bundle(path, metadata)

    def test_original_times_and_pose_count_are_preserved(self):
        data, parsed = self.parse(fpsa_fixture())
        self.assertEqual(parsed["clips"], 1)
        self.assertEqual(parsed["poses"], 2)
        self.assertEqual(parsed["entries"][0]["key_end_times_bits"], ["0x40000000", "0x0"])
        self.assertEqual(parsed["sha256"], hashlib.sha256(data).hexdigest())
        self.assertFalse(parsed["matches_v14_bundle"])

    def test_truncated_and_extra_bytes_are_rejected(self):
        data = fpsa_fixture()
        for corrupted in [data[:20], data[:-1], data + b"\0"]:
            with self.subTest(size=len(corrupted)):
                with self.assertRaises(ValueError):
                    self.parse(corrupted)

    def test_corrupt_indices_keys_and_numbers_are_rejected(self):
        original = fpsa_fixture()
        for offset, value in [(8, 20001), (12, 16), (20, 18), (24, 160), (28, 1),
                              (32, 1), (36, 0), (40, 0), (44, 99999),
                              (48, 0), (52, 0), (60, 0), (64, 0xffffffff),
                              (84, 0x7fc00000), (404, 0), (408, 0), (412, 0),
                              (416, 0x40000000), (420, 0)]:
            data = bytearray(original)
            struct.pack_into("<I", data, offset, value)
            with self.subTest(offset=offset):
                with self.assertRaises(ValueError):
                    self.parse(data)

    def test_catalogue_must_match_hashes_offsets_and_times(self):
        data, parsed = self.parse(fpsa_fixture())
        metadata = {"bundle_sha256": parsed["sha256"], "bundle_bytes": len(data),
                    "clips": 1, "poses": 2, "entries": parsed["entries"]}
        self.parse(data, metadata)
        for key, wrong in [("bundle_sha256", "wrong"), ("poses", 3)]:
            with self.assertRaises(ValueError):
                self.parse(data, dict(metadata, **{key: wrong}))
        changed = json.loads(json.dumps(metadata))
        changed["entries"][0]["block_sha256"] = "wrong"
        with self.assertRaises(ValueError):
            self.parse(data, changed)


if __name__ == "__main__":
    unittest.main()
