#!/usr/bin/env python3
"""Compare measured traces without fitting time, scale or rotation to hide errors."""
import argparse
import bisect
import hashlib
import json
import math
from pathlib import Path
import statistics


def finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def validate(trace):
    if trace.get('schema_version') != 1 or trace.get('units') != dict(time='s', distance='m'):
        raise ValueError('trace must declare schema 1 and seconds/metres')
    if trace.get('axes') != 'x_forward_y_left_z_up':
        raise ValueError('trace axes must be explicitly normalized')
    for key in ('game', 'executable_sha256', 'scenario', 'conditions', 'evidence', 'required_inputs', 'observed_inputs'):
        if key not in trace:
            raise ValueError('missing trace metadata: ' + key)
    digest = trace['executable_sha256']
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('missing actual executable SHA256')
    if not trace['conditions'] or not trace['evidence'].get('method'):
        raise ValueError('conditions and measurement method must be documented')
    if trace['evidence'].get('kind') not in ('instrumented', 'video_digitized', 'synthetic'):
        raise ValueError('unsupported measurement provenance')
    observed = trace['observed_inputs']
    required = trace['required_inputs']
    if not isinstance(observed, list) or not isinstance(required, list) or not set(required) <= set(observed):
        raise ValueError('required controller channels were not recorded')
    if not set(observed) <= {'move', 'shot', 'sprint', 'short_pass', 'high_pass', 'through_pass'}:
        raise ValueError('unsupported controller channel')
    samples = trace.get('samples', [])
    if len(samples) < 10:
        raise ValueError('at least ten measured samples required')
    previous = -1
    for frame in samples:
        t = frame['t']
        if not finite(t) or t < 0 or t <= previous:
            raise ValueError('timestamps must be finite, nonnegative and strictly increasing')
        if previous >= 0 and t - previous > .200001:
            raise ValueError('measurement gap exceeds 200 ms')
        previous = t
        for key in ('player', 'ball'):
            value = frame[key]
            if not isinstance(value, list) or len(value) != 3 or not all(finite(v) for v in value):
                raise ValueError('invalid three-dimensional position')
        for channel in observed:
            value = frame['input'][channel]
            if channel == 'move':
                if not isinstance(value, list) or len(value) != 2 or not all(finite(v) and abs(v) <= 1.0001 for v in value):
                    raise ValueError('invalid normalized movement input')
            elif not isinstance(value, bool):
                raise ValueError('button channels must be boolean')
    if abs(samples[0]['t']) > 1e-6:
        raise ValueError('trace must start at the declared t=0, without automatic alignment')
    return trace


def interpolate(samples, times, t):
    if t < times[0] or t > times[-1]:
        raise ValueError('extrapolation is prohibited')
    index = min(bisect.bisect_right(times, t) - 1, len(times) - 2)
    left, right = samples[index:index + 2]
    weight = (t - left['t']) / (right['t'] - left['t'])
    position = {key: [a + (b - a) * weight for a, b in zip(left[key], right[key])] for key in ('player', 'ball')}
    # Controller commands are sampled states, not spline-interpolated movement.
    position.update(t=t, input=(right if weight >= 1 - 1e-8 else left)['input'])
    return position


def motion_summary(samples):
    speeds = [math.dist(a['player'], b['player']) / (b['t'] - a['t']) for a, b in zip(samples, samples[1:])]
    gaps = [math.dist(s['player'][:2], s['ball'][:2]) for s in samples]
    return dict(duration_s=samples[-1]['t'],
                player_path_m=sum(math.dist(a['player'], b['player']) for a, b in zip(samples, samples[1:])),
                maximum_sampled_player_speed_mps=max(speeds), mean_player_ball_gap_m=statistics.mean(gaps),
                maximum_player_ball_gap_m=max(gaps), maximum_sampled_ball_height_m=max(s['ball'][2] for s in samples))


def compare(reference, candidate, tolerances):
    validate(reference)
    validate(candidate)
    for key in ('scenario', 'conditions', 'required_inputs'):
        if reference[key] != candidate[key]:
            raise ValueError('non-comparable setup: ' + key)
    if set(reference['observed_inputs']) != set(candidate['observed_inputs']):
        raise ValueError('recorded controller channels differ')
    wanted = {'player_position_rmse_m', 'ball_position_rmse_m', 'player_speed_rmse_mps', 'maximum_input_error'}
    if set(tolerances) != wanted or any(not finite(v) or v <= 0 for v in tolerances.values()):
        raise ValueError('four explicit positive engineering error budgets required')
    a, b = reference['samples'], candidate['samples']
    if abs(a[-1]['t'] - b[-1]['t']) > .001:
        raise ValueError('duration differs; do not time-warp the action')
    times = [s['t'] for s in b]
    # Use the coarser source cadence; resampling must not invent resolution.
    cadence = max(statistics.median(y['t'] - x['t'] for x, y in zip(s, s[1:])) for s in (a, b))
    selected = [a[0]]
    for frame in a[1:]:
        if frame['t'] - selected[-1]['t'] >= cadence - 1e-7:
            selected.append(frame)
    if len(selected) < 10:
        raise ValueError('not enough aligned samples at the measured cadence')
    other = [interpolate(b, times, min(s['t'], times[-1])) for s in selected]
    input_error = 0.
    for left, right in zip(selected, other):
        for channel in reference['observed_inputs']:
            av, bv = left['input'][channel], right['input'][channel]
            input_error = max(input_error, max(abs(x - y) for x, y in zip(av, bv)) if channel == 'move' else float(av != bv))
    rms = lambda values: math.sqrt(statistics.mean(v * v for v in values))
    velocity = lambda samples: [[(y - x) / (v['t'] - u['t']) for x, y in zip(u['player'], v['player'])] for u, v in zip(samples, samples[1:])]
    metrics = dict(player_position_rmse_m=rms(math.dist(x['player'], y['player']) for x, y in zip(selected, other)),
                   ball_position_rmse_m=rms(math.dist(x['ball'], y['ball']) for x, y in zip(selected, other)),
                   player_speed_rmse_mps=rms(math.dist(x, y) for x, y in zip(velocity(selected), velocity(other))),
                   maximum_input_error=input_error)
    within = all(metrics[key] <= budget for key, budget in tolerances.items())
    measured_pair = (reference['game'] == 'pes2017' and candidate['game'] == 'football' and
                     all(t['evidence']['kind'] != 'synthetic' for t in (reference, candidate)))
    return dict(schema_version=1,
                result=('within_declared_tolerances' if within else 'outside_declared_tolerances') if measured_pair else 'self_or_synthetic_test_only',
                within_declared_tolerances=within, pes_comparison=measured_pair,
                metrics=metrics, tolerances=tolerances, compared_samples=len(selected),
                temporal_resolution_s=cadence, reference_summary=motion_summary(a), candidate_summary=motion_summary(b),
                reference_evidence=reference['evidence'], candidate_evidence=candidate['evidence'],
                reference_executable_sha256=reference['executable_sha256'], candidate_executable_sha256=candidate['executable_sha256'],
                scope='Measured trajectory and recorded command comparison only. Declared provenance is not independently authenticated. No code equivalence, animation equivalence or complete gameplay certification.',
                tolerance_origin='Explicit engineering acceptance targets, not parameters extracted from PES.')


def export_native(log, case, executable, start_ms, end_ms, heading_rad=0):
    if not finite(heading_rad) or end_ms <= start_ms:
        raise ValueError('invalid explicit interval or coordinate heading')
    frames = []
    segment = 0
    for line in Path(log).read_text().splitlines():
        if line.startswith('TRAINING_RESET '):
            segment += 1
        elif line.startswith('TRAINING_FRAME '):
            frame = json.loads(line.partition('TRAINING_FRAME ')[2])
            frame['_segment'] = segment
            frames.append(frame)
    frames = [f for f in frames if start_ms <= f['t'] <= end_ms]
    if not frames or frames[0]['t'] != start_ms or frames[-1]['t'] != end_ms:
        raise ValueError('explicit start/end samples not found')
    if len({f['_segment'] for f in frames}) != 1:
        raise ValueError('selected interval crosses a training reset')
    origin = frames[0]['player']
    def point(value):
        x, y = value[0] - origin[0], value[1] - origin[1]
        return [x * math.cos(heading_rad) + y * math.sin(heading_rad),
                -x * math.sin(heading_rad) + y * math.cos(heading_rad), value[2]]
    keyboard = all(f['controller'] == 0 for f in frames)
    channels = ['move', 'shot'] + (['short_pass', 'through_pass', 'high_pass', 'sprint'] if keyboard else [])
    samples = []
    for frame in frames:
        commands = dict(move=frame['move'], shot=bool(frame['shot_active']))
        if keyboard:
            commands.update({name: bool(frame['keys'] & (1 << bit)) for name, bit in [('short_pass', 4), ('through_pass', 5), ('high_pass', 6), ('sprint', 8)]})
        samples.append(dict(t=(frame['t'] - start_ms) / 1000, player=point(frame['player']), ball=point(frame['ball']), input=commands))
    trace = dict(schema_version=1, game='football', units=dict(time='s', distance='m'), axes='x_forward_y_left_z_up',
                 executable_sha256=hashlib.sha256(Path(executable).read_bytes()).hexdigest(),
                 scenario=case['scenario'], conditions=case['conditions'], required_inputs=case['required_inputs'], observed_inputs=channels,
                 evidence=dict(kind='instrumented', method='Existing TRAINING_FRAME log; positions at simulation cadence. No rendering-derived motion.',
                               source_sha256=hashlib.sha256(Path(log).read_bytes()).hexdigest(), start_ms=start_ms, end_ms=end_ms,
                               transform=dict(horizontal_origin_m=origin[:2], heading_rad=heading_rad, scale=1),
                               limitation='Current gamepad log records movement and shot only. Other gamepad buttons must not be inferred.'), samples=samples)
    elapsed_wall = frames[-1]['wall_ms'] - frames[0]['wall_ms']
    if elapsed_wall <= 0:
        raise ValueError('non-monotonic wall clock')
    trace['evidence']['simulation_real_time_ratio'] = (end_ms - start_ms) / elapsed_wall
    return validate(trace)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export-native')
    export.add_argument('--log', type=Path, required=True)
    export.add_argument('--case', type=Path, required=True)
    export.add_argument('--executable', type=Path, required=True)
    export.add_argument('--start-ms', type=int, required=True)
    export.add_argument('--end-ms', type=int, required=True)
    export.add_argument('--heading-rad', type=float, default=0.)
    comparison = sub.add_parser('compare')
    comparison.add_argument('--reference', type=Path, required=True)
    comparison.add_argument('--candidate', type=Path, required=True)
    comparison.add_argument('--tolerances', type=Path, required=True)
    for child in (export, comparison):
        child.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))
    if args.command == 'export-native':
        result = export_native(args.log, load(args.case), args.executable, args.start_ms, args.end_ms, args.heading_rad)
    else:
        result = compare(load(args.reference), load(args.candidate), load(args.tolerances))
        for key, path in [('reference_trace_sha256', args.reference), ('candidate_trace_sha256', args.candidate)]:
            result[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    with args.output.open('x', encoding='utf-8') as target:
        json.dump(result, target, indent=2, allow_nan=False)
        target.write('\n')
    print(json.dumps(dict(result=result.get('result', 'exported'), samples=len(result.get('samples', [])))))
    if args.command == 'compare' and not result['within_declared_tolerances']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
