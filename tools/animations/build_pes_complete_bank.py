"""Audit the entire local decoded library and retarget native-compatible actions.

Every decoded record receives a status. Inferred contacts are Football
annotations; real weighted-skin contact remains compulsory at runtime.
Original archives and failed/intermediate poses are never copied to the game.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
from pes_motion_families import describe
from packed_animation import pack_text

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--decoded',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--core',type=Path,default=ROOT/'data/media/training/pes17')
    p.add_argument('--bake',action='store_true');p.add_argument('--limit',type=int,default=0)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]if '--'in sys.argv else None)
    if not a.bake:
        subprocess.run(['blender','-b','--python',str(Path(__file__).resolve()),'--','--bake',
                        '--decoded',str(a.decoded.resolve()),'--output',str(a.output.resolve()),
                        '--core',str(a.core.resolve()),'--limit',str(a.limit)],check=True);return
    a.output.mkdir(parents=True,exist_ok=False)
    review=a.output.parent/(a.output.name+'-review');review.mkdir()
    core=json.loads((a.core/'catalog.json').read_text())
    catalog=dict(version=2,source_archive_sha256=core['source_archive_sha256'],
                 original_pes_gameplay_integrated=False,actions=[])
    recipes=json.loads((ROOT/'config/pes2017-action-recipes.json').read_text())
    original={r['source']:r for r in recipes['actions']}
    imported=set()
    for row in core['actions']:
        if row['source']not in original:continue
        shutil.copy2(a.core/row['file'],a.output/row['file'])
        shutil.copy2((a.core/row['file']).with_suffix('.json'),(a.output/row['file']).with_suffix('.json'))
        catalog['actions'].append(row);imported.add(row['source'])
    inventory=[];converted=0
    from mathutils import Vector
    for path in sorted(a.decoded.glob('body_anime_file*/*.json')):
        clip=json.loads(path.read_text())
        if 'frames'not in clip:continue
        name=clip.get('name');recipe=describe(name)
        entry=dict(source=name,hash=format(clip['hash'],'08x'),id=clip['id'],container=path.parent.name,
                   source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),frames=clip['frames'])
        inventory.append(entry)
        if name in imported:entry['status']='curated_candidate';continue
        if clip.get('requires_auxiliary_solver'):entry.update(status='requires_auxiliary_solver');continue
        if clip.get('decode_warnings'):entry.update(status='unresolved_timing');continue
        if not recipe:
            entry['status']='unclassified'if not name else'context_not_mapped'
            continue
        if a.limit and converted>=a.limit:entry['status']='not_processed_in_limited_run';continue
        filename='motion_'+entry['hash'];output=review/(filename+'.anim')
        arguments=['retarget_fox_clip.py','--',str(path),str(path.parent/'source-rig.json'),str(output),
                   '--action',recipe['action'],'--role',recipe['role'],'--contact-bodypart',recipe['part'],
                   '--direction-degrees',str(recipe['direction']),'--power-range',*map(str,recipe['power']),
                   '--player-speed-range',*map(str,recipe['speed']),'--ball-height-range',*map(str,recipe['height']),
                   '--max-ball-speed',str(recipe['max_ball_speed']),'--root-motion','--body-support']
        if recipe.get('infer_contact'):arguments+=['--infer-contact']
        if recipe.get('infer_foot'):arguments+=['--infer-foot']
        if recipe.get('technique'):arguments+=['--technique',recipe['technique']]
        if recipe['speed'][0]==0:arguments+=['--stationary-entry']
        if recipe.get('trip_type'):arguments+=['--trip-type',str(recipe['trip_type'])]
        if recipe.get('retainer_in'):arguments+=['--retainer-in',recipe['retainer_in']]
        sys.argv=arguments
        try:
            result=runpy.run_path(str(ROOT/'tools/animations/retarget_fox_clip.py'),run_name='__main__')
            report=result['report'];poses=result['output'];q0=poses[0]['q'][0];q1=poses[-1]['q'][0]
            if report['maximum_10ms_joint_angle_change']>.35:raise ValueError('angular_discontinuity')
            text=output.read_text()
            incoming=q0@Vector((0,0,1));outgoing=q1@Vector((0,0,1))
            # Join the existing native fall/get-up graph rather than finishing
            # a lying pose directly in an upright idle animation.
            def ground_state(q):
                return 'lay_back'if (q@Vector((0,-1,0))).z>0 else'lay_front'
            if incoming.z<.35:
                if recipe['role']!='recovery':raise ValueError('requires_ground_entry_state')
                text+='<incoming_special_state>'+ground_state(q0)+'</incoming_special_state>\n'
            if outgoing.z<.35:text+='<outgoing_special_state>'+ground_state(q1)+'</outgoing_special_state>\n'
            if recipe['role']=='recovery'and incoming.z>=.35:raise ValueError('recovery_has_no_supported_ground_entry')
            if recipe.get('keeper_only'):text+='<pes_keeper_only>true</pes_keeper_only>\n'
            if recipe.get('setpiece'):text+='<pes_setpiece>true</pes_setpiece>\n'
            if recipe.get('retain_ball'):
                retainer='right_elbow'if report['contact_bodypart'].startswith('right')else'left_elbow'
                text+='<outgoing_retain_state>'+retainer+'</outgoing_retain_state>\n'
            if recipe.get('mirror'):text+='<pes_make_mirror>true</pes_make_mirror>\n'
            text+='<pes_bulk>true</pes_bulk>\n'
            if recipe['role']=='reception':
                part=report['contact_bodypart']
                region='thigh'if part.endswith('upperleg')else'chest'if part=='trunk'else'head'if part=='head'else'foot'
                text+='<reception_region>'+region+'</reception_region>\n'
            target=a.output/(filename+'.anim');target.write_bytes(pack_text(text))
            report.update(source_game='PES 2017 Windows',source_archive_sha256=core['source_archive_sha256'],
                          source_mtar=path.parent.name+'.mtar',source_name_hash=entry['hash'],source_id=entry['id'],
                          rights='Retargeted user-supplied PES motion; original rights retained. See NOTICE.',
                          output_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),recipe=recipe)
            report.update(storage_format='FBAN2',runtime_float32_exact=True)
            target.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
            row=dict(file=target.name,source=name,role=recipe['role'],mirrored=bool(recipe.get('mirror')),
                     receiving_control_variant=recipe['role']=='reception',anticipation_variants=1,sha256=report['output_sha256'])
            catalog['actions'].append(row);entry.update(status='retargeted_candidate',file=target.name,role=recipe['role'])
            converted+=1
        except (ValueError,KeyError,ZeroDivisionError)as error:
            entry.update(status='retarget_rejected',reason=str(error))
        if len(inventory)%50==0:
            print(json.dumps(dict(processed=len(inventory),integrated=len(catalog['actions']))),flush=True)
    catalog['source_clips']=len(catalog['actions'])
    catalog['runtime_candidates']=sum((2 if r['mirrored']else 1)*(2 if r['receiving_control_variant']else 1)for r in catalog['actions'])
    (a.output/'catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    summary=dict(decoded_records=len(inventory),source_clips=catalog['source_clips'],
                 runtime_candidates=catalog['runtime_candidates'])
    from collections import Counter
    summary['statuses']=dict(Counter(e['status']for e in inventory))
    summary['roles']=dict(Counter(e['role']for e in catalog['actions']))
    inventory_report=dict(version=1,source_archive_sha256=core['source_archive_sha256'],summary=summary,clips=inventory,
                          limitations='Candidate status records conversion, not in-game contact coverage. Weak family labels and kinematic Football contacts; original PES selector and event timing not recovered.')
    (a.output/'integration-audit.json').write_text(json.dumps(inventory_report,indent=2)+'\n')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
