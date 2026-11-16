"""Fails if any shipped binary contains GPL-only components.
   check_licenses.py <dir with wheels / dylibs (unpacked or not)>"""
import os
import re
import sys
import zipfile

BAD = [rb"libx264", rb"libx265", rb"x264 - core", rb"GPL version [23] or later", rb"--enable-gpl",
       rb"--enable-nonfree", rb"CHOLMOD", rb"SuiteSparse", rb"SPQR", rb"libvidstab", rb"rubberband",
       rb"xvidcore"]
ALLOW = {rb"GPL version [23] or later": rb"LGPL version [23](\.1)? or later"}
bad = 0


def scan(name, data):
    global bad
    for pat in BAD:
        hits = [m for m in re.finditer(pat, data)]
        if pat in ALLOW:  # "LGPL version ..." also matches the GPL pattern
            hits = [m for m in hits if not re.match(ALLOW[pat], data[max(0, m.start() - 1):m.end() + 4])]
        if hits:
            ctx = data[max(0, hits[0].start() - 30):hits[0].end() + 30]
            print("FOUND %-28s in %s   ...%r..." % (pat.decode(), name, ctx))
            bad += 1
    m = re.search(rb"lib(avcodec|avformat|avutil) license: ([^\x00]+)", data)
    if m:
        print("  %s: %s" % (name, m.group(0).decode()))


for root, _, files in os.walk(sys.argv[1]):
    for f in files:
        p = os.path.join(root, f)
        if f.endswith(".whl"):
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if n.endswith((".so", ".dylib")) or ".dylib" in n or ".so." in n:
                        scan(f + ":" + n, z.read(n))
        elif f.endswith((".so", ".dylib")) or ".so." in f:
            scan(p, open(p, "rb").read())
print("GPL-only components found: %d" % bad)
sys.exit(1 if bad else 0)
