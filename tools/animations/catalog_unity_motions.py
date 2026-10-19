"""Inventory uploaded Unity/FBX motions without treating GUIDs as animation data."""
import argparse,hashlib,json,re,struct
from pathlib import Path

def category(name):
    lower=name.lower()
    if 'idle2'in lower or 'start'in lower or 'counter'in lower:return 'start_or_transition'
    if '2idle'in lower or 'stop'in lower:return 'stop_or_transition'
    if any(s in lower for s in ['turn','plant','arc','ark','snake','spiral','circle']):return 'turn_or_change_of_direction'
    if 'strafe'in lower or 'stafe'in lower:return 'strafe'
    if 'sprint'in lower:return 'sprint'
    if 'run'in lower or 'jog'in lower:return 'run'
    if 'walk'in lower:return 'walk'
    if 'idle'in lower:return 'idle'
    return 'unclassified'

def inventory(roots,mask=None):
    files=[];clips=[]
    for root in roots:
        for path in sorted(root.rglob('*')):
            if not path.is_file()or path.suffix not in ['.anim','.fbx']:continue
            row=dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
            files.append(row)
            if path.suffix=='.anim':
                text=path.read_text();end=re.search(r'm_StopTime: ([\d.eE+-]+)',text)
                clips.append(dict(file=path.name,name=path.stem,category=category(path.stem),format='unity_humanoid_curves',duration=float(end[1])if end else None,requires_avatar_retarget=True))
            else:
                text=path.with_suffix('.fbx.meta').read_text()
                for block in re.split(r'    - serializedVersion: \d+\n',text)[1:]:
                    values={k:v.strip()for k,v in re.findall(r'^      (\w+): (.*)$',block,re.M)}
                    if not all(k in values for k in ['name','takeName','firstFrame','lastFrame']):continue
                    clips.append(dict(file=path.name,name=values['name'],take=values['takeName'],category=category(values['name']),format='fbx_take_range',first_frame=float(values['firstFrame']),last_frame=float(values['lastFrame']),loop=values.get('loopTime')=='1',mirror=values.get('mirror')=='1',events_in_metadata=values.get('events','[]')!='[]'))
    result=dict(files=files,clips=clips,source_files=len(files),unity_clips=sum(c['format']=='unity_humanoid_curves'for c in clips),fbx_ranges=sum(c['format']=='fbx_take_range'for c in clips),classification='Names and authored metadata; not inferred ball-contact labels',ball_contact_events_imported=False)
    if mask:
        text=mask.read_text();bits=bytes.fromhex(re.search(r'm_Mask: (\w+)',text)[1]);values=struct.unpack('<'+'I'*(len(bits)//4),bits)
        names=['root','body','head','left_leg','right_leg','left_arm','right_arm','left_fingers','right_fingers','left_foot_ik','right_foot_ik','left_hand_ik','right_hand_ik']
        result['mask']=dict(sha256=hashlib.sha256(mask.read_bytes()).hexdigest(),active=[n for n,v in zip(names,values)if v],inactive=[n for n,v in zip(names,values)if not v])
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('roots',nargs='+',type=Path);p.add_argument('--mask',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=inventory(a.roots,a.mask);a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items()if k not in ['files','clips']}))
