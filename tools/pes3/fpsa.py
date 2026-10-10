#!/usr/bin/env python3
"""Validate the supplied numeric FPSANM14 container, without resampling it."""
import hashlib
import math
import struct
from pathlib import Path


EXPECTED_BUNDLE_SHA256 = "c40813d6b23f77834877ba4a5863ae54f8b829f6fc8f2c606d373c618d26bbe5"


def read_bundle(path, catalogue=None):
    path = Path(path)
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("contêiner excede 32 MiB")
    data = path.read_bytes()
    if len(data) < 32 or data[:8] != b"FPSANM14":
        raise ValueError("assinatura FPSANM14 ausente")
    count, directory, version, bones, stride, reserved = struct.unpack_from("<6I", data, 8)
    if (not 0 < count <= 20000 or directory != 32 or version != 14
            or bones != 19 or stride != 164 or reserved != 0 or 32 + count * 16 > len(data)):
        raise ValueError("cabeçalho FPSANM14 inválido")
    entries = []
    next_offset = 32 + 16 * count
    total_poses = 0
    for index in range(count):
        clip, duration_bits, offset, length = struct.unpack_from("<4I", data, directory + index * 16)
        if clip != index or offset != next_offset or length < 32 or offset + length > len(data):
            raise ValueError("índice/intervalo de clip inválido")
        block = memoryview(data)[offset:offset + length]
        tag, flags, raw_duration, word_c, table = struct.unpack_from("<5I", block)
        duration = struct.unpack_from("<f", block, 8)[0]
        if (tag != 0x20011119 or flags != 0x20000002 or raw_duration != duration_bits
                or word_c != 60 or not 0 < duration <= 4096 or table > length - 4):
            raise ValueError("formato/duração de clip inválido")
        poses = struct.unpack_from("<I", block, table)[0]
        if not 0 < poses <= 512 or table != 28 + 164 * poses or length != 32 + 172 * poses:
            raise ValueError("tabela de poses inválida")
        endpoints, previous = [], 0
        for key in range(poses):
            endpoint, pose_offset = struct.unpack_from("<fI", block, table + 4 + key * 8)
            if pose_offset != 28 + key * 164:
                raise ValueError("offset de pose inválido")
            if key == poses - 1:
                if endpoint != 0:
                    raise ValueError("sentinela final inválida")
            elif not math.isfinite(endpoint) or not previous < endpoint <= duration:
                raise ValueError("tempos de chave inválidos")
            previous = endpoint
            endpoints.append(endpoint)
            if not all(math.isfinite(v) for v in struct.unpack_from("<3f", block, pose_offset + 8)):
                raise ValueError("translação não finita")
        entry = {"clip": clip, "duration_bits": hex(duration_bits), "duration_original_units": duration,
                 "poses": poses, "bundle_offset": offset, "block_bytes": length,
                 "block_sha256": hashlib.sha256(block).hexdigest(),
                 "key_end_times_bits": [hex(struct.unpack("<I", struct.pack("<f", t))[0]) for t in endpoints]}
        entries.append(entry)
        total_poses += poses
        next_offset += length
    if next_offset != len(data):
        raise ValueError("bytes excedentes no contêiner")
    sha = hashlib.sha256(data).hexdigest()
    if catalogue is not None:
        if (catalogue.get("bundle_sha256") != sha or catalogue.get("bundle_bytes") != len(data)
                or catalogue.get("clips") != count or catalogue.get("poses") != total_poses
                or len(catalogue.get("entries", [])) != count):
            raise ValueError("catálogo não corresponde ao contêiner")
        for actual, expected in zip(entries, catalogue["entries"]):
            if any(expected.get(key) != value for key, value in actual.items()):
                raise ValueError("catálogo diverge do clip %d" % actual["clip"])
    return data, {"schema_version": 1, "kind": "FPSANM14", "sha256": sha,
                  "bytes": len(data), "clips": count, "poses": total_poses,
                  "bones": bones, "entries": entries,
                  "matches_v14_bundle": sha == EXPECTED_BUNDLE_SHA256}
