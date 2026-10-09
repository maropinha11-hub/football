#!/usr/bin/env python3
"""Drive the rendered native game with real X11 keyboard events and inspect simulation state."""
import argparse
import json
import math
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
config.write_text((build / "training.config").read_text() + '\n"context_x" "960"\n"context_y" "540"\n')
environment = os.environ.copy()
environment["ALSOFT_DRIVERS"] = "null"
environment["LIBGL_ALWAYS_SOFTWARE"] = "1"
environment["DISPLAY"] = ":91"
server = None
game = None
held = set()
checks = []
log_path = output / "training-smoke.log"
run_id = str(uuid.uuid4())
report_path = output / "validation.json"
report_path.write_text(json.dumps({"run_id": run_id, "result": "running", "checks": []}, indent=2) + "\n")

def frames():
    result = []
    for line in log_path.read_text(errors="replace").splitlines():
        if line.startswith("TRAINING_FRAME "):
            try:
                result.append(json.loads(line[len("TRAINING_FRAME "):]))
            except json.JSONDecodeError:
                pass  # A line may still be in flight from the running process.
    return result

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
    subprocess.run(["xdotool", "keydown" if down else "keyup", name], env=environment, check=True)
    if down:
        held.add(name)
    else:
        held.discard(name)

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
        windows = subprocess.check_output(["xdotool", "search", "--name", "gameplay football"], env=environment, text=True).splitlines()
        subprocess.run(["xdotool", "windowfocus", windows[-1]], env=environment, check=True)
        starting = frames()[-1]
        key("d", True)
        walking = advance(1500)
        key("d", False)
        stopped = advance(600)
        distance = math.dist(starting["player"], walking[-1]["player"])
        check("walking and dribbling", distance > 1.0, f"Player moved {distance:.2f} m")
        check("animation playback", any(f["frame"] > 2 for f in walking), "Original animation frames advanced")
        check("release and deceleration", stopped[-1]["speed"] < 1.0, f"Stopped speed {stopped[-1]['speed']:.3f} m/s")
        key("Shift_L", True); key("d", True)
        sprinting = advance(1600)
        key("d", False); key("Shift_L", False)
        sprint_speed = max(f["speed"] for f in sprinting)
        walk_speed = max(f["speed"] for f in walking)
        check("sprinting", sprint_speed > walk_speed + 0.5, f"Walk {walk_speed:.2f}, sprint {sprint_speed:.2f} m/s")
        advance(500)
        reset()
        for name, button, function in [("short pass", "j", 4), ("through pass", "i", 5), ("high pass", "l", 6), ("shot", "k", 8)]:
            reset()
            start = frames()[-1]["t"]
            key(button, True)
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
        reset("4")
        key("Shift_L", True)
        key("space", True)
        key("a", True)
        free_run = advance(1500)
        check("super cancel free movement", min(f["player"][0] for f in free_run) < -1.0,
              f"Player moved away from incoming ball to x={free_run[-1]['player'][0]:.2f} m")
        key("l", True)
        sliding = advance(800)
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
        key("k", True)
        advance(300)
        key("k", False)
        finishing = advance(3500)
        check("goal detection", any(f["goals"] == goals_before + 1 for f in finishing) and max(f["goals"] for f in finishing) == goals_before + 1,
              f"Goal counter {goals_before} -> {frames()[-1]['goals']}")
        advance(2300)
        check("automatic ball reset", abs(frames()[-1]["ball"][0] - 30.65) < 1.5,
              f"Ball returned to x={frames()[-1]['ball'][0]:.2f} m")
        tap("Tab")
        advance(500)
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "x11grab", "-video_size", "960x540",
                        "-i", ":91", "-frames:v", "1", str(output / "training.png")], env=environment, check=True)
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
