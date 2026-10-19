"""Bake named MxM/Biped FBX takes to the native 13-joint pose format, using Blender 4.3+.

blender -b --python tools/animations/import_mxm_fbx.py -- source.fbx output.anim --rig mxm
Loop root XY stays with Gameplay Football. One-shots can retain explicit root
motion; neither mode supplies ball events absent from the source.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Matrix, Quaternion, Vector

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--non-loop', action='store_true', help='Preserve a one-shot action, including its last pose')
parser.add_argument('--contact-frame', type=float, help='Source action frame of the intended body contact (not supplied by FBX)')
parser.add_argument('--root-motion', action='store_true', help='Export horizontal motion for a non-looping action')
parser.add_argument('--rig', choices=['biped','mxm'], default='biped')
parser.add_argument('--take', help='Unique Blender action name substring')
parser.add_argument('--frames', nargs=2, type=float, help='Inclusive Blender source frame range')
parser.add_argument('--movement', action='store_true', help='Bake root motion as native non-contact locomotion')
parser.add_argument('--close-loop', action='store_true', help='Distribute a measured endpoint correction over the cycle')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
args.root_motion = args.root_motion or args.movement
if args.root_motion and not args.non_loop and not args.movement:
    raise ValueError('Horizontal motion requires a non-looping action')
rig = json.loads(Path(__file__).with_name('native_rig_reference.json').read_text())
parents = [-1, 0, 1, 1, 3, 1, 5, 0, 7, 8, 0, 10, 11]
source_names = ['Pelvis', 'Spine2', 'Head', 'LUpperArm', 'LForearm', 'RUpperArm', 'RForearm',
                'LThigh', 'LCalf', 'LFoot', 'RThigh', 'RCalf', 'RFoot']
segments = [('Pelvis','Spine'), ('Spine','Neck'), None, ('LUpperArm','LForearm'),
            ('LForearm','LHand'), ('RUpperArm','RForearm'), ('RForearm','RHand'),
            ('LThigh','LCalf'), ('LCalf','LFoot'), ('LFoot','LToe0'),
            ('RThigh','RCalf'), ('RCalf','RFoot'), ('RFoot','RToe0')]
axes = [Vector((0,0,1)), Vector((0,-.03,.5)), Vector((0,-1,0)),
        Vector((-.01,0,-.33)), Vector((0,0,-1)), Vector((.01,0,-.33)), Vector((0,0,-1)),
        Vector((0,0,-.42)), Vector((0,-.04,-.44)), Vector((0,-.14,-.05)),
        Vector((0,0,-.42)), Vector((0,-.04,-.44)), Vector((0,-.14,-.05))]
axes = [v.normalized() for v in axes]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(args.source.resolve()), use_anim=True)
actor = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
required = sorted(set(source_names + [n for pair in segments if pair for n in pair]))
joint_names={n:'Bip001'+n for n in required}
if args.rig=='mxm':
    joint_names.update(Pelvis='Hips',Spine='Spine',Spine2='UpperChest',Neck='Neck',Head='Head')
    for side in ['L','R']:
        for part,name in [('UpperArm','UpperArm'),('Forearm','LowerArm'),('Hand','Hand'),('Thigh','UpperLeg'),('Calf','LowerLeg'),('Foot','Foot'),('Toe0','Toe')]:
            joint_names[side+part]=name+'.'+side
for name in required:
    if joint_names[name] not in actor.data.bones:
        raise ValueError('Required joint missing: '+joint_names[name])
if args.take:
    actions=[a for a in bpy.data.actions if args.take in a.name]
    if len(actions)!=1:raise ValueError('Action must match once: '+repr([a.name for a in actions]))
    actor.animation_data.action=actions[0]
action = actor.animation_data.action
first, last = map(float, action.frame_range)
if args.frames:
    if not first<=args.frames[0]<args.frames[1]<=last:raise ValueError('Source range outside selected action')
    first,last=args.frames
fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
duration = (last-first)/fps
count = round(duration*100)
if not (count >= 2 and count <= 10000):
    raise ValueError('Invalid clip duration')
def evaluate(frame):
    bpy.context.scene.frame_set(math.floor(frame), subframe=frame-math.floor(frame))
    return {n: actor.matrix_world @ actor.pose.bones[joint_names[n]].matrix for n in required}
start, finish = evaluate(first), evaluate(last)
travel = finish['Pelvis'].translation-start['Pelvis'].translation
forward = Vector((travel.x,travel.y,0)).normalized()
if args.non_loop or args.rig=='mxm':
    anatomical_left=start['LThigh'].translation-start['RThigh'].translation
    anatomical_left.z=0
    forward=anatomical_left.normalized().cross(Vector((0,0,1)))
left = Vector((0,0,1)).cross(forward).normalized()
if left.dot(start['LThigh'].translation-start['RThigh'].translation) < 0:
    raise ValueError('Root motion disagrees with anatomical left/right')
basis = Matrix((left, -forward, Vector((0,0,1))))
basis_q = basis.to_quaternion()
reference_world = actor.matrix_world.copy()
rest = {n: reference_world @ actor.data.bones[joint_names[n]].matrix_local for n in required}
def point(matrices, name): return basis @ matrices[name].translation
def direction(matrices, pair): return (point(matrices,pair[1])-point(matrices,pair[0])).normalized()
def aim(q, axis, target): return (q @ axis).rotation_difference(target) @ q
def torso(matrices, lower, upper, left_name, right_name):
    z = (point(matrices,upper)-point(matrices,lower)).normalized()
    x = point(matrices,left_name)-point(matrices,right_name)
    x = (x-z*x.dot(z)).normalized()
    y = z.cross(x).normalized()
    return Matrix((x,y,z)).transposed().to_quaternion()
aligned = [axes[i].rotation_difference(direction(rest,pair)) if pair else Quaternion()
           for i,pair in enumerate(segments)]
all_poses = []
feet_clearance = []
direction_errors = []
loop_errors = []
toe_forward = []
for sample in range(count+1):
    matrices = evaluate(first+(last-first)*sample/count)
    globals_ = []
    for i,name in enumerate(source_names):
        delta = matrices[name].to_quaternion() @ rest[name].to_quaternion().inverted()
        q = basis_q @ delta @ basis_q.inverted() @ aligned[i]
        if segments[i]: q = aim(q,axes[i],direction(matrices,segments[i]))
        if i == 0: q = torso(matrices,'Pelvis','Spine','LThigh','RThigh')
        if i == 1: q = torso(matrices,'Spine','Neck','LUpperArm','RUpperArm') @ axes[i].rotation_difference(Vector((0,0,1)))
        q.normalize()
        globals_.append(q)
        if segments[i]:direction_errors.append(((q @ axes[i])-direction(matrices,segments[i])).length)
    local = [(globals_[parents[i]].inverted() @ q if parents[i]>=0 else q).normalized()
             for i,q in enumerate(globals_)]
    positions = [Vector((0,0,0))]
    for i in range(1,13):
        positions.append(positions[parents[i]]+globals_[parents[i]] @ Vector(rig['bones'][i]['offset']))
    minimum = float('inf')
    for side,index in enumerate((9,12)):
        foot = rig['feet'][side]
        for bits in itertools.product((0,1),repeat=3):
            p = Vector([foot['max' if bits[a] else 'min'][a] for a in range(3)])
            minimum = min(minimum,(positions[index]+globals_[index] @ p).z)
        toe_forward.append((globals_[index] @ Vector((0,-1,0))).dot(Vector((0,-1,0))))
    height = .008-minimum
    feet_clearance.append(minimum+height)
    if all_poses:
        for i,q in enumerate(local):
            if q.dot(all_poses[-1]['q'][i]) < 0:q.negate()
    motion=point(matrices,'Pelvis')-point(start,'Pelvis') if args.root_motion else Vector((0,0,0))
    all_poses.append({'q':local,'height':height,'motion':motion,'positions':[list(p+Vector((0,0,height))) for p in positions]})
# Close the exported loop explicitly; source endpoints are the same biped pose
# to floating-point tolerance. Never import FBX horizontal root displacement.
for a,b in zip(all_poses[0]['q'],all_poses[-1]['q']):loop_errors.append(a.rotation_difference(b).angle)
if not args.non_loop:
    if max(loop_errors) > .03 and not args.close_loop:raise ValueError('Source clip is not a seamless locomotion loop')
    if args.close_loop:
        if max(loop_errors)>1.0:raise ValueError('Endpoint mismatch exceeds one radian; choose another cycle')
        for i,pose in enumerate(all_poses):
            t=i/count;weight=t*t*(3-2*t)
            for bone,q in enumerate(pose['q']):
                correction=all_poses[-1]['q'][bone].rotation_difference(all_poses[0]['q'][bone])
                pose['q'][bone]=(q @ Quaternion().slerp(correction,weight)).normalized()
    all_poses[-1]['q']=[q.copy()for q in all_poses[0]['q']]
    all_poses[-1]['height']=all_poses[0]['height']
    # Closing a rotational seam changes foot positions. Re-solve support
    # from the corrected rotations, rather than retaining pre-correction Z.
    feet_clearance=[]
    for pose in all_poses:
        globals_=[];positions=[Vector((0,0,0))]
        for i,q in enumerate(pose['q']):
            globals_.append((globals_[parents[i]] @ q if parents[i]>=0 else q).normalized())
            if i:positions.append(positions[parents[i]]+globals_[parents[i]] @ Vector(rig['bones'][i]['offset']))
        minimum=float('inf')
        for side,index in enumerate((9,12)):
            foot=rig['feet'][side]
            for bits in itertools.product((0,1),repeat=3):
                corner=Vector([foot['max'if bits[a]else'min'][a]for a in range(3)])
                minimum=min(minimum,(positions[index]+globals_[index] @ corner).z)
        pose['height']=.008-minimum
        pose['positions']=[list(p+Vector((0,0,pose['height'])))for p in positions]
        feet_clearance.append(minimum+pose['height'])
args.output.parent.mkdir(parents=True,exist_ok=True)
root_bind=rig['bones'][0]['offset'][2]if args.movement else 0
lines=['player'+''.join(',%d,%.8f,%.8f,%.8f'%(i,p['motion'].x,p['motion'].y,p['height']-root_bind) for i,p in enumerate(all_poses))]
for bone in range(13):
    lines.append(rig['bones'][bone]['name']+''.join(',%d,%.9f,%.9f,%.9f,%.9f'%(i,p['q'][bone].x,p['q'][bone].y,p['q'][bone].z,p['q'][bone].w) for i,p in enumerate(all_poses)))
lines += ['<type>%s</type>'%('movement'if args.movement else'trainingpose'), '<source_speed_mps>%.9f</source_speed_mps>'%(travel.length/duration)]
if args.movement:lines+=['<imported_mocap>true</imported_mocap>','<touchframe>-1</touchframe>']
lines += ['<loop>%s</loop>'%('false' if args.non_loop else 'true')]
lines += ['<root_motion>%s</root_motion>'%('true' if args.root_motion else 'false')]
if args.contact_frame is not None:
    if not first <= args.contact_frame <= last:raise ValueError('Contact outside source clip')
    lines.append('<contact_frame>%.6f</contact_frame>'%((args.contact_frame-first)*100/fps))
args.output.write_text('\n'.join(lines)+'\n')
metadata={'source':args.source.name,'source_sha256':hashlib.sha256(args.source.read_bytes()).hexdigest(),
          'blender':bpy.app.version_string,'source_fps':fps,'source_frame_range':[first,last],
          'duration_seconds':duration,'baked_fps':100,'samples':count+1,
          'source_travel_m':travel.length,'source_speed_mps':travel.length/duration,
          'native_bones':[b['name'] for b in rig['bones']],
          'root_xy_imported':args.root_motion,'ball_events_in_source':False,
          'native_player_height_is_offset':args.movement,
          'loop':not args.non_loop,'contact_source_frame':args.contact_frame,
          'source_rig':args.rig,'source_action':action.name,'source_joint_map':joint_names,'loop_correction':args.close_loop,
          'contact_marker_origin':'integration marker; FBX contains no ball track' if args.contact_frame is not None else None,
          'maximum_segment_direction_error':max(direction_errors),
          'maximum_source_loop_angle_error_rad':max(loop_errors),
          'minimum_foot_clearance_m':min(feet_clearance),'minimum_toe_forward_dot':min(toe_forward),
          'native_root_height_range_m':[min(p['height'] for p in all_poses),max(p['height'] for p in all_poses)],
          'output_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}
args.output.with_suffix('.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps(metadata,indent=2))
