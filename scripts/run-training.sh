#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
source "$project_dir/scripts/native-env.sh"
build_dir="${FOOTBALL_BUILD_DIR:-$project_dir/build}"
if [[ ! -x "$build_dir/gameplayfootball" ]]; then
  echo 'Compile primeiro: ./scripts/build.sh' >&2
  exit 1
fi
python3 "$project_dir/scripts/prepare_runtime.py" "$build_dir"
cd "$build_dir"
exec ./gameplayfootball --config training.config --training "$@"
