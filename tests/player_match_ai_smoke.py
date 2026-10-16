#!/usr/bin/env python3
"""Exercise autonomous teammates/opponents in a rendered fixed-player match.

Unlike an all-player movement check, the idle-ball regression only measures
live play with a stationary low ball beside a stationary CPU player. The old
build left a home defender in that state for 13.5 seconds (seed 9 fixture).
No input or pass request rescues the CPU in this test.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

from native_training_harness import NativeTraining


def events(lines, prefix):
    return [dict(re.findall(r'(\w+)=([^\s]+)', line))
            for line in lines if line.startswith(prefix + ' ')]


def stationary_ball_spans(frames):
    spans = []
    current = None
    for frame in frames:
        players = frame['players']
        nearest = min(players, key=lambda p: math.dist(p['p'][:2], frame['ball'][:2]))
        stationary = (frame['in_play'] and not frame['set_piece'] and not frame['over']
                      and not nearest['human'] and frame['ball'][2] < .5
                      and math.dist(nearest['p'][:2], frame['ball'][:2]) < 1.1
                      and frame['ball_speed'] < 1 and nearest['speed'] < .35)
        key = nearest['id']
        if stationary:
            if current and current['actor'] == key and frame['t'] - current['end'] <= 600:
                current['end'] = frame['t']
            else:
                if current:
                    spans.append(current)
                current = dict(actor=key, team=nearest['team'], start=frame['t'], end=frame['t'])
        elif current:
            spans.append(current)
            current = None
    if current:
        spans.append(current)
    return sorted(spans, key=lambda s: s['end'] - s['start'], reverse=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--display', default=':154')
    parser.add_argument('--seed', type=int, default=9)
    parser.add_argument('--validate-existing', action='store_true',
                        help='Reevaluate this fixture log, verifying the recorded executable hash and exit result')
    args = parser.parse_args()
    report = dict(result='running', seed=args.seed, checks=[],
                  executable_sha256=hashlib.sha256((args.build / 'gameplayfootball').read_bytes()).hexdigest())

    def check(name, ok, evidence):
        item = dict(check=name, result='passed' if ok else 'failed', evidence=evidence)
        report['checks'].append(item)
        print(json.dumps(item), flush=True)

    try:
        if args.validate_existing:
            previous = json.loads((args.output / 'validation.json').read_text())
            assert previous['executable_sha256'] == report['executable_sha256']
            assert previous['seed'] == args.seed
            exit_check = next(c for c in previous['checks'] if c['check'] == 'clean rendered game exit')
            assert exit_check['result'] == 'passed' and exit_check['evidence'] == 0
            lines = (args.output / 'game' / 'game.log').read_text().splitlines()
            training = [json.loads(line[15:]) for line in lines if line.startswith('TRAINING_FRAME ')]
            exit_code = 0
        else:
            with NativeTraining(args.build, args.output / 'game', display=args.display,
                                analog_pad=True, config_overrides={
                                    'context_x': 320, 'context_y': 180, 'player_match': 'true',
                                    'player_match_half_seconds': 60, 'simulation_seed': args.seed}) as game:
                game.wait(lambda: 'PLAYER_MATCH_END ' in game.log.read_text(), seconds=280)
                lines = game.log.read_text().splitlines()
                training = game.frames()
                game.keys(['Escape'], True)
                game.game.wait(timeout=15)
                exit_code = game.game.returncode
        frames = [json.loads(line[19:]) for line in lines if line.startswith('PLAYER_MATCH_FRAME ')]
        decisions = events(lines, 'PLAYER_MATCH_AI')
        actions = events(lines, 'PLAYER_MATCH_ACTION')
        locked = frames[0]['locked_id']
        check('maximum original difficulty', all(f['difficulty'] == 1 for f in frames),
              sorted({f['difficulty'] for f in frames}))
        check('both complete teams keep one fixed human', all(
            f['human_count'] == 1 and f['locked_id'] == f['selected_id'] == locked
            and [p['id'] for p in f['players'] if p['human']] == [locked]
            and all(sum(p['team'] == side for p in f['players']) == 11 for side in (0, 1))
            for f in frames), dict(frames=len(frames), locked=locked))
        kickoff_shape = {}
        for side in (0, 1):
            team = [p for p in frames[0]['players'] if p['team'] == side]
            keeper = min(team, key=lambda p: p['id'])
            kickoff_shape[side] = dict(
                width_m=max(p['p'][1] for p in team) - min(p['p'][1] for p in team),
                depth_m=max(p['p'][0] for p in team) - min(p['p'][0] for p in team),
                keeper_position=keeper['p'])
        check('native kickoff formation retains width, depth and a goalkeeper at each goal',
              all(s['width_m'] > 25 and s['depth_m'] > 30
                  and abs(s['keeper_position'][0]) > 45 and abs(s['keeper_position'][1]) < 3
                  for s in kickoff_shape.values()), kickoff_shape)
        for side in (0, 1):
            team_decisions = [d for d in decisions if int(d['team']) == side]
            check(f'team {side} autonomously evaluates on-ball play',
                  len(team_decisions) >= 15 and all(int(d['actor']) != locked for d in team_decisions),
                  dict(samples=len(team_decisions), actors=sorted({d['actor'] for d in team_decisions})))
            moving = [d for d in team_decisions if float(d['desired_speed']) > 1]
            check(f'team {side} chooses to advance with the ball', len(moving) >= 10,
                  dict(advancing_decisions=len(moving)))
            team_passes = [a for a in actions if int(a['team']) == side and a['action'] in ('4', '5', '6')]
            check(f'team {side} executes native passes without human requests',
                  len(team_passes) >= 2 and all(a['requested'] == '0' for a in team_passes), team_passes)
            # Many different CPU actors physically collect/control/intercept the ball.
            collectors = {a['actor'] for a in actions if int(a['team']) == side
                          and a['action'] in ('2', '3', '11') and int(a['actor']) != locked}
            check(f'team {side} players actively collect the ball', len(collectors) >= 3,
                  sorted(collectors))
        spans = stationary_ball_spans(frames)
        longest = max((s['end'] - s['start'] for s in spans), default=0)
        check('no CPU remains parked beside a stationary ball for five seconds',
              longest < 5000, dict(longest_ms=longest, longest_spans=spans[:5]))
        # Native shots are conditional on reaching the central shooting zone.
        # Do not require an aimless shot in a fixture that only attacks wide.
        shooting_zone_samples = 0
        for frame in frames:
            carrier = next(p for p in frame['players'] if p['id'] == frame['designated_id'])
            attack_side = (1 if carrier['team'] == 0 else -1) * (1 if frame['phase'] == 1 else -1)
            if (frame['in_play'] and not frame['set_piece'] and not carrier['human']
                    and math.dist(carrier['p'][:2], [48 * attack_side, 0]) < 14.4):
                shooting_zone_samples += 1
        shots = [a for a in actions if a['action'] == '8']
        if shots or shooting_zone_samples:
            check('native attacking decisions produce actual shots in a shooting-zone fixture',
                  bool(shots), dict(shots=shots, shooting_zone_samples=shooting_zone_samples))
        else:
            report['coverage_note'] = 'No CPU entered the native central shooting zone; actual shots are covered by the other match fixture.'
        report['native_shots'] = shots
        check('two halves finish with the human idle', frames[-1]['over'] == 1
              and {1, 2} <= {f['phase'] for f in frames},
              dict(last_t=frames[-1]['t'], score=[frames[-1]['home'], frames[-1]['away']]))
        pace = ((training[-1]['t'] - training[0]['t']) /
                (training[-1]['wall_ms'] - training[0]['wall_ms']))
        check('simulation retains real time pace', .9 < pace < 1.1, pace)
        report['actions_by_team_and_type'] = dict(Counter(a['team'] + ':' + a['action'] for a in actions))
        check('clean rendered game exit', exit_code == 0, exit_code)
        report['result'] = 'passed' if all(c['result'] == 'passed' for c in report['checks']) else 'failed'
    except BaseException as exc:
        report.update(result='failed', error=str(exc))
        raise
    finally:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['result'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
