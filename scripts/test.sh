#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
source "$project_dir/scripts/native-env.sh"
build_dir="${FOOTBALL_BUILD_DIR:-$project_dir/build}"
ctest --test-dir "$build_dir" --output-on-failure
python3 "$project_dir/tests/training_smoke.py" --build "$build_dir"
