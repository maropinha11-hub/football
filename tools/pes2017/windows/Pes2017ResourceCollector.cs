// Read-only CRI CPK/UTF metadata reader. Written for this project; no game code.
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Security.Cryptography;

namespace FPSoccer.Pes2017 {
    public sealed class Resource {
        public string Source, Path, StoredFile, StoredSha256, Encoding;
        public long Offset, StoredBytes, DeclaredExtractBytes;
    }
    public sealed class Scan {
        public string Source, SourceSha256, HeaderSha256, TocSha256;
        public long SourceBytes, TocOffset, ContentOffset, ExportedBytes;
        public bool HeaderMasked, TocMasked;
        public int EntryCount;
        public Resource[] Resources;
        public string[] Skipped;
    }
    public static class Collector {
        public const int MaxResource = 24 * 1024 * 1024;
        const int MaxTable = 64 * 1024 * 1024;
        static readonly UTF8Encoding Utf8 = new UTF8Encoding(false, true);
        sealed class Column { public string Name; public int Type, Storage, Offset; }
        sealed class Table {
            public byte[] Bytes; public int Count, RowOffset, RowWidth, StringOffset, DataOffset, Size;
            public bool Masked; public List<Column> Columns = new List<Column>();
            public Table(byte[] packet) {
                Bytes = (byte[])packet.Clone();
                if (Bytes.Length < 32) throw new InvalidDataException("UTF truncado.");
                if (Encoding.ASCII.GetString(Bytes,0,4) != "@UTF") {
                    uint key = 0x655f;
                    for (int i=0;i<Bytes.Length;i++) { Bytes[i] ^= (byte)key; key = unchecked(key * 0x4115); }
                    Masked = true;
                }
                if (Encoding.ASCII.GetString(Bytes,0,4) != "@UTF") throw new InvalidDataException("Tabela UTF desconhecida.");
                Size = checked((int)BE(Bytes,4,4)+8);
                int version=(int)BE(Bytes,8,2);
                RowOffset = (int)BE(Bytes,10,2)+8; StringOffset=checked((int)BE(Bytes,12,4)+8);
                DataOffset=checked((int)BE(Bytes,16,4)+8); int columns=(int)BE(Bytes,24,2);
                RowWidth=(int)BE(Bytes,26,2); Count=checked((int)BE(Bytes,28,4));
                if (version>1 || Size>Bytes.Length || RowOffset<32 || StringOffset<RowOffset || DataOffset<StringOffset ||
                    DataOffset>Size || columns<1 || columns>256 || Count>200000 || (long)Count*RowWidth>StringOffset-RowOffset)
                    throw new InvalidDataException("Limites UTF invalidos.");
                Text((uint)BE(Bytes,20,4));
                int cursor=32, row=0; HashSet<string> names=new HashSet<string>(StringComparer.Ordinal);
                for(int i=0;i<columns;i++) {
                    Range(cursor,5,RowOffset); int flags=Bytes[cursor++];
                    // Legacy CPK tools can emit a four-byte flags prefix.
                    if(flags==0) { Range(cursor,4,RowOffset); if(Bytes[cursor]!=0||Bytes[cursor+1]!=0||Bytes[cursor+2]!=0)throw new InvalidDataException("Flags UTF invalidas."); cursor+=3; flags=Bytes[cursor++]; }
                    uint name=(uint)BE(Bytes,cursor,4);cursor+=4;
                    var column=new Column {Name=Text(name),Type=flags&15,Storage=flags&0xf0};
                    if(!names.Add(column.Name)|| (column.Storage!=0x10&&column.Storage!=0x30&&column.Storage!=0x50&&column.Storage!=0x70))
                        throw new InvalidDataException("Coluna UTF desconhecida/duplicada.");
                    int width=Width(column.Type);
                    if((column.Storage&0x20)!=0) {column.Offset=cursor;cursor=checked(cursor+width);Range(cursor,0,RowOffset);}
                    else if((column.Storage&0x40)!=0) {column.Offset=row;row=checked(row+width);if(row>RowWidth)throw new InvalidDataException("Linha UTF curta.");}
                    Columns.Add(column);
                }
            }
            string Text(uint relative) {
                if(relative>=DataOffset-StringOffset)throw new InvalidDataException("String UTF fora da tabela.");
                int start=StringOffset+(int)relative,end=start;
                while(end<DataOffset && end-start<=4096 && Bytes[end]!=0)end++;
                if(end>=DataOffset||end-start>4096)throw new InvalidDataException("String UTF sem terminador.");
                return Utf8.GetString(Bytes,start,end-start);
            }
            static int Width(int type) {
                if(type<=1)return 1;if(type<=3)return 2;if(type<=5||type==8||type==10)return 4;
                if(type==6||type==7||type==9||type==11)return 8;
                throw new InvalidDataException("Tipo UTF nao suportado.");
            }
            public Dictionary<string,object> Row(int index) {
                if(index<0||index>=Count)throw new InvalidDataException("Indice UTF invalido.");
                var values=new Dictionary<string,object>(StringComparer.Ordinal);
                foreach(var c in Columns) {
                    if(c.Storage==0x10) {values[c.Name]=c.Type==10?(object)"":(object)(ulong)0;continue;}
                    int at=(c.Storage&0x20)!=0?c.Offset:RowOffset+index*RowWidth+c.Offset;
                    int width=Width(c.Type);Range(at,width,(c.Storage&0x20)!=0?RowOffset:RowOffset+Count*RowWidth);
                    ulong raw=BE(Bytes,at,width);
                    if(c.Type==10)values[c.Name]=Text((uint)raw);
                    else if(c.Type==11) {
                        long offset=checked(DataOffset+(long)BE(Bytes,at,4)),size=(long)BE(Bytes,at+4,4);
                        if(offset<0||size<0||offset>Size||size>Size-offset)throw new InvalidDataException("Dados UTF fora da tabela.");
                        values[c.Name]=new long[]{offset,size};
                    } else if(c.Type==8||c.Type==9) {
                        byte[] number=new byte[width];Array.Copy(Bytes,at,number,0,width);if(BitConverter.IsLittleEndian)Array.Reverse(number);
                        values[c.Name]=c.Type==8?(object)BitConverter.ToSingle(number,0):(object)BitConverter.ToDouble(number,0);
                    } else if(c.Type==1||c.Type==3||c.Type==5||c.Type==7) {
                        long signed=unchecked((long)raw);
                        if(width<8&&(raw&(1UL<<(width*8-1)))!=0)signed=unchecked((long)(raw|(~0UL<<(width*8))));
                        values[c.Name]=signed;
                    } else values[c.Name]=raw;
                }
                return values;
            }
        }
        static void Range(long offset,long count,long size) {if(offset<0||count<0||offset>size||count>size-offset)throw new InvalidDataException("Intervalo fora dos limites.");}
        static ulong BE(byte[] bytes,int offset,int count) {Range(offset,count,bytes.Length);ulong value=0;for(int i=0;i<count;i++)value=(value<<8)|bytes[offset+i];return value;}
        static byte[] Read(FileStream file,long offset,int count) {
            Range(offset,count,file.Length);file.Position=offset;byte[] data=new byte[count];int done=0;
            while(done<count){int got=file.Read(data,done,count-done);if(got==0)throw new EndOfStreamException();done+=got;}return data;
        }
        static byte[] Packet(FileStream file,long offset,string expected) {
            byte[] header=Read(file,offset,16);
            if(Encoding.ASCII.GetString(header,0,4)!=expected)throw new InvalidDataException("Assinatura de pacote CPK/TOC invalida.");
            ulong count=BitConverter.ToUInt64(header,8);
            if(count<32||count>MaxTable)throw new InvalidDataException("Tabela CPK muito grande/curta.");
            return Read(file,checked(offset+16),(int)count);
        }
        static long Number(Dictionary<string,object> row,string key) {
            object value;if(!row.TryGetValue(key,out value))throw new InvalidDataException("Campo numerico CPK ausente: "+key);
            if(value is ulong&&(ulong)value<=long.MaxValue)return (long)(ulong)value;
            if(value is long&&(long)value>=0)return (long)value;
            throw new InvalidDataException("Campo numerico CPK invalido: "+key);
        }
        static string Name(Dictionary<string,object> row,string key) {
            object value;if(!row.TryGetValue(key,out value)||!(value is string))throw new InvalidDataException("Campo textual CPK ausente: "+key);return (string)value;
        }
        public static string Normalize(string path) {
            path=path.Replace('\\','/');while(path.StartsWith("./",StringComparison.Ordinal))path=path.Substring(2);
            if(path.StartsWith("cpk_dat/",StringComparison.OrdinalIgnoreCase))path=path.Substring(8);
            if(path.StartsWith("/",StringComparison.Ordinal)||path.IndexOf(':')>=0)throw new InvalidDataException("Caminho absoluto no CPK.");
            foreach(string part in path.Split('/'))if(part==".."||part=="."||part.Length==0)throw new InvalidDataException("Caminho CPK invalido.");
            return path;
        }
        public static bool IsTarget(string path) {
            path=Normalize(path).ToLowerInvariant();
            if(path.StartsWith("common/match/constant/",StringComparison.Ordinal))return path.EndsWith(".bin",StringComparison.Ordinal)||path.EndsWith(".json",StringComparison.Ordinal);
            return path.EndsWith(".bin",StringComparison.Ordinal)&&(path.StartsWith("common/anime/playerid/bin/",StringComparison.Ordinal)||
                path.StartsWith("common/anime/animetable/bin/",StringComparison.Ordinal)||path.StartsWith("common/anime/mbinfo/bin/",StringComparison.Ordinal));
        }
        public static string Hash(byte[] bytes) {using(SHA256 sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();}
        public static string HashFile(string path) {using(var file=File.OpenRead(path))using(SHA256 sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(file)).Replace("-","").ToLowerInvariant();}
        static void Save(byte[] bytes,Resource resource,string directory) {
            resource.StoredSha256=Hash(bytes);resource.StoredFile=resource.StoredSha256+".stored";
            resource.Encoding=bytes.Length>=8&&Encoding.ASCII.GetString(bytes,0,8)=="CRILAYLA"?"CRILAYLA-preserved":
                resource.StoredBytes==resource.DeclaredExtractBytes?"stored-unmodified":"unknown-compression-preserved";
            Directory.CreateDirectory(directory);string target=Path.Combine(directory,resource.StoredFile);
            if(File.Exists(target)){if(new FileInfo(target).Length!=bytes.Length||HashFile(target)!=resource.StoredSha256)throw new InvalidDataException("Saida existente nao corresponde ao hash.");}
            else using(var output=new FileStream(target,FileMode.CreateNew,FileAccess.Write))output.Write(bytes,0,bytes.Length);
        }
        public static Scan Collect(string source,string label,string directory,long budget) {
            var result=new Scan {Source=label,Skipped=new string[0]};var selected=new List<Resource>();var skipped=new List<string>();
            using(var file=new FileStream(source,FileMode.Open,FileAccess.Read,FileShare.Read)) {
                result.SourceBytes=file.Length;byte[] headerPacket=Packet(file,0,"CPK ");var header=new Table(headerPacket);
                if(header.Count!=1)throw new InvalidDataException("CPK exige um cabecalho.");
                var h=header.Row(0);result.TocOffset=Number(h,"TocOffset");result.ContentOffset=Number(h,"ContentOffset");
                Range(result.ContentOffset,0,file.Length);
                byte[] tocPacket=Packet(file,result.TocOffset,"TOC ");var toc=new Table(tocPacket);
                result.HeaderSha256=Hash(headerPacket);result.TocSha256=Hash(tocPacket);result.HeaderMasked=header.Masked;result.TocMasked=toc.Masked;result.EntryCount=toc.Count;
                long relativeBase=Math.Min(result.ContentOffset,result.TocOffset);
                var paths=new HashSet<string>(StringComparer.OrdinalIgnoreCase);var spans=new List<long[]>();
                for(int i=0;i<toc.Count;i++) {
                    var row=toc.Row(i);string dir=Name(row,"DirName"),name=Name(row,"FileName");
                    string path=Normalize((dir.Length==0?"":dir+"/")+name);
                    long stored=Number(row,"FileSize"),extracted=Number(row,"ExtractSize"),offset=checked(relativeBase+Number(row,"FileOffset"));
                    Range(offset,stored,file.Length);
                    long end=checked(offset+stored),tocEnd=checked(result.TocOffset+16+tocPacket.Length);
                    if(stored>0&&(offset<16+headerPacket.Length||(offset<tocEnd&&end>result.TocOffset)))throw new InvalidDataException("Recurso sobrepoe tabela CPK.");
                    if(!paths.Add(path))throw new InvalidDataException("Caminho CPK duplicado.");
                    if(stored>0)spans.Add(new long[]{offset,end});
                    if(!IsTarget(path))continue;
                    if(stored>MaxResource){skipped.Add(path+" | recurso acima de 24 MiB");continue;}
                    result.ExportedBytes=checked(result.ExportedBytes+stored);
                    if(result.ExportedBytes>budget)throw new InvalidDataException("Limite total de coleta atingido.");
                    selected.Add(new Resource {Source=label,Path=path,Offset=offset,StoredBytes=stored,DeclaredExtractBytes=extracted});
                }
                spans.Sort(delegate(long[] a,long[] b){return a[0].CompareTo(b[0]);});long previousStart=-1,previousEnd=-1;
                foreach(var span in spans){if(span[0]<previousEnd&&(span[0]!=previousStart||span[1]!=previousEnd))throw new InvalidDataException("Recursos CPK parcialmente sobrepostos.");previousStart=span[0];previousEnd=span[1];}
                // Commit selected bytes only after checking the entire named TOC.
                foreach(var resource in selected)Save(Read(file,resource.Offset,(int)resource.StoredBytes),resource,directory);
                if(selected.Count>0&&result.SourceBytes<=512L*1024*1024) {
                    file.Position=0;using(SHA256 sha=SHA256.Create())result.SourceSha256=BitConverter.ToString(sha.ComputeHash(file)).Replace("-","").ToLowerInvariant();
                }
            }
            // Resource hashes are always integral. Very large parent archives
            // retain explicit partial provenance rather than a fake full hash.
            result.Resources=selected.ToArray();result.Skipped=skipped.ToArray();return result;
        }
        public static Resource CollectLoose(string source,string label,string virtualPath,string directory,long budget) {
            if(!IsTarget(virtualPath))throw new InvalidDataException("Arquivo avulso fora da selecao.");
            long count=new FileInfo(source).Length;if(count>MaxResource||count>budget)throw new InvalidDataException("Arquivo avulso acima do limite.");
            if((File.GetAttributes(source)&FileAttributes.ReparsePoint)!=0)throw new InvalidDataException("Link de arquivo nao sera seguido.");
            var resource=new Resource {Source=label,Path=Normalize(virtualPath),StoredBytes=count,DeclaredExtractBytes=count,Offset=0};
            Save(File.ReadAllBytes(source),resource,directory);return resource;
        }
    }
}
