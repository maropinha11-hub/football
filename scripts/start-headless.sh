#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
source "$project_dir/scripts/native-env.sh"
football_display="${FOOTBALL_X_DISPLAY:-:92}"
display_number="${football_display#:}"
if [[ ! "$display_number" =~ ^[0-9]+$ ]] || [[ -e "/tmp/.X11-unix/X$display_number" ]]; then
  echo 'Use an unoccupied local X display, for example FOOTBALL_X_DISPLAY=:92.' >&2
  exit 1
fi
mkdir -p "$project_dir/artifacts"
Xvfb "$football_display" -screen 0 1280x720x24 -nolisten tcp > "$project_dir/artifacts/headless-display.log" 2>&1 &
football_server_pid=$!
football_game_pid=""
cleanup() {
  if [[ -n "$football_game_pid" ]] && kill -0 "$football_game_pid" 2>/dev/null; then
    kill "$football_game_pid" 2>/dev/null || true
    wait "$football_game_pid" 2>/dev/null || true
  fi
  kill "$football_server_pid" 2>/dev/null || true
  wait "$football_server_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for attempt in {1..100}; do
  if [[ -S "/tmp/.X11-unix/X$display_number" ]]; then break; fi
  if ! kill -0 "$football_server_pid" 2>/dev/null; then
    cat "$project_dir/artifacts/headless-display.log" >&2
    exit 1
  fi
  sleep 0.05
done
export DISPLAY="$football_display"
export ALSOFT_DRIVERS=null
export LIBGL_ALWAYS_SOFTWARE=1
"$project_dir/scripts/run-training.sh" --telemetry "$@" &
football_game_pid=$!
wait "$football_game_pid"
