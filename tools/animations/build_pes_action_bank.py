"""Bake the curated PES action recipes from the user's locally decoded files.

Normal Python invokes one Blender process. Raw CPK/MTAR/rig inputs stay local;
the output contains only the transformed candidates and their provenance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decoded', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recipes', type=Path, default=ROOT/'config/pes2017-action-recipes.json')
    parser.add_argument('--blender', default='blender')
    parser.add_argument('--bake', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None)
    if not args.bake:
        subprocess.run([args.blender, '-b', '--python', str(Path(__file__).resolve()), '--',
                        '--bake', '--decoded', str(args.decoded.resolve()), '--output', str(args.output.resolve()),
                        '--recipes', str(args.recipes.resolve())], check=True)
        return
    recipes = json.loads(args.recipes.read_text())
    files = {}
    for path in args.decoded.glob('body_anime_file*/*.json'):
        if path.name == 'source-rig.json':
            continue
        clip = json.loads(path.read_text())
        if clip.get('name'):
            if clip['name'] in files:
                raise ValueError('Ambiguous source name: '+clip['name'])
            files[clip['name']] = path
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = dict(version=1, source_archive_sha256=recipes['source_archive_sha256'],
                    original_pes_gameplay_integrated=False, actions=[])
    for recipe in recipes['actions']:
        path = files[recipe['source']]
        clip = json.loads(path.read_text())
        output = args.output/(recipe['file']+'.anim')
        part = recipe.get('part', 'head' if recipe['role'] == 'header' else 'right_foot')
        extra = ['--short-pass'] if recipe.get('legacy') else ['--action', recipe['action'], '--role', recipe['role']]
        extra += ['--contact-frame', str(recipe['contact']), '--contact-point', *map(str, recipe['point'])]
        extra += ['--contact-bodypart', part, '--direction-degrees', str(recipe.get('direction', 0))]
        for key, flag, default in [('power', '--power-range', [0,.6]), ('speed', '--player-speed-range', [0,1.4]),
                                   ('height', '--ball-height-range', [0,.27])]:
            extra += [flag, *map(str, recipe.get(key, default))]
        if recipe.get('root_motion'):
            extra += ['--root-motion']
            if recipe.get('speed',[0,1.4])[0]<2:
                extra += ['--stationary-entry']
        extra += ['--max-ball-speed',str(recipe.get('max_ball_speed',18 if recipe.get('speed',[0])[0]>=2 else 2.5))]
        if recipe.get('technique'):
            extra += ['--technique', recipe['technique']]
        sys.argv = ['retarget_fox_clip.py', '--', str(path), str(path.parent/'source-rig.json'), str(output), *extra]
        result = runpy.run_path(str(ROOT/'tools/animations/retarget_fox_clip.py'), run_name='__main__')
        report = result['report']
        if report['maximum_10ms_joint_angle_change'] > .35:
            raise ValueError('Discontinuous source pose: '+recipe['source'])
        text = output.read_text()
        if recipe.get('mirror'):
            text += '<pes_make_mirror>true</pes_make_mirror>\n'
        if recipe.get('upper_reception'):
            text += '<pes_upper_reception>true</pes_upper_reception>\n'
        if recipe['role'] == 'reception':
            region = 'thigh' if part.endswith('upperleg') else 'chest' if part == 'trunk' else 'head' if part == 'head' else 'foot'
            text += '<reception_region>'+region+'</reception_region>\n'
        output.write_text(text)
        report.update(source_game='PES 2017 Windows', source_archive_sha256=recipes['source_archive_sha256'],
                      source_mtar=path.parent.name+'.mtar', source_name_hash=format(clip['hash'], '08x'), source_id=clip['id'],
                      rights='Retargeted user-supplied PES motion; rights remain with original owners. See NOTICE.',
                      output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(), recipe=recipe)
        output.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
        # FK review samples are diagnostic data, not a second runtime copy.
        diagnostic = args.output.parent/(args.output.name+'-review')
        diagnostic.mkdir(exist_ok=True)
        output.with_suffix('.positions.json').replace(diagnostic/(output.stem+'.positions.json'))
        manifest['actions'].append(dict(file=output.name, source=recipe['source'], role=recipe['role'],
                                        mirrored=bool(recipe.get('mirror')), receiving_control_variant=recipe['role']=='reception',
                                        anticipation_variants=1,
                                        sha256=report['output_sha256']))
    manifest['source_clips'] = len(manifest['actions'])
    manifest['runtime_candidates'] = sum((2 if row['mirrored'] else 1)*(2 if row['receiving_control_variant'] else 1)*row['anticipation_variants'] for row in manifest['actions'])
    (args.output/'catalog.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(result='baked', source_clips=manifest['source_clips'], runtime_candidates=manifest['runtime_candidates'])))


if __name__ == '__main__':
    main()
