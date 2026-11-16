#!/bin/bash
# PyAV wheel built against our LGPL FFmpeg (libraries bundled into the wheel).
#   build_pyav.sh <ffmpeg_prefix> <out_dir>
set -euo pipefail
PREFIX="$(cd "${1:?ffmpeg prefix}" && pwd)"; OUT="${2:?out dir}"
VER="${PYAV_VERSION:-19.0.2}"
mkdir -p "$OUT" raw-av; OUT="$(cd "$OUT" && pwd)"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
export ARCHFLAGS="-arch arm64"
python -m pip wheel "av==$VER" --no-binary av --no-deps -w raw-av
python -m pip install -q delocate
DYLD_LIBRARY_PATH="$PREFIX/lib" delocate-wheel -v -w "$OUT" raw-av/av-*.whl
cp "$PREFIX/COPYING.LGPLv2.1" "$OUT/FFmpeg-COPYING.LGPLv2.1.txt"
cp "$PREFIX/ffmpeg-build-info.txt" "$PREFIX/ffmpeg-config.h" "$OUT/"
ls -la "$OUT"
