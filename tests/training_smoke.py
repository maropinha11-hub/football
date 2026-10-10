#!/usr/bin/env python3
"""Drive the rendered native game with real X11 keyboard events and inspect simulation state."""
import argparse
import json
import math
import re
import statistics
import os
from pathlib import Path
import subprocess
import time
import uuid

parser = argparse.ArgumentParser()
parser.add_argument("--build", type=Path, default=Path(__file__).resolve().parents[1] / "build")
parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "artifacts")
args = parser.parse_args()
build = args.build.resolve()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
config = output / "smoke.config"
# Exercise the shipped defaults, rather than a developer's preserved local preferences.
config.write_text((Path(__file__).resolve().parents[1] / "config/training.config").read_text() + '\n"context_x" "960"\n"context_y" "540"\n"training_camera" "0"\n')
environment = os.environ.copy()
environment["ALSOFT_DRIVERS"] = "null"
environment["LIBGL_ALWAYS_SOFTWARE"] = "1"
# Limit llvmpipe workers to the cloud CPU budget so rendering cannot starve
# SDL input delivery while the simulation continues to advance its charge.
environment["LP_NUM_THREADS"] = "2"
environment["DISPLAY"] = ":91"
server = None
game = None
held = set()
# Match the telemetry's keyboard/HID acknowledgement bits. Timing begins
# only after the game observes both press and release, not after xdotool exits.
key_bits = {name: 1 << i for i, name in enumerate([
    "w", "s", "a", "d", "j", "i", "l", "k", "Shift_L", "space", "q",
    "Left", "Right", "Up", "Down", "r", "1", "2", "3", "4", "5", "Tab"])}
checks = []
log_path = output / "training-smoke.log"
run_id = str(uuid.uuid4())
report_path = output / "validation.json"
report_path.write_text(json.dumps({"run_id": run_id, "result": "running", "checks": []}, indent=2) + "\n")
frame_cache = []
log_offset = 0
log_pending = b""

def frames():
    global log_offset, log_pending
    # Consume only new telemetry. Re-parsing the whole log in each input
    # predicate eventually delayed key-up enough to miss a completed action.
    with log_path.open("rb") as stream:
        stream.seek(log_offset)
        fresh = stream.read()
        log_offset = stream.tell()
    lines = (log_pending + fresh).split(b"\n")
    log_pending = lines.pop()
    for line in lines:
        if line.startswith(b"TRAINING_FRAME "):
            try:
                frame_cache.append(json.loads(line[len(b"TRAINING_FRAME "):]))
            except json.JSONDecodeError:
                pass
    return frame_cache

def charge_seen(start, target):
    return any(f["t"] > start and f["shot_active"] and
               (f["charge_ms"] >= target or (target >= 520 and f["function"] == 8))
               for f in frames())

def wait_for(predicate, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if game is not None and game.poll() is not None:
            raise RuntimeError(f"Game exited with {game.returncode}; inspect {log_path}")
        found = predicate()
        if found:
            return found
        time.sleep(0.05)
    raise TimeoutError(f"Native game did not meet readiness/behavior check; inspect {log_path}")

def advance(milliseconds):
    current = frames()[-1]["t"]
    wait_for(lambda: frames() and frames()[-1]["t"] >= current + milliseconds)
    return [frame for frame in frames() if frame["t"] > current]

def key(name, down):
    # Address the game's own window directly. XTest's server-wide key state
    # and autorepeat can keep a charge held after its synthetic release.
    subprocess.run(["xdotool", "keydown" if down else "keyup", "--window", windows[-1], name],
                   env=environment, check=True)
    if down:
        held.add(name)
    else:
        held.discard(name)
    if name in key_bits and game is not None and game.poll() is None:
        bit = key_bits[name]
        sent = time.monotonic()
        def acknowledged():
            nonlocal sent
            if (frames()[-1]["keys"] & bit) == (bit if down else 0):
                return True
            # XTest can drop a release while the software-rendered window is
            # catching up. Re-send key-up to that same window; keep requiring
            # a real SDL/HID acknowledgement rather than clearing game state.
            if not down and time.monotonic() - sent > 1:
                subprocess.run(["xdotool", "keyup", "--window", windows[-1], name],
                               env=environment, check=True)
                sent = time.monotonic()
            return False
        wait_for(acknowledged)

def tap(name):
    key(name, True)
    time.sleep(0.15)
    advance(100)
    key(name, False)
    time.sleep(0.1)
    advance(100)

def check(name, condition, evidence):
    if not condition:
        raise AssertionError(f"{name}: {evidence}")
    checks.append({"check": name, "result": "passed", "evidence": evidence})
    print(f"PASS {name}: {evidence}", flush=True)

def reset(exercise="1"):
    previous = log_path.read_text().count("TRAINING_RESET")
    tap(exercise)
    wait_for(lambda: log_path.read_text().count("TRAINING_RESET") > previous, seconds=10)
    advance(300)

def check_possession(name, samples):
    distances = [math.dist(f["player"], f["ball"]) for f in samples]
    controlled = sum(f["with_ball"] for f in samples)
    check(name, max(distances) < 2.3 and distances[-1] < 1.2 and controlled == len(samples),
          f"Ball distance max/end {max(distances):.2f}/{distances[-1]:.2f} m; controlled {controlled}/{len(samples)} frames")

def dribble_phase(name, buttons, milliseconds):
    origin = frames()[-1]["player"]
    for button in buttons:
        key(button, True)
    direction = [int("d" in buttons) - int("a" in buttons), int("w" in buttons) - int("s" in buttons)]
    length = math.hypot(*direction)
    direction = [component / length for component in direction]
    wait_for(lambda: all(abs(frames()[-1]["move"][i] - direction[i]) < 0.01 for i in range(2)))
    samples = advance(milliseconds)
    for button in reversed(buttons):
        key(button, False)
    check_possession(name, samples)
    distance = math.dist(origin, samples[-1]["player"])
    if distance < 0.5:
        raise AssertionError(f"{name}: player was stuck, displacement {distance:.2f} m")
    return samples

def angle(value):
    return math.atan2(math.sin(value), math.cos(value))

def body_yaw(frame):
    return angle(frame["yaw"] - frame["head_yaw"])

def travel(frame, samples):
    delta = [samples[-1]["player"][i] - frame["player"][i] for i in range(2)]
    yaw = body_yaw(frame)
    return (delta[0] * math.cos(yaw) + delta[1] * math.sin(yaw),
            delta[0] * math.sin(yaw) - delta[1] * math.cos(yaw))

try:
    if Path("/tmp/.X11-unix/X91").exists():
        raise RuntimeError("Display :91 is already occupied; do not stop another task's server")
    server = subprocess.Popen(["Xvfb", ":91", "-screen", "0", "960x540x24", "-nolisten", "tcp"],
                              env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    deadline = time.monotonic() + 10
    while not Path("/tmp/.X11-unix/X91").exists():
        if server.poll() is not None:
            raise RuntimeError(server.stderr.read().decode(errors="replace"))
        if time.monotonic() > deadline:
            raise TimeoutError("Xvfb startup timeout")
        time.sleep(0.05)
    with log_path.open("w") as log:
        game = subprocess.Popen([str(build / "gameplayfootball"), "--config", str(config), "--training", "--telemetry"],
                                cwd=build, env=environment, stdout=log, stderr=subprocess.STDOUT)
        wait_for(lambda: frames() and frames()[-1]["t"] >= 500, seconds=60)
        check("rendered game startup", True, "Native simulation emitted live frames")
        windows = wait_for(lambda: subprocess.run(["xdotool", "search", "--pid", str(game.pid)],
                           env=environment, text=True, capture_output=True).stdout.splitlines())
        subprocess.run(["xdotool", "windowfocus", windows[-1]], env=environment, check=True)
        starting = frames()[-1]
        key("d", True)
        wait_for(lambda: frames()[-1]["move_active"])
        walking = advance(1500)
        key("d", False)
        stopped = advance(600)
        distance = math.dist(starting["player"], walking[-1]["player"])
        check("walking and dribbling", distance > 1.0, f"Player moved {distance:.2f} m")
        check_possession("walking retains ball", walking)
        check("animation playback", any(f["frame"] > 2 for f in walking), "Original animation frames advanced")
        check("release and deceleration", stopped[-1]["speed"] < 1.0, f"Stopped speed {stopped[-1]['speed']:.3f} m/s")
        key("Shift_L", True); key("d", True)
        wait_for(lambda: frames()[-1]["move_active"])
        sprinting = advance(1600)
        key("d", False); key("Shift_L", False)
        sprint_speed = max(f["speed"] for f in sprinting)
        walk_speed = max(f["speed"] for f in walking)
        check("sprinting", sprint_speed > walk_speed + 0.5, f"Walk {walk_speed:.2f}, sprint {sprint_speed:.2f} m/s")
        check_possession("sprinting retains ball", sprinting)
        advance(500)
        reset()
        for name, button, function in [("short pass", "j", 4), ("through pass", "i", 5), ("high pass", "l", 6), ("shot", "k", 8)]:
            reset()
            start = frames()[-1]["t"]
            key(button, True)
            wait_for(lambda: any(f["t"] > start and f["action_mode"] == 2 for f in frames()))
            advance(400)
            key(button, False)
            action = advance(1800)
            action = [f for f in frames() if f["t"] > start]
            peak = max(f["ball_speed"] for f in action)
            observed = sorted(set(f["function"] for f in action))
            check(name, function in observed and peak > 2.0,
                  f"Functions {observed}; ball speed {peak:.2f} m/s")
        aerial_start = frames()[-1]["t"]
        reset("4")
        advance(1200)
        aerial = [f for f in frames() if f["t"] > aerial_start and f["exercise"] == 3]
        check("aerial physics", max(f["ball"][2] for f in aerial) > 2.0,
              f"Peak height {max(f['ball'][2] for f in aerial):.2f} m")
        key("Shift_L", True)
        key("space", True)
        key("a", True)
        wait_for(lambda: frames()[-1]["move_active"])
        reset("4")
        free_run = advance(1500)
        check("super cancel free movement", min(f["player"][0] for f in free_run) < -1.0,
              f"Player moved away from incoming ball to x={free_run[-1]['player'][0]:.2f} m")
        # Aerial reception can catch up during reset on a software renderer.
        # Keep running until B is unambiguously a defensive action, not a high pass.
        wait_for(lambda: math.dist(frames()[-1]["player"], frames()[-1]["ball"]) > 4.0)
        sliding_start = frames()[-1]["t"]
        key("l", True)
        wait_for(lambda: any(f["t"] > sliding_start and f["function"] == 13 for f in frames()))
        advance(800)
        sliding = [f for f in frames() if f["t"] > sliding_start]
        key("l", False)
        key("a", False)
        key("space", False)
        key("Shift_L", False)
        check("off-ball sliding", any(f["function"] == 13 for f in sliding),
              f"Functions {sorted(set(f['function'] for f in sliding))}")
        advance(900)
        reset("3")
        shot_origin = frames()[-1]["player"][0]
        check("finishing exercise", abs(shot_origin - 30.0) < 1.0, f"Player starts at x={shot_origin:.2f} m")
        goals_before = frames()[-1]["goals"]
        # A ground pass from the finishing fixture crosses the empty goal.
        # This isolates goal/net/reset checks from charged-shot elevation and
        # delayed movement release on the software renderer. Shots are checked
        # separately below; do not dribble across the line before the action.
        finishing_start = frames()[-1]["t"]
        key("d", True)  # Explicit +X aim; idle torso sway is not an aiming input.
        key("j", True)
        advance(400)
        key("j", False)
        # Preserve the explicit aim through the queued passing animation,
        # until its real touch sends the ball away from the player.
        wait_for(lambda: any(f["t"] > finishing_start and f["function"] == 4 for f in frames()) and
                 frames()[-1]["ball_speed"] > 10 and frames()[-1]["ball"][0] - frames()[-1]["player"][0] > 3)
        key("d", False)
        wait_for(lambda: any(f["t"] > finishing_start and f["goals"] > goals_before for f in frames()))
        finishing = [f for f in frames() if f["t"] > finishing_start]
        check("goal detection", any(f["function"] == 4 for f in finishing) and
              any(f["goals"] == goals_before + 1 for f in finishing) and max(f["goals"] for f in finishing) == goals_before + 1,
              f"Goal counter {goals_before} -> {frames()[-1]['goals']}")
        advance(2500)
        check("automatic ball reset", abs(frames()[-1]["ball"][0] - 30.65) < 1.5,
              f"Ball returned to x={frames()[-1]['ball'][0]:.2f} m")
        trajectories = {}
        delivered_charge = {}
        for name, hold_ms, chip in [("light", 80, False), ("quick", 250, False), ("charged", 520, False), ("chip", 520, True)]:
            reset()
            start = frames()[-1]["t"]
            if chip:
                key("q", True)
            key("k", True)
            wait_for(lambda: charge_seen(start, hold_ms))
            key("k", False)
            wait_for(lambda: not frames()[-1]["shot_active"])
            advance(2500)
            if chip:
                key("q", False)
            # Include the observed flight after key-up, not an assumed deadline
            # from before LB/X delivery and the original kick preparation.
            trajectory = [f for f in frames() if f["t"] > start]
            trajectories[name] = (max(f["ball_speed"] for f in trajectory), max(f["ball"][2] for f in trajectory))
            # The original gauge can keep ticking during the kick wind-up;
            # the applied training shot power already saturates at 520 ms.
            delivered_charge[name] = min(520, max(f["charge_ms"] for f in trajectory))
        check("charged shot elevation", trajectories["charged"][1] > trajectories["light"][1] + 0.6,
              f"Light {trajectories['light']}, charged {trajectories['charged']} (speed, height); delivered charge {delivered_charge}")
        check("quick shot elevation", trajectories["quick"][0] > 22 and trajectories["quick"][1] > 0.7,
              f"Target 250 ms, delivered {delivered_charge['quick']} ms; shot {trajectories['quick']} (speed, height)")
        check("LB chip trajectory", trajectories["chip"][0] < trajectories["charged"][0] and trajectories["chip"][1] > trajectories["charged"][1],
              f"Chip {trajectories['chip']}; charged {trajectories['charged']}")
        reset("5")
        check("free kick exercise", frames()[-1]["exercise"] == 4 and abs(frames()[-1]["player"][0] - 28) < 1,
              f"Player starts at {frames()[-1]['player']}")
        tap("Tab"); tap("Tab")
        reset()
        check("first person camera", frames()[-1]["camera"] == 2, "Camera switches to first person")
        origin = frames()[-1]["player"]
        key("Right", True)
        wait_for(lambda: frames()[-1]["look_active"])
        looking = advance(350)
        key("Right", False)
        wait_for(lambda: not frames()[-1]["look_active"])
        head_at_release = abs(frames()[-1]["head_yaw"])
        check("head free look with ball", abs(looking[-1]["head_yaw"]) > 0.3 and math.dist(origin, looking[-1]["player"]) < 0.4,
              f"Head yaw {looking[-1]['head_yaw']:.2f}, player stays still")
        centered = advance(2200)
        check("gradual head recenter", abs(centered[-1]["head_yaw"]) < head_at_release * 0.3,
              f"Head magnitude {head_at_release:.2f} -> {abs(centered[-1]['head_yaw']):.2f} rad after input release")
        origin = frames()[-1]["player"]
        key("Right", True); key("w", True)
        wait_for(lambda: frames()[-1]["look_active"] and frames()[-1]["move_active"])
        dribbling_look = advance(1000)
        key("Right", False); key("w", False)
        wait_for(lambda: not frames()[-1]["look_active"] and not frames()[-1]["move_active"])
        delta = [dribbling_look[-1]["player"][i] - origin[i] for i in range(2)]
        check("head look does not steer dribbling", delta[0] > 0.4 and abs(delta[1]) < delta[0] * 0.3 + 0.1 and
              any(f["with_ball"] and abs(f["head_yaw"]) > 0.4 for f in dribbling_look),
              f"Player delta {delta}; head turns independently")
        reset()
        origin = frames()[-1]["player"]
        key("w", True)
        wait_for(lambda: frames()[-1]["move_active"])
        straight_run = advance(1700)
        key("w", False)
        wait_for(lambda: not frames()[-1]["move_active"])
        delta = [straight_run[-1]["player"][i] - origin[i] for i in range(2)]
        check("straight dribbling", delta[0] > 3 and abs(delta[1]) < 0.08 * delta[0] + 0.08,
              f"Forward/side displacement {delta} m")
        check_possession("straight movement retains ball", straight_run)
        reset()
        key("w", True)
        advance(600)
        # Change direction without a neutral-stick gap: this failed when the
        # movement frame stayed at the initial heading throughout the dribble.
        key("d", True); key("w", False)
        wait_for(lambda: frames()[-1]["move"] == [1.0, 0.0])
        turn_origin = frames()[-1]
        right_first = advance(700)
        right_second = advance(700)
        first_turn = angle(body_yaw(right_first[-1]) - body_yaw(turn_origin))
        next_turn = angle(body_yaw(right_second[-1]) - body_yaw(right_first[-1]))
        check("held right keeps turning relative to new front", first_turn < -0.3 and next_turn < -0.3,
              f"Successive right-turn angles {first_turn:.2f}/{next_turn:.2f} rad")
        check_possession("continuous relative turn retains ball", right_first + right_second)
        key("w", True); key("d", False)
        wait_for(lambda: frames()[-1]["move"] == [0.0, 1.0])
        forward_origin = frames()[-1]
        new_forward = advance(1200)
        ahead, sideways = travel(forward_origin, new_forward)
        check("forward follows new front after turn", ahead > 2 and abs(sideways) < 0.25 * ahead + 0.15 and
              all(abs(angle(body_yaw(f) - body_yaw(forward_origin))) < 0.03 for f in new_forward),
              f"New front {body_yaw(forward_origin):.2f} rad; forward/side travel {ahead:.2f}/{sideways:.2f} m")
        check_possession("new forward retains ball", new_forward)
        key("space", True)
        rt_origin = frames()[-1]
        rt_forward = advance(1200)
        ahead, sideways = travel(rt_origin, rt_forward)
        check("RT preserves new forward direction", ahead > 1 and abs(sideways) < 0.3 * ahead + 0.15 and
              abs(angle(body_yaw(rt_forward[-1]) - body_yaw(rt_origin))) < 0.03 and
              statistics.median(f["speed"] for f in rt_forward[-5:]) < statistics.median(f["speed"] for f in new_forward[-5:]),
              f"RT forward/side travel {ahead:.2f}/{sideways:.2f} m; speed {rt_forward[-1]['speed']:.2f} m/s")
        check_possession("RT after turn retains ball", rt_forward)
        key("w", False); key("space", False)
        advance(800)
        rt_idle_origin = frames()[-1]
        key("space", True)
        rt_idle = advance(1500)
        key("space", False)
        idle_turn = angle(rt_idle[-1]["player_yaw"] - rt_idle_origin["player_yaw"])
        check("idle RT does not turn player toward goal", abs(idle_turn) < 0.4 and
              math.dist(rt_idle_origin["player"], rt_idle[-1]["player"]) < 0.3,
              f"Idle RT changed actual body heading {idle_turn:.2f} rad; no automatic goal-facing turn")
        reset()
        key("k", True)
        wait_for(lambda: frames()[-1]["shot_active"] and frames()[-1]["action_mode"] == 2 and frames()[-1]["charge_ms"] >= 100)
        reset()
        key("k", False)
        wait_for(lambda: not frames()[-1]["shot_active"])
        cancelled = advance(900)
        check("reset cancels buffered shot", all(f["function"] != 8 and f["action_mode"] == 0 for f in cancelled) and
              max(f["ball_speed"] for f in cancelled) < 3,
              f"Functions {sorted(set(f['function'] for f in cancelled))}; no stale shot after reset")
        reset()
        # Exercise successive turns without resetting or returning the ball.
        # The previous movement override passed straight runs but abandoned
        # the ball on a reversal once no immediate touch animation was valid.
        dribble_phase("forward before turns retains ball", ["w"], 1200)
        dribble_phase("left turn retains ball", ["a"], 1200)
        reversal = dribble_phase("right reversal retains ball", ["d"], 1600)
        dribble_phase("backward turn retains ball", ["s"], 1200)
        stopped = advance(700)
        check_possession("stopping after turns retains ball", stopped)
        check("stopping after turns releases movement", stopped[-1]["speed"] < 0.5,
              f"Stopped speed {stopped[-1]['speed']:.3f} m/s")
        dribble_phase("restart after turns retains ball", ["w"], 1800)
        check("turning uses original ball-control animations", any(f["function"] == 2 for f in reversal),
              f"Functions {sorted(set(f['function'] for f in reversal))}")
        reset()
        dribble_phase("close control diagonal retains ball", ["space", "w", "a"], 2200)
        dribble_phase("close control reversal retains ball", ["space", "s"], 1600)
        reset()
        dribble_phase("first person sprint retains ball", ["Shift_L", "w"], 2500)
        reset()
        # RB+RT deliberately pushes the ball farther than a normal dribble.
        # Keep sprinting after releasing RT and check it is reached again.
        knock_origin = frames()[-1]["player"]
        key("Shift_L", True); key("space", True); key("w", True)
        wait_for(lambda: frames()[-1]["move_active"])
        knock_on = advance(2200)
        key("space", False)
        knock_recovery = advance(1500)
        key("w", False); key("Shift_L", False)
        maximum = max(math.dist(f["player"], f["ball"]) for f in knock_on)
        ending = math.dist(knock_recovery[-1]["player"], knock_recovery[-1]["ball"])
        check("original knock-on and recovery", maximum < 3.5 and ending < 1.2 and
              all(f["with_ball"] for f in knock_recovery[-3:]) and
              any(f["function"] == 2 for f in knock_recovery) and
              math.dist(knock_origin, knock_on[-1]["player"]) > 6,
              f"Long-touch distance max {maximum:.2f} m; recovered to {ending:.2f} m after releasing RT")
        # Once a pass leaves the feet, the single designated training player
        # must stop being attracted to the ball without needing super cancel.
        reset()
        key("j", True)
        advance(150)
        key("j", False)
        wait_for(lambda: frames()[-1]["with_ball"] == 0 and
                 math.dist(frames()[-1]["player"], frames()[-1]["ball"]) > 3)
        pass_idle = advance(900)
        check("pass releases possession", all(not f["with_ball"] for f in pass_idle),
              f"Ball distance {math.dist(pass_idle[-1]['player'], pass_idle[-1]['ball']):.2f} m")
        idle_origin = frames()[-1]["player"]
        still = advance(600)
        check("off ball idle does not chase", still[-1]["speed"] < 0.5 and math.dist(idle_origin, still[-1]["player"]) < 0.15,
              f"Idle displacement {math.dist(idle_origin, still[-1]['player']):.3f} m; speed {still[-1]['speed']:.3f} m/s")
        origin = frames()[-1]["player"]
        facing = frames()[-1]["yaw"]
        key("d", True)
        wait_for(lambda: frames()[-1]["move_active"])
        leaving = advance(900)
        key("d", False)
        delta = [leaving[-1]["player"][i] - origin[i] for i in range(2)]
        sideways = delta[0] * math.sin(facing) - delta[1] * math.cos(facing)
        check("off ball movement is free after pass", sideways > 1.0 and all(not f["with_ball"] for f in leaving),
              f"Sideways displacement {sideways:.2f} m without super cancel")
        advance(500)
        recovery_start = frames()[-1]
        resets_before = log_path.read_text().count("TRAINING_RESET")
        # Approach the passed ball using normal FPS steering, then verify a
        # real touch brings it back under control. Do not reset or summon it.
        key("Shift_L", True)
        approach_buttons = set()
        # FPS strafing approaches the target without a full-speed keyboard
        # look servo. Slow down near the ball for an actual receiving touch.
        while not frames()[-1]["with_ball"] and frames()[-1]["t"] < recovery_start["t"] + 12000:
            sample = frames()[-1]
            dx, dy = [sample["ball"][i] - sample["player"][i] for i in range(2)]
            ahead = dx * math.cos(sample["yaw"]) + dy * math.sin(sample["yaw"])
            side = dx * math.sin(sample["yaw"]) - dy * math.cos(sample["yaw"])
            wanted = set()
            if abs(ahead) >= abs(side) * 0.3:
                wanted.add("w" if ahead >= 0 else "s")
            if abs(side) >= abs(ahead) * 0.3:
                wanted.add("d" if side >= 0 else "a")
            if math.hypot(dx, dy) < 6 and "Shift_L" in held:
                key("Shift_L", False)
                key("space", True)
            for button in sorted(approach_buttons - wanted):
                key(button, False)
            for button in sorted(wanted - approach_buttons):
                key(button, True)
            approach_buttons = wanted
            advance(100)
        if "Shift_L" in held:
            key("Shift_L", False)
        if "space" not in held:
            key("space", True)
        for button in sorted(approach_buttons):
            key(button, False)
        advance(400)
        key("w", True)
        recovery = advance(1000)
        key("w", False); key("space", False)
        check("manual approach recovers passed ball", recovery[-1]["with_ball"] and
              math.dist(recovery[-1]["player"], recovery[-1]["ball"]) < 1.2 and
              any(f["function"] == 2 for f in recovery) and
              log_path.read_text().count("TRAINING_RESET") == resets_before,
              f"Recovered in {(recovery[-1]['t'] - recovery_start['t']) / 1000:.1f} s; ball distance {math.dist(recovery[-1]['player'], recovery[-1]['ball']):.2f} m; functions {sorted(set(f['function'] for f in recovery))}")
        # Move out of the incoming ball's lane so it cannot become possession
        # during the off-ball camera check on a slow software renderer.
        key("Shift_L", True); key("space", True); key("a", True)
        wait_for(lambda: frames()[-1]["move_active"])
        reset("4")
        advance(900)
        key("a", False); key("space", False); key("Shift_L", False)
        advance(500)
        wait_for(lambda: frames()[-1]["with_ball"] == 0)
        yaw_before = frames()[-1]["yaw"]
        key("Right", True)
        turning = advance(300)
        key("Right", False)
        yaw_change = math.atan2(math.sin(turning[-1]["yaw"] - yaw_before), math.cos(turning[-1]["yaw"] - yaw_before))
        check("off ball FPS turning", turning[-1]["with_ball"] == 0 and yaw_change < -0.3,
              f"Yaw changed {yaw_change:.2f} rad without ball")
        origin = frames()[-1]["player"]
        key("w", True)
        moving_fps = advance(700)
        key("w", False)
        check("first person forward movement", math.dist(origin, moving_fps[-1]["player"]) > 0.6,
              f"Player moved {math.dist(origin, moving_fps[-1]['player']):.2f} m")
        reset()
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "x11grab", "-video_size", "960x540",
                        "-i", ":91", "-frames:v", "1", str(output / "firstperson-forward.png")], env=environment, check=True)
        pixels = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(output / "firstperson-forward.png"),
                                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-frames:v", "1", "pipe:1"], capture_output=True, check=True).stdout
        # Inspect a roof band across the small vertical range of the animated
        # eye position. Bright crowd sections are not missing geometry/sky.
        covered = max(sum(max(pixels[(y * 960 + x) * 3:(y * 960 + x) * 3 + 3]) < 215
                          for y in range(top, top + 40) for x in range(320, 640)) / (40 * 320)
                      for top in range(80, 171, 5))
        check("front stadium remains visible", covered > 0.8, f"Central distant roof covers {covered:.1%} of inspection band")
        key("Down", True)
        advance(900)
        key("Down", False)
        all_frames = frames()
        check("ball stays above turf", min(f["ball"][2] for f in all_frames) >= 0.109,
              f"Minimum ball center {min(f['ball'][2] for f in all_frames):.3f} m")
        check("finite physics state", all(math.isfinite(v) for f in all_frames for v in f["ball"] + f["player"]),
              f"{len(all_frames)} live samples are finite")
        poses = [tuple(map(float, m)) for m in re.findall(r"TRAINING_FOOT_POSE side=\w+ before=([\d.]+) after=([\d.]+)", log_path.read_text())]
        check("rendered foot contact correction", len(poses) > 3 and
              statistics.median(p[1] for p in poses) < statistics.median(p[0] for p in poses),
              f"{len(poses)} rendered foot corrections; median error {statistics.median(p[0] for p in poses):.3f} -> {statistics.median(p[1] for p in poses):.3f} m" if poses else "No rendered foot corrections")
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "x11grab", "-video_size", "960x540",
                        "-i", ":91", "-frames:v", "1", str(output / "training.png")], env=environment, check=True)
        tap("Tab")
        check("external camera restoration", frames()[-1]["camera"] == 0, "First person cycles back to external view")
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "x11grab", "-video_size", "960x540",
                        "-i", ":91", "-frames:v", "1", str(output / "training-external.png")], env=environment, check=True)
        key("Escape", True)
        game.wait(timeout=15)
        held.clear()
        check("clean shutdown", game.returncode == 0, f"Exit status {game.returncode}")
    report_path.write_text(json.dumps({"run_id": run_id, "checks": checks, "total": len(checks), "result": "passed"}, indent=2) + "\n")
    print(f"{len(checks)} native gameplay checks passed", flush=True)
except BaseException as error:
    report_path.write_text(json.dumps({"run_id": run_id, "checks": checks, "total": len(checks), "result": "failed", "error": str(error)}, indent=2) + "\n")
    raise
finally:
    for name in list(held):
        subprocess.run(["xdotool", "keyup", name], env=environment, check=False)
    if game is not None and game.poll() is None:
        game.terminate()
        try:
            game.wait(timeout=10)
        except subprocess.TimeoutExpired:
            game.kill(); game.wait()
    if server is not None:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill(); server.wait()
