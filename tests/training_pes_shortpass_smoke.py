"""Exercise an annotated PES pass through native selection and real skin contact.

This validates Football integration, not equivalence with PES ball physics,
timing or selection. Off-axis/running passes must retain native fallback.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

from native_training_harness import NativeTraining


def events(text, prefix):
    return [dict(re.findall(r'(\w+)=([^\s]+)', line))
            for line in text.splitlines() if line.startswith(prefix + ' ')]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--display', default=':3950')
    p.add_argument('--camera', type=int, choices=[1, 2], default=1)
    p.add_argument('--launch-via-cli', action='store_true', help='Use the same --pes-actions switch as the Windows launcher')
    a = p.parse_args()
    report = dict(result='running', checks=[], scenarios={},
                  executable_sha256=hashlib.sha256((a.build/'gameplayfootball').read_bytes()).hexdigest(),
                  scope='Rendered Linux/SDL Xbox input. One retargeted pass with an annotated Football contact; not original PES gameplay.')

    def check(name, ok, evidence):
        row = dict(check=name, result='passed' if ok else 'failed', evidence=evidence)
        report['checks'].append(row)
        print(json.dumps(row), flush=True)

    try:
        with NativeTraining(a.build, a.output/'game', display=a.display, analog_pad=True, camera=a.camera,
                            config_overrides=dict(context_x=640, context_y=360, training_physical_lab='true',
                                                  training_pes_shortpass='false' if a.launch_via_cli else 'true'),
                            extra_arguments=['--pes-actions'] if a.launch_via_cli else []) as g:
            def pad(x, y, **kw):
                g.pad(*((-y, x) if a.camera == 1 else (x, y)), **kw)

            def toggle(expected):
                start = len(g.read_log())
                g.keys(['Insert'], True); g.advance(100)
                g.keys(['Insert'], False); g.advance(100)
                rows = events(g.read_log()[start:], 'PES_ACTION_TOGGLE')
                check('Insert changes comparison mode to '+str(expected),
                      len(rows) == 1 and rows[0]['enabled'] == str(int(expected)), rows)

            for name, enabled, run, stick, hold in [
                    ('short_pass', True, 0, (0, 0), 120),
                    ('medium_pass', True, 0, (0, 0), 180),
                    ('native_comparison', False, 0, (0, 0), 120),
                    ('running_fallback', True, 900, (0, -1), 180),
                    ('sideways_fallback', True, 0, (1, 0), 180)]:
                if name in ('native_comparison', 'running_fallback'):
                    toggle(enabled)
                g.reset()
                if run:
                    pad(0, -1, sprint=True); g.advance(run)
                start = len(g.read_log())
                pad(*stick, sprint=bool(run), buttons=1); g.advance(hold)
                pad(*stick, sprint=bool(run))
                for _ in range(35):
                    g.advance(50)
                    if events(g.read_log()[start:], 'TRAINING_ACTION_TOUCH'):
                        break
                if name == 'short_pass':
                    subprocess.run(['import', '-window', g.window, str(a.output/'short-pass.png')],
                                   env=g.env, check=True)
                g.advance(1800)
                pad(0, 0)
                log = g.read_log()[start:]
                hits = [r for r in events(log, 'TRAINING_ACTION_TOUCH') if r['function'] == '4']
                pes = events(log, 'PES_ACTION_CONTACT')
                selected = [r for r in events(log, 'TRAINING_NATIVE_START') if r['function'] == '4']
                expected_pes = name in ('short_pass', 'medium_pass')
                report['scenarios'][name] = dict(touches=hits, pes_contacts=pes, selected=selected)
                check(name+' completes one pass using the expected source',
                      len(hits) == 1 and len(pes) == int(expected_pes) and bool(selected)
                      and any(('pes17/' in r['name']) == expected_pes for r in selected),
                      report['scenarios'][name])
                if expected_pes:
                    skins = [r for r in events(log, 'TRAINING_SKIN_CONTACT')
                             if pes and r['t'] == pes[0]['t'] and r.get('part') == 'right_foot'
                             and r.get('accepted') == '1']
                    check(name+' strikes with the annotated right foot on the actual skin',
                          len(pes) == 1 and pes[0]['part'] == 'right_foot' and bool(skins)
                          and max(float(r['gap']) for r in skins) <= .00251
                          and -3 <= int(pes[0]['frame'])-int(pes[0]['planned']) <= 6,
                          dict(contact=pes, skins=skins))
                    time = int(pes[0]['t']) if pes else -10000
                    frames = [f for f in g.frames() if time <= f['t'] <= time+600]
                    check(name+' sends the real ball forward', bool(frames)
                          and max(f['ball_speed'] for f in frames) > 4
                          and frames[-1]['ball'][0]-frames[0]['ball'][0] > 1,
                          dict(frames=frames))
                    joints = [r for r in events(log, 'TRAINING_CONTACT_JOINTS')
                              if time-600 <= int(r['t']) <= time+1500]
                    quats = [[float(x) for x in row[key].strip('[]').split(',')]
                             for row in joints for key in row if key.startswith('j')]
                    check(name+' keeps rendered joint rotations finite and normalized',
                          bool(quats) and all(all(math.isfinite(x) for x in q)
                                            and abs(sum(x*x for x in q)-1) < .00002 for q in quats),
                          dict(samples=len(joints), rotations=len(quats)))
                    rates = []
                    for previous, current in zip(joints, joints[1:]):
                        elapsed = (int(current['t'])-int(previous['t']))/1000
                        if not 0 < elapsed <= .08:
                            continue
                        for key in previous:
                            if not key.startswith('j'):
                                continue
                            u = [float(x) for x in previous[key].strip('[]').split(',')]
                            v = [float(x) for x in current[key].strip('[]').split(',')]
                            dot = sum(x*y for x, y in zip(u, v))/math.sqrt(sum(x*x for x in u)*sum(x*x for x in v))
                            rates.append(2*math.acos(min(1, abs(dot)))/elapsed)
                    check(name+' has no abrupt joint teleport through entry and exit',
                          len(rates) > 50 and max(rates) < 20,
                          dict(intervals=len(rates), maximum_angular_speed_rad_s=max(rates, default=0),
                               scope='Rendered local torso/leg joints, from 600 ms before contact through 1500 ms after contact'))
                    before = g.frames()[-1]['player']
                    pad(0, -1); moved = g.advance(800); pad(0, 0)
                    distance = math.dist(before[:2], moved[-1]['player'][:2])
                    check(name+' releases movement after the follow-through', distance > .4,
                          dict(distance_m=distance))

            # Deliberately put the ball out of reach; an animation must never
            # manufacture a PES touch while the ball is twenty metres away.
            g.reset()
            g.keys(['Shift_L', 'Control_L', 'F4'], True); g.advance(100)
            g.keys(['Shift_L', 'Control_L', 'F4'], False); g.advance(100)
            start = len(g.read_log()); pad(0, 0, buttons=1); g.advance(120)
            pad(0, 0); frames = g.advance(1000)
            log = g.read_log()[start:]
            check('an unreachable ball receives no invented pass contact',
                  not events(log, 'PES_ACTION_CONTACT') and not events(log, 'TRAINING_ACTION_TOUCH')
                  and min(math.dist(f['player'][:2], f['ball'][:2]) for f in frames) > 10,
                  dict(pes_contacts=events(log, 'PES_ACTION_CONTACT'),
                       minimum_distance_m=min(math.dist(f['player'][:2], f['ball'][:2]) for f in frames)))
            g.keys(['Escape'], True); g.game.wait(timeout=15)
            check('the session exits cleanly', g.game.returncode == 0, g.game.returncode)
    except Exception as error:
        check('rendered run completes', False, repr(error))
    report['result'] = 'passed' if report['checks'] and all(r['result'] == 'passed' for r in report['checks']) else 'failed'
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output/'validation.json').write_text(json.dumps(report, indent=2)+'\n')
    raise SystemExit(0 if report['result'] == 'passed' else 1)


if __name__ == '__main__':
    main()
