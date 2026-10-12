#!/usr/bin/env python3
"""Measure normal-pace speed and ball lead against the same game with tuning off."""
import argparse
import json
import math
import statistics
from pathlib import Path
from native_training_harness import NativeTraining

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--display', default=':95')
args = parser.parse_args()
report = {'result': 'running', 'checks': [], 'cases': []}
metrics = {}

def check(name, ok, evidence):
    report['checks'].append({'check': name, 'result': 'passed' if ok else 'failed', 'evidence': evidence})
    print(('PASS ' if ok else 'FAIL ') + name + ': ' + str(evidence), flush=True)

try:
    for mode in ('native pace', 'requested pace'):
        overrides = {'training_walk_speed_scale': 1, 'training_dribble_spacing_m': 0} if mode == 'native pace' else {}
        with NativeTraining(args.build, args.output / mode.replace(' ', '-'), display=args.display,
                            analog_pad=True, config_overrides=overrides) as game:
            metrics[mode] = {}
            for name, magnitude, sprint in [('walking', 1, False), ('light stick', .5, False), ('sprint', 1, True)]:
                game.reset()
                game.pad(0, -magnitude, sprint=sprint)
                game.advance(1400)
                samples = game.advance(3000)
                speed = statistics.median(f['speed'] for f in samples)
                distances = [math.dist(f['player'][:2], f['ball'][:2]) for f in samples]
                evidence = {'speed_mps': speed, 'median_ball_distance_m': statistics.median(distances),
                            'max_ball_distance_m': max(distances), 'samples': len(samples)}
                metrics[mode][name] = evidence
                report['cases'].append({'mode': mode, 'case': name, 'evidence': evidence, 'frames': samples})
                check(mode + ' ' + name + ' retains control', all(f['with_ball'] for f in samples) and
                      max(distances) < 2.3, evidence)
                check(mode + ' ' + name + ' has no extra rebounds',
                      samples[-1]['contacts'] == samples[0]['contacts'], evidence)
            game.keys(['Escape'], True)
            game.game.wait(timeout=15)
            check(mode + ' clean exit', game.game.returncode == 0, game.game.returncode)
    before, after = metrics['native pace'], metrics['requested pace']
    check('normal movement is modestly slower', .8 < after['walking']['speed_mps'] / before['walking']['speed_mps'] < .97,
          {'before': before['walking']['speed_mps'], 'after': after['walking']['speed_mps']})
    check('light stick still reduces pace', after['light stick']['speed_mps'] < after['walking']['speed_mps'] * .75,
          after['light stick'])
    check('sprint keeps original speed', abs(after['sprint']['speed_mps'] - before['sprint']['speed_mps']) < .2,
          {'before': before['sprint']['speed_mps'], 'after': after['sprint']['speed_mps']})
    check('normal dribble gives the ball more room',
          after['walking']['median_ball_distance_m'] > before['walking']['median_ball_distance_m'] + .03,
          {'before': before['walking']['median_ball_distance_m'], 'after': after['walking']['median_ball_distance_m']})
    report['result'] = 'passed' if all(c['result'] == 'passed' for c in report['checks']) else 'failed'
except BaseException as error:
    report['result'] = 'failed'
    report['error'] = str(error)
    raise
finally:
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
if report['result'] != 'passed':
    raise SystemExit(1)
