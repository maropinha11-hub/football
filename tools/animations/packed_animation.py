"""FBAN2: lossless storage of the engine's float32 keys and original metadata.

No quaternion quantization or pose-key removal. Text and packed forms decode
to identical IEEE float values in the native engine.
"""
import math
from pathlib import Path
import struct

MAGIC=b'FBAN2'

def pack_text(text):
    tracks=[];footer=[];started=False
    for line in text.splitlines():
        if started or line.startswith(('extension,','<')):
            started=True;footer.append(line);continue
        fields=line.split(',');name=fields[0].encode('ascii')
        width=3 if fields[0]=='player'else 4;step=width+1
        if not 1<=len(name)<=64 or (len(fields)-1)%step:raise ValueError('Invalid pose track')
        times=[];columns=[[]for _ in range(width)]
        for at in range(1,len(fields),step):
            key=int(fields[at]);p=[float(v)for v in fields[at+1:at+step]]
            if key<0 or not all(math.isfinite(v)for v in p):raise ValueError('Invalid pose key')
            times.append(key)
            for axis,value in enumerate(p):columns[axis].append(struct.unpack('<I',struct.pack('<f',value))[0])
        encoded=[]
        for values in columns:
            previous=previous2=0;residuals=[]
            for value in values:
                prediction=(2*previous-previous2)&0xffffffff
                residual=(value-prediction)&0xffffffff
                residuals.append(((residual<<1)^(0xffffffff if residual&0x80000000 else 0))&0xffffffff)
                previous2,previous=previous,value
            encoded.append(b''.join(bytes((v>>shift)&255 for v in residuals)for shift in [0,8,16,24]))
        tracks.append(struct.pack('<B',len(name))+name+struct.pack('<BI',width,len(times))+
                      struct.pack('<'+'I'*len(times),*times)+b''.join(encoded))
    metadata=('\n'.join(footer)+'\n').encode('utf-8')
    return MAGIC+struct.pack('<I',len(tracks))+b''.join(tracks)+struct.pack('<I',len(metadata))+metadata

def read_text(path):
    data=Path(path).read_bytes()
    if data[:5]not in [b'FBAN1',b'FBAN2']:return data.decode('utf-8')
    version=data[:5]
    at=len(MAGIC)
    def take(fmt):
        nonlocal at
        size=struct.calcsize(fmt)
        if at+size>len(data):raise ValueError('Truncated packed animation')
        value=struct.unpack_from(fmt,data,at);at+=size;return value
    count,=take('<I')
    if count!=14:raise ValueError('Packed humanoid must have fourteen tracks')
    lines=[]
    for _ in range(count):
        size,=take('<B')
        if not 1<=size<=64 or at+size>len(data):raise ValueError('Invalid track name')
        name=data[at:at+size].decode('ascii');at+=size
        width,n=take('<BI')
        if width!=(3 if name=='player'else 4)or not 1<=n<=20000:raise ValueError('Invalid pose dimensions')
        fields=[name];previous=-1;records=[]
        if version==b'FBAN1':
            records=[take('<I'+'f'*width)for _ in range(n)]
        else:
            times=take('<'+'I'*n);columns=[]
            for axis in range(width):
                if at+4*n>len(data):raise ValueError('Truncated packed channel')
                residuals=[sum(data[at+plane*n+i]<<(8*plane)for plane in range(4))for i in range(n)];at+=4*n
                previous1=previous2=0;values=[]
                for encoded in residuals:
                    residual=(encoded>>1)^(-int(encoded&1)&0xffffffff)
                    bits=((2*previous1-previous2)+residual)&0xffffffff
                    values.append(struct.unpack('<f',struct.pack('<I',bits))[0]);previous2,previous1=previous1,bits
                columns.append(values)
            records=[(time,*(columns[axis][i]for axis in range(width)))for i,time in enumerate(times)]
        for key,*values in records:
            if key<=previous or not all(math.isfinite(v)for v in values):raise ValueError('Invalid packed key')
            previous=key;fields.extend([str(key),*(format(v,'.9g')for v in values)])
        lines.append(','.join(fields))
    size,=take('<I')
    if size>1048576 or at+size!=len(data):raise ValueError('Invalid packed metadata')
    return '\n'.join(lines)+'\n'+data[at:].decode('utf-8')
