#!/usr/bin/env python3
"""Felix-Edit (Stand v15) im Stil des Referenz-Edits von @sorinyx.

Was hier drin steckt (Details: docs/effekte-katalog.md):
 * Intro = EIN Clip: Stotter-Spruenge, S/W-Flackern, Zoom-Stoesse, Farbe blendet weich aus,
   Lichtblitz am linken Rand, Kipp-Drehung + Wellen-Shake in den ersten Clip
 * Kamerabewegung jedes Clips Bild fuer Bild aus der Referenz uebernommen (ref_camera.json)
 * Uebergaenge der Referenz (Zoom-Unschaerfe-Streifen, Abdunkeln, Echo, schwarzer Kreis, ...)
 * Trommel-Break 9,15-10,90 s: ein Schnitt exakt auf jedem Schlag, alle gleicher Uebergang
 * CC-Filter (edit-toolkit/look.py), Teal-Look fuer den Kreis-Clip
 * Ruckelfreie Wiedergabe: doppelte Bildschirmaufnahme-Frames werden entfernt

Aufruf:
  python3 render.py                       -> rendert das ganze Video nach out/
  python3 render.py frames 110 117 120    -> nur einzelne Vorschaubilder nach out/
Medien: siehe media.md / link_media.py (Ordner media/, wird nicht ins Git eingecheckt)
"""
import math, os, re, subprocess, sys, time
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "edit-toolkit"))
from scenes import SCENES, BASE
from look import cc
from teal_look import teal_look

MEDIA = os.environ.get("EDIT_MEDIA", os.path.join(HERE, "media"))
FEL = MEDIA                                     # clip1.mov ... clip13.mov
EXAMPLE = os.path.join(MEDIA, "reference.mp4")  # Referenz-Edit (liefert auch die Tonspur)
OUTDIR = os.environ.get("EDIT_OUT", os.path.join(HERE, "out"))
OUT = os.path.join(OUTDIR, "Felix_Edit.mp4")
FPS, W, NF = 30, 1080, 558
G = W / 576.0

GR = {
    "normal": ("eq=contrast=1.06:saturation=1.08:gamma=0.98", ""),
    "dark":   ("eq=brightness=-0.03:contrast=1.15:saturation=0.92:gamma=0.94", ""),
    "bright": ("eq=brightness=0.03:contrast=1.02:saturation=1.05:gamma=1.08", ""),
    "teal":   ("eq=brightness=0.12:gamma=1.55:contrast=0.92:saturation=1.15",
               "curves=r='0/0.03 0.5/0.64 1/1':g='0/0.40 0.5/0.80 1/1':b='0/0.40 0.5/0.80 1/1'"),
    "pink":   ("eq=contrast=1.15:saturation=1.3", "colorhold=color=0xE89AB0:similarity=0.32:blend=0.30"),
    "redsel": ("eq=contrast=1.12:saturation=1.25", "colorhold=color=0xC0182A:similarity=0.38:blend=0.18"),
}
DN = "hqdn3d=2.2:1.8:3:3"

# ------------------------------------------------------------------ shots
class Shot:
    def __init__(self, f0, scene, src, grade="normal", direction=1, mag=0.11, tag=""):
        self.f0, self.scene, self.src, self.grade = f0, scene, src, grade
        self.dir, self.mag, self.tag = direction, mag, tag

shots = [Shot(0, "glove_x", 3.70, "normal", 1, 0.0, "intro")]
S1 = [117, 131, 143, 159, 173, 186, 199, 211, 226, 239, 252, 264, 279, 284, 290, 295, 302, 309, 316, 324]
P2 = 214
part1 = [("stg_flip", 3.30, "normal"), ("stg_green", 1.70, "normal"), ("stg_thumb", 4.20, "normal"),
         ("stg_red", 5.40, "normal"), ("shoot_red", 6.00, "dark"), ("selfie", 4.40, "bright"),
         ("micsmile", 2.00, "dark"), ("fur", 6.40, "normal"), ("suit", 1.40, "teal"),
         ("pink_room", 9.00, "normal"), ("shoot_sit", 4.60, "normal"), ("pink_kiss", 7.70, "pink"),
         ("floor", 11.00, "dark"), ("tank", 13.75, "bright"), ("claws", 0.30, "dark"),
         ("red_hair", 5.20, "redsel"), ("coffee", 8.20, "normal"), ("brick", 13.00, "bright"),
         ("silver", 2.80, "dark"), ("red_shy", 6.30, "normal")]
part2 = [("stg_arm", 0.94, "normal"), ("shoot_cam", 10.00, "normal"), ("stg_blue", 0.30, "normal"),
         ("blue_up", 2.20, "normal"), ("red_laugh", 9.10, "dark"), ("tank", 14.10, "bright"),
         ("bear", 0.15, "dark"), ("fur", 3.40, "normal"), ("suit", 2.60, "teal"),
         ("pink_face", 4.70, "normal"), ("furwide", 0.40, "normal"), ("pink_up", 13.40, "pink"),
         ("floor", 12.30, "dark"), ("selfie", 6.50, "bright"), ("shoot_red", 7.60, "dark"),
         ("red_hair", 4.20, "redsel"), ("claws", 1.00, "normal"), ("brick", 15.20, "bright"),
         ("silver", 3.80, "dark"), ("red_shy", 6.60, "normal")]
# drum break 9.15 s - 10.90 s: one cut exactly on every drum hit (measured from the audio)
BREAK = [274, 280, 287, 294, 300, 307, 313, 320, 327]
BREAK_CLIPS = [("floor", 11.00), ("tank", 13.75), ("claws", 0.30), ("glove_mic", 0.30), ("red_hair", 5.20),
               ("coffee", 8.20), ("brick", 13.00), ("silver", 2.80), ("red_shy", 6.30)]
part1 = part1[:12]
for base, part, nm in ((0, part1, "p1"), (P2, part2, "p2")):
    for j, (sc, src, gr) in enumerate(part):
        mag = 0.11 if j < 12 else 0.06
        shots.append(Shot(S1[j] + base, sc, src, gr, 1 if j % 2 == 0 else -1, mag, f"{nm}_{j + 1}"))
for k, (sc, src) in enumerate(BREAK_CLIPS):
    shots.append(Shot(BREAK[k], sc, src, "normal", 1, 0.0, f"brk_{k + 1}"))
shots.sort(key=lambda sh: sh.f0)
for k in range(len(shots)):
    shots[k].f1 = shots[k + 1].f0 if k + 1 < len(shots) else NF

# ------------------------------------------------------------------ reference effects (offsets to switch frame)
def e(**kw):
    return kw
# Calibrated on the reference: during a transition ~20-35 % of the detail stays visible and the
# picture dips smoothly darker over ~5 frames (no fully smeared frames).
SIG = {-3: 1.2, -2: 2.0, -1: 2.8, 0: 2.8, 1: 2.3, 2: 1.7, 3: 1.0}
MUL = {"generic": {-3: .95, -2: .82, -1: .60, 0: .54, 1: .68, 2: .83, 3: .94},
       "deep":    {-3: .90, -2: .64, -1: .32, 0: .36, 1: .57, 2: .76, 3: .90},
       "mild":    {-2: .92, -1: .76, 0: .74, 1: .84, 2: .93}}
ZOOM = {-3: 1.01, -2: 1.03, -1: 1.07, 0: 1.07, 1: 1.035, 2: 1.012}
def blur_tr(depth="generic", d="v", echo=None, outgoing=True):
    t = {}
    for off in range(-3, 4):
        if off < 0 and not outgoing:
            continue
        sp = {}
        sp["sig"] = SIG[off]
        m = MUL[depth].get(off)
        if m is not None:
            sp["mul"] = m
        if off in ZOOM:
            sp["z"] = ZOOM[off]
        if off in (-1, 0, 1):
            sp["L"], sp["d"] = {-1: 0.020, 0: 0.025, 1: 0.012}[off], d
        t[off] = sp
    for k, a_ in enumerate(echo or []):
        t.setdefault(2 + k, {})["echo"] = a_
    return t
# Motion-streak transitions measured on the reference (streak length = fraction of the frame,
# almost no defocus blur, darkness like the reference)
TR = {
    0:  {0: e(sig=40, mul=0.32, z=1.08), 1: e(L=0.12, d="d", sig=10, mul=0.55, z=1.05),
         2: e(L=0.12, d="d", mul=0.72, z=1.03), 3: e(L=0.04, d="d", mul=0.88, z=1.01)},
    1:  {-2: e(L=0.08, d="d", z=1.03), -1: e(L=0.12, d="d", z=1.07, mul=0.85),
         0: e(L=0.45, d="h", mul=0.48, z=1.07), 1: e(L=0.12, d="h", echo=0.25, z=1.035), 2: e(L=0.03, d="h", z=1.012)},
    2:  {0: e(L=0.08, d="d", sig=0.8, mul=0.9, z=1.04), 1: e(L=0.03, d="d", z=1.015)},
    3:  {-3: e(L=0.05, d="v", z=1.01), -2: e(L=0.30, d="v", mul=0.55, z=1.04), -1: e(L=0.50, d="v", mul=0.2, z=1.08),
         0: e(L=0.25, d="v", mul=0.5, z=1.07), 1: e(L=0.06, d="v", mul=0.85, z=1.03),
         2: e(echo=0.45), 3: e(echo=0.40), 4: e(echo=0.28)},
    4:  {-2: e(L=0.30, d="v", mul=0.6, z=1.04), -1: e(L=0.45, d="v", sig=3, mul=0.35, z=1.08),
         0: e(L=0.40, d="v", sig=3, mul=0.35, z=1.08), 1: e(L=0.15, d="d", mul=0.8, z=1.04), 2: e(L=0.06, d="d", z=1.015)},
    5:  {-3: e(L=0.03, d="v"), -2: e(L=0.08, d="v", z=1.03), -1: e(L=0.40, d="v", mul=0.6, z=1.07),
         0: e(L=0.35, d="v", mul=0.7, z=1.07), 1: e(L=0.03, d="v", z=1.02)},
    6:  {-2: e(L=0.06, d="v", z=1.03), -1: e(L=0.45, d="v", mul=0.55, z=1.07),
         0: e(sig=4, mul=0.85, z=1.05), 1: e(sig=2, z=1.02)},
    7:  {-2: e(sig=1.5, mul=0.7, z=1.03), -1: e(L=0.50, d="v", sig=6, mul=0.35, z=1.08),
         0: e(L=0.30, d="d", mul=0.8, z=1.07), 1: e(L=0.14, d="d", z=1.035), 2: e(L=0.05, d="d", z=1.012)},
    8:  {-2: e(L=0.08, d="h", z=1.03), -1: e(L=0.30, d="h", mul=0.85, z=1.07),
         0: e(L=0.25, d="h", sig=3, mul=0.9, z=1.09), 1: e(L=0.08, d="h", sig=2, z=1.04), 2: e(echo=0.40), 3: e(echo=0.25)},
    9:  {-5: e(cout=0.006), -4: e(cout=0.023), -3: e(cout=0.054, mul=0.98, vig=0.10, z=1.02),
         -2: e(cout=0.12, mul=0.92, vig=0.28, z=1.05), -1: e(cout=0.283, mul=0.80, vig=0.50, z=1.10),
         0: e(cin=0.40, L=0.45, d="v", mul=0.55, z=1.08), 1: e(cin=0.55, L=0.30, d="v", mul=0.75, z=1.05),
         2: e(L=0.10, d="v", mul=0.92, z=1.02)},
    10: {-2: e(L=0.20, d="v", z=1.03), -1: e(L=0.50, d="v", mul=0.75, z=1.07),
         0: e(L=0.20, d="v", sig=2, z=1.05), 1: e(L=0.05, d="v", z=1.02)},
    11: {-1: e(sig=1, mul=0.75), 0: e(sig=5, L=0.10, d="v", mul=0.9, z=1.06), 1: e(sig=2.5, z=1.02),
         2: e(echo=0.32), 3: e(echo=0.28), 4: e(echo=0.22), 5: e(echo=0.16), 6: e(echo=0.10)},
    12: {-3: e(mul=0.85), -2: e(mul=0.55), -1: e(mul=0.15), 0: e(mul=0.45, sig=1.5), 1: e(mul=0.8)},
    13: {}, 14: {-1: e(z=1.04, expo=1.08), 2: e(leak=0.65), 3: e(leak=0.35)},
    15: {}, 16: {},
    17: {0: e(expo=0.75), 1: e(expo=0.92), 2: e(expo=1.06, glow=0.35)},
    18: {0: e(expo=0.20), 1: e(expo=0.55)},
    19: {0: e(sig=1.5, mul=0.9)},
}
PRE_PART2 = {}   # the last drum-hit clip stays clean; part 2 fades in from dark like part 1
SPEC, ZIN, ZOUT = {}, {}, {}
for base in (0, P2):
    for n, sw in enumerate(S1):
        if base == 0 and n >= 12:
            continue
        for off, d in TR[n].items():
            SPEC.setdefault(sw + base + off, {}).update(d)
            if "z" in d:
                (ZIN if off >= 0 else ZOUT)[sw + base + off] = d["z"]
for off, d in PRE_PART2.items():
    SPEC.setdefault(S1[0] + P2 + off, {}).update(d)
    if "z" in d:
        ZOUT[S1[0] + P2 + off] = d["z"]

import json
REFP = {int(k): v for k, v in json.load(open(os.path.join(HERE, "ref_camera.json"))).items()}
ROT_GAIN = 0.0          # measured rotations are mostly head/body movement, not edit rotation

def _ref_vals(ref0, n, vmax, kmax=None):
    v = [None] * n; r = [None] * n
    for k in range(1, n):
        if kmax is not None and k > kmax:
            continue
        rr = REFP.get(ref0 + k)
        if rr and rr[4] >= 0.8 and abs(math.log(rr[0])) <= vmax:
            v[k] = math.log(rr[0])
            if abs(rr[1]) <= 4.0:
                r[k] = rr[1]
    return v, r

def _first_valid(vals):
    for x in vals[1:]:
        if x is not None:
            return x
    return 0.0

def _fill(vals, end_sign, cap=0.12, decay_tail=False):
    n = len(vals)
    out = [0.0] * n
    idx = [k for k in range(1, n) if vals[k] is not None]
    if not idx:
        return [0.0] + [0.01 * end_sign] * (n - 1)
    for k in idx:
        out[k] = vals[k]
    for k in range(1, idx[0]):                       # incoming: keep the arriving energy
        out[k] = float(np.clip(vals[idx[0]] * 1.6 ** (idx[0] - k), -cap, cap))
    for a, b in zip(idx, idx[1:]):
        for k in range(a + 1, b):
            out[k] = vals[a] + (vals[b] - vals[a]) * (k - a) / (b - a)
    last = vals[idx[-1]]
    for k in range(idx[-1] + 1, n):                  # outgoing: accelerate into the cut
        step = k - idx[-1]
        if decay_tail:
            out[k] = last * 0.8 ** step
            continue
        target = end_sign * min(cap, max(abs(last), 0.015) * 1.8 ** step)
        out[k] = target if last * end_sign >= 0 else last + (target - last) * min(1.0, step / 2)
    return out

def _fill_rot(rv):
    n = len(rv); out = [0.0] * n
    idx = [k for k in range(1, n) if rv[k] is not None]
    for k in idx:
        out[k] = rv[k]
    for a, b in zip(idx, idx[1:]):
        for k in range(a + 1, b):
            out[k] = rv[a] + (rv[b] - rv[a]) * (k - a) / (b - a)
    return out

CURVE = {}
def _build():
    info = []
    for i, sh in enumerate(shots):
        n = sh.f1 - sh.f0
        kmax = None
        if sh.tag.startswith("brk"):
            vel = [0.0]
            for k in range(1, n):
                u = (k - 1) / max(1, n - 2)
                vel.append((2.2 + 2.8 * (1 - u) ** 3 + 2.3 * u ** 3) / 100)
            L = np.cumsum(vel)
            for k in range(n):
                CURVE[sh.f0 + k] = (float(math.exp(L[k])), 0.0)
            info.append((sh.tag, sh.scene, 1.0, round(float(math.exp(L[-1])), 3), 0, 0, 1))
            continue
        if sh.tag == "intro":
            ref0, vmax, rng_max, end_sign = 0, 0.16, math.log(1.5), -1
        else:
            part, j = sh.tag.split("_"); j = int(j) - 1
            off = P2 if part == "p2" else 0
            ref0, vmax, rng_max = S1[j] + off, 0.12, math.log(1.42)
            if part == "p2" and j == 19:
                kmax = 6
            nxt = S1[j + 1] + off if j < 19 else (S1[0] + P2 if part == "p1" else None)
            if nxt is None or nxt in (239, 239 + P2):
                end_sign = 1
            else:
                nv, _ = _ref_vals(nxt, 8, 0.12)
                end_sign = 1 if _first_valid(nv) < 0 else -1
        vals, rots = _ref_vals(ref0, n, vmax, kmax)
        vel = _fill(vals, end_sign, decay_tail=(sh.tag == "p2_20"))
        L = np.cumsum(vel)
        rng = L.max() - L.min()
        if rng > rng_max:
            L = L * (rng_max / rng)
        th = np.cumsum(_fill_rot(rots)) * ROT_GAIN
        cov = np.array([math.cos(math.radians(abs(t))) + math.sin(math.radians(abs(t))) for t in th])
        L = L - np.min(L - np.log(cov))
        for k in range(n):
            CURVE[sh.f0 + k] = (float(math.exp(L[k])), float(th[k]))
        info.append((sh.tag, sh.scene, round(float(np.exp(L.min())), 3), round(float(np.exp(L.max())), 3),
                     round(float(th.min()), 1), round(float(th.max()), 1), end_sign))
    return info
CURVE_INFO = _build()

# 1) the picture tilts (~9 deg) and drifts up in the last frames of the intro (background-tracked)
INTRO_TILT = {111: 0.0, 112: -1.7, 113: -3.8, 114: -5.7, 115: -7.3, 116: -9.2}
SHIFT = {111: (0.0, 0.0), 112: (0.0006, 0.002), 113: (-0.002, 0.006), 114: (-0.0006, -0.006),
         115: (-0.004, -0.029), 116: (-0.012, -0.051)}
for _f, _a in INTRO_TILT.items():
    CURVE[_f] = (CURVE[_f][0], CURVE[_f][1] + _a)
SHIFT = {f: (dx * W, dy * W) for f, (dx, dy) in SHIFT.items()}
# 2) the small "shake": a fine wave distortion that builds up before the cut and dies away in clip 1
SHAKE_AMP = {113: .0010, 114: .0015, 115: .0022, 116: .0030, 117: .0040, 118: .0050, 119: .0050, 120: .0045,
             121: .0035, 122: .0028, 123: .0020, 124: .0014, 125: .0010, 126: .0007, 127: .0004}
# the incoming clip arrives slightly turned and settles - the spin continues the direction of the outgoing tilt
for _f, _a in {117: 5.0, 118: 3.6, 119: 2.0, 120: 0.5}.items():
    CURVE[_f] = (CURVE[_f][0], CURVE[_f][1] + _a)
_GY, _GX = np.mgrid[0:W, 0:W].astype(np.float32)
def shake(img, f):
    A = SHAKE_AMP[f] * W
    ph, ps = 2.1 * f, 1.7 * f + 1.0
    dx = A * np.sin(2 * np.pi * _GY / (0.45 * W) + ph) + 0.15 * A * np.sin(2 * np.pi * _GY / (0.09 * W) + 1.3 * ph)
    dy = 0.6 * A * np.sin(2 * np.pi * _GX / (0.5 * W) + ps) + 0.12 * A * np.sin(2 * np.pi * _GX / (0.1 * W) + 1.1 * ps)
    return cv2.remap(img, _GX + dx, _GY + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
# 3) colour fades out smoothly over ~0.5 s like the reference (instead of a hard switch to B&W)
_REF_SAT = {101: .256, 102: .248, 103: .240, 104: .235, 105: .228, 106: .207, 107: .188, 108: .169, 109: .161,
            110: .149, 111: .134, 112: .127, 113: .102, 114: .077, 115: .059, 116: .038}
SATK = {f: min(1.0, v / 0.265) ** 1.3 for f, v in _REF_SAT.items()}

for h in BREAK:                                   # same short, clean accent on every drum hit
    SPEC.setdefault(h, {}).update(expo=1.12)
    SPEC.setdefault(h + 1, {}).update(expo=1.04)

FLICKER = {45, 46, 47, 50, 51, 55, 56, 59, 60, 61}
INTRO_BW_END = range(111, 117)
# intro: ONE clip (glove_x) - like the reference it stutters (jumps ahead within the same clip)
# on the flicker beats; (first frame, source time, speed, zoom start, zoom end)
INTRO_SEG = [(0, 3.70, 0.80, 1.00, 1.18), (48, 5.23, 0.80, 1.13, 1.14), (52, 5.54, 0.80, 1.17, 1.17),
             (53, 5.77, 0.80, 1.10, 1.12), (59, 6.08, 0.80, 1.15, 1.16), (65, 6.44, 0.80, 1.04, 1.30),
             (85, 7.07, 0.55, 1.12, 1.28), (200, 0, 0, 0, 0)]
def intro_seg(f):
    for k in range(len(INTRO_SEG) - 1):
        if INTRO_SEG[k][0] <= f < INTRO_SEG[k + 1][0]:
            return INTRO_SEG[k], INTRO_SEG[k + 1][0]
    return INTRO_SEG[-2], 117
def intro_src(f):
    (f0, t0, sp, _, _), _ = intro_seg(f)
    return t0 + (f - f0) / FPS * sp
def intro_zoom(f):
    (f0, _, _, z0, z1), fend = intro_seg(f)
    fend = min(fend, 117)
    p = (f - f0) / max(1, fend - 1 - f0)
    p = min(max(p, -0.2), 1.2)
    q = p * p * (3 - 2 * p) if 0 <= p <= 1 else p
    return z0 + (z1 - z0) * q
FLARE = {111: 0.9, 112: 0.4}
FLAREMASK = None

def catmull(keys, t):
    ts = [k[0] for k in keys]
    i = max(1, min(len(keys) - 3, np.searchsorted(ts, t) - 1))
    (t0, p0), (t1, p1), (t2, p2), (t3, p3) = keys[i - 1], keys[i], keys[i + 1], keys[i + 2]
    u = (t - t1) / (t2 - t1)
    m1 = (p2 - p0) / (t2 - t0) * (t2 - t1)
    m2 = (p3 - p1) / (t3 - t1) * (t2 - t1)
    u2, u3 = u * u, u * u * u
    return (2 * u3 - 3 * u2 + 1) * p1 + (u3 - 2 * u2 + u) * m1 + (-2 * u3 + 3 * u2) * p2 + (u3 - u2) * m2

# ------------------------------------------------------------------ decoding without judder
def crop_size(pre):
    m = re.findall(r"crop=(\d+):(\d+)", pre)
    return int(m[-1][0]), int(m[-1][1])

RATES = np.array([24, 25, 30, 50, 60])
cache = {}
def load(i):
    """decode a shot, drop repeated screen-recording frames, keep real frame times,
    and pick a playback speed that gives an even cadence at 30 fps"""
    if i in cache:
        return cache[i]
    sh = shots[i]
    clip, a, b, pre, _ = SCENES[sh.scene]
    nfr = sh.f1 - sh.f0 + 3
    s = max(a, sh.src - 0.10)
    e_ = min(b, sh.src + nfr / FPS * 1.25 + 0.25)
    yuv, rgb = GR["normal" if sh.grade == "teal" else sh.grade]
    vf = (f"{BASE},{pre},{DN},{yuv},scale=in_color_matrix=bt709:in_range=tv:flags=lanczos,format=rgb24"
          + (f",{rgb}" if rgb else "") + ",showinfo")
    w, h = crop_size(pre)
    cmd = ["ffmpeg", "-v", "info", "-ss", f"{s:.3f}", "-t", f"{e_ - s:.3f}", "-i",
           os.path.join(FEL, clip), "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    r = subprocess.run(cmd, capture_output=True)
    arr = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w, 3)
    times = np.array([float(x) for x in re.findall(rb"pts_time:([0-9.]+)", r.stderr)][:len(arr)])
    if len(times) < len(arr):                      # pad missing timestamps
        dtc = np.median(np.diff(times)) if len(times) > 2 else 1 / 60
        last = times[-1] if len(times) else 0.0
        times = np.concatenate([times, last + dtc * np.arange(1, len(arr) - len(times) + 1)])
    small = np.stack([cv2.resize(cv2.cvtColor(x, cv2.COLOR_RGB2GRAY), (96, 96), interpolation=cv2.INTER_AREA)
                      for x in arr]).astype(np.float32)
    diff = np.abs(np.diff(small, axis=0)).mean(axis=(1, 2))
    keep = [0] + [k + 1 for k, dv in enumerate(diff) if dv > 0.18]
    uniq, ut = arr[keep], times[keep]
    dt = np.median(np.diff(ut)) if len(ut) > 3 else 1 / 30
    rate = int(RATES[np.argmin(np.abs(RATES - 1 / max(dt, 1e-3)))])
    speed = {60: 1.0, 50: 0.6 if sh.tag == "intro" else 1.2, 30: 1.0, 25: 25 / 30, 24: 24 / 30}[rate]
    cache[i] = dict(frames=uniq, times=ut, size=w, off=sh.src - s, speed=speed, rate=rate)
    return cache[i]

def src_img(i, f):
    d = load(i)
    if shots[i].tag == "intro":
        target = d["off"] + (intro_src(f) - shots[i].src)
    else:
        target = d["off"] + (f - shots[i].f0) / FPS * d["speed"]
    k = int(np.searchsorted(d["times"], target))
    if k > 0 and (k >= len(d["times"]) or abs(d["times"][k - 1] - target) <= abs(d["times"][k] - target)):
        k -= 1
    return d["frames"][min(max(k, 0), len(d["frames"]) - 1)]

# ------------------------------------------------------------------ zoom model
def Z(i, f):
    sh = shots[i]
    return CURVE[min(max(f, sh.f0), sh.f1 - 1)][0]

def ANG(i, f):
    sh = shots[i]
    return CURVE[min(max(f, sh.f0), sh.f1 - 1)][1]

def warp(img, size, scale, dx=0.0, dy=0.0, interp=cv2.INTER_LANCZOS4, ang=0.0):
    sc = W / size * scale
    cs, co = (size - 1) / 2.0, (W - 1) / 2.0
    t = math.radians(ang)
    a, b = sc * math.cos(t), -sc * math.sin(t)
    c, d = sc * math.sin(t), sc * math.cos(t)
    M = np.array([[a, b, co + dx - (a * cs + b * cs)], [c, d, co + dy - (c * cs + d * cs)]], np.float32)
    return cv2.warpAffine(img, M, (W, W), flags=interp, borderMode=cv2.BORDER_REFLECT_101).astype(np.float32)

def dir_blur(img, L, d):
    n = int(L * W)
    if n < 3:
        return img
    if d == "v":
        return cv2.blur(img, (1, n))
    if d == "h":
        return cv2.blur(img, (n, 1))
    c = (W / 2, W / 2)
    r = cv2.warpAffine(img, cv2.getRotationMatrix2D(c, 45, 1.0), (W, W), borderMode=cv2.BORDER_REFLECT_101)
    r = cv2.blur(r, (n, 1))
    return cv2.warpAffine(r, cv2.getRotationMatrix2D(c, -45, 1.0), (W, W), borderMode=cv2.BORDER_REFLECT_101)

def gray(img, contrast=1.3):
    g = img[..., 0] * 0.2126 + img[..., 1] * 0.7152 + img[..., 2] * 0.0722
    return np.repeat(((g - 128) * contrast + 128)[..., None], 3, axis=2)

def glow(img, amt):
    return img + amt * cv2.GaussianBlur(np.clip(img - 150, 0, None), (0, 0), 18)

YY, XX = np.mgrid[0:W, 0:W].astype(np.float32)
RR = np.sqrt((XX - (W - 1) / 2) ** 2 + (YY - (W - 1) / 2) ** 2)
VIG = (1.0 - 0.22 * np.clip((RR / (W * 0.72)) ** 2.2, 0, 1))[..., None].astype(np.float32)
LEAK = np.exp(-(((XX - W * 0.92) ** 2 + (YY - W * 0.12) ** 2) / (2 * (W * 0.32) ** 2)))[..., None] * np.array([255, 170, 110], np.float32)

def smooth(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

def shot_of(f):
    return max(k for k in range(len(shots)) if shots[k].f0 <= f)

def render(f):
    i = shot_of(f)
    sh = shots[i]
    sp = SPEC.get(f, {})
    d = load(i)
    img_src = src_img(i, f)
    z = Z(i, f); a0 = ANG(i, f)
    sx0, sy0 = SHIFT.get(f, (0.0, 0.0))
    n_sh = sh.f1 - sh.f0
    if f == sh.f0:
        v = math.log(Z(i, f + 1) / z) if n_sh > 1 else 0.0
        w = ANG(i, f + 1) - a0 if n_sh > 1 else 0.0
    elif f == sh.f1 - 1:
        v = math.log(z / Z(i, f - 1)); w = a0 - ANG(i, f - 1)
    else:
        v = math.log(Z(i, f + 1) / Z(i, f - 1)) / 2; w = (ANG(i, f + 1) - ANG(i, f - 1)) / 2
    if sh.tag == "intro" and any(f in (g0, g0 - 1) for g0, *_ in INTRO_SEG):
        v = 0.0; w = 0.0
    heavy = abs(v) > 0.05 or sp.get("L", 0) >= 0.1 or sp.get("sig", 0) >= 1.5 or "cin" in sp or "cout" in sp
    shutter = 1.0 if heavy else 0.5                      # 180 deg shutter normally, full only in heavy transition frames
    sv, sw = v * shutter, w * shutter
    amount = abs(sv) + abs(math.radians(sw))
    if amount > 0.008:                                   # motion blur that follows the zoom / rotation
        K = int(min(14, max(4, amount * 150)))
        acc = np.zeros((W, W, 3), np.float32)
        for j in range(K):
            u = (j + 0.5) / K - 0.5
            acc += warp(img_src, d["size"], max(1.0, z * math.exp(sv * u)), dx=sx0, dy=sy0, interp=cv2.INTER_LINEAR, ang=a0 + sw * u)
        img = acc / K
        if f in SHAKE_AMP:
            img = shake(img, f)
    else:
        img = warp(img_src, d["size"], z, dx=sx0, dy=sy0, ang=a0)
    if f in SHAKE_AMP:
        img = shake(img, f)
    if sp.get("L"):
        img = dir_blur(img, sp["L"], sp.get("d", "v"))
    if sp.get("sig"):
        img = cv2.GaussianBlur(img, (0, 0), sp["sig"])
    if sp.get("echo"):
        ghost = warp(img_src, d["size"], z * 1.18, dx=-0.10 * W, dy=-0.03 * W, interp=cv2.INTER_LINEAR, ang=a0)
        img = img * (1 - sp["echo"]) + ghost * sp["echo"]
    if "mul" in sp:
        img = img * sp["mul"]
    if sp.get("expo"):
        img = img * sp["expo"]
    if sp.get("glow"):
        img = glow(img, sp["glow"])
    if sp.get("leak"):
        img = img + LEAK * sp["leak"]
    if sp.get("vig"):
        img = img * (1 - sp["vig"] * np.clip((RR / (W * 0.72)) ** 1.5, 0, 1))[..., None]
    if "cout" in sp:
        img = img * (1 - np.clip((sp["cout"] * W - RR) + 0.5, 0, 1)[..., None])
    if "cin" in sp:
        img = img * np.clip((sp["cin"] * W - RR) + 0.5, 0, 1)[..., None]
    if sh.tag == "intro":
        if f in FLICKER:
            img = gray(img, 1.3)
        if f in FLARE:                          # white light flash on the left edge (reference 3.69 s)
            edge = np.exp(-XX / (W * 0.09))[..., None]
            img = img + 255 * FLARE[f] * edge
    if sh.grade == "pink" and sh.tag in ("p1_12", "p2_12"):
        s = 0.55 * smooth((f - sh.f0 - 4) / 8)
        img = img * (1 - s) + gray(img, 1.15) * s
    if f >= 543:
        k = smooth((f - 543) / 14)
        img = cv2.GaussianBlur(img, (0, 0), 0.1 + 6 * k) * (1 - k)
    img = cc(img, detail=0.30, clarity=0.22)
    if sh.tag == "intro" and f in SATK:
        lum = (img[..., 0] * 0.2126 + img[..., 1] * 0.7152 + img[..., 2] * 0.0722)[..., None]
        img = lum + (img - lum) * SATK[f]
    if sh.grade == "teal":
        ring = None
        if "cout" in sp:
            ring = np.clip((sp["cout"] * W - RR) + 0.5, 0, 1)[..., None]
        img = teal_look(img)
        if "vig" in sp or "mul" in sp:
            img = img * sp.get("mul", 1.0) * (1 - sp.get("vig", 0) * np.clip((RR / (W * 0.72)) ** 1.5, 0, 1))[..., None]
        if ring is not None:
            img = img * (1 - ring)
    img = img * VIG
    return np.clip(img, 0, 255).astype(np.uint8)

if __name__ == "__main__":
    os.makedirs(OUTDIR, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "frames":
        for f in map(int, sys.argv[2:]):
            cv2.imwrite(os.path.join(OUTDIR, f"preview_{f:03d}.png"), cv2.cvtColor(render(f), cv2.COLOR_RGB2BGR))
        for i in sorted(cache):
            print("shot", i, shots[i].scene, "rate", cache[i]["rate"], "speed", round(cache[i]["speed"], 2), "uniq", len(cache[i]["frames"]))
        sys.exit(0)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{W}", "-r", str(FPS), "-i", "-",
         "-ss", "0", "-t", f"{NF / FPS}", "-i", EXAMPLE, "-map", "0:v", "-map", "1:a",
         "-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=lanczos,format=yuv420p,unsharp=5:5:0.15:5:5:0.0",
         "-c:v", "libx264", "-preset", "slow", "-tune", "film", "-crf", "15", "-profile:v", "high", "-level", "4.1",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
         "-af", f"afade=t=out:st={NF / FPS - 0.5}:d=0.5", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
         "-t", f"{NF / FPS}", OUT], stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(NF):
        i = shot_of(f)
        for k in list(cache):
            if k < i:
                del cache[k]
        enc.stdin.write(render(f).tobytes())
        if f % 60 == 0:
            print(f"frame {f}/{NF} shot {i} {time.time() - t0:.0f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    print("done", OUT, round(time.time() - t0))
