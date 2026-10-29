"""Inspect/decode user-supplied PES 2021 animations without changing the game.

Sparse source keys, root motion and the source rig remain separate. There is
no automatic retarget, contact annotation or gameplay/physics recovery here.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[2]
VENDOR=ROOT/'third_party/pes-gani'
sys.path.insert(0,str(VENDOR))
from pes_gani import pesmtar, foxhash


def bounded_file(path, maximum=256*1024*1024):
    path=Path(path)
    if not path.is_file() or not 0<path.stat().st_size<=maximum:
        raise ValueError(f'Invalid or oversized input: {path.name}')
    data=path.read_bytes()
    if len(data)>maximum:raise ValueError('Input grew beyond its size limit')
    return data


def mtar(data):
    if len(data)<32:raise ValueError('Truncated MTAR header')
    count=struct.unpack_from('<I',data,4)[0]
    if not 0<count<=10000 or 32+count*16>len(data):raise ValueError('Invalid MTAR entry table')
    result=pesmtar.read_mtar(data)
    for entry in result['entries']:
        if entry['addr']<32+count*16 or entry['size']<164 or entry['addr']+entry['size']>len(data):
            raise ValueError('MTAR clip is outside its source container')
    return result


def gani(data):
    if len(data)<12:raise ValueError('Truncated GANI header')
    offset=struct.unpack_from('<I',data,4)[0]+0x70
    if offset<0x70 or offset+20>len(data):raise ValueError('Invalid GANI motion offset')
    groups,channels,_,frames,_=struct.unpack_from('<5I',data,offset)
    if not 0<groups<=256 or channels>512 or not 0<frames<=18000 or offset+20+groups*4>len(data):
        raise ValueError('Invalid GANI motion dimensions')
    total=0
    for i in range(groups):
        address=offset+struct.unpack_from('<I',data,offset+20+i*4)[0]
        if address<offset+20+groups*4 or address+8>len(data):raise ValueError('Invalid GANI track offset')
        count=data[address+4];total+=count
        if total>512 or address+8+8*count>len(data):raise ValueError('Invalid GANI channel table')
        for c in range(count):
            channel=address+8+c*8;relative,_,_,bits=struct.unpack_from('<IhBb',data,channel)
            if channel+relative<address+8+8*count or channel+relative>=len(data) or bits not in (12,16,20):
                raise ValueError('Unsupported or out-of-bounds GANI channel')
    return pesmtar.read_gani(data)


def skeleton(data):
    if len(data)<8:raise ValueError('Truncated ASK header')
    _,count=struct.unpack_from('<ii',data)
    if not 0<count<=256 or 8+44*count>len(data):raise ValueError('Invalid ASK bone table')
    result=pesmtar.read_ask(data)
    names=set()
    for i,bone in enumerate(result):
        if not bone['name'] or bone['name'] in names or not -1<=bone['parent']<i:
            raise ValueError('Invalid ASK bone hierarchy')
        names.add(bone['name'])
        if not all(math.isfinite(x)for x in bone['pos']+bone['rot']) or sum(x*x for x in bone['rot'])<1e-8:
            raise ValueError('Invalid ASK rest transform')
    return result


def rig(data,bones):
    if len(data)<32:raise ValueError('Truncated FRIG header')
    header=struct.unpack_from('<8I',data);count=header[3]
    if not 0<count<=256 or header[4]>512 or header[7]>len(data) or 32+4*count>len(data):
        raise ValueError('Invalid FRIG dimensions')
    offsets=list(struct.unpack_from(f'<{count}I',data,32));ends=offsets[1:]+[header[7]]
    if offsets!=sorted(set(offsets)) or offsets[0]<32+4*count or any(b-a not in (32,64)for a,b in zip(offsets,ends)):
        raise ValueError('Unsupported FRIG unit layout')
    result=pesmtar.read_frig(data)
    if any(not 0<=bone<bones for unit in result for bone in unit['bones']):raise ValueError('FRIG refers to a missing ASK bone')
    return result


def validate_clip(clip):
    for track in [clip['root'],*clip['tracks'].values()]:
        for kind,keys in track.items():
            last=-1
            for key in keys:
                if len(key)!=(5 if kind=='rot' else 4) or not all(math.isfinite(x)for x in key):raise ValueError('Invalid decoded key')
                if key[0]<=last or key[0]>clip['frames']:raise ValueError('Invalid decoded key timing')
                if kind=='rot' and abs(sum(x*x for x in key[1:])-1)>.001:raise ValueError('Invalid decoded rotation')
                last=key[0]


def inspect(path,ask=None,frig=None,output=None,limit=None):
    data=bounded_file(path);container=mtar(data)
    table=json.loads((VENDOR/'clip_name_map.json').read_text())
    names={int(meta['hash']):name for name,meta in table.items()}
    report=dict(source=Path(path).name,sha256=hashlib.sha256(data).hexdigest(),clips=container['count'],
                named=sum(e['hash']in names for e in container['entries']),decoded=0,retargeted=False,
                gameplay_recovered=False,physics_recovered=False,source_rig_bones=None)
    if (ask is None)!=(frig is None):raise ValueError('ASK and FRIG must be supplied together')
    if ask is None:
        report['status']='inventory_only; skeleton and rig required for decoding';return report
    ask_data=bounded_file(ask,8*1024*1024);frig_data=bounded_file(frig,8*1024*1024)
    bones=skeleton(ask_data);units=rig(frig_data,len(bones));report['source_rig_bones']=len(bones)
    report['skeleton_sha256']=hashlib.sha256(ask_data).hexdigest();report['rig_sha256']=hashlib.sha256(frig_data).hexdigest()
    if output is None:raise ValueError('An output directory is required for decoded clips')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'source-rig.json').write_text(json.dumps(dict(bones=bones,units=units),indent=2,allow_nan=False)+'\n')
    for entry in container['entries'][:limit]:
        raw=data[entry['addr']:entry['addr']+entry['size']];header=gani(raw)
        mapping=pesmtar.channel_map(units,header['channels'])
        if any(c['index'] not in mapping for c in header['channels']):raise ValueError('Unmapped source channel; decode would be incomplete')
        if any(index is not None and index>=len(bones)for _,index in mapping.values()):raise ValueError('Channel maps outside the source skeleton')
        clip=pesmtar.clip_to_json(raw,mapping,[b['name']for b in bones],dense=False);validate_clip(clip)
        clip.update(name=names.get(entry['hash']),hash=entry['hash'],id=entry['id'],source_sha256=report['sha256'])
        # Source names are metadata, never output paths. Hash + entry ordinal
        # also preserves multiple clips with the same hash without overwrites.
        (output/f'{report["decoded"]:05d}-{entry["hash"]:08x}.json').write_text(json.dumps(clip,allow_nan=False)+'\n')
        report['decoded']+=1
    report['status']='decoded_sparse_source; not installed in the game'
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mtar',type=Path)
    p.add_argument('--skeleton',type=Path);p.add_argument('--rig',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--limit',type=int);a=p.parse_args()
    if a.limit is not None and not 1<=a.limit<=10000:p.error('limit must be between 1 and 10000')
    try:print(json.dumps(inspect(a.mtar,a.skeleton,a.rig,a.output,a.limit),indent=2))
    except (ValueError,IndexError,struct.error,OSError)as error:p.exit(1,f'Cannot decode source animation: {error}\n')
