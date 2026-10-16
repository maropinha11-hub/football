#!/usr/bin/env python3
"""Rendered SDL/Xbox checks for the experimental physical training profile."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

from native_training_harness import NativeTraining


def events(text, prefix):
    return [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines()
            if line.startswith(prefix + ' ')]


def physical_frames(game):
    return [json.loads(line[len('PHYSICAL_RIG_FRAME '):]) for line in game.log.read_text().splitlines()
            if line.startswith('PHYSICAL_RIG_FRAME ')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--display', default=':154')
    parser.add_argument('--match', action='store_true')
    args = parser.parse_args()
    report = dict(result='running', checks=[], scenario='contact_match' if args.match else 'training',
                  executable_sha256=hashlib.sha256((args.build / 'gameplayfootball').read_bytes()).hexdigest())

    def check(name, ok, evidence):
        row = dict(check=name, result='passed' if ok else 'failed', evidence=evidence)
        report['checks'].append(row)
        print(json.dumps(row), flush=True)

    def key(game, name):
        game.keys([name], True)
        game.keys([name], False)

    def screenshot(game, name):
        subprocess.run(['import', '-window', game.window, str(args.output / (name + '.png'))],
                       env=game.env, check=True)

    try:
        with NativeTraining(args.build, args.output / 'game', display=args.display, analog_pad=True,
                            camera=1, config_overrides={
                                'context_x': 640, 'context_y': 360,
                                'training_physical_rig': 'true', 'training_physical_lab': 'true',
                                'player_match': 'true' if args.match else 'false',
                                'player_match_half_seconds': 60, 'simulation_seed': 9}) as game:
            check('physical pose is simulated at startup', len(physical_frames(game)) >= 3,
                  physical_frames(game)[-1])
            if args.match:
                game.advance(2500)
                for _ in range(40):
                    frames = [json.loads(line[19:]) for line in game.log.read_text().splitlines()
                              if line.startswith('PLAYER_MATCH_FRAME ')]
                    frame = frames[-1]
                    actor = next(p for p in frame['players'] if p['human'])
                    opponents = [p for p in frame['players'] if p['team'] == 1 and p['id'] != 18]
                    opponent = min(opponents, key=lambda p: math.dist(p['p'][:2], actor['p'][:2]))
                    dx, dy = [opponent['p'][i] - actor['p'][i] for i in range(2)]
                    size = max(.001, math.hypot(dx, dy))
                    game.pad(dx / size, -dy / size, sprint=True)
                    game.advance(400)
                game.pad(0, 0)
                log = game.log.read_text()
                check('real native player collisions feed impulses into the controlled physical rig',
                      bool(events(log, 'PHYSICAL_RIG_IMPULSE')), events(log, 'PHYSICAL_RIG_IMPULSE')[:12])
                check('CPU formation and player lock coexist with the physical actor',
                      all(f['human_count'] == 1 and f['selected_id'] == f['locked_id']
                          and len(f['players']) == 22 for f in frames), dict(frames=len(frames)))
                screenshot(game, 'physical-contact-match')
            else:
                game.reset()
                start = len(game.log.read_text())
                origin = game.frames()[-1]
                game.pad(0, -1)
                frames = game.advance(3500)
                log = game.log.read_text()[start:]
                travel = math.dist(origin['player'][:2], frames[-1]['player'][:2])
                gap = max(math.dist(f['player'][:2], f['ball'][:2]) for f in frames)
                check('native right-foot dribble still advances under the physical layer',
                      travel > 8 and any(e.get('part') == 'right_foot' for e in events(log, 'TRAINING_ACTION_TOUCH')),
                      dict(travel_m=travel, maximum_ball_range_m=gap))
                check('ordinary physical dribbling retains the ball', gap < 2, gap)
                for stick in ((.7071, -.7071), (-.7071, -.7071), (0, 1)):
                    game.pad(*stick)
                    game.advance(1000)
                game.pad(0, 0)
                check('ordinary walking turns remain upright',
                      all(f['mode'] == 0 for f in physical_frames(game)),
                      dict(peak_lean=max(f['lean'] for f in physical_frames(game))))
                screenshot(game, 'physical-dribble')
                game.reset()
                start_t = game.frames()[-1]['t']
                key(game, 'F8')
                game.advance(1200)
                response = [f for f in physical_frames(game) if f['t'] >= start_t]
                check('small physical impulse produces damped balance without a fall',
                      max(f['lean'] for f in response) > .025 and all(f['mode'] == 0 for f in response),
                      dict(peak_lean=max(f['lean'] for f in response)))
                for cycle in range(2):
                    game.reset()
                    start = len(game.log.read_text())
                    key(game, 'F9')
                    game.pad(0, -1, buttons=4)
                    game.advance(850)
                    game.pad(0, 0)
                    if cycle == 0:
                        screenshot(game, 'physical-fall')
                    game.wait(lambda: 'PHYSICAL_RIG_RECOVERED ' in game.log.read_text()[start:], seconds=18)
                    segment = game.log.read_text()[start:]
                    states = events(segment, 'PHYSICAL_RIG_STATE')
                    check(f'fall {cycle + 1} completes falling, get-up and return to control without a crash',
                          {('0', '1'), ('1', '2'), ('2', '0')} <= {(e['from'], e['to']) for e in states}, states)
                    # Controls held while falling cannot fire an invisible queued kick.
                    check(f'fall {cycle + 1} does not execute a queued kick through the physical body',
                          not events(segment, 'TRAINING_ACTION_TOUCH'), events(segment, 'TRAINING_ACTION_TOUCH'))
                    game.pad(0, -1)
                    frames = game.advance(650)
                    game.pad(0, 0)
                    check(f'movement resumes after fall {cycle + 1}', max(f['speed'] for f in frames) > 1,
                          max(f['speed'] for f in frames))
                screenshot(game, 'physical-recovered')
                falls = [f for f in physical_frames(game) if f['mode'] == 1]
                check('pelvis and articulated body actually descend during the fall',
                      bool(falls) and min(f['root'][2] for f in falls) < .6,
                      dict(minimum_pelvis_m=min(f['root'][2] for f in falls)))
                # Physical pose composition must keep the source hierarchy lengths.
                rendered = events(game.log.read_text(), 'PHYSICAL_RIG_RENDER')
                check('rendered skeleton preserves its bone lengths', bool(rendered)
                      and max(float(e['length_error']) for e in rendered) < 1e-5,
                      dict(samples=len(rendered), maximum_error_m=max(float(e['length_error']) for e in rendered)))
                game.reset()
                key(game, 'F5')
                game.advance(2600)
                log = game.log.read_text()
                upper = [e for e in events(log, 'TRAINING_ACTION_TOUCH') if e.get('upper_layer') == '1']
                check('standing chest reception still makes actual skin contact in the physical profile',
                      bool(upper), upper[-2:])
                # Keyboard toggle compares profiles without repurposing Xbox controls.
                key(game, 'F7')
                start = len(game.log.read_text())
                game.advance(350)
                check('F7 disables the experiment for comparison', 'PHYSICAL_RIG_TOGGLE enabled=0' in game.log.read_text()
                      and not physical_frames_from_text(game.log.read_text()[start:]), {})
                key(game, 'F7')
                game.advance(200)
                check('F7 re-enables physical composition', 'PHYSICAL_RIG_TOGGLE enabled=1' in game.log.read_text(), {})
                game.reset()
                key(game, 'F9')
                game.advance(400)
                key(game, 'r')
                game.advance(350)
                check('R clears a fall and its momentum immediately', physical_frames(game)[-1]['mode'] == 0,
                      physical_frames(game)[-1])
                # First person still uses the interpolated head and right-stick look.
                key(game, 'Tab')
                game.advance(100)
                game.keys(['Right'], True)
                game.advance(400)
                game.keys(['Right'], False)
                check('first-person head look remains responsive', game.frames()[-1]['camera'] == 2
                      and abs(game.frames()[-1]['head_yaw']) > .1, game.frames()[-1])
                screenshot(game, 'physical-first-person')
            log = game.log.read_text()
            skin = [e for e in events(log, 'TRAINING_SKIN_CONTACT') if e['accepted'] == '1']
            touches = events(log, 'TRAINING_ACTION_TOUCH')
            accepted = {e['t'] for e in skin}
            if touches or not args.match:
                check('all authored ball impulses retain the real-skin gate', bool(touches)
                      and all(e['t'] in accepted for e in touches)
                      and all(float(e['gap']) <= .00251 for e in skin),
                      dict(impulses=len(touches), accepted_contacts=len(skin)))
            else:
                report['ball_contact_coverage'] = 'Not exercised by this body-collision fixture; checked in the separate solo suite.'
            game.keys(['Escape'], True)
            game.game.wait(timeout=15)
            check('clean game exit', game.game.returncode == 0, game.game.returncode)
        report['result'] = 'passed' if all(c['result'] == 'passed' for c in report['checks']) else 'failed'
    except BaseException as exc:
        report.update(result='failed', error=str(exc))
        raise
    finally:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['result'] != 'passed':
        raise SystemExit(1)


def physical_frames_from_text(text):
    return [line for line in text.splitlines() if line.startswith('PHYSICAL_RIG_FRAME ')]


if __name__ == '__main__':
    main()
