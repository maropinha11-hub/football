#!/usr/bin/env python3
"""Native gameplay with FP input: sprint release, reserved RT and real-time pace."""
import argparse
import json
import math
import re
import statistics
import subprocess
from pathlib import Path
from native_training_harness import NativeTraining

parser = argparse.ArgumentParser()
parser.add_argument('--build', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--display', default=':95')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
report = {'result': 'running', 'checks': [], 'cases': []}

def check(name, ok, evidence):
    report['checks'].append({'check': name, 'result': 'passed' if ok else 'failed', 'evidence': evidence})
    print(('PASS ' if ok else 'FAIL ') + name + ': ' + str(evidence), flush=True)

def retain(name, frames):
    distances = [math.dist(f['player'][:2], f['ball'][:2]) for f in frames]
    evidence = {'max_distance_m': max(distances), 'end_distance_m': distances[-1],
                'controlled': sum(f['with_ball'] for f in frames), 'samples': len(frames)}
    check(name, max(distances) < 2.3 and distances[-1] < 1.2 and all(f['with_ball'] for f in frames), evidence)
    return evidence

try:
    for name in ('ball.cpp', 'ball.hpp', 'player/humanoid/humanoid_utils.cpp'):
        original = subprocess.check_output(['git', 'show', '881193e:src/onthepitch/' + name], cwd=root)
        check(name + ' matches original source', (root/'src/onthepitch'/name).read_bytes() == original,
              'Original Gameplay Football source, upstream revision 68159a2')
    with NativeTraining(args.build, args.output / 'game', display=args.display, analog_pad=True) as game:
        for duration in (300, 900, 1800, 3500):
            game.reset()
            game.pad(0, -1, sprint=True)
            running = game.advance(duration)
            game.pad(0, -1)
            walking = game.advance(2400)
            evidence = retain('RB release after ' + str(duration) + ' ms retains ball', running + walking)
            report['cases'].append({'case': 'sprint release ' + str(duration), 'evidence': evidence,
                                    'frames': running + walking})
            speed = statistics.median(f['speed'] for f in walking[-5:])
            check('RB release after ' + str(duration) + ' ms returns to native walking',
                  4.0 < speed < 5.5, {'walking_speed_mps': speed})
        game.reset()
        repeated = []
        for _ in range(4):
            game.pad(0, -1, sprint=True); repeated.extend(game.advance(700))
            game.pad(0, -1); repeated.extend(game.advance(700))
        retain('repeated RB presses and releases retain ball', repeated)
        game.pad(0, 0)
        stopped = game.advance(2000)
        retain('release RB and stick keeps ball within reach', stopped)
        check('native stop settles without forced touches', stopped[-1]['speed'] < .5 and
              stopped[-1]['ball_speed'] < 1, {'player_speed': stopped[-1]['speed'], 'ball_speed': stopped[-1]['ball_speed']})
        modes = {}
        for rt in (False, True):
            for sprint in (False, True):
                game.reset(); game.pad(0, -1, sprint=sprint, close=rt); game.advance(1500)
                samples = game.advance(1600)
                retain('RT ' + str(rt) + ' RB ' + str(sprint) + ' retains ball', samples)
                modes[(rt, sprint)] = statistics.median(f['speed'] for f in samples)
        for sprint in (False, True):
            check('RT has no speed effect with RB ' + str(sprint),
                  abs(modes[(False, sprint)] - modes[(True, sprint)]) < .15,
                  {'without_RT': modes[(False, sprint)], 'with_RT': modes[(True, sprint)]})
        game.reset()
        origin = game.frames()[-1]
        game.pad(0, -1)
        game.keys(['Right'], True); looking = game.advance(400); game.keys(['Right'], False)
        check('head look stays independent with ball', abs(looking[-1]['head_yaw']) > .3 and
              abs(looking[-1]['player'][1] - origin['player'][1]) < .3, looking[-1])
        check('head recenters gradually', abs(game.advance(2200)[-1]['head_yaw']) < .2, 'Native body direction retained')
        game.reset(); game.pad(0, -1)
        game.advance(1000); origin = game.frames()[-1]; timed = game.advance(4000)
        ratio = (timed[-1]['t'] - origin['t']) / (timed[-1]['wall_ms'] - origin['wall_ms'])
        check('simulation runs in real time', .85 < ratio < 1.15, {'simulation_to_real_time': ratio})
        # Real Xbox face buttons; native contact times, power and impulses.
        for name, button, function in [('short pass', 0, 4), ('through pass', 3, 5),
                                       ('high pass', 1, 6), ('shot', 2, 8)]:
            game.reset(); start = game.frames()[-1]['t']
            game.pad(0, 0, buttons=1 << button); game.advance(300); game.pad(0, 0)
            samples = game.advance(2200)
            touches = [(int(t), int(kind)) for t, kind in re.findall(
                r'TRAINING_ACTION_TOUCH t=(\d+) part=\w+ function=(\d+)', game.log.read_text()) if int(t) > start]
            check('original ' + name + ' acts at native contact', any(kind == function for _, kind in touches) and
                  max(f['ball_speed'] for f in samples) > 4, {'touches': touches, 'peak_speed_mps': max(f['ball_speed'] for f in samples)})
        log = game.log.read_text()
        check('native pose and impulses remain active', not any(token in log for token in
              ('PES3_BODY_APPLY', 'TRAINING_PULLBACK', 'TRAINING_TURN_TOUCH', 'TRAINING_FOOT_POSE')), 'No custom pose or dribble impulse overrides')
        game.keys(['Escape'], True); game.game.wait(timeout=15)
        check('clean exit', game.game.returncode == 0, game.game.returncode)
    report['result'] = 'passed' if all(c['result'] == 'passed' for c in report['checks']) else 'failed'
except BaseException as error:
    report['result'] = 'failed'; report['error'] = str(error)
    raise
finally:
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'validation.json').write_text(json.dumps(report, indent=2) + '\n')
if report['result'] != 'passed':
    raise SystemExit(1)
