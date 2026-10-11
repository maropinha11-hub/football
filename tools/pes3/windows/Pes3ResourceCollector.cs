// Streaming, read-only collector for the resource-bank paths in SLES_519.12.
// Uses only .NET Framework APIs available in Windows PowerShell 5.1.
using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace FPSoccer.Pes3 {
    public sealed class ResourceExport {
        public string Source, SourceSha256, ResourceId, StoredFile, StoredSha256;
        public long SourceBytes, AbsoluteOffset, StoredBytes;
        public uint HeaderTag, UnpackedBytes, ReportedUnpackedBytes;
        public int[] Indices;
    }
    public static class ResourceCollector {
        public const string ExecutableSha256 = "a3d39bf0f1d0030ccd4be17428d1dbdb7010e0b7a06ee545b5d614d378640b53";
        private const long MaxResource = 16 * 1024 * 1024;
        private sealed class Entry { public long Offset, Size; }
        private sealed class Target {
            public string Id, Label;
            public int[] Path, Counts;
            public uint ReportedSize;
            public Target(string id, string label, int[] path, int[] counts, uint size) {
                Id = id; Label = label; Path = path; Counts = counts; ReportedSize = size;
            }
        }
        // Parent/index/count descriptors recovered at 0x0129D440 (92 records).
        private static readonly Target[] Targets = {
            new Target("0x00470000", "body_lnk.bin", new int[]{14,2,0}, new int[]{17,4,2}, 1315982),
            new Target("0x00470001", "mon_lnk.bin", new int[]{14,2,1}, new int[]{17,4,2}, 678945),
            new Target("0x00370000", "anime2.bin", new int[]{14,0,0}, new int[]{17,4,3}, 1302320),
            new Target("0x00370001", "anime3.bin", new int[]{14,0,1}, new int[]{17,4,3}, 1300928),
            new Target("0x00080000", "anime.bin", new int[]{1,1,2,0,0}, new int[]{17,2,4,3,2}, 3835920),
            new Target("0x00080001", "game.mbc", new int[]{1,1,2,0,1}, new int[]{17,2,4,3,2}, 1750)
        };
        private static byte[] Read(FileStream file, long baseOffset, long size, long offset, int count) {
            if (baseOffset < 0 || size < 0 || offset < 0 || count < 0 ||
                offset > size || count > size - offset || baseOffset > file.Length || size > file.Length - baseOffset)
                throw new InvalidDataException("Intervalo fora do arquivo/AFS.");
            file.Position = baseOffset + offset;
            byte[] data = new byte[count]; int done = 0;
            while (done < count) {
                int got = file.Read(data, done, count - done);
                if (got == 0) throw new EndOfStreamException("Arquivo truncado.");
                done += got;
            }
            return data;
        }
        private static uint U32(byte[] bytes, int offset) {
            return (uint)(bytes[offset] | bytes[offset+1] << 8 | bytes[offset+2] << 16 | bytes[offset+3] << 24);
        }
        private static Entry[] Afs(FileStream file, long baseOffset, long size, int expectedCount) {
            byte[] header = Read(file, baseOffset, size, 0, 8);
            if (U32(header, 0) != 0x00534641 || U32(header, 4) != expectedCount)
                throw new InvalidDataException("Assinatura/contagem AFS difere dos descritores SLES_519.12.");
            long tableEnd = 8 + expectedCount * 8;
            byte[] table = Read(file, baseOffset, size, 8, expectedCount * 8);
            Entry[] entries = new Entry[expectedCount]; List<Entry> occupied = new List<Entry>();
            for (int index = 0; index < expectedCount; ++index) {
                Entry entry = new Entry { Offset = U32(table, index * 8), Size = U32(table, index * 8 + 4) };
                if (entry.Offset > size || entry.Size > size - entry.Offset || (entry.Size > 0 && entry.Offset < tableEnd))
                    throw new InvalidDataException("Entrada AFS fora dos limites.");
                entries[index] = entry; if (entry.Size > 0) occupied.Add(entry);
            }
            occupied.Sort((left, right) => left.Offset.CompareTo(right.Offset));
            for (int index = 1; index < occupied.Count; ++index)
                if (occupied[index-1].Offset + occupied[index-1].Size > occupied[index].Offset)
                    throw new InvalidDataException("Entradas AFS sobrepostas.");
            long first = occupied.Count > 0 ? occupied[0].Offset : size;
            if (tableEnd + 8 <= first) {
                byte[] pointer = Read(file, baseOffset, size, tableEnd, 8);
                long offset = U32(pointer, 0), length = U32(pointer, 4);
                if (offset != 0 || length != 0) {
                    if (offset < tableEnd + 8 || length < expectedCount * 48 || offset > size || length > size - offset)
                        throw new InvalidDataException("Diretorio de nomes AFS invalido.");
                    foreach (Entry entry in occupied)
                        if (entry.Offset < offset + length && entry.Offset + entry.Size > offset)
                            throw new InvalidDataException("Diretorio AFS sobrepoe recurso.");
                }
            }
            return entries;
        }
        private static string HashRegion(FileStream file, long offset, long size) {
            file.Position = offset;
            using (SHA256 sha = SHA256.Create()) {
                byte[] buffer = new byte[65536]; long left = size;
                while (left > 0) {
                    int got = file.Read(buffer, 0, (int)Math.Min(left, buffer.Length));
                    if (got == 0) throw new EndOfStreamException();
                    sha.TransformBlock(buffer, 0, got, buffer, 0); left -= got;
                }
                sha.TransformFinalBlock(new byte[0], 0, 0);
                return BitConverter.ToString(sha.Hash).Replace("-", "").ToLowerInvariant();
            }
        }
        public static string HashFile(string path) {
            using (FileStream file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
                return HashRegion(file, 0, file.Length);
        }
        public static ResourceExport[] Collect(string source, string outputDirectory) {
            List<ResourceExport> exports = new List<ResourceExport>();
            using (FileStream file = new FileStream(source, FileMode.Open, FileAccess.Read, FileShare.Read)) {
                // Validate every selected path before creating any output.
                List<Entry> found = new List<Entry>();
                foreach (Target target in Targets) {
                    long baseOffset = 0, size = file.Length;
                    for (int level = 0; level < target.Path.Length; ++level) {
                        Entry[] entries = Afs(file, baseOffset, size, target.Counts[level]);
                        Entry entry = entries[target.Path[level]];
                        baseOffset += entry.Offset; size = entry.Size;
                    }
                    if (size < 32 || size > MaxResource) throw new InvalidDataException("Recurso fora do limite de coleta.");
                    byte[] header = Read(file, baseOffset, size, 0, 32);
                    uint tag = U32(header, 0);
                    // The study reports game.mbc as a raw 1750-byte payload
                    // after its 32-byte header. Preserve it without assuming
                    // that its tag/length fields describe a zlib stream.
                    bool rawMbc = target.Label == "game.mbc" && size == 1782;
                    if (!rawMbc && (tag != 0x00010600 || U32(header, 4) != size - 32 || U32(header, 8) > MaxResource))
                        throw new InvalidDataException("Cabecalho compactado PES divergente; nenhum recurso desta AFS foi exportado.");
                    found.Add(new Entry { Offset = baseOffset, Size = size });
                }
                string sourceHash = HashRegion(file, 0, file.Length);
                Directory.CreateDirectory(outputDirectory);
                for (int index = 0; index < Targets.Length; ++index) {
                    Target target = Targets[index]; Entry entry = found[index];
                    string hash = HashRegion(file, entry.Offset, entry.Size);
                    string name = target.Id.Substring(2) + "-" + target.Label + "-" + hash.Substring(0,16) + ".stored";
                    string destination = Path.Combine(outputDirectory, name);
                    if (File.Exists(destination)) {
                        if (new FileInfo(destination).Length != entry.Size || HashFile(destination) != hash)
                            throw new IOException("Saida anterior divergente: " + name);
                    } else {
                        file.Position = entry.Offset;
                        using (FileStream output = new FileStream(destination, FileMode.CreateNew, FileAccess.Write, FileShare.None)) {
                            byte[] buffer = new byte[65536]; long left = entry.Size;
                            while (left > 0) {
                                int got = file.Read(buffer, 0, (int)Math.Min(left, buffer.Length));
                                if (got == 0) throw new EndOfStreamException();
                                output.Write(buffer, 0, got); left -= got;
                            }
                        }
                        if (HashFile(destination) != hash) {
                            File.Delete(destination); throw new IOException("Arquivo mudou durante a leitura.");
                        }
                    }
                    byte[] header = Read(file, entry.Offset, entry.Size, 0, 32);
                    exports.Add(new ResourceExport { Source = Path.GetFileName(source), SourceBytes = file.Length,
                        SourceSha256 = sourceHash, ResourceId = target.Id, StoredFile = name, StoredSha256 = hash,
                        AbsoluteOffset = entry.Offset, StoredBytes = entry.Size, HeaderTag = U32(header,0),
                        UnpackedBytes = U32(header,8), ReportedUnpackedBytes = target.ReportedSize,
                        Indices = (int[])target.Path.Clone() });
                }
            }
            return exports.ToArray();
        }
    }
}
