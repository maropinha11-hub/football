"""Inventory native clips and generate bounded procedural action profiles.

This does not bake animations, change contact events, or claim new captures.
The native selector remains responsible for function, foot, timing, special
state and ball reach. Source/profile pair counts are metadata-compatible
candidates, not a claim that every candidate has been rendered or played.

    python3 tools/animations/build_situational_catalog.py
    python3 tools/animations/build_situational_catalog.py --check
    python3 tools/animations/build_situational_catalog.py --inventory /tmp/catalog.json
"""
from __future__ import annotations

import argparse
import bisect
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRECTORY = Path("data/media/animations")
UTILITY_MODEL = Path("data/media/objects/players/player.object")
HEADER = Path("src/onthepitch/player/humanoid/situational_profiles.hpp")
MANIFEST = Path("config/situational-motion-catalog.json")
KNOWN_TYPES = frozenset(("movement", "ballcontrol", "trap", "shortpass",
                         "longpass", "highpass", "shot", "deflect", "catch",
                         "interfere", "trip", "sliding", "special"))
KIND_VALUES = {"None": 0, "Pass": 1, "Shot": 2, "Cross": 3,
               "Header": 4, "Control": 5}
CONTACT_TYPES = frozenset(("ballcontrol", "trap", "shortpass", "longpass",
                           "highpass", "shot", "deflect", "catch", "interfere",
                           "sliding"))
BALL_ACTIONS = {"shortpass": "Pass", "shot": "Shot", "highpass": "Cross",
                "ballcontrol": "Control", "trap": "Control"}
FOOT_PARTS = frozenset(("left_foot", "right_foot"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n"


def numbers(value: str) -> tuple[float, ...]:
    result = tuple(float(x.strip()) for x in value.split(","))
    if not all(math.isfinite(x) for x in result):
        raise ValueError("Non-finite animation value")
    return result


def qnormalize(q):
    length = math.sqrt(sum(x*x for x in q))
    if length < 1e-8:
        raise ValueError("Zero quaternion in source clip")
    return tuple(x / length for x in q)


def qmul(a, b):
    x, y, z, w = a
    xx, yy, zz, ww = b
    return (w*xx+x*ww+y*zz-z*yy, w*yy-x*zz+y*ww+z*xx,
            w*zz+x*yy-y*xx+z*ww, w*ww-x*xx-y*yy-z*zz)


def rotate(q, p):
    return qmul(qmul(q, (*p, 0)), (-q[0], -q[1], -q[2], q[3]))[:3]


def slerp(a, b, factor):
    a, b = qnormalize(a), qnormalize(b)
    dot = sum(x*y for x, y in zip(a, b))
    if dot < 0:
        b, dot = tuple(-x for x in b), -dot
    dot = max(-1., min(1., dot))
    if dot > .9995:
        return qnormalize(tuple(x+(y-x)*factor for x, y in zip(a, b)))
    angle = math.acos(dot)
    a_weight = math.sin((1-factor)*angle)/math.sin(angle)
    b_weight = math.sin(factor*angle)/math.sin(angle)
    return tuple(a_weight*x+b_weight*y for x, y in zip(a, b))


def sample(keys, frame, rotation=False):
    frames = [key[0] for key in keys]
    after = bisect.bisect_left(frames, frame)
    if after == 0:
        return keys[0][1]
    if after == len(keys):
        return keys[-1][1]
    a_frame, a = keys[after-1]
    b_frame, b = keys[after]
    factor = (frame-a_frame)/(b_frame-a_frame)
    if rotation:
        return slerp(a, b, factor)
    return tuple(x+(y-x)*factor for x, y in zip(a, b))


def utility_hierarchy(root=ROOT):
    """Read the same geometry origins used by AnimCollection::AddExtraTouches."""
    output = []

    def visit(node, parent):
        if node.tag == "node":
            name = node.findtext("name")
            offset = numbers(node.findtext("position", "0,0,0"))
            geometries = []
            for geometry in node.findall("geometry"):
                geometries.append((geometry.findtext("name"),
                                   numbers(geometry.findtext("position", "0,0,0"))))
            index = len(output)
            output.append({"name": name, "parent": parent,
                           "offset": offset, "geometries": geometries})
            parent = index
        for child in node.findall("node"):
            visit(child, parent)

    visit(ET.parse(root/UTILITY_MODEL).getroot(), -1)
    if len(output) != 13:
        raise ValueError("Expected native 13-joint utility model")
    return output


def velocity(keys, outgoing=False):
    if len(keys) < 2:
        return 0., 0.
    (a_frame, a), (b_frame, b) = keys[-2:] if outgoing else keys[:2]
    raw = math.hypot(b[0]-a[0], b[1]-a[1])*100/(b_frame-a_frame)
    quantized = 0. if raw < 1.8 else 3.5 if raw < 4.2 else 5. if raw < 6 else 7.
    return raw, quantized


def parse_source(path: Path, root=ROOT):
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    metadata = dict(re.findall(r"<([a-zA-Z0-9_]+)>\s*([^<]*?)\s*</\1>", text))
    tracks, contacts = {}, []
    for line in text.splitlines():
        fields = line.strip().split(",")
        if not fields or fields[0].startswith("<") or len(fields) < 4:
            continue
        if fields[0] == "extension":
            if fields[1] != "football" or (len(fields)-2) % 4:
                raise ValueError(f"Unsupported event in {path}")
            for start in range(2, len(fields), 4):
                contacts.append((int(fields[start]), numbers(",".join(fields[start+1:start+4]))))
            continue
        step = 4 if fields[0] == "player" else 5
        if (len(fields)-1) % step:
            raise ValueError(f"Invalid track shape: {path}:{fields[0]}")
        keys = []
        for start in range(1, len(fields), step):
            value = numbers(",".join(fields[start+1:start+step]))
            if step == 5:
                value = qnormalize(value)
            keys.append((int(fields[start]), value))
        if keys != sorted(keys) or len({x[0] for x in keys}) != len(keys):
            raise ValueError(f"Unordered source keys in {path}")
        tracks[fields[0]] = keys
    kind = metadata.get("type", "")
    if kind not in KNOWN_TYPES:
        raise ValueError(f"Unknown native animation type {kind!r}: {path}")
    if "player" not in tracks:
        raise ValueError(f"Missing root track in {path}")
    return tracks, sorted(contacts), metadata, raw


def contact_geometry(tracks, frame, ball, hierarchy):
    root_position = sample(tracks["player"], frame)
    positions, rotations, geometries = [], [], []
    for bone in hierarchy:
        local = sample(tracks[bone["name"]], frame, rotation=True)
        if bone["parent"] < 0:
            position = tuple(x+y for x, y in zip(root_position, bone["offset"]))
            global_q = local
        else:
            parent = bone["parent"]
            offset = rotate(rotations[parent], bone["offset"])
            position = tuple(x+y for x, y in zip(positions[parent], offset))
            global_q = qmul(rotations[parent], local)
        positions.append(position)
        rotations.append(global_q)
        for name, local_position in bone["geometries"]:
            offset = rotate(global_q, local_position)
            point = tuple(x+y for x, y in zip(position, offset))
            geometries.append((math.dist(ball, point), name))
    # Native utility geometry origins classify an event, not skin contact. The
    # running game still proves contact against the deformed native mesh.
    distance, part = min(geometries)
    direction = rotate(rotations[0], (0., -1., 0.))
    return part, distance, positions[0], direction


def source_kind(kind, part):
    if kind not in BALL_ACTIONS:
        return None
    if part == "head" and kind in ("shortpass", "shot", "highpass"):
        return "Header"
    if part not in FOOT_PARTS:
        return None
    return BALL_ACTIONS[kind]


def profiles():
    output = []
    for kind, kind_value in KIND_VALUES.items():
        for effort in range(3):
            for pressure in range(3):
                for turn in range(3):
                    for reach in range(3):
                        if kind == "None" and any((effort, pressure, turn, reach)):
                            continue
                        if kind == "Header" and turn == 2:
                            continue
                        if kind == "Control" and (effort == 2 or reach == 2):
                            continue
                        e, p, t, r = (x*.5 for x in (effort, pressure, turn, reach))
                        for pattern in range(1 if kind == "None" else 32):
                            eligible={9: {"Control"}, 10: {"Control"}, 11: {"Header"},
                                      12: {"Pass", "Shot", "Cross"}, 13: {"Pass", "Shot"},
                                      14: {"Shot", "Cross"},15: {"Control"},16: {"Control"},17: {"Header"},18: {"Control"},19: {"Control","Pass"},20: {"Pass","Shot","Cross"},21: {"Shot","Cross"},22: {"Control","Pass"},23: {"Header"},24: {"Pass","Cross"},25: {"Pass","Shot"},26: {"Control"},27: {"Control"}}
                            if pattern in eligible and kind not in eligible[pattern]:
                                continue
                            output.append({
                                "id": (kind_value*128+effort*27+pressure*9+turn*3+reach)*32+pattern,
                                "kind": kind, "effort": effort, "pressure": pressure,
                                "turn": turn, "reach": reach, "pattern": pattern,
                                "trunkGain": round(.78+e*.12+t*.13+r*.11+p*.04, 5),
                                "armGain": round(.76+p*.15+t*.10+r*.10+e*.08, 5),
                                "followThroughGain": round(.80+e*.16+t*.08+r*.10-p*.04, 5),
                            })
    return sorted(output, key=lambda profile: profile["id"])



def matching_profiles(record, all_profiles):
    """Conservative quantized neighborhood of the authored contact, not reach IK."""
    action = record["action_kind"]
    if action is None:
        return []
    metadata, contact = record["metadata"], record["contact"]
    if any(metadata.get(key) for key in ("incoming_special_state", "outgoing_special_state",
                                         "incoming_retain_state", "outgoing_retain_state")):
        return []
    maximum_power = min(1., max(0., float(metadata.get("touch_maxpowerfactor", "1"))))
    source_reach = min(1., math.hypot(contact["pelvis_offset"][0], contact["pelvis_offset"][1])/.85)
    direction = numbers(metadata.get("balldirection", "0,-1,0"))
    facing = contact["body_direction"]
    angle = math.atan2(facing[0]*direction[1]-facing[1]*direction[0],
                       facing[0]*direction[0]+facing[1]*direction[1])
    source_turn = abs(angle)/math.pi
    # Half the bin width permits rounding; authored directional freedom adds
    # only its own stated deviation. It does not grant arbitrary spin or reach.
    turn_margin = .2500001 + max(0., float(metadata.get("outgoingballdirection_maxdeviation", "0")))/math.pi
    compatible = []
    for profile in all_profiles:
        if profile["kind"] != action:
            continue
        if profile["pattern"] in (2,12) and contact["ball"][2] < .45:
            continue
        if profile["effort"]*.5 > maximum_power+.000001:
            continue
        if abs(profile["reach"]*.5-source_reach) > .2500001:
            continue
        if abs(profile["turn"]*.5-source_turn) > turn_margin:
            continue
        compatible.append(profile["id"])
    return compatible


def build_catalog(root=ROOT):
    hierarchy = utility_hierarchy(root)
    all_profiles = profiles()
    records = []
    source_hash = hashlib.sha256((root/UTILITY_MODEL).read_bytes())
    for path in sorted((root/SOURCE_DIRECTORY).rglob("*.anim")):
        relative = path.relative_to(root).as_posix()
        tracks, events, metadata, raw = parse_source(path, root)
        # Imported non-contact locomotion has its own retarget manifest and
        # support/loop checks. It cannot supply a contextual ball action, and
        # must not invalidate the authored action catalog's source digest.
        if metadata.get("imported_mocap")=="true" and metadata["type"]=="movement" and not events:
            continue
        source_hash.update(relative.encode()+b"\0"+raw)
        excluded = "templates" in path.parts or "luxury" in path.parts
        frame_end = max(keys[-1][0] for keys in tracks.values())
        raw_in, quantized_in = velocity(tracks["player"])
        raw_out, quantized_out = velocity(tracks["player"], outgoing=True)
        record = {
            "id": digest(relative.encode())[:16], "source": relative,
            "sha256": digest(raw), "native_type": metadata["type"],
            "native_loader_enabled": not excluded, "frame_end": frame_end,
            "incoming_speed_mps": round(raw_in, 6),
            "incoming_native_speed_mps": quantized_in,
            "outgoing_speed_mps": round(raw_out, 6),
            "outgoing_native_speed_mps": quantized_out,
            "mirrored_by_native_loader": not excluded,
            "metadata": metadata, "contact": None, "action_kind": None,
        }
        if events:
            frame, ball = events[0]
            if not (0 <= frame <= frame_end):
                raise ValueError(f"Event outside authored source duration: {relative}")
            part, distance, pelvis, facing = contact_geometry(tracks, frame, ball, hierarchy)
            if metadata["type"] == "trap" and "chest" in path.name:
                part = "trunk"
            classification = "native_utility_geometry_origin"
            if metadata["type"] in ("shortpass", "shot") and "header" in path.name and "arm" in part:
                part = "head"
                classification = "native_header_semantics_with_runtime_head_skin_gate"
            record["contact"] = {
                "frame": frame, "ball": ball, "part": part,
                "classification": classification,
                "origin_distance_m": round(distance, 6),
                "pelvis_offset": tuple(round(x-y, 6) for x, y in zip(ball, pelvis)),
                "body_direction": tuple(round(x, 6) for x in facing),
                "event_count": len(events),
            }
            if not excluded:
                record["action_kind"] = source_kind(metadata["type"], part)
        record["profile_ids"] = matching_profiles(record, all_profiles)
        records.append(record)
    return {"source_digest": source_hash.hexdigest(), "profiles": all_profiles,
            "sources": records}


def summary(catalog):
    records, all_profiles = catalog["sources"], catalog["profiles"]
    active = [r for r in records if r["native_loader_enabled"]]
    contextual = [r for r in active if r["profile_ids"]]
    pairs = sum(len(record["profile_ids"]) for record in contextual)
    return {
        "schema": 2,
        "description": "Bounded procedural upper-body gain profiles over original native animation clips",
        "source_digest": catalog["source_digest"],
        "counts": {
            "authored_source_files": len(records), "native_loader_source_files": len(active),
            "native_loader_excluded_files": len(records)-len(active),
            "native_source_types": dict(sorted(Counter(r["native_type"] for r in active).items())),
            "profiles": len(all_profiles),
            "profiles_per_kind": dict(sorted(Counter(p["kind"] for p in all_profiles).items())),
            "action_sources_with_compatible_profiles": len(contextual),
            "action_sources_per_kind": dict(sorted(Counter(r["action_kind"] for r in contextual).items())),
            "metadata_compatible_source_profile_pairs": pairs,
            "metadata_compatible_pairs_including_native_mirrors": pairs*2,
            "new_captured_clips": 0, "new_baked_animation_files": 0,
            "exhaustively_rendered_contexts": 0,
        },
        "coordinates": {"effort": "max(power,difficulty), normalized 0..1",
                        "pressure": "opponent proximity/physical pressure, normalized 0..1",
                        "turn": "abs(signed body-local action turn)/pi",
                        "reach": "min(1, horizontal ball offset from pelvis / 0.85m)",
                        "bins": [0, .5, 1], "patterns": ["compact", "open_lateral", "airborne_counterbalance", "low_drive", "inside_sweep", "lofted_release", "back_turn", "first_time", "pressure_brace", "cushioned_control", "directed_control", "reactive_header", "volley", "outside_strike", "instep_power", "shoulder_cushion", "thigh_cushion", "head_cushion", "chest_absorption", "low_reach_balance", "lateral_release", "full_follow_through", "soft_inside", "braced_header", "overlap_rotation", "plant_release", "outside_control", "recovery_control", "late_balance", "near_pressure", "soft_follow", "long_counter"]},
        "constraints": [
            "Native function, contact part, event frame, foot and special/retainer-state eligibility stay authoritative",
            "Header has no full-turn torso profile; Control excludes maximum effort and maximum reach profiles",
            "Contact classification uses utility-model origins with native header semantic correction; runtime deformed head/foot skin contact must still pass",
            "Source/profile counts include only the authored reach/turn neighborhood and permitted maximum power",
            "CPU/player pressure may choose another gain profile without cloning animation tracks",
            "Profiles adjust torso/arm response; they never change root, legs, ball position or contact timing",
            "Continuous parameters permit intermediate responses; these are not additional authored or captured clips",
            "Metadata compatibility is an eligibility bound, not proof that every context is realistic or collision-free",
        ],
        "reproduce": "python3 tools/animations/build_situational_catalog.py --check",
        "inspect_sources": "python3 tools/animations/build_situational_catalog.py --inventory /tmp/situational-inventory.json",
    }


def cpp_header(catalog):
    counts = summary(catalog)["counts"]
    lines = [
        "// Generated by tools/animations/build_situational_catalog.py; do not hand edit.",
        "// Procedural gain profiles, not captured clips. Native contact eligibility remains authoritative.",
        "#pragma once", "", '#include "situational_action.hpp"', "#include <cmath>",
        "#include <algorithm>", "#include <cstddef>", "#include <cstdint>", "", "namespace football_situations {", "",
        "struct Profile {", "  std::uint16_t id;", "  ActionKind kind;",
        "  std::uint8_t effort, pressure, turn, reach, pattern;",
        "  float trunkGain, armGain, followThroughGain;", "};", "",
        f'constexpr const char *kCatalogSourceDigest="{catalog["source_digest"]}";',
        f'constexpr std::size_t kCatalogSourceFiles={counts["authored_source_files"]};',
        f'constexpr std::size_t kCatalogCompatiblePairs={counts["metadata_compatible_pairs_including_native_mirrors"]};',
        "constexpr Profile kProfiles[]={",
    ]
    for profile in catalog["profiles"]:
        values = ",".join(str(profile[key]) for key in ("effort", "pressure", "turn", "reach", "pattern"))
        gains = ",".join(f'{profile[key]:.5f}f' for key in ("trunkGain", "armGain", "followThroughGain"))
        lines.append(f'  {{{profile["id"]},ActionKind::{profile["kind"]},{values},{gains}}},')
    lines.extend((
        "};", "constexpr std::size_t kProfileCount=sizeof(kProfiles)/sizeof(kProfiles[0]);", "",
        "inline float profileUnit(float x){ return std::isfinite(x)?(x<0?0:(x>1?1:x)):0; }", "",
        "inline const Profile &profileFor(ActionKind kind,float effort,float pressure,float turn,float reach,unsigned pattern=0){",
        "  const float query[4]={profileUnit(effort)*2,profileUnit(pressure)*2,",
        "                        profileUnit(turn)*2,profileUnit(reach)*2};",
        "  const Profile *best=&kProfiles[0]; float bestCost=1e9f;",
        "  for(const Profile &profile:kProfiles){",
        "    if(profile.kind!=kind || profile.pattern!=std::min(pattern,31u))continue;",
        "    const float delta[4]={query[0]-profile.effort,query[1]-profile.pressure,",
        "                          query[2]-profile.turn,query[3]-profile.reach};",
        "    const float cost=delta[0]*delta[0]+delta[1]*delta[1]+delta[2]*delta[2]+delta[3]*delta[3];",
        "    if(cost<bestCost){bestCost=cost;best=&profile;}",
        "  }", "  return *best;", "}", "", "} // namespace football_situations", "",
    ))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if tracked generated files are stale")
    parser.add_argument("--inventory", type=Path, help="Write detailed per-source metadata and compatible profile IDs")
    args = parser.parse_args()
    catalog = build_catalog()
    artifacts = {ROOT/HEADER: cpp_header(catalog), ROOT/MANIFEST: canonical(summary(catalog))}
    for path, expected in artifacts.items():
        if args.check:
            if not path.exists() or path.read_text() != expected:
                raise SystemExit(f"Generated catalog is stale: {path.relative_to(ROOT)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected)
    if args.inventory:
        args.inventory.parent.mkdir(parents=True, exist_ok=True)
        args.inventory.write_text(canonical(catalog))
    print(json.dumps(summary(catalog)["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
