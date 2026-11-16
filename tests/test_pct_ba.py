"""Checks libpct_ba on a synthetic scene: noisy cameras, points and lens must
converge back to the truth.   python test_pct_ba.py <path to libpct_ba>"""
import ctypes
import sys

import numpy as np
from scipy.spatial.transform import Rotation

lib = ctypes.CDLL(sys.argv[1])
D, I, U = ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_ubyte)
lib.pct_ba_solve.restype = ctypes.c_int
lib.pct_ba_solve.argtypes = [ctypes.c_int, D, D, U, ctypes.c_int, D, ctypes.c_int, I, I, D, D, ctypes.c_int,
                             ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_double, ctypes.c_int,
                             ctypes.c_int, ctypes.c_int, ctypes.c_int, D]


def run(n_cams, n_pts, seed=0, window=None):
    rng = np.random.default_rng(seed)
    f, cx, cy, k1 = 900.0, 640.0, 360.0, -0.08
    X = np.c_[rng.uniform(-4, 4, n_pts), rng.uniform(-2, 2, n_pts), rng.uniform(6, 14, n_pts)]
    rv = np.c_[rng.normal(0, .02, n_cams), np.linspace(-.25, .25, n_cams), rng.normal(0, .02, n_cams)]
    R = Rotation.from_rotvec(rv).as_matrix()
    C = np.c_[np.linspace(-2, 2, n_cams), rng.normal(0, .1, n_cams), rng.normal(0, .2, n_cams)]
    t = -np.einsum("nij,nj->ni", R, C)
    oc, op, xy = [], [], []
    for c in range(n_cams):
        p = X @ R[c].T + t[c]
        u, v = p[:, 0] / p[:, 2], p[:, 1] / p[:, 2]
        d = 1 + k1 * (u * u + v * v)
        px = np.c_[f * d * u + cx, f * d * v + cy]
        ok = (p[:, 2] > 0) & (px[:, 0] > 0) & (px[:, 0] < 1280) & (px[:, 1] > 0) & (px[:, 1] < 720)
        if window:  # video-like tracks: each point lives for a limited run of frames
            ok &= np.abs(np.arange(n_pts) * n_cams / n_pts - c) < window
        oc += [c] * int(ok.sum()); op += list(np.flatnonzero(ok)); xy.append(px[ok] + rng.normal(0, .3, (int(ok.sum()), 2)))
    oc, op, xy = np.array(oc, np.int32), np.array(op, np.int32), np.ascontiguousarray(np.concatenate(xy))
    q = Rotation.from_matrix(R).as_quat()[:, [3, 0, 1, 2]]
    q0 = np.ascontiguousarray(q + rng.normal(0, .004, q.shape)); q0 /= np.linalg.norm(q0, axis=1)[:, None]
    q0[:2] = q[:2]
    t0 = t + rng.normal(0, .03, t.shape); t0[:2] = t[:2]
    X0 = X + rng.normal(0, .08, X.shape)
    K = np.array([f * 1.08, cx, cy, 0.0])
    info = np.zeros(6)
    P = lambda a, T: a.ctypes.data_as(ctypes.POINTER(T))
    rc = lib.pct_ba_solve(n_cams, P(q0, ctypes.c_double), P(t0, ctypes.c_double), None, n_pts,
                          P(X0, ctypes.c_double), len(oc), P(oc, ctypes.c_int32), P(op, ctypes.c_int32),
                          P(xy, ctypes.c_double), P(K, ctypes.c_double), 1, 1, 1.0, 100, 1e-9, 0, 1, 0, 0,
                          P(info, ctypes.c_double))
    # the solution is defined up to a similarity transform: align before comparing
    ms, md = X0.mean(0), X.mean(0)
    Uu, Dd, Vt = np.linalg.svd((X - md).T @ (X0 - ms) / len(X))
    Sg = np.diag([1, 1, np.sign(np.linalg.det(Uu) * np.linalg.det(Vt))])
    Ra = Uu @ Sg @ Vt
    sc = np.trace(np.diag(Dd) @ Sg) / ((X0 - ms) ** 2).sum() * len(X)
    perr = np.linalg.norm(sc * (X0 - ms) @ Ra.T + md - X, axis=1)
    print(f"cams={n_cams} obs={len(oc)} rc={rc} cost {info[0]:.1f} -> {info[1]:.2f} iters={int(info[2])} "
          f"solver={int(info[4])}  f={K[0]:.2f} k1={K[3]:+.4f}  point err median {np.median(perr):.4f}")
    assert rc == 0 and info[5] == 1
    assert abs(K[0] - f) / f < 0.004 and abs(K[3] - k1) < 0.01, "lens not recovered"
    assert np.median(perr) < (0.03 if not window else 0.15), "structure not recovered"
    assert info[1] / len(oc) < 0.12, "residuals above the noise level"


run(30, 600)            # dense Schur
run(450, 3000, seed=1, window=45)  # sparse Schur (Accelerate on macOS, Eigen elsewhere)
print("PCT_BA OK")
