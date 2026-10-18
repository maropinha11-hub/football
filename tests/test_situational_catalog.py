"""Source/eligibility proofs for the generated procedural action catalog.

These checks validate metadata and the profile lookup ABI. They deliberately
do not label unrendered contextual combinations as captured or tested motion.
"""
import ctypes
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "situational_catalog", ROOT/"tools/animations/build_situational_catalog.py")
catalogue = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalogue)


class CatalogSources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = catalogue.build_catalog()
        cls.sources = cls.catalog["sources"]
        cls.profiles = cls.catalog["profiles"]

    def test_inventory_is_repeatable_and_generated_files_are_current(self):
        self.assertEqual(catalogue.canonical(self.catalog),
                         catalogue.canonical(catalogue.build_catalog()))
        self.assertEqual((ROOT/catalogue.HEADER).read_text(),
                         catalogue.cpp_header(self.catalog))
        self.assertEqual(json.loads((ROOT/catalogue.MANIFEST).read_text()),
                         catalogue.summary(self.catalog))

    def test_source_ids_hashes_and_paths_are_real_and_unique(self):
        self.assertEqual(len({r["id"] for r in self.sources}), len(self.sources))
        self.assertEqual(len({r["source"] for r in self.sources}), len(self.sources))
        for record in self.sources:
            with self.subTest(record["source"]):
                path = ROOT/record["source"]
                self.assertTrue(path.is_file())
                self.assertEqual(catalogue.digest(path.read_bytes()), record["sha256"])
                self.assertEqual(catalogue.digest(record["source"].encode())[:16], record["id"])

    def test_native_types_and_authored_events_are_preserved(self):
        expected_parts = {name for bone in catalogue.utility_hierarchy()
                          for name, unused in bone["geometries"]}
        for record in self.sources:
            with self.subTest(record["source"]):
                tracks, events, metadata, unused = catalogue.parse_source(ROOT/record["source"])
                self.assertIn(record["native_type"], catalogue.KNOWN_TYPES)
                self.assertEqual(metadata, record["metadata"])
                self.assertEqual(bool(events), record["native_type"] in catalogue.CONTACT_TYPES)
                if events:
                    self.assertEqual(events[0][0], record["contact"]["frame"])
                    self.assertEqual(events[0][1], record["contact"]["ball"])
                    self.assertLessEqual(record["contact"]["frame"], record["frame_end"])
                    self.assertIn(record["contact"]["part"], expected_parts)
                self.assertEqual(len(tracks), 14)

    def test_function_part_and_foot_combinations_are_not_invented(self):
        indexed = {p["id"]: p for p in self.profiles}
        for record in self.sources:
            for identifier in record["profile_ids"]:
                with self.subTest(record["source"], profile=identifier):
                    profile = indexed[identifier]
                    self.assertEqual(profile["kind"], record["action_kind"])
                    contact = record["contact"]
                    if profile["kind"] == "Header":
                        self.assertEqual(contact["part"], "head")
                        self.assertIn(record["native_type"], ("shortpass", "highpass", "shot"))
                    else:
                        self.assertIn(contact["part"], catalogue.FOOT_PARTS)
                        self.assertEqual(catalogue.BALL_ACTIONS[record["native_type"]], profile["kind"])

    def test_chest_trip_and_retainer_clips_stay_native(self):
        for record in self.sources:
            if (not record["native_loader_enabled"] or
                    record["native_type"] in ("trip", "special", "deflect", "sliding", "interfere") or
                    (record["native_type"] == "trap" and record["contact"]["part"] not in catalogue.FOOT_PARTS) or
                    any(record["metadata"].get(key) for key in
                        ("incoming_special_state", "outgoing_special_state", "incoming_retain_state", "outgoing_retain_state"))):
                self.assertEqual(record["profile_ids"], [], record["source"])

    def test_known_source_contacts_do_not_depend_on_filename_alone(self):
        indexed = {r["source"]: r for r in self.sources}
        header = indexed["data/media/animations/pass/idle/nonbase/000_header.anim"]
        chest = indexed["data/media/animations/trap/idle/highballs/000_chest.anim"]
        control = indexed["data/media/animations/ballcontrol/idle/000.anim"]
        self.assertEqual(header["contact"]["part"], "head")
        self.assertEqual(header["action_kind"], "Header")
        self.assertEqual(chest["contact"]["part"], "trunk")
        self.assertIsNone(chest["action_kind"])
        self.assertIn(control["contact"]["part"], catalogue.FOOT_PARTS)
        self.assertEqual(control["action_kind"], "Control")
        # Raised arms are closer to the utility marker in these authored
        # headers. The corrected native loader requires actual HEAD contact.
        ambiguous = indexed["data/media/animations/pass/idle/nonbase/090_header.anim"]
        self.assertEqual(ambiguous["contact"]["part"], "head")
        self.assertEqual(ambiguous["contact"]["classification"],
                         "native_header_semantics_with_runtime_head_skin_gate")
        self.assertEqual(ambiguous["action_kind"], "Header")
        self.assertTrue(ambiguous["profile_ids"])

    def test_native_speed_quantization_matches_real_root_keys(self):
        for record in self.sources:
            tracks, unused, unused_metadata, unused_raw = catalogue.parse_source(ROOT/record["source"])
            for outgoing, prefix in ((False, "incoming"), (True, "outgoing")):
                keys = tracks["player"][-2:] if outgoing else tracks["player"][:2]
                if len(keys) < 2:
                    expected = 0
                else:
                    (a_frame, a), (b_frame, b) = keys
                    expected = math.hypot(b[0]-a[0], b[1]-a[1])*100/(b_frame-a_frame)
                self.assertAlmostEqual(expected, record[prefix+"_speed_mps"], places=5)
                self.assertIn(record[prefix+"_native_speed_mps"], (0, 3.5, 5, 7))

    def test_candidate_counts_are_conditional_and_do_not_claim_captures(self):
        counts = catalogue.summary(self.catalog)["counts"]
        candidates = sum(len(record["profile_ids"]) for record in self.sources)
        self.assertEqual(counts["metadata_compatible_source_profile_pairs"], candidates)
        self.assertEqual(counts["metadata_compatible_pairs_including_native_mirrors"], candidates*2)
        self.assertEqual(counts["authored_source_files"], len(self.sources))
        self.assertLess(candidates, len(self.sources)*len(self.profiles)//10)
        self.assertEqual(counts["new_baked_animation_files"], 0)
        self.assertEqual(counts["new_captured_clips"], 0)
        self.assertEqual(counts["exhaustively_rendered_contexts"], 0)

    def test_candidate_power_and_geometric_neighborhood_are_constrained(self):
        indexed = {p["id"]: p for p in self.profiles}
        for record in self.sources:
            if not record["profile_ids"]:
                continue
            contact, metadata = record["contact"], record["metadata"]
            source_reach = min(1., math.hypot(*contact["pelvis_offset"][:2])/.85)
            direction = catalogue.numbers(metadata.get("balldirection", "0,-1,0"))
            facing = contact["body_direction"]
            turn = abs(math.atan2(facing[0]*direction[1]-facing[1]*direction[0],
                                  facing[0]*direction[0]+facing[1]*direction[1]))/math.pi
            turn_margin = .2500001+max(0., float(metadata.get("outgoingballdirection_maxdeviation", "0")))/math.pi
            for identifier in record["profile_ids"]:
                profile = indexed[identifier]
                self.assertLessEqual(profile["effort"]*.5, float(metadata.get("touch_maxpowerfactor", "1"))+.000001)
                if profile["pattern"] in (2,12):
                    self.assertGreaterEqual(record["contact"]["ball"][2], .45)
                self.assertLessEqual(abs(profile["reach"]*.5-source_reach), .2500001)
                self.assertLessEqual(abs(profile["turn"]*.5-turn), turn_margin)

    def test_profile_ids_are_stable_and_gains_are_bounded(self):
        self.assertEqual(len({p["id"] for p in self.profiles}), len(self.profiles))
        for profile in self.profiles:
            expected = (catalogue.KIND_VALUES[profile["kind"]]*128+
                        profile["effort"]*27+profile["pressure"]*9+
                        profile["turn"]*3+profile["reach"])
            self.assertEqual(profile["id"], expected*16+profile["pattern"])
            for field in ("trunkGain", "armGain", "followThroughGain"):
                self.assertGreaterEqual(profile[field], .7)
                self.assertLessEqual(profile[field], 1.2)
            if profile["kind"] == "Header":
                self.assertLess(profile["turn"], 2)
            if profile["kind"] == "Control":
                self.assertLess(profile["reach"], 2)
                self.assertLess(profile["effort"], 2)

    def test_parser_rejects_unknown_types_nonfinite_values_and_invalid_tracks(self):
        with tempfile.TemporaryDirectory(prefix="situational-source-") as folder:
            source = Path(folder)/"bad.anim"
            for text in ("player,0,0,0,0\n<type>invented</type>\n",
                         "player,0,nan,0,0\n<type>movement</type>\n",
                         "player,0,0,0\n<type>movement</type>\n",
                         "player,0,0,0,0\nbody,0,0,0,0,0\n<type>movement</type>\n"):
                source.write_text(text)
                with self.subTest(text=text):
                    with self.assertRaises(ValueError):
                        catalogue.parse_source(source)


@unittest.skipUnless(shutil.which("g++"), "g++ unavailable")
class CompiledProfileLookup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix="situational-profile-abi-")
        folder = Path(cls.folder.name)
        source = folder/"profiles.cpp"
        source.write_text('''
#include "situational_profiles.hpp"
extern "C" unsigned query(int kind,float effort,float pressure,float turn,float reach,unsigned pattern){
  return football_situations::profileFor(
    static_cast<football_situations::ActionKind>(kind),effort,pressure,turn,reach,pattern).id;
}
''')
        subprocess.run(["g++", "-std=c++14", "-Wall", "-Wextra", "-Werror",
                        "-shared", "-fPIC", "-I", str(ROOT/catalogue.HEADER.parent),
                        str(source), "-o", str(folder/"profiles.so")],
                       check=True, capture_output=True)
        cls.library = ctypes.CDLL(str(folder/"profiles.so"))
        query = cls.library.query
        query.argtypes = [ctypes.c_int]+[ctypes.c_float]*4+[ctypes.c_uint]
        query.restype = ctypes.c_uint
        cls.query = staticmethod(lambda kind, effort, pressure, turn, reach, pattern=0: query(kind, effort, pressure, turn, reach, pattern))

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_every_profile_can_be_selected_without_alias_or_wrong_category(self):
        for profile in catalogue.profiles():
            self.assertEqual(self.query(catalogue.KIND_VALUES[profile["kind"]],
                                        profile["effort"]*.5, profile["pressure"]*.5,
                                        profile["turn"]*.5, profile["reach"]*.5, profile["pattern"]),
                             profile["id"])

    def test_category_constraints_clamp_unsupported_extremes(self):
        indexed = {p["id"]: p for p in catalogue.profiles()}
        header = indexed[self.query(4, 1, 1, 1, 1)]
        self.assertEqual(header["kind"], "Header")
        self.assertLess(header["turn"], 2)
        control = indexed[self.query(5, 1, 1, 1, 1)]
        self.assertEqual(control["kind"], "Control")
        self.assertLess(control["effort"], 2)
        self.assertLess(control["reach"], 2)

    def test_nonfinite_out_of_range_and_unknown_kind_are_deterministic(self):
        self.assertEqual(self.query(1, -10, -10, -10, -10), self.query(1, 0, 0, 0, 0))
        self.assertEqual(self.query(1, 10, 10, 10, 10), self.query(1, 1, 1, 1, 1))
        self.assertEqual(self.query(1, float("nan"), float("inf"), -float("inf"), 0),
                         self.query(1, 0, 0, 0, 0))
        self.assertEqual(self.query(99, 1, 1, 1, 1), 0)


if __name__ == "__main__":
    unittest.main()
