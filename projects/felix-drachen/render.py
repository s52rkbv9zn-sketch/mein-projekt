#!/usr/bin/env python3
"""Felix-Edit nach Referenz 6 ("Drachen"-Edit, 1024x576 Querformat, 29,6 s Edit + TikTok-Abspann).

Vorbild Bild fuer Bild zerlegt (docs/effekte-katalog.md, Referenz 6): 27 Szenen, ruhige Musik
(kaum Schlaege, Schnitte folgen der Melodie -> Schnittbilder 1:1 uebernommen).
Uebergaenge: Wisch mit Spiegelrand, Zoom-Unschaerfe, Kaleidoskop, Glitch-Streifen, weiches Scharfwerden,
Zoom-Stoss mit Aufhellen. Kamera: Zoom und Drehung je Bild aus dem Vorbild (ECC, gedaempft, begrenzt),
Bewegungsunschaerfe passend zur Geschwindigkeit. Farben jeder Szene an die Vorbild-Szene angeglichen.
Ton: Tonspur des Vorbilds bis 29,6 s (danach kommt im Vorbild der TikTok-Abspann mit eigenem Ton),
auf -14 LUFS angehoben (Vorbild-Musik nur -25,5 LUFS), am Ende 0,6 s ausgeblendet.

Aufruf:  python3 render.py | python3 render.py frames 100 200 | python3 render.py vergleich name.jpg 18 22 146
         python3 render.py shots
"""
import json, math, os, re, subprocess, sys, time
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLKIT = os.path.join(HERE, "..", "..", "edit-toolkit")
FELIX = os.path.join(HERE, "..", "felix-sorinyx")
sys.path.insert(0, TOOLKIT)
sys.path.insert(0, FELIX)
from scenes import SCENES, BASE
from face_track import FaceTracker, track, smooth_track
from slowmo import resample
from dedupe import unique_indices
from look import cc

MEDIA = os.environ.get("EDIT_MEDIA", os.path.join(FELIX, "media"))
REF = os.environ.get("REF6", os.path.join(MEDIA, "reference_drachen.mp4"))
OUTDIR = os.environ.get("EDIT_OUT", os.path.join(HERE, "out"))
OUT = os.path.join(OUTDIR, "Felix_Drachen_Edit_v1.mp4")
W, H, FPS = 1920, 1080, 30
ASPECT = W / H
K = W / 1024.0                   # Pixelwerte wurden bei 1024 px Breite gemessen
NF = 888                         # Edit-Ende (ab 888 TikTok-Abspann im Vorbild)
SPEED = 0.5

CUTS = [0, 22, 45, 66, 118, 146, 172, 215, 247, 269, 322, 353, 375, 430, 481, 537, 565, 589, 649, 670,
        692, 750, 775, 797, 821, 840, 868]
# Felix-Szene je Vorbild-Szene: face = (Gesicht senkrecht, Gesichtshoehe) als Anteil der Bildhoehe
PLAN = [
    dict(scene="floor",     t=11.00, face=(0.42, 0.36)),  # 1  dunkelblau, Nahaufnahme
    dict(scene="stg_flip",  t=3.30,  face=(0.40, 0.28)),  # 2  Drehung im Flug -> Haare werfen
    dict(scene="suit",      t=3.30,  face=(0.30, 0.22)),  # 3  helle Wolke, weit
    dict(scene="shoot_sit", t=2.00,  face=(0.40, 0.30)),  # 4  zusammen fliegen, hell -> Fotoshooting, Armbewegung
    dict(scene="coffee",    t=6.00,  face=(0.42, 0.42)),  # 5  Profil, hell
    dict(scene="pink_face", t=5.00,  face=(0.42, 0.44)),  # 6  Gesicht an Gesicht -> Nahaufnahme
    dict(scene="suit",      t=0.55,  face=(0.30, 0.24)),  # 7  heller Himmel, weit
    dict(scene="micsmile",  t=2.30,  face=(0.42, 0.42)),  # 8  laechelt, tuerkis-dunkel
    dict(scene="stg_green", t=1.70,  face=(0.40, 0.28)),  # 9  dunkles Tuerkis mit Lichtstreifen
    dict(scene="red_hair",  t=4.10,  face=(0.42, 0.38)),  # 10 starrt in die Kamera, dunkel
    dict(scene="red_laugh", t=8.00,  face=(0.42, 0.40)),  # 11 lacht, rosa-blaues Licht
    dict(scene="furwide",   t=0.30,  face=(0.40, 0.30)),  # 12 hell-rosa
    dict(scene="fur",       t=4.00,  face=(0.42, 0.40)),  # 13 kuscheln, rosa
    dict(scene="pink_room", t=9.00,  face=(0.40, 0.32)),  # 14 rosa-lila, Blick nach unten
    dict(scene="brick",     t=13.30, face=(0.42, 0.44)),  # 15 laechelt, Augen zu, hell
    dict(scene="stg_red",   t=6.10,  face=(0.40, 0.30)),  # 16 fliegt auf die Kamera zu -> Peace
    dict(scene="selfie",    t=4.10,  face=(0.42, 0.42)),  # 17 suess, dunkler Hintergrund
    dict(scene="eat",       t=2.00,  face=(0.40, 0.26)),  # 18 malt in den Sand -> isst
    dict(scene="bear",      t=1.20,  face=(0.32, 0.30)),  # 19 laechelt am Strand
    dict(scene="pink_up",   t=13.00, face=(0.42, 0.40)),  # 20 Profil
    dict(scene="tank",      t=13.60, face=(0.45, 0.56)),  # 21 Augen ganz nah
    dict(scene="claws",     t=0.40,  face=(0.45, 0.50)),  # 22 Augen ganz nah, dunkel
    dict(scene="red_shy",   t=6.40,  face=(0.42, 0.40)),  # 23 laechelt nachts, blau
    dict(scene="pink_kiss", t=8.00,  face=(0.42, 0.40)),  # 24 Blick in die Kamera, blau (Kussmund)
    dict(scene="shoot_red", t=6.50,  face=(0.40, 0.34)),  # 25 Profil, grau
    dict(scene="shoot_sit", t=4.60,  face=(0.40, 0.30)),  # 26 hell, grau-blau
    dict(scene="floor",     t=12.30, face=(0.42, 0.34)),  # 27 dunkelblau wie am Anfang
]
# sichere Bereiche (ohne Logos, Untertitel, Player-Leisten, schwarze Raender), nach Videobereich + Drehung
SAFE = {
    "clip2.mov": (220, 80, 1950, 1000), "clip3.mov": (520, 0, 2096, 1180), "clip4.mov": (0, 0, 2096, 900),
    "clip5.mov": (0, 80, 1180, 1950), "clip6.mov": (290, 0, 2096, 1080), "clip7.mov": (290, 0, 2096, 1180),
    "clip9.mov": (0, 0, 2096, 960), "clip10.mov": (0, 0, 2096, 1180), "clip12.mov": (0, 0, 2096, 1000),
    "clip13.mov": (0, 0, 2096, 1020),
}
SAFE_SCENE = {"selfie": (150, 0, 1945, 1180), "tank": (190, 0, 1700, 930), "floor": (0, 0, 2096, 1085),
              "claws": (0, 0, 2096, 1180)}
PATCHES = {"clip5.mov": [(64, 926, 162, 1170)]}
MIN_CH = 560                     # kleinster Ausschnitt (Hoehe) -> hoechstens ~1,9x hochskalieren

# ------------------------------------------------------------------ Uebergaenge je Bild (am Vorbild gemessen)
# Arten: hb/vb = Wisch-Unschaerfe (Anteil Breite/Hoehe), sig = Gauss (px bei 1024), zb = Zoom-Unschaerfe (log-Umfang)
#        -> die Staerken gleicht calibrate.py Bild fuer Bild an die Schaerfe des Vorbilds an (fx_cal.json)
#        ring = Ring-Bokeh (helle Details werden zu duennen Ringen), st = Strecken (x0, Faktor, gespiegelt),
#        bend = Woelbung (A, senkrechte Streckung), hg = Sanduhr (m0, m1), glitch, zoom, gain, white
FX = {}


def _fx(frames, **kw):
    for f in frames:
        FX.setdefault(f, {}).update(kw)


for f, z, g in [(18, 1.12, 1.35), (19, 1.10, 1.30), (20, 1.08, 1.22), (21, 1.06, 1.15)]:
    _fx([f], zoom=z, gain=g)                                   # Zoom-Stoss + Aufhellen vor dem Schnitt
for f, r in zip(range(66, 71), (.9, .8, .6, .35, 0)):
    _fx([f], sig=2.0, **({"ring": r} if r else {}))
_fx(range(115, 118), vb=0.02)
_fx(range(118, 123), sig=1.5)
_fx(range(143, 156), hb=0.02)
_fx(range(169, 172), hb=0.03)
_fx(range(212, 215), vb=0.02)
_fx(range(215, 220), sig=1.0)
_fx(range(244, 247), sig=1.5)
for f, g in zip(range(247, 252), (.6, .8, .9, 1, 1)):
    _fx([f], sig=4, gain=g)
for f, r in zip(range(269, 274), (.9, .8, .6, .4, .2)):
    _fx([f], ring=r)
_fx(range(319, 322), hb=0.03)
_fx([322], vb=0.1, glitch=1.0)
_fx([323, 324], vb=0.05)
_fx([325, 326], sig=2)
for f, r in zip(range(350, 353), (.5, .7, .9)):
    _fx([f], ring=r, sig=1.5)
for f, g in zip(range(353, 358), (1.15, 1.08, 1.04, 1, 1)):
    _fx([f], zb=0.2, gain=g)
_fx([371], st=(0.55, 5, False), hb=0.01)                  # Strecken: Mitte auf Felix (bunte Linien wie im Vorbild)
_fx([372], st=(0.45, 7, False), hb=0.015)
_fx([373], st=(0.45, 8, True), hb=0.02)
_fx([374], st=(0.50, 10, True), hb=0.02)
_fx([375], bend=(0.30, 3.0), gain=0.8, hb=0.02)
for f, bd in zip(range(376, 380), ((.25, 1.6), (.14, 1.25), (.08, 1.1), (.03, 1.0))):
    _fx([f], bend=bd, hb=0.03)
_fx(range(427, 430), zb=0.1)
_fx([430], zb=0.5, gain=0.85)
for f, r in zip(range(431, 434), (.8, .6, .4)):
    _fx([f], zb=0.3, ring=r)
_fx([434], zb=0.1)
for f, r in zip(range(478, 481), (.4, .6, .8)):
    _fx([f], vb=0.02, ring=r)
for f, g in zip(range(481, 486), (1.15, 1.07, 1, 1, 1)):
    _fx([f], vb=0.03, gain=g)
_fx(range(534, 537), zb=0.05)
_fx(range(537, 549), zb=0.2)
_fx(range(562, 565), zb=0.05)
for f, h in zip(range(567, 571), ((0.20, 1.2), (0.15, 0.9), (0.60, 0.45), (0.97, 0.05))):
    _fx([f], hg=h, vb=0.05)
_fx(range(586, 595), hb=0.03)
_fx(range(646, 649), hb=0.05)
for f, r in zip(range(649, 652), (.9, .7, .5)):
    _fx([f], zb=0.3, ring=r, ring_r=16)
_fx(range(652, 655), zb=0.2)
_fx(range(667, 670), hb=0.05)
_fx(range(670, 675), sig=4)
_fx(range(689, 697), sig=3)
_fx(range(747, 755), sig=3)
_fx([750], gain=0.9)
_fx(range(772, 780), sig=4)
for f, r in zip(range(794, 797), (.5, .7, .9)):
    _fx([f], ring=r, sig=2)
_fx(range(797, 802), sig=3)
_fx(range(818, 821), vb=0.02)
_fx(range(821, 827), sig=8)
for f, r in zip(range(837, 840), (.5, .7, .9)):
    _fx([f], ring=r, sig=2)
_fx(range(840, 845), hb=0.03)
_fx([865, 866], sig=3)
_fx([867], sig=6, white=0.3)
for f, r in zip(range(868, 873), (0, .8, .9, .6, 0)):
    _fx([f], sig=3, **({"ring": r} if r else {}))

BLUR_KEYS = ("hb", "vb", "sig", "zb")
CAL_FILE = os.path.join(HERE, "fx_cal.json")
if os.path.exists(CAL_FILE) and not os.environ.get("NO_CAL"):
    for _k, _v in json.load(open(CAL_FILE)).items():
        FX.setdefault(int(_k), {}).update(_v)

# ------------------------------------------------------------------ Kamera: Zoom + Drehung aus dem Vorbild (gedaempft)
REFP = {int(k): v for k, v in json.load(open(os.path.join(HERE, "ref_camera.json"))).items()}
DAMP_Z, DAMP_R = 0.55, 0.30
ZMAX, RMAX = 1.40, 3.0           # Zoom-Umfang je Szene, Drehung in Grad


def seg_of(f):
    return max(i for i, c in enumerate(CUTS) if c <= f)


def seg_end(i):
    return CUTS[i + 1] if i + 1 < len(CUTS) else NF


def _series(i, idx, damp, lim):
    a, b = CUTS[i], seg_end(i)
    vals = {}
    for f in range(a + 1, b + 2):
        r = REFP.get(f)
        if r and r[4] >= 0.85 and f not in (a, b) and abs(math.log(r[0])) <= 0.25 and abs(r[1]) <= 8:
            vals[f] = (math.log(r[0]) if idx == 0 else r[1]) * damp
    known = sorted(vals)
    seq = []
    for f in range(a + 1, b + 2):
        if f in vals:
            seq.append(vals[f])
        else:
            lo = [k for k in known if k < f]
            hi = [k for k in known if k > f]
            seq.append(vals[lo[-1]] if lo else (vals[hi[0]] if hi else 0.0))
    L = np.concatenate([[0.0], np.cumsum(seq)])
    return {a + k: float(v) for k, v in enumerate(L)}


CAM = []
for _i in range(len(CUTS)):
    lz = _series(_i, 0, DAMP_Z, ZMAX)
    rt = _series(_i, 1, DAMP_R, RMAX)
    fs = sorted(lz)
    z = np.array([lz[f] for f in fs])
    if z.max() - z.min() > math.log(ZMAX):
        z = z * math.log(ZMAX) / (z.max() - z.min())
    z = z - z.min()
    r = np.array([rt[f] for f in fs])
    r = r - r.mean()
    if np.abs(r).max() > RMAX:
        r = r * RMAX / np.abs(r).max()
    CAM.append({f: (float(math.exp(zz)), float(rr)) for f, zz, rr in zip(fs, z, r)})
    CAM[-1][fs[0] - 1] = CAM[-1][fs[0]]
    CAM[-1][fs[0] - 2] = CAM[-1][fs[0]]


def camera(i, f):
    c = CAM[i]
    f = min(max(f, min(c)), max(c))
    return c[f]


# ------------------------------------------------------------------ Quellen, Gesichtsverfolgung
TRACKER = None
cache = {}


def _decode(clip, rot, s, e):
    vf = f"{BASE}," + ("transpose=1," if rot else "") + \
         "hqdn3d=1.6:1.2:2.5:2.5,scale=in_color_matrix=bt709:in_range=tv,format=rgb24,showinfo"
    h, w = (2096, 1180) if rot else (1180, 2096)
    r = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", os.path.join(MEDIA, clip),
                        "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    arr = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w, 3)
    times = np.array([float(x) for x in re.findall(rb"pts_time:([0-9.]+)", r.stderr)])
    n = min(len(arr), len(times))
    arr, times = arr[:n], times[:n]
    keep = unique_indices(arr)
    arr = arr[keep]
    if clip in PATCHES:
        arr = arr.copy()
        for (px0, py0, px1, py1) in PATCHES[clip]:
            mx0, my0, mx1, my1 = max(0, px0 - 60), max(0, py0 - 60), min(w, px1 + 60), min(h, py1 + 60)
            mask = np.zeros((my1 - my0, mx1 - mx0), np.uint8)
            mask[py0 - my0:py1 - my0, px0 - mx0:px1 - mx0] = 255
            for a in arr:
                a[my0:my1, mx0:mx1] = cv2.inpaint(np.ascontiguousarray(a[my0:my1, mx0:mx1]), mask, 9, cv2.INPAINT_TELEA)
    return arr, times[keep] + s


def ts_of(i, f):
    return PLAN[i]["t"] + (f - CUTS[i]) / FPS * SPEED


def load(i):
    global TRACKER
    if i in cache:
        return cache[i]
    p = PLAN[i]
    clip, a, b, pre, _ = SCENES[p["scene"]]
    rot = "transpose=1" in pre
    s = max(a, ts_of(i, CUTS[i] - 4) - 0.10)
    e = min(b, ts_of(i, seg_end(i) + 4) + 0.12)
    frames, times = _decode(clip, rot, s, e)
    src_fps = 1.0 / float(np.median(np.diff(times))) if len(times) > 2 else 60.0
    want = [min(max(ts_of(i, f), float(times[0])), float(times[-1])) for f in range(CUTS[i] - 4, seg_end(i) + 4)]
    n_real = len(frames)
    frames, times = resample(frames, times, want)
    m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", pre)[-1]
    cw0, ch0, cx0, cy0 = map(int, m)
    TRACKER = TRACKER or FaceTracker()
    raw = track(list(frames), hint=(cx0 + cw0 / 2, cy0 + ch0 / 2), tracker=TRACKER)
    fx, fy, fh = smooth_track(times, raw, sigma_s=0.18)
    found = int((~np.isnan(raw[:, 0])).sum())
    x0, y0, x1, y1 = SAFE_SCENE.get(p["scene"], SAFE[clip])
    yf, hf = p["face"]
    ch = float(np.nanmedian(raw[:, 2]) / hf)
    ch_max = min(y1 - y0, (x1 - x0) / ASPECT)
    yf_top, yf_bot = max(0.15, yf - 0.08), min(0.6, yf + 0.08)
    lim = min(np.percentile(2 * np.minimum(fx - x0, x1 - fx), 5) / ASPECT,
              np.percentile((fy - y0) / yf_top, 5), np.percentile((y1 - fy) / (1 - yf_bot), 5))
    ch = float(np.clip(ch, MIN_CH, min(ch_max, max(lim, MIN_CH))))
    cache[i] = dict(frames=frames, times=times, fx=fx, fy=fy, ch=ch, safe=(x0, y0, x1, y1), found=found,
                    total=n_real, fps=src_fps, lab=None)
    return cache[i]


def src_index(i, f):
    d = load(i)
    return int(np.argmin(np.abs(d["times"] - ts_of(i, f))))


def _cover(theta_deg):
    t = math.radians(abs(theta_deg))
    return math.cos(t) + math.sin(t) * max(ASPECT, 1 / ASPECT)


def warp(img, cx, cy, ch, ang, pad=0.0, interp=cv2.INTER_LANCZOS4):
    """Ausschnitt (Mitte cx,cy, Hoehe ch, 16:9) um ang Grad gedreht -> Leinwand (W, H) * (1 + 2 pad)"""
    wc, hc = int(round(W * (1 + 2 * pad))), int(round(H * (1 + 2 * pad)))
    sc = H / ch
    M = cv2.getRotationMatrix2D((cx, cy), -ang, sc)
    M[0, 2] += (wc - 1) / 2 - cx
    M[1, 2] += (hc - 1) / 2 - cy
    return cv2.warpAffine(img, M, (wc, hc), flags=interp, borderMode=cv2.BORDER_REFLECT_101).astype(np.float32)


def geometry(i, f, extra=1.0, sub=0.0):
    """Ausschnitt fuer Bild f (+ Bruchteil sub fuer Bewegungsunschaerfe)"""
    d = load(i)
    p = PLAN[i]
    x0, y0, x1, y1 = d["safe"]
    fa = int(math.floor(f + sub))
    w_ = f + sub - fa
    z0, r0 = camera(i, fa)
    z1, r1 = camera(i, fa + 1)
    z = math.exp(math.log(z0) * (1 - w_) + math.log(z1) * w_) * extra
    ang = r0 * (1 - w_) + r1 * w_
    cov = _cover(ang)
    ch = min(d["ch"] / z, (y1 - y0) / cov, (x1 - x0) / ASPECT / cov)
    cw = ch * ASPECT
    k = src_index(i, f)
    half_w, half_h = cw * cov / 2, ch * cov / 2
    cx = float(np.clip(d["fx"][k], x0 + half_w, x1 - half_w))
    cy = float(np.clip(d["fy"][k] + (0.5 - p["face"][0]) * ch, y0 + half_h, y1 - half_h))
    return k, cx, cy, ch, ang


def cam(i, f, pad=0.0, extra=1.0):
    d = load(i)
    k, cx, cy, ch, ang = geometry(i, f, extra)
    img = d["frames"][k]
    za, ra = camera(i, f - 1)
    zb_, rb = camera(i, f + 1)
    vz = abs(math.log(zb_ / za)) / 2
    vr = abs(rb - ra) / 2
    n = int(min(10, max(1, vz * 120 + vr * 3)))
    if n <= 1:
        return warp(img, cx, cy, ch, ang, pad)
    acc = None
    for j in range(n):
        u = ((j + 0.5) / n - 0.5) * 0.5                            # 180-Grad-Verschluss
        _, cx_, cy_, ch_, ang_ = geometry(i, f, extra, u)
        w_ = warp(img, cx_, cy_, ch_, ang_, pad, interp=cv2.INTER_LINEAR)
        acc = w_ if acc is None else acc + w_
    return acc / n


# ------------------------------------------------------------------ Farben: CC + Angleichung an die Vorbild-Szene
REF_ARR = None
REF_STATS = {}
STRENGTH = np.array([0.65, 0.82, 0.82], np.float32)


def _lab(img):
    return cv2.cvtColor(np.clip(img, 0, 255).astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)


def ref_frames():
    global REF_ARR
    if REF_ARR is None:
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", REF, "-vf", "fps=30:start_time=0", "-frames:v", str(NF),
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        REF_ARR = np.frombuffer(r.stdout, np.uint8).reshape(-1, 576, 1024, 3)
    return REF_ARR


def ref_stats(i):
    if i in REF_STATS:
        return REF_STATS[i]
    ra = ref_frames()
    mask = np.ones((576, 1024), bool)
    mask[:70, :120] = False              # TikTok-Zeichen
    mask[500:, 900:] = False
    mask[480:560, 380:650] = False       # Kennung des Editors
    a, b = CUTS[i] + 3, seg_end(i) - 3
    fs = [f for f in range(a, max(a + 1, b), 2) if f not in FX]
    lab = np.concatenate([_lab(cv2.resize(ra[f], (512, 288)))[mask[::2, ::2]] for f in fs])
    REF_STATS[i] = (lab.mean(0), lab.std(0) + 1e-3)
    return REF_STATS[i]


def base_look(img):
    return cc(img, sat=1.0, clarity=0.12, detail=0.25, bloom=0.05)


def shot_stats(i):
    d = load(i)
    if d["lab"] is None:
        fs = np.linspace(CUTS[i] + 2, seg_end(i) - 2, 5).astype(int)
        lab = np.concatenate([_lab(cv2.resize(base_look(cam(i, f)), (320, 180), interpolation=cv2.INTER_AREA)).reshape(-1, 3)
                              for f in fs])
        d["lab"] = (lab.mean(0), lab.std(0) + 1e-3)
    return d["lab"]


def grade(img, i):
    img = base_look(img)
    ms, ss = shot_stats(i)
    mt, st = ref_stats(i)
    ratio = np.clip(st / ss, 0.5, 1.4)
    lab = _lab(img)
    tgt = (lab - ms) * ratio + mt
    lab = lab + (tgt - lab) * STRENGTH
    return np.clip(cv2.cvtColor(lab.astype(np.float32), cv2.COLOR_LAB2RGB), 0, 1) * 255.0


def finish(img, soften=0.15, glow=0.10):
    x = np.clip(img, 0, 255) / 255.0
    x = x * (1 - soften) + cv2.GaussianBlur(x, (0, 0), 1.4) * soften
    b = cv2.GaussianBlur(np.clip(x - 0.55, 0, None), (0, 0), 20)
    x = 1 - (1 - x) * (1 - glow * 2.2 * b)
    return np.clip(x, 0, 1) * 255.0


# ------------------------------------------------------------------ Effekt-Bausteine
RING_GAIN = 0.85


def center(img):
    hc, wc = img.shape[:2]
    if hc == H and wc == W:
        return img
    oy, ox = (hc - H) // 2, (wc - W) // 2
    return img[oy:oy + H, ox:ox + W]


def hblur(img, L):
    n = int(round(L * W))
    return img if n < 2 else cv2.blur(img, (min(n, 3 * W), 1), borderType=cv2.BORDER_REFLECT)


def vblur(img, L):
    n = int(round(L * H))
    return img if n < 2 else cv2.blur(img, (1, min(n, 3 * H)), borderType=cv2.BORDER_REFLECT)


def zoom_blur(canvas, amount, cy=0.42):
    if amount < 0.01:
        return canvas
    h, w = canvas.shape[:2]
    py = (h - H) / 2 + cy * H
    n = int(min(24, max(5, amount * 40)))
    acc = np.zeros_like(canvas)
    for j in range(n):
        s = math.exp(amount * ((j + 0.5) / n - 0.5))
        M = np.array([[s, 0, (1 - s) * (w - 1) / 2], [0, s, (1 - s) * py]], np.float32)
        acc += cv2.warpAffine(canvas, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return acc / n


_RING_KER = {}


def ring_layer(img, strength, radius=12.0, face=None):
    """Ring-Bokeh (Vorbild 66-69, 269-273, 350-352, 431-433, 478-480, 649-651, 794-796, 837-839, 869-871):
    an hellen Detail-Spitzen erscheinen einzelne duenne Ringe (Radius ~12 px bei 1024) mit Rot/Blau-Saum,
    in Ketten entlang heller Kanten. Das Gesicht wird geschont (face = (Hoehe, Groesse) als Anteil)."""
    r = radius * K
    key = round(r, 2)
    if key not in _RING_KER:
        t = max(1.8, 0.20 * r)
        n = int(math.ceil(r + 2 * t))
        yy, xx = np.mgrid[-n:n + 1, -n:n + 1].astype(np.float32)
        d = np.sqrt(xx * xx + yy * yy)
        _RING_KER[key] = (np.exp(-0.5 * ((d - r) / (t / 2)) ** 2).astype(np.float32), n)
    spr, n = _RING_KER[key]
    x = np.clip(img, 0, 255) / 255.0
    q = 4
    sm = cv2.resize(x, (W // q, H // q), interpolation=cv2.INTER_AREA)
    lum = sm[..., 0] * 0.2126 + sm[..., 1] * 0.7152 + sm[..., 2] * 0.0722
    det = np.clip(lum - cv2.GaussianBlur(lum, (0, 0), 3), 0, None) * np.clip((lum - 0.2) / 0.3, 0, 1)
    if face is not None:
        fy, fh = face
        yy, xx = np.mgrid[0:H // q, 0:W // q].astype(np.float32)
        e = ((xx - W / (2 * q)) / (0.8 * fh * H / q)) ** 2 + ((yy - fy * H / q) / (0.95 * fh * H / q)) ** 2
        det = det * (1 - 0.92 * np.exp(-e))
    sp = max(2, int(round(0.75 * r / q)))
    dil = cv2.dilate(det, np.ones((2 * sp + 1, 2 * sp + 1), np.uint8))
    ys, xs = np.where((det >= dil) & (det > 0.012))
    ring = np.zeros((H + 2 * n, W + 2 * n, 3), np.float32)
    if len(ys):
        v = det[ys, xs]
        order = np.argsort(-v)[: int(30 + 110 * strength)]
        vmax = float(np.percentile(v[order], 85)) + 1e-6
        for k_ in order:
            cy, cx = int(ys[k_] * q + q // 2) + n, int(xs[k_] * q + q // 2) + n
            col = 0.4 + 0.6 * sm[ys[k_], xs[k_]]
            ring[cy - n:cy + n + 1, cx - n:cx + n + 1] += spr[..., None] * col[None, None, :] * min(1.0, v[k_] / vmax)
    ring = ring[n:n + H, n:n + W]
    sh = 1.3 * K
    ring[..., 0] = cv2.warpAffine(ring[..., 0], np.float32([[1, 0, sh], [0, 1, 0]]), (W, H), borderMode=cv2.BORDER_REFLECT)
    ring[..., 2] = cv2.warpAffine(ring[..., 2], np.float32([[1, 0, -sh], [0, 1, 0]]), (W, H), borderMode=cv2.BORDER_REFLECT)
    return np.clip(ring * strength * RING_GAIN, 0, 1)


def stretch(img, x0, s, mirror):
    """waagerecht strecken ab x0 (Vorbild 371-374); gespiegelt -> V-Form um x0"""
    xs = np.arange(W, dtype=np.float32)
    X0 = x0 * W
    src = X0 + np.abs(xs - X0) / s if mirror else np.where(xs < X0, xs, X0 + (xs - X0) / s)
    mapx = np.repeat(src[None, :].astype(np.float32), H, axis=0)
    mapy = np.repeat(np.arange(H, dtype=np.float32)[:, None], W, axis=1)
    return cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def bend(img, A, vs):
    """Woelbung: Mitte nach unten gebogen, senkrecht gestreckt (Vorbild 375-379)"""
    u = np.linspace(-1, 1, W, dtype=np.float32)
    off = A * H * (1 - u * u)
    yy = np.arange(H, dtype=np.float32)[:, None]
    mapy = (H / 2 + (yy - H / 2 - off[None, :]) / vs).astype(np.float32)
    mapx = np.repeat(np.arange(W, dtype=np.float32)[None, :], H, axis=0)
    return cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def hourglass(img, m0, m1):
    """Sanduhr: in der Mitte schmal zusammengedrueckt, oben/unten breit, Seiten schwarz (Vorbild 567-570)"""
    yy = np.linspace(-1, 1, H, dtype=np.float32)[:, None]
    m = m0 + m1 * np.abs(yy)
    xs = np.arange(W, dtype=np.float32)[None, :]
    mapx = (W / 2 + (xs - W / 2) / m).astype(np.float32)
    mapy = np.repeat(np.arange(H, dtype=np.float32)[:, None], W, axis=1)
    return cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def glitch(img, k):
    """senkrechte Streifen: Spalten in Bloecken versetzt (322)"""
    if k <= 0:
        return img
    rng = np.random.default_rng(322)
    out = img.copy()
    x = 0
    while x < W:
        w_ = int(rng.integers(40, 180))
        sh = int(rng.integers(-60, 60) * k)
        out[:, x:x + w_] = np.roll(img[:, x:x + w_], sh, axis=0)
        x += w_
    return out


def canvas(i, f, spec):
    pad = 0.18 if spec.get("zb", 0) > 0.01 else 0.0
    return grade(cam(i, f, pad=pad, extra=spec.get("zoom", 1.0)), i)


def apply_fx(img, i, spec):
    rings = (ring_layer(center(img), spec["ring"], spec.get("ring_r", 12.0), PLAN[i]["face"])
             if spec.get("ring") else None)
    if spec.get("zb", 0) > 0.01 and img.shape[0] > H:
        img = zoom_blur(img, spec["zb"], PLAN[i]["face"][0])
    img = center(img)
    if spec.get("st"):
        img = stretch(img, *spec["st"])
    if spec.get("bend"):
        img = bend(img, *spec["bend"])
    if spec.get("hg"):
        img = hourglass(img, *spec["hg"])
    if spec.get("hb"):
        img = hblur(img, spec["hb"])
    if spec.get("vb"):
        img = vblur(img, spec["vb"])
    if spec.get("glitch"):
        img = glitch(img, spec["glitch"])
    if spec.get("sig", 0) > 0.3:
        img = cv2.GaussianBlur(img, (0, 0), spec["sig"] * K)
    if rings is not None:
        img = 255.0 * (1 - (1 - np.clip(img / 255.0, 0, 1)) * (1 - rings))
    img = img * spec.get("gain", 1.0)
    if spec.get("white"):
        img = img * (1 - spec["white"]) + 255.0 * spec["white"]
    return img


def layer(i, f, spec):
    return apply_fx(canvas(i, f, spec), i, spec)


def render(f):
    i = seg_of(f)
    img = layer(i, f, FX.get(f, {}))
    img = finish(img)
    if f >= NF - 6:                                               # weich ins Schwarze am Ende
        img = img * (NF - f) / 7.0
    return np.clip(img, 0, 255).astype(np.uint8)


def release(f):
    i = seg_of(f)
    for k in list(cache):
        if k < i:
            del cache[k]


def compare(frames, name):
    ra = ref_frames()
    cols = []
    for f in frames:
        r = cv2.resize(ra[min(f, len(ra) - 1)], (384, 216), interpolation=cv2.INTER_AREA)
        e = cv2.resize(render(f), (384, 216), interpolation=cv2.INTER_AREA)
        t = cv2.cvtColor(np.vstack([r, e]), cv2.COLOR_RGB2BGR)
        cv2.putText(t, str(f), (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(t, str(f), (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cols.append(t)
    rows = [np.hstack(cols[k:k + 6]) for k in range(0, len(cols), 6)]
    wmax = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, wmax - r.shape[1]), (0, 0))) for r in rows]
    cv2.imwrite(os.path.join(OUTDIR, name), np.vstack(rows))


if __name__ == "__main__":
    os.makedirs(OUTDIR, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "frames":
        for f in map(int, sys.argv[2:]):
            cv2.imwrite(os.path.join(OUTDIR, f"preview_{f:03d}.png"), cv2.cvtColor(render(f), cv2.COLOR_RGB2BGR))
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "vergleich":
        compare([int(x) for x in sys.argv[3:]], sys.argv[2])
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "shots":
        for i, p in enumerate(PLAN):
            d = load(i)
            zs = [camera(i, f)[0] for f in range(CUTS[i], seg_end(i))]
            rs = [camera(i, f)[1] for f in range(CUTS[i], seg_end(i))]
            print(f"{i + 1:2d} {p['scene']:10s} t={p['t']:5.2f} Gesicht {d['found']}/{len(d['frames'])} "
                  f"Ausschnitt {d['ch']:.0f}px (x{H / d['ch']:.2f}) {d['fps']:.0f}fps  Zoom {min(zs):.2f}-{max(zs):.2f} "
                  f"Drehung {min(rs):+.1f}..{max(rs):+.1f}")
            del cache[i]
        sys.exit(0)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", REF, "-map", "0:v", "-map", "1:a",
         "-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=lanczos,format=yuv420p",
         "-c:v", "libx264", "-preset", "slow", "-tune", "film", "-crf", "16", "-profile:v", "high", "-level", "4.2",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
         "-af", f"atrim=0:{NF / FPS - 0.05:.3f},loudnorm=I=-14:TP=-1.5:LRA=11,"
                f"afade=t=out:st={NF / FPS - 0.65:.3f}:d=0.6",
         "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-t", f"{NF / FPS:.3f}", OUT], stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(NF):
        release(f)
        enc.stdin.write(render(f).tobytes())
        if f % 60 == 0:
            print(f"Bild {f}/{NF} {time.time() - t0:.0f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    print("fertig", OUT, round(time.time() - t0))
