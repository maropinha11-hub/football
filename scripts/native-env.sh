#!/usr/bin/env bash
native_dir="${FOOTBALL_NATIVE_ROOT:-/workspace/.football-native}"
if [[ -x "$native_dir/root/usr/bin/cmake" ]]; then
  export PATH="$native_dir/root/usr/bin:$PATH"
  export LD_LIBRARY_PATH="$native_dir/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
