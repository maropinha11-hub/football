#!/usr/bin/env bash
set -euo pipefail
# Rootless Debian 13 installation. APT verifies repository signatures and hashes;
# packages are extracted locally, never installed into the host operating system.
native_dir="${FOOTBALL_NATIVE_ROOT:-/workspace/.football-native}"
if [[ "$(dpkg --print-architecture)" != amd64 ]] || ! rg -q 'VERSION_CODENAME=trixie' /etc/os-release; then
  echo 'This cloud bootstrap requires Debian 13 amd64. See README for normal system installation.' >&2
  exit 1
fi
mkdir -p "$native_dir/apt/lists/partial" "$native_dir/apt/cache/archives/partial" \
  "$native_dir/apt/log" "$native_dir/apt/empty" "$native_dir/root"
cp /var/lib/dpkg/status "$native_dir/apt/status"
cat > "$native_dir/apt/sources.list" <<'EOF'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
EOF
cat > "$native_dir/apt/apt.conf" <<EOF
Dir::Etc::parts "$native_dir/apt/empty";
Dir::Etc::main "-";
Dir::Etc::sourcelist "$native_dir/apt/sources.list";
Dir::Etc::sourceparts "$native_dir/apt/empty";
Dir::State::lists "$native_dir/apt/lists";
Dir::State::status "$native_dir/apt/status";
Dir::Cache "$native_dir/apt/cache";
Dir::Log "$native_dir/apt/log";
APT::Sandbox::User "$(id -un)";
Acquire::Retries "2";
EOF
APT_CONFIG="$native_dir/apt/apt.conf" /usr/bin/apt-get update
APT_CONFIG="$native_dir/apt/apt.conf" /usr/bin/apt-get --download-only --no-install-recommends -y install \
  cmake libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev libsdl2-gfx-dev libopenal-dev \
  libboost-filesystem-dev libboost-thread-dev libboost-system-dev libgl-dev libsqlite3-dev \
  xvfb xauth xdotool mesa-utils
python3 - "$native_dir" <<'PY'
import os
from pathlib import Path
import subprocess
import sys
native = Path(sys.argv[1]).resolve()
root = native / 'root'
packages = list((native / 'apt/cache/archives').glob('*.deb'))
for package in packages:
    subprocess.run(['dpkg-deb', '-x', str(package), str(root)], check=True)
# Development package symlinks may target runtime libraries already installed on
# the host, which APT correctly does not download a second time.
for link in root.rglob('*'):
    if link.is_symlink() and not link.exists():
        target = Path(os.path.normpath(str(link.parent / os.readlink(link))))
        if target.is_relative_to(root):
            host = Path('/') / target.relative_to(root)
            if host.exists() and not target.exists() and not target.is_symlink():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(host)
print(f'Prepared {len(packages)} verified APT packages in {root}')
PY
"$(dirname "$0")/build.sh"
