#!/bin/bash
# Rootless EMANE 1.5.3 install for Ubuntu 24.04 (tested on WSL2 Ubuntu 24.04.2).
#
# Downloads the official Adjacent Link release bundle
#   https://adjacentlink.com/downloads/emane/emane-1.5.3-release-1.ubuntu-24_04.amd64.tar.gz
# (linked from https://github.com/adjacentlink/emane/wiki/Install) and extracts
# only the packages this project needs with `dpkg-deb -x` into a user-owned
# sysroot.  Missing runtime dependencies are fetched from the Ubuntu archive the
# same way.  No root, no maintainer scripts, nothing written outside $PREFIX.
#
# With root, the official route is simply:  dpkg -i *.deb && apt-get install -f
#
# Usage: emane/install_rootless.sh [PREFIX]        (default PREFIX=$HOME/vmn-emane)
set -euo pipefail

PREFIX="${1:-$HOME/vmn-emane}"
SYSROOT="$PREFIX/sysroot"
BUNDLE=emane-1.5.3-release-1.ubuntu-24_04.amd64.tar.gz
BUNDLE_SHA256=a60a2fd1ebf73cc2a26e7fa48e8eef0c5cac44e17b11ab7e31dd06de6cf53638   # as downloaded 2026-10-26
URL=https://adjacentlink.com/downloads/emane/$BUNDLE
UBUNTU=http://archive.ubuntu.com/ubuntu/pool

mkdir -p "$PREFIX/dl" "$PREFIX/sysdeps" "$SYSROOT"
cd "$PREFIX/dl"
[ -f "$BUNDLE" ] || curl -fsSLO "$URL"
echo "$BUNDLE_SHA256  $BUNDLE" | sha256sum -c - || { echo "checksum mismatch: refusing to install"; exit 1; }
[ -d emane-1.5.3-release-1 ] || tar xzf "$BUNDLE"
DEBS="$PREFIX/dl/emane-1.5.3-release-1/debs/ubuntu-24_04/amd64"

for p in emane-libs emane emane-dtds emane-manifest emane-trans-common emane-trans-virtual \
         emane-trans-raw emane-model-tdmaeventscheduler emane-model-rfpipe emane-eventservice python3-emane; do
  dpkg-deb -x "$(ls "$DEBS"/${p}_*.deb)" "$SYSROOT" && echo "extracted $p"
done

# Runtime dependencies that a minimal Ubuntu 24.04 may lack (skipped when already installed).
cd "$PREFIX/sysdeps"
need() { ! dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "ok installed"; }
for p in libpcre3 python3-lxml libxslt1.1 python3-zmq libzmq5 libpcap0.8t64; do
  if need "$p"; then apt-get download "$p" || echo "WARN: apt-get download $p failed"; fi
done
# protobuf: fetch the current point release directly (apt lists may be stale)
for spec in "main/p/protobuf libprotobuf32t64" "universe/p/protobuf python3-protobuf"; do
  set -- $spec
  if need "$2"; then
    f=$(curl -fsSL "$UBUNTU/$1/" | grep -oE "$2_3\.21\.12-8\.2ubuntu[^\"]*_amd64\.deb" | sort -V | tail -1)
    [ -f "$f" ] || curl -fsSLO "$UBUNTU/$1/$f"
  fi
done
for f in *.deb; do [ -f "$f" ] && dpkg-deb -x "$f" "$SYSROOT" && echo "extracted $f"; done

cat > "$PREFIX/env.sh" <<EOF
# Rootless EMANE 1.5.3 environment (sysroot extracted from the official Adjacent Link .debs)
export VMN_EMANE_SYSROOT="$SYSROOT"
export PATH="\$VMN_EMANE_SYSROOT/usr/bin:\$PATH"
export LD_LIBRARY_PATH="\$VMN_EMANE_SYSROOT/usr/lib:\$VMN_EMANE_SYSROOT/usr/lib/x86_64-linux-gnu:\$VMN_EMANE_SYSROOT/lib/x86_64-linux-gnu\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
export PYTHONPATH="\$VMN_EMANE_SYSROOT/usr/lib/python3/dist-packages\${PYTHONPATH:+:\$PYTHONPATH}"
EOF

# shellcheck disable=SC1091
source "$PREFIX/env.sh"
emane --version
python3 -c "from emane.events import TDMAScheduleEvent, PathlossEvent; from emane.shell import ControlPortClient; print('EMANE Python API OK')"
unshare --user --map-root-user --net true && echo "unprivileged user+net namespaces OK"
echo "done: source $PREFIX/env.sh"
