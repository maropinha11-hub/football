#!/usr/bin/env python3
"""Verify original assets and core physics/animation modules against import hashes."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "docs/upstream-manifest.json").read_text())
failures = []
for relative, expected in manifest["files"].items():
    path = root / relative
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        failures.append(relative)
if failures:
    print("Original files missing or changed:", *failures, sep="\n", file=sys.stderr)
    sys.exit(1)
print(f"Verified {len(manifest['files'])} original assets/core modules from {manifest['revision']}")
