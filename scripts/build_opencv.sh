#!/bin/bash
# OpenCV Python wheel without FFmpeg / GStreamer / AVFoundation (no external
# media libraries at all).  Image codecs are OpenCV's own bundled (permissive) ones.
#   build_opencv.sh <out_dir>
set -euo pipefail
OUT="${1:?out dir}"
VER="${OPENCV_VERSION:-5.0.0.93}"
mkdir -p "$OUT" raw-cv; OUT="$(cd "$OUT" && pwd)"
export ENABLE_HEADLESS=1
export CMAKE_BUILD_PARALLEL_LEVEL="${JOBS:-$( (sysctl -n hw.ncpu 2>/dev/null || nproc) )}"
# All OpenCV modules stay enabled (the Python packaging expects the complete
# module set); what is switched off are the external media back-ends, so the
# video module contains only OpenCV's own code.  Image codecs are the bundled ones.
export CMAKE_ARGS="\
 -DWITH_FFMPEG=OFF -DWITH_GSTREAMER=OFF -DWITH_AVFOUNDATION=OFF -DWITH_1394=OFF \
 -DWITH_QT=OFF -DWITH_GTK=OFF -DWITH_OPENGL=OFF \
 -DWITH_TBB=OFF -DWITH_OPENMP=OFF -DWITH_GDAL=OFF -DWITH_JASPER=OFF \
 -DWITH_AVIF=OFF -DWITH_JPEGXL=OFF -DWITH_GDCM=OFF -DWITH_EIGEN=OFF -DWITH_VTK=OFF \
 -DBUILD_ZLIB=ON -DBUILD_PNG=ON -DBUILD_JPEG=ON -DBUILD_TIFF=ON -DBUILD_WEBP=ON \
 -DBUILD_OPENJPEG=ON -DWITH_OPENEXR=ON -DBUILD_OPENEXR=ON \
 -DOPENCV_ENABLE_NONFREE=OFF -DBUILD_EXAMPLES=OFF"
if [ "$(uname)" = "Darwin" ]; then
  export CMAKE_ARGS="$CMAKE_ARGS -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_DEPLOYMENT_TARGET=${MACOSX_DEPLOYMENT_TARGET:-14.0} -DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local;/opt/local"
  export ARCHFLAGS="-arch arm64"
  export _PYTHON_HOST_PLATFORM="macosx-${MACOSX_DEPLOYMENT_TARGET:-14.0}-arm64"
fi
python -m pip wheel "opencv-python-headless==$VER" --no-binary opencv-python-headless --no-deps -w raw-cv
if [ "$(uname)" = "Darwin" ]; then
  python -m pip install -q delocate
  delocate-wheel --require-archs arm64 -w "$OUT" raw-cv/opencv_python_headless-*.whl
else
  cp raw-cv/opencv_python_headless-*.whl "$OUT/"
fi
ls -la "$OUT"
