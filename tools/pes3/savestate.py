#!/usr/bin/env python3
"""Read bounded PCSX2 ZIP/Zstandard states without running emulator code."""
import argparse
import hashlib
import io
import json
import struct
import zipfile
import zlib
from pathlib import Path

MAX_ARCHIVE = 64 * 1024 * 1024
MAX_MEMBER = 64 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MEMORY_SIZES = {"eeMemory.bin": 32 * 1024 * 1024, "Scratchpad.bin": 16384,
                "iopMemory.bin": 2 * 1024 * 1024, "eeHwRegs.bin": 65536,
                "iopHwRegs.bin": 65536, "vu0Memory.bin": 4096,
                "vu1Memory.bin": 16384, "vu0MicroMem.bin": 4096,
                "vu1MicroMem.bin": 16384}
REQUIRED = {"PCSX2 Savestate Version.id", "PCSX2 Internal Structures.dat",
            "eeMemory.bin", "Scratchpad.bin"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decode_zstd(payload, expected):
    try:
        import zstandard
    except ImportError as exc:
        raise ValueError("ZIP Zstandard requer o pacote Python zstandard") from exc
    try:
        header = zstandard.get_frame_parameters(payload)
        if header.window_size > MAX_MEMBER:
            raise ValueError("janela Zstandard excede o limite")
        if header.content_size not in (expected, zstandard.CONTENTSIZE_UNKNOWN):
            raise ValueError("tamanho do frame Zstandard diverge do ZIP")
        return zstandard.ZstdDecompressor().decompress(
            payload, max_output_size=expected, allow_extra_data=False)
    except zstandard.ZstdError as exc:
        raise ValueError("frame Zstandard inválido") from exc


class SaveState:
    def __init__(self, source):
        source = Path(source)
        if source.stat().st_size > MAX_ARCHIVE:
            raise ValueError("save state excede o limite de leitura")
        raw = source.read_bytes()
        self.members = {}
        inventory = []
        spans = []
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if not 4 <= len(entries) <= 64 or sum(f.file_size for f in entries) > MAX_TOTAL:
                raise ValueError("inventário ZIP excede os limites")
            for entry in entries:
                name = entry.filename
                if (not name or name in self.members or name in (".", "..")
                        or any(c in name for c in ("/", "\\", "\x00"))
                        or any(ord(c) < 32 for c in name)):
                    raise ValueError("nome de membro inválido ou repetido")
                if entry.flag_bits & 1 or entry.compress_type not in (0, 8, 93):
                    raise ValueError("membro criptografado ou compressão não suportada")
                if not 0 < entry.file_size <= MAX_MEMBER:
                    raise ValueError("tamanho de membro fora do limite")
                if name in MEMORY_SIZES and entry.file_size != MEMORY_SIZES[name]:
                    raise ValueError("tamanho de memória PCSX2 divergente")
                at = entry.header_offset
                if at < 0 or at + 30 > archive.start_dir:
                    raise ValueError("cabeçalho local fora dos limites")
                header = struct.unpack_from("<IHHHHHIIIHH", raw, at)
                if header[0] != 0x04034B50 or header[3] != entry.compress_type or header[2] & 1:
                    raise ValueError("cabeçalho ZIP local divergente")
                start = at + 30 + header[-2] + header[-1]
                end = start + entry.compress_size
                encoding = "utf-8" if header[2] & 0x800 else "cp437"
                local_name = raw[at + 30:at + 30 + header[-2]].decode(encoding)
                if local_name != name or end > archive.start_dir:
                    raise ValueError("payload ou nome ZIP divergente")
                if any(at < other_end and end > other_start for other_start, other_end in spans):
                    raise ValueError("membros ZIP sobrepostos")
                spans.append((at, end))
                contents = (decode_zstd(raw[start:end], entry.file_size)
                            if entry.compress_type == 93 else archive.read(entry))
                if len(contents) != entry.file_size or zlib.crc32(contents) & 0xFFFFFFFF != entry.CRC:
                    raise ValueError("tamanho ou CRC de membro inválido")
                self.members[name] = contents
                inventory.append({"name": name, "bytes": len(contents),
                                  "sha256": digest(contents), "compression": entry.compress_type})
        if not REQUIRED <= self.members.keys():
            raise ValueError("save state não contém a memória completa necessária")
        version = self.members["PCSX2 Savestate Version.id"]
        if len(version) < 20:
            raise ValueError("identificador PCSX2 truncado")
        self.metadata = {"file": source.name, "bytes": len(raw), "sha256": digest(raw),
                         "format_version": hex(struct.unpack_from("<I", version)[0]),
                         "pcsx2_version": version[4:20].split(b"\0", 1)[0].decode("ascii"),
                         "members": inventory}

    @property
    def ram(self):
        return self.members["eeMemory.bin"]

    @property
    def scratch(self):
        return self.members["Scratchpad.bin"]

    def cpu_metadata(self):
        # Layout inspected in PCSX2 v2.8.2 SaveState.cpp and R5900.h.
        # No guessing another build's internal C++ layout.
        if (self.metadata["pcsx2_version"] != "v2.8.2"
                or self.metadata["format_version"] != "0x9a590000"):
            return {"status": "unsupported_layout"}
        contents = self.members["PCSX2 Internal Structures.dat"]
        tag = b"cpuRegs" + bytes(25)
        position = contents.find(tag)
        if position < 0 or contents.find(tag, position + 1) >= 0:
            raise ValueError("tag cpuRegs ausente ou ambígua")
        start = position + 32
        if start + 688 > len(contents):
            raise ValueError("registradores EE truncados")
        registers = [struct.unpack_from("<2Q", contents, start + 16 * i) for i in range(32)]
        if registers[0] != (0, 0):
            raise ValueError("registrador zero divergente")
        return {"status": "decoded", "tag_offset": position,
                "gp": hex(registers[28][0]), "sp": hex(registers[29][0]),
                "ra": hex(registers[31][0]),
                "pc": hex(struct.unpack_from("<I", contents, start + 680)[0]),
                "delay_slot": struct.unpack_from("<I", contents, start + 676)[0],
                "scope": "Snapshot metadata only; replay calls use explicit function arguments, not a resumed frame."}


def main():
    parser = argparse.ArgumentParser(description="Conferir save state PCSX2 sem executar o jogo")
    parser.add_argument("state", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extract", type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.extract and args.extract.exists():
        parser.error("escolha saídas novas")
    try:
        state = SaveState(args.state)
        report = dict(state.metadata, cpu=state.cpu_metadata())
        if args.extract:
            args.extract.mkdir(parents=True)
            for name, contents in state.members.items():
                with (args.extract / name).open("xb") as destination:
                    destination.write(contents)
        with args.output.open("x") as destination:
            destination.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({k: v for k, v in report.items() if k != "members"}, indent=2))
    except (OSError, ValueError, zipfile.BadZipFile, UnicodeError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
