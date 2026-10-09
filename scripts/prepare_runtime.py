#!/usr/bin/env python3
"""Stage original resources without overwriting local saves or configuration."""
import argparse
from pathlib import Path
import shutil

parser = argparse.ArgumentParser()
parser.add_argument("build", type=Path)
args = parser.parse_args()
project = Path(__file__).resolve().parents[1]
runtime = args.build.resolve()
runtime.mkdir(parents=True, exist_ok=True)
if not (runtime / "media").exists():
    try:
        (runtime / "media").symlink_to(project / "data" / "media", target_is_directory=True)
    except OSError:
        shutil.copytree(project / "data" / "media", runtime / "media")
if not (runtime / "databases").exists():
    shutil.copytree(project / "data" / "databases", runtime / "databases")
if not (runtime / "football.config").exists():
    shutil.copy2(project / "data" / "football.config", runtime / "football.config")
if not (runtime / "training.config").exists():
    shutil.copy2(project / "config" / "training.config", runtime / "training.config")
