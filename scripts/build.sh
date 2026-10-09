#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
source "$project_dir/scripts/native-env.sh"
build_dir="${FOOTBALL_BUILD_DIR:-$project_dir/build}"
cmake_args=(-S "$project_dir" -B "$build_dir" -DCMAKE_BUILD_TYPE=RelWithDebInfo)
if [[ -x "$native_dir/root/usr/bin/cmake" ]]; then
  cmake_args+=(-DCMAKE_PREFIX_PATH="$native_dir/root/usr"
    -DCMAKE_BUILD_RPATH="$native_dir/root/usr/lib/x86_64-linux-gnu"
    -DCMAKE_CXX_FLAGS="-isystem $native_dir/root/usr/include/x86_64-linux-gnu")
fi
cmake "${cmake_args[@]}"
cmake --build "$build_dir" --parallel "${FOOTBALL_BUILD_JOBS:-4}"
python3 "$project_dir/scripts/prepare_runtime.py" "$build_dir"
