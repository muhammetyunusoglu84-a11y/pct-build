#!/bin/bash
# Builds libpct_ba (bundle adjustment core) with a private static Ceres Solver.
#   ./build.sh <work_dir> <out_dir>
# Ceres is configured WITHOUT SuiteSparse (GPL parts) and without glog/gflags:
# sparse solves use Apple Accelerate (macOS) or Eigen; everything linked in is
# BSD / MPL-2.0 / Apache-2.0.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:?work dir}"; OUT="${2:?output dir}"
CERES_TAG="${CERES_TAG:-2.2.0}"
EIGEN_TAG="${EIGEN_TAG:-3.4.0}"
JOBS="${JOBS:-$( (sysctl -n hw.ncpu 2>/dev/null || nproc) )}"
mkdir -p "$WORK" "$OUT"; WORK="$(cd "$WORK" && pwd)"; OUT="$(cd "$OUT" && pwd)"
PREFIX="$WORK/prefix"
COMMON=(-DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DBUILD_SHARED_LIBS=OFF
        -DCMAKE_INSTALL_PREFIX="$PREFIX" -DCMAKE_PREFIX_PATH="$PREFIX")
if [ "$(uname)" = "Darwin" ]; then
  COMMON+=(-DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-14.0}")
fi
if [ ! -f "$PREFIX/.eigen-$EIGEN_TAG" ] && [ -z "${USE_SYSTEM_EIGEN:-}" ]; then
  [ -d "$WORK/eigen" ] || git clone -q --depth 1 --branch "$EIGEN_TAG" https://gitlab.com/libeigen/eigen.git "$WORK/eigen"
  cmake -S "$WORK/eigen" -B "$WORK/eigen-build" "${COMMON[@]}" -DBUILD_TESTING=OFF -DEIGEN_BUILD_DOC=OFF >/dev/null
  cmake --install "$WORK/eigen-build" >/dev/null
  touch "$PREFIX/.eigen-$EIGEN_TAG"
fi
if [ ! -f "$PREFIX/.ceres-$CERES_TAG-q" ]; then
  [ -d "$WORK/ceres-solver" ] || git clone -q --depth 1 --branch "$CERES_TAG" https://github.com/ceres-solver/ceres-solver.git "$WORK/ceres-solver"
  cmake -S "$WORK/ceres-solver" -B "$WORK/ceres-build" "${COMMON[@]}" \
    -DMINIGLOG=ON -DMINIGLOG_MAX_LOG_LEVEL=-2 -DGFLAGS=OFF -DSUITESPARSE=OFF -DEIGENMETIS=OFF -DUSE_CUDA=OFF \
    -DEIGENSPARSE=ON -DLAPACK=ON -DSCHUR_SPECIALIZATIONS=ON \
    -DBUILD_TESTING=OFF -DBUILD_EXAMPLES=OFF -DBUILD_BENCHMARKS=OFF -DBUILD_DOCUMENTATION=OFF \
    -DPROVIDE_UNINSTALL_TARGET=OFF > "$WORK/ceres-configure.log"
  grep -i "suitesparse\|accelerate\|lapack\|eigen sparse\|miniglog" "$WORK/ceres-configure.log" || true
  cmake --build "$WORK/ceres-build" -j "$JOBS" > "$WORK/ceres-build.log" 2>&1 || { tail -40 "$WORK/ceres-build.log"; exit 1; }
  cmake --install "$WORK/ceres-build" >/dev/null
  touch "$PREFIX/.ceres-$CERES_TAG-q"
fi
cmake -S "$HERE" -B "$WORK/pct_ba-build" "${COMMON[@]}" -DCMAKE_INSTALL_PREFIX="$OUT" >/dev/null
cmake --build "$WORK/pct_ba-build" -j "$JOBS"
cmake --install "$WORK/pct_ba-build" >/dev/null
cp "$WORK/ceres-solver/LICENSE" "$OUT/LICENSE-ceres-solver.txt"
ls -la "$OUT"
