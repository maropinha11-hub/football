#!/usr/bin/env python3
"""Inventory original .anim tracks and authored ball contacts, without edits.

This is source data, not the runtime collection: mirrors, generated movement
clips, extra touches and physical feasibility checks happen in C++.
"""
import argparse
import collections
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def finite_values(tokens):
    values = [float(token) for token in tokens]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("valor não finito")
    return values


def frame_number(token):
    value = finite_values([token])[0]
    if value < 0 or int(value) != value:
        raise ValueError("índice de quadro inválido")
    return int(value)


def read_animation(path, root):
    data = path.read_bytes()
    lines = data.decode("utf-8").splitlines()
    tracks, touches, metadata_lines = {}, [], []
    xml_started = False
    for line in lines:
        if not line.strip():
            continue
        if line.lstrip().startswith("<"):
            xml_started = True
        if xml_started:
            metadata_lines.append(line)
            continue
        tokens = [token.strip() for token in line.split(",")]
        if tokens[0] == "extension":
            if len(tokens) < 2 or tokens[1] != "football" or (len(tokens) - 2) % 4:
                raise ValueError("extensão desconhecida ou incompleta")
            for i in range(2, len(tokens), 4):
                touches.append({"frame": frame_number(tokens[i]),
                                "position_m": finite_values(tokens[i + 1:i + 4])})
            continue
        stride = 4 if tokens[0] == "player" else 5
        if (len(tokens) - 1) % stride or len(tokens) == 1 or tokens[0] in tracks:
            raise ValueError("canal de animação incompleto ou duplicado")
        keys = []
        for i in range(1, len(tokens), stride):
            keys.append({"frame": frame_number(tokens[i]),
                         "values": finite_values(tokens[i + 1:i + stride])})
        if any(a["frame"] >= b["frame"] for a, b in zip(keys, keys[1:])):
            raise ValueError("chaves de animação fora de ordem")
        tracks[tokens[0]] = keys
    if "player" not in tracks:
        raise ValueError("canal de translação player ausente")
    tree = ET.fromstring("<metadata>" + "\n".join(metadata_lines) + "</metadata>")
    properties = {element.tag: (element.text or "").strip() for element in tree}
    if not properties.get("type"):
        raise ValueError("tipo da animação ausente")
    last_frame = max(key["frame"] for keys in tracks.values() for key in keys)
    if any(touch["frame"] > last_frame for touch in touches):
        raise ValueError("contato além do último quadro")
    relative = path.relative_to(root)
    return {"path": relative.as_posix(), "sha256": hashlib.sha256(data).hexdigest(),
            "type": properties["type"], "source_last_frame": last_frame,
            "source_endpoint_ms": last_frame * 10,
            "channels": list(tracks), "key_count": sum(map(len, tracks.values())),
            "authored_contacts": touches, "properties": properties,
            "runtime_load_policy": "template" if relative.parts[0] == "templates"
                                   else "omitted_luxury" if "luxury" in relative.as_posix()
                                   else "loaded_and_mirrored"}


def build_catalogue(root):
    animations, errors = [], []
    for path in sorted(root.rglob("*.anim")):
        try:
            animations.append(read_animation(path, root))
        except (OSError, ValueError, ET.ParseError) as exc:
            errors.append({"path": path.relative_to(root).as_posix(), "error": str(exc)})
    if not animations and not errors:
        raise ValueError("nenhum arquivo .anim encontrado")
    return {"schema_version": 1, "source": "GameplayFootball_authored_files",
            "simulation_step_ms": 10,
            "runtime_generated_clips_and_contacts_included": False,
            "animation_count": len(animations),
            "types": dict(sorted(collections.Counter(a["type"] for a in animations).items())),
            "authored_contact_count": sum(len(a["authored_contacts"]) for a in animations),
            "channel_sets": [list(channels) for channels in sorted(
                {tuple(sorted(a["channels"])) for a in animations})],
            "animations": animations, "errors": errors}


def main():
    default_root = Path(__file__).resolve().parents[2] / "data/media/animations"
    parser = argparse.ArgumentParser(description="Catalogar as animações e contatos da base atual")
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        catalogue = build_catalogue(args.root)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(catalogue, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("%d animações; %d contatos escritos; %d erro(s)." % (
        catalogue["animation_count"], catalogue["authored_contact_count"], len(catalogue["errors"])))
    return 1 if catalogue["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
