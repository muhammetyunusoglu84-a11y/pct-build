"""Checks the custom OpenCV and PyAV builds: every function the tracker uses
exists, FFmpeg is LGPL without GPL codecs, ProRes round-trips."""
import os
import sys
import tempfile

import numpy as np

import av
import cv2

need = """resize cvtColor circle rectangle USAC_MAGSAC Rodrigues imwrite imread imencode imdecode findHomography
triangulatePoints remap calcOpticalFlowPyrLK solvePnPRefineLM solvePnPRansac setRNGSeed recoverPose
goodFeaturesToTrack getStructuringElement findFundamentalMat findEssentialMat dilate cornerSubPix bitwise_or
SOLVEPNP_SQPNP ORB_create NORM_HAMMING Laplacian GaussianBlur BFMatcher OPTFLOW_USE_INITIAL_FLOW""".split()
missing = [n for n in need if not hasattr(cv2, n)]
print("opencv", cv2.__version__, "missing:", missing)
assert not missing
info = cv2.getBuildInformation()
assert "FFMPEG:                      YES" not in info, "OpenCV must not link FFmpeg"

# geometry smoke test (SQPnP RANSAC + MAGSAC + LK + ORB)
rng = np.random.default_rng(0)
X = np.c_[rng.uniform(-2, 2, 200), rng.uniform(-1, 1, 200), rng.uniform(5, 9, 200)]
Kc = np.array([[800., 0, 320], [0, 800., 240], [0, 0, 1]])
rv, tv = np.array([0.05, -0.1, 0.02]), np.array([0.3, -0.1, 0.5])
uv, _ = cv2.projectPoints(X, rv, tv, Kc, None)
ok, r, t, inl = cv2.solvePnPRansac(X, uv, Kc, None, flags=cv2.SOLVEPNP_SQPNP, reprojectionError=2.0)
assert ok and np.linalg.norm(r.ravel() - rv) < 1e-3 and np.linalg.norm(t.ravel() - tv) < 1e-3
uv0, _ = cv2.projectPoints(X, np.zeros(3), np.zeros(3), Kc, None)
F, m = cv2.findFundamentalMat(uv0.reshape(-1, 2), uv.reshape(-1, 2), cv2.USAC_MAGSAC, 1.0, 0.999, 2000)
assert F is not None and m.sum() > 150
img = (rng.random((240, 320)) * 255).astype(np.uint8)
img = cv2.GaussianBlur(img, (0, 0), 1.5)
p0 = cv2.goodFeaturesToTrack(img, 100, 0.01, 5)
img2 = np.roll(img, 3, axis=1)
p1, st, _ = cv2.calcOpticalFlowPyrLK(img, img2, p0, None)
assert st.sum() > 50 and abs(np.median((p1 - p0)[st.ravel() == 1][:, 0, 0]) - 3) < 0.2
kp, des = cv2.ORB_create(500).detectAndCompute(img, None)
assert len(kp) > 20
okp, buf = cv2.imencode(".png", img); assert okp and (cv2.imdecode(buf, cv2.IMREAD_UNCHANGED) == img).all()
okj, buf = cv2.imencode(".jpg", img); assert okj

# FFmpeg / PyAV
lic = av.library_versions if hasattr(av, "library_versions") else {}
print("pyav", av.__version__, lic)
cfg = getattr(av, "ffmpeg_version_info", "")
print("ffmpeg", cfg)
codecs = av.codecs_available
for bad in ("libx264", "libx265", "libxvid"):
    assert bad not in codecs, bad + " must not be present"
for good in ("h264", "hevc", "prores", "prores_ks", "dnxhd", "mpeg2video", "mjpeg", "png", "exr", "dpx"):
    assert good in codecs, good + " missing"
tmp = os.path.join(tempfile.mkdtemp(), "t.mov")
with av.open(tmp, "w") as out:
    s = out.add_stream("prores_ks", rate=25)
    s.width, s.height, s.pix_fmt = 320, 240, "yuv422p10le"
    for i in range(10):
        fr = av.VideoFrame.from_ndarray(np.full((240, 320, 3), i * 20, np.uint8), format="bgr24")
        for pkt in s.encode(fr):
            out.mux(pkt)
    for pkt in s.encode():
        out.mux(pkt)
with av.open(tmp) as inp:
    frames = [f.to_ndarray(format="bgr24") for f in inp.decode(video=0)]
assert len(frames) == 10 and abs(int(frames[5].mean()) - 100) <= 3, (len(frames), frames[5].mean())
if sys.platform == "darwin":
    assert "h264_videotoolbox" in codecs
print("MEDIA OK")
