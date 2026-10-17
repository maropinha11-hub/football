#!/usr/bin/env python3
"""Render whole-body action variations while preserving native ball contacts.

The telemetry measures applied additive rotations, not the number of catalog
entries. Native animation selection and a real weighted-skin contact must still
complete each command. This is deliberately separate from the physics runner
so it can retain an independent executable hash and scenario evidence.
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
    return [dict(re.findall(r"(\w+)=([^\s]+)", line))
            for line in text.splitlines() if line.startswith(prefix + " ")]


def maximum(rows, field, default=0.0):
    return max((float(row[field]) for row in rows if field in row), default=default)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--display", default=":197")
    parser.add_argument("--camera", type=int, choices=[1, 2], default=2,
                        help="1: external whole-body view; 2: approved first-person controls.")
    parser.add_argument("--quick", action="store_true",
                        help="Run one easy and three difficult kicks for iteration.")
    args = parser.parse_args()
    executable = args.build / "gameplayfootball"
    report = dict(result="running", checks=[], scenarios={},
                  executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
                  measurement_scope={
                      "simulation_rotations": "Isolated situational layer measured by actual before/after FK.",
                      "rendered_rotations": "Final upper-body delta also includes native contact preparation and anatomical projection; not an isolated layer magnitude.",
                  },
                  scope="Rendered Linux/X11 gameplay with a virtual Xbox controller; not Windows GUI execution.")

    def check(name, ok, evidence):
        row = dict(check=name, result="passed" if ok else "failed", evidence=evidence)
        report["checks"].append(row)
        print(json.dumps(row), flush=True)

    def capture(game, name):
        subprocess.run(["import", "-window", game.window,
                        str(args.output / (name + ".png"))], env=game.env, check=True)

    try:
        with NativeTraining(args.build, args.output / "game", display=args.display,
                            analog_pad=True, camera=args.camera,
                            config_overrides={"context_x": 640, "context_y": 360,
                                              "training_physical_rig": "true",
                                              "training_physical_lab": "true"}) as game:
            def pad(x, y, **options):
                # The external camera uses field axes; the player initially
                # faces +X. Preserve the same requested local directions.
                game.pad(*((-y, x) if args.camera == 1 else (x, y)), **options)

            # Stick coordinates are in the approved first-person movement
            # frame. Change action direction while running, exactly as in the
            # existing successful running-kick regression.
            scenarios = [
                ("standing_forward_pass", 0, (0, 0), 1, 4, 180),
                ("running_right_pass", 900, (1, 0), 1, 4, 180),
                ("running_right_shot", 900, (1, 0), 4, 8, 300),
                ("running_left_cross", 900, (-1, 0), 2, 6, 300),
            ]
            if not args.quick:
                scenarios += [
                    ("running_forward_pass", 900, (0, -1), 1, 4, 180),
                    ("running_left_pass", 900, (-1, 0), 1, 4, 180),
                    ("running_left_shot", 1450, (-1, 0), 4, 8, 300),
                    ("running_right_cross", 1450, (1, 0), 2, 6, 300),
                    ("running_diagonal_cross", 1450, (.7071, -.7071), 2, 6, 300),
                ]
            for name, run_ms, stick, button, function, hold_ms in scenarios:
                game.reset()
                if run_ms:
                    pad(0, -1, sprint=True)
                    game.advance(run_ms)
                start = len(game.log.read_text())
                pad(*stick, sprint=bool(run_ms), buttons=button)
                game.advance(hold_ms)
                pad(*stick, sprint=bool(run_ms))
                # Capture preparation/follow-through rather than only the
                # resting pose after the ball has gone.
                if name in {"standing_forward_pass", "running_right_shot"}:
                    game.advance(150)
                    capture(game, name)
                frames = game.advance(2200)
                pad(0, 0)
                log = game.log.read_text()[start:]
                hits = [row for row in events(log, "TRAINING_ACTION_TOUCH")
                        if int(row["function"]) == function]
                selected = [row for row in events(log, "TRAINING_NATIVE_START")
                            if int(row["function"]) == function]
                action_kind = {4: 1, 8: 2, 6: 3}[function]
                body = [row for row in events(log, "PHYSICAL_SITUATION")
                        if row.get("action") == str(action_kind)]
                rendered = events(log, "PHYSICAL_SITUATION_RENDER")
                summary = dict(
                    function=function, running_ms=run_ms, stick=stick,
                    touches=hits, native_sources=selected,
                    body_samples=len(body), sources=sorted({row.get("source", "") for row in body}),
                    profiles=sorted({row.get("profile", "") for row in body}),
                    peak_difficulty=maximum(body, "difficulty"),
                    peak_weight=maximum(body, "weight"),
                    peak_trunk_rotation_rad=maximum(body, "trunk"),
                    peak_arm_rotation_rad=maximum(body, "arms"),
                    maximum_foot_error_m=maximum(body, "foot_error"),
                    maximum_root_error_m=maximum(body, "root_error"),
                    rendered_samples=len(rendered),
                    rendered_peak_trunk_rotation_rad=maximum(rendered, "trunk"),
                    rendered_peak_arm_rotation_rad=maximum(rendered, "arms"),
                    peak_ball_speed_mps=max(frame["ball_speed"] for frame in frames),
                )
                report["scenarios"][name] = summary
                check(name + " completes exactly one native kick at the real ball",
                      len(hits) == 1 and bool(selected)
                      and summary["peak_ball_speed_mps"] > 4,
                      dict(touches=hits, selected=selected,
                           peak_ball_speed_mps=summary["peak_ball_speed_mps"]))
                schema = {"t", "actor", "action", "profile", "source", "difficulty", "phase",
                          "weight", "trunk", "arms", "foot_error", "root_error"}
                check(name + " measures an applied whole-body situation",
                      len(body) >= 4 and all(schema <= row.keys() for row in body)
                      and bool(summary["sources"]), summary)
                check(name + " keeps the native root and feet in place",
                      bool(body) and all("foot_error" in row and "root_error" in row for row in body)
                      and summary["maximum_foot_error_m"] < .0001
                      and summary["maximum_root_error_m"] < .0001,
                      dict(foot_error_m=summary["maximum_foot_error_m"],
                           root_error_m=summary["maximum_root_error_m"]))
                check(name + " applies the body response to the rendered character",
                      len(rendered) >= 3
                      and summary["rendered_peak_trunk_rotation_rad"] > .001
                      and summary["rendered_peak_arm_rotation_rad"] > .001
                      and all("foot_error" in row and "root_error" in row for row in rendered)
                      and maximum(rendered, "foot_error") < .0001
                      and maximum(rendered, "root_error") < .0001,
                      dict(samples=len(rendered),
                           trunk_rotation_rad=summary["rendered_peak_trunk_rotation_rad"],
                           arm_rotation_rad=summary["rendered_peak_arm_rotation_rad"],
                           foot_error_m=maximum(rendered, "foot_error"),
                           root_error_m=maximum(rendered, "root_error")))
                if body:
                    scalar = [float(row[field]) for row in body
                              for field in ("difficulty", "phase", "weight", "trunk", "arms")]
                    check(name + " has bounded finite blending",
                          all(math.isfinite(value) for value in scalar)
                          and all(0 <= float(row["weight"]) <= 1.00001 for row in body)
                          and summary["peak_trunk_rotation_rad"] < .55
                          and summary["peak_arm_rotation_rad"] < 1.0,
                          dict(samples=len(body), peak_weight=summary["peak_weight"],
                               peak_trunk_rotation_rad=summary["peak_trunk_rotation_rad"],
                               peak_arm_rotation_rad=summary["peak_arm_rotation_rad"]))
                    # Compare within one native source and its forward phase;
                    # source transitions have a separate authored crossfade.
                    rates = []
                    for previous, current in zip(body, body[1:]):
                        elapsed = (int(current["t"]) - int(previous["t"])) / 1000
                        same = (current.get("source") == previous.get("source")
                                and current.get("actor") == previous.get("actor")
                                and float(current["phase"]) >= float(previous["phase"]))
                        if same and 0 < elapsed <= .05:
                            rates.append(max(abs(float(current[field]) - float(previous[field])) / elapsed
                                             for field in ("trunk", "arms")))
                    check(name + " keeps the procedural angular response below its rate cap",
                          bool(rates) and max(rates) <= 2.25,
                          dict(checked_intervals=len(rates),
                               maximum_scalar_angle_rate_rad_s=max(rates, default=0),
                               configured_offset_rate_cap_rad_s=2.1))

            easy = report["scenarios"]["standing_forward_pass"]
            difficult = report["scenarios"]["running_right_shot"]
            check("difficult running action visibly recruits more trunk and arms than an easy pass",
                  difficult["peak_trunk_rotation_rad"] > easy["peak_trunk_rotation_rad"] + .02
                  and difficult["peak_arm_rotation_rad"] > easy["peak_arm_rotation_rad"] + .03,
                  dict(easy_trunk_rad=easy["peak_trunk_rotation_rad"],
                       difficult_trunk_rad=difficult["peak_trunk_rotation_rad"],
                       easy_arms_rad=easy["peak_arm_rotation_rad"],
                       difficult_arms_rad=difficult["peak_arm_rotation_rad"]))
            difficult_pass = report["scenarios"]["running_right_pass"]
            # Different native pass sources already have different authored
            # upper-body motion and contact blends. Compare the isolated
            # procedural response here; the per-scenario checks above prove
            # actual rendered application and its root/foot preservation.
            check("a running sideways pass recruits more isolated trunk and arm response",
                  difficult_pass["peak_difficulty"] > easy["peak_difficulty"] + .05
                  and difficult_pass["peak_trunk_rotation_rad"] > easy["peak_trunk_rotation_rad"] + .02
                  and difficult_pass["peak_arm_rotation_rad"] > easy["peak_arm_rotation_rad"] + .02,
                  dict(easy_difficulty=easy["peak_difficulty"],
                       running_difficulty=difficult_pass["peak_difficulty"],
                       easy_isolated_trunk_rad=easy["peak_trunk_rotation_rad"],
                       running_isolated_trunk_rad=difficult_pass["peak_trunk_rotation_rad"],
                       easy_isolated_arms_rad=easy["peak_arm_rotation_rad"],
                       running_isolated_arms_rad=difficult_pass["peak_arm_rotation_rad"],
                       easy_rendered_trunk_rad=easy["rendered_peak_trunk_rotation_rad"],
                       running_rendered_trunk_rad=difficult_pass["rendered_peak_trunk_rotation_rad"],
                       easy_rendered_arms_rad=easy["rendered_peak_arm_rotation_rad"],
                       running_rendered_arms_rad=difficult_pass["rendered_peak_arm_rotation_rad"]))

            if not args.quick:
                # First-time decisions retain the native action semantics;
                # a procedural arm/torso layer must not cancel a header or
                # author a contact against an invisible body surface.
                for name, launch, part in [("ground_first_time", "F4", None),
                                           ("aerial_first_time", "F6", "head")]:
                    game.reset()
                    start = len(game.log.read_text())
                    game.keys([launch], True)
                    game.keys([launch], False)
                    for _ in range(5):
                        pad(0, 0, buttons=1)
                        game.advance(100)
                        pad(0, 0)
                        game.advance(100)
                    game.advance(1800)
                    log = game.log.read_text()[start:]
                    hits = [row for row in events(log, "TRAINING_ACTION_TOUCH")
                            if row["function"] == "4" and (part is None or row["part"] == part)]
                    check(name + " still reaches a physical first-time pass",
                          bool(hits), dict(touches=hits))

            log = game.log.read_text()
            hits = events(log, "TRAINING_ACTION_TOUCH")
            accepted = [row for row in events(log, "TRAINING_SKIN_CONTACT")
                        if row["accepted"] == "1"]
            accepted_times = {row["t"] for row in accepted}
            check("every action impulse has same-tick weighted-skin contact at the original tolerance",
                  bool(hits) and all(row["t"] in accepted_times for row in hits)
                  and bool(accepted) and maximum(accepted, "gap") <= .00251,
                  dict(impulses=len(hits), accepted_contacts=len(accepted),
                       maximum_accepted_gap_m=maximum(accepted, "gap")))
            arm = events(log, "PHYSICAL_ARM_RENDER")
            check("final rendered arms remain inside anatomical limits and outside the trunk proxy",
                  len(arm) > 50 and maximum(arm, "error") < .00001
                  and maximum(arm, "penetration") < .004,
                  dict(samples=len(arm), maximum_limit_error_rad=maximum(arm, "error"),
                       maximum_trunk_penetration_m=maximum(arm, "penetration")))
            poses = events(log, "TRAINING_NATIVE_POSE")
            check("native contact preparation retains bone lengths and its bounded foot adjustment",
                  bool(poses) and maximum(poses, "length_error") < .0001
                  and maximum(poses, "foot_shift") <= .0801,
                  dict(samples=len(poses), maximum_bone_length_error_m=maximum(poses, "length_error"),
                       maximum_contact_foot_adjustment_m=maximum(poses, "foot_shift")))

            # F1 changes only the new situation layer. The rigid body and
            # final anatomical projection must remain active for comparison.
            for enabled in (False, True):
                game.reset()
                game.keys(["F1"], True)
                game.advance(100)
                game.keys(["F1"], False)
                game.advance(100)
                start = len(game.log.read_text())
                pad(0, 0, buttons=1)
                game.advance(180)
                pad(0, 0)
                game.advance(2300)
                segment = game.log.read_text()[start:]
                touches = [row for row in events(segment, "TRAINING_ACTION_TOUCH")
                           if row["function"] == "4"]
                situation = events(segment, "PHYSICAL_SITUATION")
                physical_arms = events(segment, "PHYSICAL_ARM_RENDER")
                check("F1 " + ("reenables" if enabled else "disables")
                      + " only the situation layer while retaining physical tracking and the native pass",
                      len(touches) == 1 and len(physical_arms) > 20
                      and (bool(situation) if enabled else not situation),
                      dict(touches=touches, situation_samples=len(situation),
                           physical_arm_samples=len(physical_arms)))

            # Turning the experiment off must return to the existing authored
            # gameplay path without losing an otherwise valid kick.
            game.reset()
            game.keys(["F7"], True)
            game.keys(["F7"], False)
            game.advance(200)
            start = len(game.log.read_text())
            pad(0, -1, buttons=1)
            game.advance(180)
            pad(0, -1)
            game.advance(2300)
            off = game.log.read_text()[start:]
            off_hits = [row for row in events(off, "TRAINING_ACTION_TOUCH") if row["function"] == "4"]
            check("disabling physical rig preserves the original pass and removes the situation overlay",
                  len(off_hits) == 1 and not events(off, "PHYSICAL_SITUATION"),
                  dict(touches=off_hits, situation_samples=len(events(off, "PHYSICAL_SITUATION"))))

            game.keys(["Escape"], True)
            game.game.wait(timeout=15)
            check("clean exit", game.game.returncode == 0, game.game.returncode)
        report["result"] = "passed" if all(row["result"] == "passed" for row in report["checks"]) else "failed"
    except BaseException as error:
        report.update(result="failed", error=str(error))
        raise
    finally:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    if report["result"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
