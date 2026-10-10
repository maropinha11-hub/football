#!/usr/bin/env python3
"""Verify import hashes; --assets-only excludes intentionally adapted source."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--assets-only", action="store_true", help="Verify original data/ resources plus explicitly recorded training shader overrides")
args = parser.parse_args()
manifest = json.loads((root / "docs/upstream-manifest.json").read_text())
failures = []
verified = 0
adapted = 0
overrides = json.loads((root / "docs/training-asset-overrides.json").read_text()) if args.assets_only else {}
for relative, expected in manifest["files"].items():
    if args.assets_only and not relative.startswith("data/"):
        continue
    path = root / relative
    if relative in overrides:
        override = overrides[relative]
        if override["original_sha256"] != expected or relative != "data/media/shaders/postprocess.frag":
            failures.append(relative)
            continue
        expected = override["sha256"]
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        failures.append(relative)
    else:
        if relative in overrides:
            adapted += 1
        else:
            verified += 1
if failures:
    print("Original files missing or changed:", *failures, sep="\n", file=sys.stderr)
    sys.exit(1)
print(f"Verified {verified} original {'assets' if args.assets_only else 'assets/core modules'} from {manifest['revision']}")
if adapted:
    print(f"Verified {adapted} documented training shader override against its recorded hash")
