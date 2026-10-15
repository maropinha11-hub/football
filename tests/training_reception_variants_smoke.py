#!/usr/bin/env python3
"""Compatibility entry point: the upper-layer trial supersedes full-body locking."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('training_upper_body_smoke.py')),run_name='__main__')
