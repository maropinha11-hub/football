"""Bake one decoded Fox clip to native bones, using Blender.

blender -b --python tools/animations/retarget_fox_clip.py -- clip.json source-rig.json output.anim
The default export is visual only. Gameplay exports require an explicit Football
contact annotation; it does not recover PES ball timing or gameplay logic.
Source cadence and angle calibration remain to verify against the source game.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
from mathutils import Matrix,Quaternion,Vector

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('clip',type=Path);p.add_argument('rig',type=Path);p.add_argument('output',type=Path)
p.add_argument('--short-pass',action='store_true',help='Export an additional Football short-pass candidate')
p.add_argument('--action',choices=['shortpass','highpass','shot','trap','ballcontrol'],help='Native action for the additional candidate')
p.add_argument('--role',choices=['pass','cross','shot','header','reception','control'],default='pass')
p.add_argument('--contact-bodypart',choices=['right_foot','left_foot','right_upperleg','left_upperleg','right_lowerleg','left_lowerleg','trunk','head'],default='right_foot')
p.add_argument('--direction-degrees',type=float,default=0)
p.add_argument('--power-range',type=float,nargs=2,default=[0,.6])
p.add_argument('--player-speed-range',type=float,nargs=2,default=[0,1.4])
p.add_argument('--ball-height-range',type=float,nargs=2,default=[0,.27])
p.add_argument('--root-motion',action='store_true',help='Preserve decoded horizontal root travel for a moving action')
p.add_argument('--stationary-entry',action='store_true',help='Fit the first/last 100 ms of root velocity to standing locomotion')
p.add_argument('--technique',choices=['inside','outside','instep','heel'])
p.add_argument('--max-ball-speed',type=float,default=2.5)
p.add_argument('--contact-frame',type=int,help='Explicit integration contact frame at 100 Hz, not recovered from PES')
p.add_argument('--contact-point',type=float,nargs=3,help='Annotated native ball centre at the contact frame')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
action='shortpass'if a.short_pass else a.action
if a.short_pass and a.action:raise ValueError('Use either --short-pass or --action')
if not all(math.isfinite(v)for v in [a.direction_degrees,a.max_ball_speed,*a.power_range,*a.player_speed_range,*a.ball_height_range]):
    raise ValueError('Nonfinite action limits')
if any(lo>hi for lo,hi in [a.power_range,a.player_speed_range,a.ball_height_range]):raise ValueError('Reversed action limits')
clip=json.loads(a.clip.read_text());source=json.loads(a.rig.read_text())['bones']
if clip.get('requires_auxiliary_solver'):raise ValueError('Active IK targets require reconstruction before retargeting')
if clip.get('decode_warnings'):raise ValueError('Unresolved source key timing prevents a reliable retarget')
ref=json.loads(Path(__file__).with_name('native_rig_reference.json').read_text())
parents=[-1,0,1,1,3,1,5,0,7,8,0,10,11]
# Source X-left/Y-up/Z-forward -> native X-left/Y-back/Z-up. Proper rotation,
# no left/right exchange or reflection, unlike the unrelated PES3 rig basis.
basis=Matrix(((1,0,0),(0,0,-1),(0,1,0)));basis_q=basis.to_quaternion()
indices={b['name']:i for i,b in enumerate(source)}
selected=['sk_root_hip','sk_chest','sk_head','sk_upperarm_l','sk_forearm_l',
          'sk_upperarm_r','sk_forearm_r','sk_thigh_l','sk_leg_l','sk_foot_l',
          'sk_thigh_r','sk_leg_r','sk_foot_r']
segments=[None,('sk_chest','sk_head'),None,('sk_upperarm_l','sk_forearm_l'),
          ('sk_forearm_l','sk_hand_l'),('sk_upperarm_r','sk_forearm_r'),
          ('sk_forearm_r','sk_hand_r'),('sk_thigh_l','sk_leg_l'),('sk_leg_l','sk_foot_l'),None,
          ('sk_thigh_r','sk_leg_r'),('sk_leg_r','sk_foot_r'),None]
axes=[Vector(v).normalized()for v in [(0,0,1),(0,-.03,.5),(0,-1,0),(-.01,0,-.33),(0,0,-1),
       (.01,0,-.33),(0,0,-1),(0,0,-.42),(0,-.04,-.44),(0,-1,0),(0,0,-.42),(0,-.04,-.44),(0,-1,0)]]

def quat(values):return Quaternion((values[3],values[0],values[1],values[2])).normalized()
def sample(keys,frame,rotation=False):
    if not keys:return Quaternion()if rotation else Vector((0,0,0))
    left=keys[0];right=keys[-1]
    for key in keys:
        if key[0]<=frame:left=key
        if key[0]>=frame:right=key;break
    weight=(frame-left[0])/(right[0]-left[0])if right[0]>left[0]else 0
    return quat(left[1:]).slerp(quat(right[1:]),weight)if rotation else Vector(left[1:]).lerp(Vector(right[1:]),weight)

def evaluate(frame,rest=False):
    poses={};rotations={}
    for bone in source:
        track={}if rest else clip['tracks'].get(bone['name'],{})
        q=sample(track['rot'],frame,True)if 'rot'in track else quat(bone['rot'])
        point=Vector(bone['pos'])+(sample(track['pos'],frame)if 'pos'in track else Vector())
        if bone['parent']>=0:
            parent=source[bone['parent']]['name'];point=poses[parent]+rotations[parent]@point;q=rotations[parent]@q
        poses[bone['name']]=point;rotations[bone['name']]=q.normalized()
    # Fox stores animation-root rotation separately from the bone hierarchy.
    # It turns the complete skeleton (not just horizontal root travel).
    # Ignoring it preserves limb lengths but breaks turns/follow-throughs.
    motion=Quaternion()if rest else sample(clip.get('root',{}).get('rot',[]),frame,True)
    return {n:basis@(motion@v)for n,v in poses.items()},\
        {n:(basis_q@motion@v@basis_q.inverted()).normalized()for n,v in rotations.items()}

def direction(points,pair):return (points[pair[1]]-points[pair[0]]).normalized()
def torso(points):
    z=(points['sk_chest']-points['sk_root_hip']).normalized()
    x=points['sk_thigh_l']-points['sk_thigh_r'];x=(x-z*x.dot(z)).normalized()
    return Matrix((x,z.cross(x).normalized(),z)).transposed().to_quaternion()

rest,rest_q=evaluate(0,True)
aligned=[axes[i].rotation_difference(direction(rest,pair))if pair else Quaternion()for i,pair in enumerate(segments)]
frames=round(clip['frames']*100/clip['fps']);output=[];errors=[];max_length_error=0
if action and (a.contact_frame is None or a.contact_point is None or not 8<=a.contact_frame<frames-8 or
                    not all(math.isfinite(x)for x in a.contact_point)):
    raise ValueError('A gameplay candidate requires an explicit bounded contact annotation')
for tick in range(frames+1):
    points,world=evaluate(tick*clip['fps']/100);global_=[]
    if (torso(points)@Vector((0,0,1))).z<.35:
        raise ValueError('This first preview fits foot-supported upright poses; ground-contact falls need a different support solve')
    for i,name in enumerate(selected):
        q=world[name]@rest_q[name].inverted()@aligned[i]
        if segments[i]:
            target=direction(points,segments[i]);q=(q@axes[i]).rotation_difference(target)@q
            errors.append(((q@axes[i])-target).length)
        if i==0:q=torso(points)
        global_.append(q.normalized())
    local=[(global_[parents[i]].inverted()@q if parents[i]>=0 else q).normalized()for i,q in enumerate(global_)]
    locations=[Vector((0,0,0))]
    for i in range(1,13):
        offset=Vector(ref['bones'][i]['offset']);locations.append(locations[parents[i]]+global_[parents[i]]@offset)
        max_length_error=max(max_length_error,abs((locations[i]-locations[parents[i]]).length-offset.length))
    minimum=min((locations[ankle]+global_[ankle]@Vector([foot['max'if bits[i]else'min'][i]for i in range(3)])).z
        for ankle,foot in zip((9,12),ref['feet'])for bits in itertools.product((0,1),repeat=3))
    airborne=max(0,min(points[n].z for n in ['sk_foot_l','sk_foot_r'])-min(rest[n].z for n in ['sk_foot_l','sk_foot_r']))
    height=.008-minimum+airborne
    if output:
        for i,q in enumerate(local):
            if q.dot(output[-1]['q'][i])<0:q.negate()
    travel=basis@sample(clip['root'].get('pos',[]),tick*clip['fps']/100)if a.root_motion else Vector()
    travel.z=0
    if a.stationary_entry and a.root_motion:
        def smooth(v):
            v=max(0,min(1,v));return v*v*(3-2*v)
        if tick<10:travel*=smooth(tick/10)
        if tick>frames-10:
            end=basis@sample(clip['root'].get('pos',[]),clip['frames']);end.z=0
            travel=end+(travel-end)*smooth((frames-tick)/10)
    output.append(dict(q=local,height=height,travel=travel,positions=[list(v+Vector((0,0,height)))for v in locations]))
root_bind=ref['bones'][0]['offset'][2]if action else 0
lines=['player'+''.join(',%d,%.9f,%.9f,%.9f'%(i,row['travel'].x,row['travel'].y,row['height']-root_bind)for i,row in enumerate(output))]
for i,bone in enumerate(ref['bones']):
    lines.append(bone['name']+''.join(',%d,%.9f,%.9f,%.9f,%.9f'%(t,row['q'][i].x,row['q'][i].y,row['q'][i].z,row['q'][i].w)for t,row in enumerate(output)))
if action:
    contact=Vector(a.contact_point)+output[a.contact_frame]['travel']
    lines+=['extension,football,%d,%.9f,%.9f,%.9f'%(a.contact_frame,*contact),
        '<type>'+action+'</type>','<pes_action>true</pes_action>',
        '<pes_contact_bodypart>'+a.contact_bodypart+'</pes_contact_bodypart>',
        '<pes_source_name>'+str(clip.get('name'))+'</pes_source_name>',
        '<balldirection>%.9f,%.9f,0</balldirection>'%(math.sin(math.radians(a.direction_degrees)),-math.cos(math.radians(a.direction_degrees))),
        '<outgoingballdirection_maxdeviation>0.25</outgoingballdirection_maxdeviation>',
        '<touch_difficultyfactor>0.0</touch_difficultyfactor>',
        '<touch_maxpowerfactor>0.8</touch_maxpowerfactor>',
        '<pes_contact_annotation>Football integration marker; not recovered from PES</pes_contact_annotation>']
    if not a.short_pass:
        for key,value in dict(pes_role=a.role,pes_min_power=a.power_range[0],pes_max_power=a.power_range[1],
            pes_min_speed=a.player_speed_range[0],pes_max_speed=a.player_speed_range[1],
            pes_min_height=a.ball_height_range[0],pes_max_height=a.ball_height_range[1],
            pes_max_ball_speed=a.max_ball_speed,pes_preserve_facing='true',
            incomingballdirection='0,1,0',incomingballdirection_maxdeviation=.4).items():
            lines.append('<%s>%s</%s>'%(key,value,key))
        if a.technique:lines.append('<physical_technique>'+a.technique+'</physical_technique>')
else:lines+=['<type>trainingpose</type>']
lines+=['<loop>false</loop>','<root_motion>'+str(a.root_motion).lower()+'</root_motion>']
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text('\n'.join(lines)+'\n')
report=dict(name=clip.get('name'),source_sha256=hashlib.sha256(a.clip.read_bytes()).hexdigest(),
    output_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),samples=len(output),source_fps_assumed=clip['fps'],
    source_game_pose_comparison_pending=True,root_xy_imported=a.root_motion,ball_events_added=bool(action),
    motion_root_rotation_applied=True,
    root_velocity_entry_exit_fitted=a.stationary_entry,
    action=action,role=a.role if action else None,contact_bodypart=a.contact_bodypart if action else None,
    contact_frame_100hz=a.contact_frame if action else None,
    contact_annotation_origin='Football integration; original PES ball timing not recovered'if action else None,
    maximum_direction_error=max(errors),maximum_bone_length_error=max_length_error,
    maximum_10ms_joint_angle_change=max(2*math.acos(min(1,abs(left.dot(right))))
        for before,after in zip(output,output[1:])for left,right in zip(before['q'],after['q'])),
    root_height_range=[min(r['height']for r in output),max(r['height']for r in output)])
a.output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
a.output.with_suffix('.positions.json').write_text(json.dumps([r['positions']for r in output])+'\n')
print(json.dumps(report))
