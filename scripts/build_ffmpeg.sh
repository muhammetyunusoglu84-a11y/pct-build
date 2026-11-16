#!/bin/bash
# FFmpeg as LGPL shared libraries (no GPL / nonfree parts, no external codec
# libraries).  Decoders, demuxers and the ProRes encoder are FFmpeg's own.
#   build_ffmpeg.sh <work_dir> <prefix>
set -euo pipefail
WORK="${1:?work dir}"; PREFIX="${2:?prefix}"
TAG="${FFMPEG_TAG:-n9.0.2}"
JOBS="${JOBS:-$( (sysctl -n hw.ncpu 2>/dev/null || nproc) )}"
mkdir -p "$WORK" "$PREFIX"; WORK="$(cd "$WORK" && pwd)"; PREFIX="$(cd "$PREFIX" && pwd)"
[ -d "$WORK/ffmpeg" ] || git clone -q --depth 1 --branch "$TAG" https://github.com/FFmpeg/FFmpeg.git "$WORK/ffmpeg"
cd "$WORK/ffmpeg"
ARGS=(--prefix="$PREFIX" --enable-shared --disable-static --enable-pic
      --disable-programs --disable-doc --disable-debug
      --disable-autodetect --enable-zlib)
if [ "$(uname)" = "Darwin" ]; then
  T="${MACOSX_DEPLOYMENT_TARGET:-14.0}"
  ARGS+=(--enable-videotoolbox --enable-audiotoolbox --arch=arm64 --cc=clang
         --extra-cflags="-arch arm64 -mmacosx-version-min=$T"
         --extra-ldflags="-arch arm64 -mmacosx-version-min=$T")
fi
./configure "${ARGS[@]}" > "$WORK/ffmpeg-configure.log" || { tail -30 ffbuild/config.log; exit 1; }
grep -i "^License" "$WORK/ffmpeg-configure.log"
# hard guarantees: LGPL, no GPL / nonfree code compiled in
grep -q '^#define FFMPEG_LICENSE "LGPL version 2.1 or later"' config.h
grep -q '^#define CONFIG_GPL 0' config.h
grep -q '^#define CONFIG_NONFREE 0' config.h
grep -q '^#define CONFIG_VERSION3 0' config.h
if grep -Eq '^#define CONFIG_LIB(X264|X265|XVID|VIDSTAB|RUBBERBAND)[A-Z0-9_]* 1' config.h; then echo 'GPL library enabled'; exit 1; fi
make -j "$JOBS" > "$WORK/ffmpeg-build.log" 2>&1 || { tail -40 "$WORK/ffmpeg-build.log"; exit 1; }
make install > /dev/null
cp COPYING.LGPLv2.1 "$PREFIX/COPYING.LGPLv2.1"
cp config.h "$PREFIX/ffmpeg-config.h"
{ echo "FFmpeg $TAG"; echo "configure ${ARGS[*]}"; } > "$PREFIX/ffmpeg-build-info.txt"
ls "$PREFIX/lib" | grep -E "dylib|\.so" | head -30
