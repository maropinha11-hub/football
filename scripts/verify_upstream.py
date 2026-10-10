#!/usr/bin/env python3
"""Verify import hashes; --assets-only excludes intentionally adapted source."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--assets-only", action="store_true", help="Verify original resources under data/ only")
args = parser.parse_args()
manifest = json.loads((root / "docs/upstream-manifest.json").read_text())
failures = []
verified = 0
for relative, expected in manifest["files"].items():
    if args.assets_only and not relative.startswith("data/"):
        continue
    path = root / relative
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        failures.append(relative)
    else:
        verified += 1
if failures:
    print("Original files missing or changed:", *failures, sep="\n", file=sys.stderr)
    sys.exit(1)
print(f"Verified {verified} original {'assets' if args.assets_only else 'assets/core modules'} from {manifest['revision']}")
