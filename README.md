# pct-build

Build scripts for the open-source libraries used by Pro Camera Tracker
(macOS, Apple Silicon).  Everything built here is free of GPL-only code:

| Output | What | License |
|---|---|---|
| `libpct_ba` | bundle adjustment core: a thin C wrapper over Ceres Solver, built without SuiteSparse (Apple Accelerate / Eigen instead) | Ceres BSD-3-Clause, Eigen MPL-2.0 |
| PyAV wheel | PyAV with FFmpeg built as **LGPL 2.1+** shared libraries: no `--enable-gpl`, no x264/x265, no external codec libraries | PyAV BSD-3-Clause, FFmpeg LGPL-2.1+ |
| OpenCV wheel | `opencv-python-headless` reduced to the modules the tracker needs; no FFmpeg, no video I/O | Apache-2.0 |

`scripts/build_ffmpeg.sh` records the exact FFmpeg tag and configure line
(`ffmpeg-build-info.txt`, `ffmpeg-config.h`), so the bundled FFmpeg libraries
can be rebuilt or replaced, as the LGPL requires.

`scripts/check_licenses.py` scans every produced binary and fails the build if
a GPL-only component is found.
