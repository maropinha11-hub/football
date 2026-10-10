#!/usr/bin/env python3
"""Read-only PES 3 resource inventory. Never loads or executes PS2 code.

AFS names use the optional 48-byte directory addressed after the entry table.
Extraction uses numeric paths, preserves stored bytes, and validates the PES
32-byte/zlib wrapper only when its reported 0x00010600 tag is present.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path


REPORT_HASHES = {
    "executable": "a3d39bf0f1d0030ccd4be17428d1dbdb7010e0b7a06ee545b5d614d378640b53",
    "over": "aa1942fd00fd60c7bdbedea766e94bbe6b7865593a4ca1479c89681e464166f3",
    "game_overlay": "f2e3c4dc6d81a3a8b1908a09a7b295a44137185dc0fe78efd45330a8dd423b92",
}
SELECTED_NAMES = {
    "anime.bin", "anime2.bin", "anime3.bin", "game.mbc",
    "body_lnk.bin", "mon_lnk.bin", "game.ovl", "training_free.ovl",
    "training_common.ovl",
}
MAX_ENTRIES = 100000
MAX_DEPTH = 16


class FormatError(ValueError):
    pass


def digest_file(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def read_region(stream, base, size, offset, length):
    if offset < 0 or length < 0 or offset + length > size:
        raise FormatError("intervalo fora dos limites do arquivo/contêiner")
    stream.seek(base + offset)
    data = stream.read(length)
    if len(data) != length:
        raise FormatError("arquivo truncado durante a leitura")
    return data


def read_afs(stream, base, size):
    signature, count = struct.unpack("<4sI", read_region(stream, base, size, 0, 8))
    if signature != b"AFS\0" or count > MAX_ENTRIES:
        raise FormatError("assinatura AFS ou quantidade de entradas inválida")
    table_end = 8 + count * 8
    table = read_region(stream, base, size, 8, count * 8)
    entries = []
    occupied = []
    for index in range(count):
        offset, length = struct.unpack_from("<II", table, index * 8)
        if offset + length > size or (length and offset < table_end):
            raise FormatError("entrada AFS %d fora dos limites" % index)
        entries.append({"index": index, "offset": offset, "size": length, "name": None})
        if length:
            occupied.append((offset, offset + length))
    occupied.sort()
    if any(left[1] > right[0] for left, right in zip(occupied, occupied[1:])):
        raise FormatError("entradas AFS sobrepostas")

    directory = None
    first_data = occupied[0][0] if occupied else size
    # Some AFS variants put the pointer at first_data - 8 instead. Do not
    # guess names for those layouts: numeric extraction remains possible.
    if table_end + 8 <= first_data:
        name_offset, name_size = struct.unpack("<II", read_region(stream, base, size, table_end, 8))
        if name_offset or name_size:
            if name_offset < table_end + 8 or name_size < count * 48 or name_offset + name_size > size:
                raise FormatError("diretório de nomes AFS inválido")
            if any(start < name_offset + name_size and end > name_offset for start, end in occupied):
                raise FormatError("diretório de nomes AFS sobrepõe uma entrada")
            names = read_region(stream, base, size, name_offset, count * 48)
            for entry in entries:
                raw = names[entry["index"] * 48:entry["index"] * 48 + 32].split(b"\0", 1)[0]
                entry["name"] = raw.decode("utf-8", errors="replace") or None
            directory = {"offset": name_offset, "size": name_size}
    return entries, directory


def unpack_resource(data, max_bytes):
    if len(data) < 32:
        raise FormatError("cabeçalho PES de 32 bytes truncado")
    tag, stored_size, unpacked_size = struct.unpack_from("<III", data)
    if tag != 0x00010600:
        raise FormatError("tipo de compactação não suportado; bytes preservados")
    if stored_size != len(data) - 32:
        raise FormatError("tamanho do payload diverge do cabeçalho PES")
    if unpacked_size > max_bytes:
        raise FormatError("tamanho descompactado excede o limite configurado")
    decoder = zlib.decompressobj()
    try:
        payload = decoder.decompress(data[32:], unpacked_size + 1)
    except zlib.error as exc:
        raise FormatError("fluxo zlib inválido: %s" % exc) from exc
    if (len(payload) != unpacked_size or not decoder.eof
            or decoder.unused_data or decoder.unconsumed_tail):
        raise FormatError("fluxo zlib incompleto, excedente ou de tamanho incorreto")
    return payload


def virtual_to_offset(segments, address, length=1):
    matches = [s["offset"] + address - s["virtual_address"] for s in segments
               if s["type"] == 1 and s["file_size"] and length > 0
               and s["virtual_address"] <= address
               and address + length <= s["virtual_address"] + s["file_size"]]
    if len(matches) != 1:
        raise FormatError("endereço não pertence a um único segmento com bytes")
    return matches[0]


def read_elf(stream, size):
    header = read_region(stream, 0, size, 0, 52)
    if header[:7] != b"\x7fELF\x01\x01\x01":
        raise FormatError("esperado ELF32 little-endian versão 1")
    (kind, machine, version, entry, phoff, shoff, flags, ehsize,
     phsize, phcount, shsize, shcount, shnames) = struct.unpack_from("<HHIIIIIHHHHHH", header, 16)
    if machine != 8 or version != 1 or ehsize != 52 or phsize != 32 or phcount > 4096:
        raise FormatError("cabeçalho ELF/MIPS não suportado")
    programs = read_region(stream, 0, size, phoff, phcount * phsize)
    if shcount:
        if shsize != 40 or shnames >= shcount:
            raise FormatError("tabela de seções ELF inválida")
        read_region(stream, 0, size, shoff, shcount * shsize)
    segments = []
    for index in range(phcount):
        ptype, offset, vaddr, paddr, filesz, memsz, permissions, align = struct.unpack_from("<8I", programs, index * 32)
        if (offset + filesz > size or vaddr + memsz > 2 ** 32
                or (ptype == 1 and filesz > memsz)):
            raise FormatError("segmento ELF fora dos limites")
        segments.append({"index": index, "type": ptype, "offset": offset,
                         "virtual_address": vaddr, "physical_address": paddr,
                         "file_size": filesz, "memory_size": memsz,
                         "flags": permissions, "alignment": align})
    return {"kind": "elf32-mips", "entry_point": entry, "flags": flags,
            "elf_type": kind, "section_count": shcount, "segments": segments}


def safe_label(name):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name or "resource.bin").strip(".")[:80] or "resource.bin"


def write_new(path, data):
    # Never replace an earlier extraction or an input file.
    with Path(path).open("xb") as stream:
        stream.write(data)


def inspect_file(path, extract=None, max_bytes=16 * 1024 * 1024):
    path = Path(path)
    size = path.stat().st_size
    sha = digest_file(path)
    report = {"file": path.name, "size": size, "sha256": sha,
              "matches_supplied_report": [key for key, value in REPORT_HASHES.items() if sha == value]}
    with path.open("rb") as stream:
        prefix = read_region(stream, 0, size, 0, min(64, size))
        if prefix.startswith(b"\x7fELF"):
            report.update(read_elf(stream, size))
        elif prefix.startswith(b"AFS\0"):
            report["kind"] = "afs"
            report["containers"] = []
            report["resources"] = []
            report["exports"] = []
            budget = [MAX_ENTRIES]

            def visit(base, region_size, indices, display_path):
                if len(indices) > MAX_DEPTH:
                    raise FormatError("AFS excede o limite de profundidade")
                entries, directory = read_afs(stream, base, region_size)
                budget[0] -= len(entries)
                if budget[0] < 0:
                    raise FormatError("AFS excede o limite total de entradas")
                report["containers"].append({"indices": indices, "path": display_path,
                                             "absolute_offset": base, "size": region_size,
                                             "entry_count": len(entries), "name_directory": directory})
                for entry in entries:
                    child_indices = indices + [entry["index"]]
                    child_base = base + entry["offset"]
                    child_path = display_path + "/%04d:%s" % (entry["index"], entry["name"] or "<sem nome>")
                    head = read_region(stream, child_base, entry["size"], 0, min(64, entry["size"]))
                    if head.startswith(b"AFS\0"):
                        visit(child_base, entry["size"], child_indices, child_path)
                        continue
                    resource = dict(entry, indices=child_indices, path=child_path,
                                    absolute_offset=child_base, prefix_hex=head[:32].hex())
                    report["resources"].append(resource)
                    # MWo modules preserve their name even if AFS names are absent.
                    ovl_name = None
                    if head.startswith(b"MWo3"):
                        match = re.search(rb"[A-Za-z0-9_]+\.ovl\x00", head)
                        if match:
                            ovl_name = match[0][:-1].decode("ascii")
                            resource["overlay_name"] = ovl_name
                    selected_name = (entry["name"] or ovl_name or "").lower()
                    if selected_name not in SELECTED_NAMES or extract is None:
                        continue
                    if entry["size"] > max_bytes:
                        raise FormatError("recurso selecionado excede o limite de extração")
                    stored = read_region(stream, child_base, entry["size"], 0, entry["size"])
                    label = "-".join("%04d" % i for i in child_indices) + "-" + safe_label(selected_name)
                    wrapped = len(stored) >= 4 and struct.unpack_from("<I", stored)[0] == 0x00010600
                    # Validate first; do not publish invalid decompressed data.
                    unpacked = unpack_resource(stored, max_bytes) if wrapped else None
                    target = Path(extract) / sha[:16]
                    target.mkdir(parents=True, exist_ok=True)
                    write_new(target / (label + ".stored"), stored)
                    exported = {"path": child_path, "stored_file": sha[:16] + "/" + label + ".stored",
                                "sha256": hashlib.sha256(stored).hexdigest(), "size": len(stored)}
                    if unpacked is not None:
                        write_new(target / (label + ".payload"), unpacked)
                        exported.update(payload_file=sha[:16] + "/" + label + ".payload",
                                        payload_size=len(unpacked), payload_sha256=hashlib.sha256(unpacked).hexdigest())
                    report["exports"].append(exported)

            visit(0, size, [], path.name)
            report["selected_resource_count"] = sum(
                (r["name"] or r.get("overlay_name") or "").lower() in SELECTED_NAMES
                for r in report["resources"])
        elif prefix.startswith(b"MWo3"):
            report["kind"] = "mw-overlay"
            report["header_hex"] = prefix.hex()
        else:
            report["kind"] = "unclassified"
            report["prefix_hex"] = prefix[:32].hex()
    return report


def main():
    parser = argparse.ArgumentParser(description="Inventariar ELF/AFS do PES 3 sem executar seus bytes")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extract", type=Path, help="Extrair apenas recursos selecionados em arquivos novos")
    parser.add_argument("--max-resource-mib", type=int, default=16)
    args = parser.parse_args()
    if not 1 <= args.max_resource_mib <= 128:
        parser.error("--max-resource-mib deve estar entre 1 e 128")
    if args.output.exists():
        parser.error("o relatório de saída já existe; escolha um caminho novo")
    results, errors = [], []
    for path in args.files:
        try:
            results.append(inspect_file(path, args.extract, args.max_resource_mib * 1024 * 1024))
        except (OSError, FormatError) as exc:
            errors.append({"file": path.name, "error": str(exc)})
    document = {"schema_version": 1, "source": "files_read_this_run",
                "supplied_report_hashes_are_external_claims": True,
                "files": results, "errors": errors}
    write_new(args.output, (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print("%d arquivo(s) inventariado(s); %d erro(s). Relatório: %s" % (len(results), len(errors), args.output))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
