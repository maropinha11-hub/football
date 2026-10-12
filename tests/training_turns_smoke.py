#!/usr/bin/env python3
"""Exercise continuous cuts with real SDL stick input in both training cameras."""
import argparse
import json
import math
from pathlib import Path
from native_training_harness import NativeTraining

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--display', default=':94')
parser.add_argument('--observe', action='store_true')
args = parser.parse_args()
report = {'result': 'running', 'checks': [], 'cases': []}

def check(name, passed, evidence):
    report['checks'].append({'check': name, 'result': 'passed' if passed else 'failed', 'evidence': evidence})
    print(('PASS ' if passed else 'FAIL ') + name + ': ' + str(evidence), flush=True)

try:
    for camera in (0, 2):
        with NativeTraining(args.build, args.output / ('camera-' + str(camera)),
                            display=args.display, analog_pad=True, camera=camera) as game:
            def direction(angle):
                # External movement is world-relative; FP movement is body-relative.
                return (math.cos(angle), -math.sin(angle)) if camera == 0 else (math.sin(angle), -math.cos(angle))
            scenarios = {
                'opposite cuts': [(0, 1300), (math.pi, 1200), (0, 1300), (math.pi, 1200)],
                'side cuts': [(0, 1100), (math.pi/2, 650), (-math.pi/2, 1100),
                              (0, 700), (math.pi, 1100), (0, 900)],
                'circling': [(i*math.pi/8, 250) for i in range(32)],
            }
            for name, phases in scenarios.items():
                game.reset()
                origin = game.frames()[-1]
                samples = []
                for angle, duration in phases:
                    game.pad(*direction(angle))
                    samples.extend(game.advance(duration))
                game.pad(0, 0)
                samples.extend(game.advance(500))
                distances = [math.dist(f['player'][:2], f['ball'][:2]) for f in samples]
                path = sum(math.dist(a['player'], b['player']) for a, b in zip(samples, samples[1:]))
                evidence = {'max_distance_m': max(distances), 'end_distance_m': distances[-1],
                            'path_m': path, 'controlled': sum(f['with_ball'] for f in samples),
                            'samples': len(samples), 'extra_body_contacts': samples[-1]['contacts'] - origin['contacts']}
                report['cases'].append({'camera': camera, 'case': name, 'evidence': evidence,
                                        'origin': origin, 'frames': samples})
                prefix = 'camera ' + str(camera) + ' ' + name
                check(prefix + ' retains native control', max(distances) < 2.3 and
                      distances[-1] < 1.2 and all(f['with_ball'] for f in samples), evidence)
                check(prefix + ' remains responsive', path > 2, evidence)
                check(prefix + ' has no extra leg rebounds', evidence['extra_body_contacts'] == 0, evidence)
            check('camera ' + str(camera) + ' keeps native animations',
                  'PES3_BODY_APPLY' not in game.log.read_text(), 'No study animation applied')
            game.keys(['Escape'], True)
            game.game.wait(timeout=15)
            check('camera ' + str(camera) + ' clean exit', game.game.returncode == 0, game.game.returncode)
    report['result'] = 'passed' if all(c['result'] == 'passed' for c in report['checks']) else 'failed'
finally:
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
if report['result'] != 'passed' and not args.observe:
    raise SystemExit(1)
