#!/usr/bin/env python3
"""Felix-Edit nach Referenz 5 ("Anzug"-Edit, 576x768 Hochformat, 14 s, ca. 99 BPM).

Aufbau wie im Vorbild (Bild fuer Bild gemessen, Katalog: docs/effekte-katalog.md, Referenz 5):
  0-103    Intro: EIN ruhiger Clip in Zeitlupe, ruhige Kamera; am Ende seitlicher Wisch (101-103)
  104-251  Hauptteil, 6 Szenen:
             S1 104  Wisch herein, Weissblitz 115, Unschaerfe-Blitz 123
             S2 124  Zoom-Stoss, geteiltes Bild 140/141
             S3 140  Farbe/Schwarz-Weiss im Takt (153 S/W, 164 Farbe, 171 S/W), Negativ-Kaestchen 165,
                     senkrechter Wisch 176-179
             S4 178  heller Wisch 196/197
             S5 196  weisser Schiebe-Balken 214/215
             S6 215  langes Scharfwerden, S/W 226, Farbe 237, Negativ-Augenbalken 241, S/W 245, Wisch 250/251
  252-399  Hauptteil noch einmal (dieselben Bilder, wie im Vorbild)
  400-419  schwarz
Aufruf:  python3 render.py   |   python3 render.py frames 104 140 214   |   python3 render.py vergleich 101 104 123
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
from slowmo import double_rate
from dedupe import unique_indices
from look import cc

MEDIA = os.environ.get("EDIT_MEDIA", os.path.join(FELIX, "media"))
REF = os.environ.get("REF5", os.path.join(MEDIA, "reference_anzug.mov"))
OUTDIR = os.environ.get("EDIT_OUT", os.path.join(HERE, "out"))
OUT = os.path.join(OUTDIR, "Felix_Anzug_Edit_v2.mp4")
W, H, FPS = 1080, 1440, 30
ASPECT = W / H
K = W / 576.0                    # Pixelwerte wurden bei 576 px Breite gemessen
NF, END = 420, 400
REP_A, REP_B = 104, 252          # Bilder 252-399 = Bilder 104-251
SPEED = 0.5                      # Zeitlupe wie im Vorbild

# Szenen (erste Haelfte). ref = Bildbereich der Vorbild-Szene fuer Farbe und Gesichtsgroesse
PLAN = [
    dict(name="intro", f0=0,   f1=104, scene="suit",      t=2.40,  ref=(2, 99),   face=(0.30, 0.144)),
    dict(name="S1",    f0=104, f1=124, scene="brick",     t=15.42, ref=(107, 122), face=(0.44, 0.405)),
    dict(name="S2",    f0=124, f1=140, scene="bear",      t=0.35,  ref=(126, 139), face=(0.29, 0.224)),
    dict(name="S3",    f0=140, f1=178, scene="micsmile",  t=2.30,  ref=(143, 175), face=(0.34, 0.300)),
    dict(name="S4",    f0=178, f1=196, scene="brick",     t=12.20, ref=(183, 195), face=(0.35, 0.369)),
    dict(name="S5",    f0=196, f1=215, scene="red_hair",  t=5.30,  ref=(199, 213), face=(0.32, 0.226)),
    dict(name="S6",    f0=215, f1=252, scene="shoot_red", t=5.80,  ref=(218, 249), face=(0.32, 0.260)),
]
FRAME_WIDER = 0.85               # etwas weiter als im Vorbild -> weniger Hochskalieren
ZMAX = 1.32                      # groesster Zoom-Umfang je Szene (Qualitaet; Quellen sind enger gefilmt als das Vorbild)

# sichere Bereiche (ohne Logos, Untertitel, Player-Leisten), Koordinaten nach Videobereich + Drehung
SAFE = {
    "clip3.mov": (520, 0, 2096, 1180),         # "Dispatch"-Logo oben links
    "clip10.mov": (0, 0, 2096, 1180),
    "clip2.mov": (220, 80, 1950, 1000),        # Baerenmuetze: Leisten oben/unten weg
    "clip5.mov": (0, 80, 1180, 1950),
    "clip13.mov": (190, 0, 1700, 930),         # schwarze Raender, Fortschrittsbalken + "+10" des Players
    "clip12.mov": (150, 0, 1945, 1180),        # schwarze Raender links/rechts
    "clip7.mov": (290, 0, 2096, 1180),         # "zoom"-Logo oben links
}
PATCHES = {"clip5.mov": [(64, 926, 162, 1170)]}     # ">> She"-Einblendung, wird weggerechnet

# ------------------------------------------------------------------ Effekte je Bild (erste Haelfte, Werte gemessen)
# hb/vb: Wisch-Unschaerfe (Laenge x Breite/Hoehe), db: (Laenge, Winkel), zb: Zoom-Unschaerfe (log-Umfang),
# sig: Gauss (px bei 576), dx/dy: Versatz (Anteil), gain: Helligkeit, white: Weiss-Anteil, bw: Schwarz-Weiss
FX = {
    101: dict(hb=0.024, dx=0.014),
    102: dict(hb=0.20, dx=0.098),
    103: dict(hb=0.85, dx=0.143, wrap=True),
    104: dict(hb=1.4, dy=-0.064, gain=0.97, wrap=True),
    105: dict(hb=0.71, dx=-0.154, dy=-0.054, wrap=True),
    106: dict(hb=0.135, dx=0.011, dy=-0.036),
    107: dict(hb=0.03),
    115: dict(flash=True),
    123: dict(sig=60, gain=1.13),
    124: dict(sig=13.7),
    125: dict(sig=7.3),
    126: dict(sig=3.0),
    127: dict(sig=1.2),
    138: dict(zb=0.06),
    139: dict(zb=0.14),
    142: dict(zb=0.30, gain=1.14),
    143: dict(zb=0.18, gain=1.10),
    144: dict(zb=0.10, gain=1.03),
    145: dict(zb=0.04),
    151: dict(zb=0.02),
    152: dict(zb=0.21),
    153: dict(zb=0.18),
    154: dict(zb=0.08),
    155: dict(zb=0.03),
    162: dict(zb=0.03),
    163: dict(zb=0.15),
    164: dict(zb=0.30),
    165: dict(zb=0.22, inv=(0.170, 0.293, 0.339, 0.670)),
    166: dict(zb=0.07),
    169: dict(zb=0.06),
    170: dict(zb=0.18),
    171: dict(zb=0.30),
    172: dict(zb=0.10),
    173: dict(zb=0.03),
    176: dict(vb=0.153, dy=0.046),
    177: dict(vb=1.5, gain=1.06),
    178: dict(vb=1.1, gain=1.45),
    179: dict(vb=0.8, gain=1.2),
    180: dict(vb=0.35, gain=1.13),
    181: dict(vb=0.22, zb=0.06, gain=1.10),
    182: dict(vb=0.10, sig=2.0, gain=1.06),
    183: dict(sig=1.0, gain=1.03),
    196: dict(db=(1.6, 24), dx=0.12, gain=1.10, white=0.18),
    197: dict(db=(1.4, 24), dx=-0.10, white=0.55),
    198: dict(db=(0.05, 24)),
    212: dict(zb=0.04),
    213: dict(zb=0.10),
    216: dict(sig=24, hb=0.10),
    217: dict(sig=19, hb=0.06),
    218: dict(sig=15),
    219: dict(sig=12),
    220: dict(sig=8.5),
    221: dict(sig=8.0),
    222: dict(sig=5.5),
    223: dict(sig=3.0),
    224: dict(sig=1.5),
    225: dict(zb=0.02),
    226: dict(zb=0.22),
    227: dict(zb=0.08),
    228: dict(zb=0.03),
    237: dict(zb=0.30),
    238: dict(zb=0.25),
    239: dict(zb=0.15),
    240: dict(zb=0.06),
    241: dict(inv=(0.3125, 0.255, 0.672, 0.339)),
    243: dict(zb=0.03),
    244: dict(zb=0.25),
    245: dict(zb=0.14),
    246: dict(zb=0.06),
    250: dict(hb=0.03, dx=0.008),
    251: dict(hb=0.85, dx=0.143, wrap=True),
}
BW = set(range(153, 164)) | set(range(171, 180)) | {197} | set(range(226, 237)) | set(range(245, 252))
# Zoom-Schritte, die in der Messung unzuverlaessig sind (Wisch-Bilder), gemessen per Bild-Anpassung
LOGZ = {105: math.log(0.815 / 0.763), 106: math.log(0.89 / 0.815), 107: math.log(0.954 / 0.89),
        115: -0.004, 116: -0.008, 125: math.log(1 / 1.208)}
# geteilte Bilder (oben/unten bzw. links/rechts)
SPLIT_Y = {140: 0.495, 141: 0.55}
SPLIT_X = {214: 0.5, 215: 0.5}
PANEL = [(0.0, 254), (0.375, 254), (0.5, 224), (0.625, 198), (0.75, 172), (0.875, 161), (1.0, 156)]

# ------------------------------------------------------------------ Kamera (Zoom je Bild aus dem Vorbild)
REFP = {int(k): v for k, v in json.load(open(os.path.join(HERE, "ref_camera.json"))).items()}


def scene_of(f):
    return max(i for i, p in enumerate(PLAN) if p["f0"] <= f)


def _curve(i):
    p = PLAN[i]
    if p["name"] == "intro":
        return {f: 1.0 for f in range(p["f0"] - 2, p["f1"] + 3)}      # ruhige Kamera wie im Vorbild
    fa, fb = p["f0"], p["f1"] + 2
    steps = {}
    for f in range(fa + 1, fb + 1):
        if f in LOGZ:
            steps[f] = LOGZ[f]
            continue
        r = REFP.get(f)
        if r and r[4] >= 0.85 and abs(math.log(r[0])) <= 0.20 and f not in (p["f1"],):
            steps[f] = math.log(r[0])
    known = sorted(steps)
    vals = []
    for f in range(fa + 1, fb + 1):
        if f in steps:
            vals.append(steps[f])
            continue
        lo = [k for k in known if k < f]
        hi = [k for k in known if k > f]
        if lo and hi:
            a, b = lo[-1], hi[0]
            vals.append(steps[a] + (steps[b] - steps[a]) * (f - a) / (b - a))
        elif lo:
            vals.append(steps[lo[-1]] * 0.8)
        elif hi:
            vals.append(steps[hi[0]] * 0.8)
        else:
            vals.append(0.0)
    L = np.concatenate([[0.0], np.cumsum(vals)])
    # Bezug sind die scharfen Bilder der Szene; stark verwischte Wisch-Bilder duerfen nicht weiter heraus
    sharp = [k for k in range(len(L)) if fa + k < p["f1"] and fa + k not in FX and k >= 3] or list(range(len(L)))
    lo, hi = min(L[k] for k in sharp), max(L[k] for k in sharp)
    if hi - lo > math.log(ZMAX):
        L = L * (math.log(ZMAX) / (hi - lo))
        lo = min(L[k] for k in sharp)
    L = np.maximum(L - lo, 0.0)
    out = {fa + k: float(math.exp(v)) for k, v in enumerate(L)}
    out[fa - 1] = out[fa]
    out[fa - 2] = out[fa]
    return out


CURVES = [_curve(i) for i in range(len(PLAN))]


def Z(i, f):
    c = CURVES[i]
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
    p = PLAN[i]
    return p["t"] + (f - p["f0"]) / FPS * SPEED


def load(i):
    global TRACKER
    if i in cache:
        return cache[i]
    p = PLAN[i]
    clip, a, b, pre, _ = SCENES[p["scene"]]
    rot = "transpose=1" in pre
    s = max(a, ts_of(i, p["f0"] - 3) - 0.10)
    e = min(b, ts_of(i, p["f1"] + 3) + 0.12)
    frames, times = _decode(clip, rot, s, e)
    src_fps = 1.0 / float(np.median(np.diff(times))) if len(times) > 2 else 60.0
    interp = src_fps < 45
    if interp:                                   # 30-fps-Quelle: Zwischenbilder fuer weiche Zeitlupe
        frames, times = double_rate(frames, times)
    m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", pre)[-1]
    cw0, ch0, cx0, cy0 = map(int, m)
    TRACKER = TRACKER or FaceTracker()
    raw = track(list(frames), hint=(cx0 + cw0 / 2, cy0 + ch0 / 2), tracker=TRACKER)
    fx, fy, fh = smooth_track(times, raw, sigma_s=0.12)
    found = int((~np.isnan(raw[:, 0])).sum())
    x0, y0, x1, y1 = SAFE[clip]
    yf, hf = p["face"]
    # Grundausschnitt (Hoehe) so, dass das Gesicht im Mittel so gross ist wie im Vorbild (etwas weiter)
    rz = np.median([Z(i, f) for f in range(*p["ref"])])
    ch = float(np.nanmedian(raw[:, 2]) * rz / (hf * FRAME_WIDER))
    ch_max = min(y1 - y0, (x1 - x0) / ASPECT)
    # so klein, dass Felix im sicheren Bereich immer mittig sitzen kann
    # (senkrecht etwas Spielraum: das Gesicht darf bis zu 0,08 hoeher/tiefer sitzen, dafuer weiterer Ausschnitt)
    yf_top, yf_bot = max(0.12, yf - 0.08), min(0.6, yf + 0.08)
    lim = min(np.percentile(2 * np.minimum(fx - x0, x1 - fx), 5) / ASPECT,
              np.percentile((fy - y0) / yf_top, 5), np.percentile((y1 - fy) / (1 - yf_bot), 5))
    ch = float(np.clip(ch, 400, min(ch_max, max(lim, 400))))
    cache[i] = dict(frames=frames, times=times, fx=fx, fy=fy, ch=ch, safe=(x0, y0, x1, y1), found=found,
                    total=len(frames), fps=src_fps, interp=interp, lab=None)
    return cache[i]


def src_index(i, f):
    d = load(i)
    return int(np.argmin(np.abs(d["times"] - ts_of(i, f))))


def warp_crop(img, cx, cy, ch, pad=0.0, interp=cv2.INTER_LANCZOS4):
    """Ausschnitt (Mitte cx,cy, Hoehe ch, 3:4) -> Bild W x H; pad vergroessert die Leinwand rundum"""
    wc, hc = int(round(W * (1 + 2 * pad))), int(round(H * (1 + 2 * pad)))
    sc = H / ch
    M = np.array([[sc, 0, (wc - 1) / 2 - sc * cx], [0, sc, (hc - 1) / 2 - sc * cy]], np.float32)
    return cv2.warpAffine(img, M, (wc, hc), flags=interp, borderMode=cv2.BORDER_REFLECT_101).astype(np.float32)


def cam(i, f, pad=0.0, extra=1.0):
    """Felix-Bild der Szene i fuer Ausgabebild f: Gesicht mittig, Zoom wie im Vorbild, Bewegungsunschaerfe"""
    d = load(i)
    k = src_index(i, f)
    p = PLAN[i]
    x0, y0, x1, y1 = d["safe"]
    z = Z(i, f) * extra
    ch = min(d["ch"] / z, y1 - y0, (x1 - x0) / ASPECT)
    cwid = ch * ASPECT
    cx = float(np.clip(d["fx"][k], x0 + cwid / 2, x1 - cwid / 2))
    cy = float(np.clip(d["fy"][k] + (0.5 - p["face"][0]) * ch, y0 + ch / 2, y1 - ch / 2))
    img = d["frames"][k]
    v = math.log(Z(i, f + 1) / Z(i, f - 1)) / 2 * 0.5          # Zoom-Geschwindigkeit (180-Grad-Verschluss)
    if abs(v) > 0.006:
        n = int(min(12, max(4, abs(v) * 160)))
        acc = None
        for jj in range(n):
            u = (jj + 0.5) / n - 0.5
            w_ = warp_crop(img, cx, cy, ch / math.exp(v * u), pad, interp=cv2.INTER_LINEAR)
            acc = w_ if acc is None else acc + w_
        return acc / n
    return warp_crop(img, cx, cy, ch, pad)


# ------------------------------------------------------------------ Farben: CC + Angleichung an die Vorbild-Szene
REF_ARR = None
REF_STATS = {}
STRENGTH = np.array([0.45, 0.75, 0.75], np.float32)
STRENGTH_SCENE = {"intro": np.array([0.15, 0.40, 0.40], np.float32)}
SAT = {"intro": 0.85, "S3": 0.80, "S5": 0.72}     # Vorbild ist blass (Haut hell-rosa, Haare platin)


def _lab(img):
    return cv2.cvtColor(np.clip(img, 0, 255).astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)


def ref_frames():
    global REF_ARR
    if REF_ARR is None:
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", REF, "-vf", "fps=30:start_time=0", "-frames:v", "400",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        REF_ARR = np.frombuffer(r.stdout, np.uint8).reshape(-1, 768, 576, 3)
    return REF_ARR


def ref_stats(i):
    if i in REF_STATS:
        return REF_STATS[i]
    ra = ref_frames()
    mask = np.ones((768, 576), bool)
    mask[150:280, :100] = False          # TikTok-Zeichen
    mask[620:, 460:] = False
    mask[540:720, 160:420] = False       # Logo des Editors
    a, b = PLAN[i]["ref"]
    fs = [f for f in range(a, b, 2) if f not in BW and f not in FX]
    lab = np.concatenate([_lab(ra[f])[mask] for f in fs])
    REF_STATS[i] = (lab.mean(0), lab.std(0) + 1e-3)
    return REF_STATS[i]


def base_look(img):
    return cc(img, sat=1.0, clarity=0.10, detail=0.22, bloom=0.05)


def shot_stats(i):
    d = load(i)
    if d["lab"] is None:
        p = PLAN[i]
        fs = np.linspace(p["f0"] + 3, p["f1"] - 3, 6).astype(int)
        lab = np.concatenate([_lab(cv2.resize(base_look(cam(i, f)), (240, 320), interpolation=cv2.INTER_AREA)).reshape(-1, 3)
                              for f in fs])
        d["lab"] = (lab.mean(0), lab.std(0) + 1e-3)
    return d["lab"]


def grade(img, i):
    img = base_look(img)
    ms, ss = shot_stats(i)
    mt, st = ref_stats(i)
    ratio = np.clip(st / ss, 0.5, 1.35)
    lab = _lab(img)
    tgt = (lab - ms) * ratio + mt
    lab = lab + (tgt - lab) * STRENGTH_SCENE.get(PLAN[i]["name"], STRENGTH)
    sat = SAT.get(PLAN[i]["name"], 1.0)
    if sat != 1.0:
        lab[..., 1:] *= sat
    return np.clip(cv2.cvtColor(lab.astype(np.float32), cv2.COLOR_LAB2RGB), 0, 1) * 255.0


def finish(img, soften=0.18, glow=0.08):
    x = np.clip(img, 0, 255) / 255.0
    x = x * (1 - soften) + cv2.GaussianBlur(x, (0, 0), 1.4) * soften
    b = cv2.GaussianBlur(np.clip(x - 0.55, 0, None), (0, 0), 16)
    x = 1 - (1 - x) * (1 - glow * 2.2 * b)
    return np.clip(x, 0, 1) * 255.0


# ------------------------------------------------------------------ Effekt-Bausteine
def to_bw(img, contrast=1.05):
    y = img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114
    m = float(y.mean())
    y = np.clip((y - m) * contrast + m, 0, 255)
    return np.repeat(y[..., None], 3, axis=2)


def flash(img):
    y = to_bw(img, 1.0)[..., 0] / 255.0
    k = 4.0
    out = 20 + 235 * (1 - np.exp(-k * y)) / (1 - math.exp(-k))
    return np.repeat(out[..., None], 3, axis=2)


def hblur(img, L, wrap=False):
    n = int(round(L * W))
    if n < 2:
        return img
    if wrap:                                     # Bild laeuft seitlich herum (wie beim schnellen Wisch im Vorbild)
        n = min(n, 4 * W)
        reps = (n // 2 + 2) // W + 1
        big = np.concatenate([img] * (2 * reps + 1), axis=1)
        return cv2.blur(big, (n, 1), borderType=cv2.BORDER_REFLECT)[:, reps * W:(reps + 1) * W]
    return cv2.blur(img, (n, 1), borderType=cv2.BORDER_REFLECT)


def vblur(img, L):
    n = int(round(L * H))
    if n < 2:
        return img
    n = min(n, 2 * H)
    return cv2.blur(img, (1, n), borderType=cv2.BORDER_REFLECT)


def dblur(img, L, ang):
    """gerichtete Bewegungsunschaerfe: drehen, waagerecht verwischen, zurueckdrehen"""
    h, w = img.shape[:2]
    D = int(math.ceil(math.hypot(w, h))) + 4
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    M[0, 2] += (D - w) / 2
    M[1, 2] += (D - h) / 2
    rot = cv2.warpAffine(img, M, (D, D), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    rot = cv2.blur(rot, (max(2, int(round(L * W))), 1), borderType=cv2.BORDER_REFLECT)
    Mi = cv2.invertAffineTransform(M)
    return cv2.warpAffine(rot, Mi, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def zoom_blur(canvas, amount, cy=0.5):
    """radiale Zoom-Unschaerfe um das Gesicht (cy = Hoehe des Zentrums als Anteil der Ausgabe)"""
    if amount < 0.01:
        return canvas
    h, w = canvas.shape[:2]
    py = (h - H) / 2 + cy * H
    n = int(min(24, max(5, amount * 50)))
    acc = np.zeros_like(canvas)
    for j in range(n):
        s = math.exp(amount * ((j + 0.5) / n - 0.5))
        M = np.array([[s, 0, (1 - s) * (w - 1) / 2], [0, s, (1 - s) * py]], np.float32)
        acc += cv2.warpAffine(canvas, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return acc / n


def invert_box(img, box, gain=0.9):
    x0, y0, x1, y1 = int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)
    y = to_bw(img[y0:y1, x0:x1], 1.0)
    img = img.copy()
    img[y0:y1, x0:x1] = (255 - y) * gain
    return img


def panel():
    ys = np.linspace(0, 1, H)
    v = np.interp(ys, [p[0] for p in PANEL], [p[1] for p in PANEL]).astype(np.float32)
    return np.repeat(np.repeat(v[:, None], W, axis=1)[..., None], 3, axis=2)


# ------------------------------------------------------------------ ein Bild einer Szene mit Effekten
def layer(i, f, spec, bw=False):
    pad = 0.0
    if spec.get("zb", 0) > 0.01 or abs(spec.get("dx", 0)) > 0 or abs(spec.get("dy", 0)) > 0:
        pad = 0.18
    img = grade(cam(i, f, pad=pad, extra=spec.get("scale", 1.0)), i)
    if spec.get("zb", 0) > 0.01:
        img = zoom_blur(img, spec["zb"], PLAN[i]["face"][0])
    if pad > 0:
        hc, wc = img.shape[:2]
        ox = int(round((wc - W) / 2 - spec.get("dx", 0) * W)) if not spec.get("wrap") else (wc - W) // 2
        oy = int(round((hc - H) / 2 - spec.get("dy", 0) * H))
        ox = int(np.clip(ox, 0, wc - W))
        oy = int(np.clip(oy, 0, hc - H))
        img = img[oy:oy + H, ox:ox + W]
        if spec.get("wrap") and spec.get("dx"):
            img = np.roll(img, int(round(spec["dx"] * W)), axis=1)
    if spec.get("hb"):
        img = hblur(img, spec["hb"], wrap=spec.get("wrap", False))
    if spec.get("vb"):
        img = vblur(img, spec["vb"])
    if spec.get("db"):
        img = dblur(img, *spec["db"])
    if spec.get("sig", 0) > 0.3:
        img = cv2.GaussianBlur(img, (0, 0), spec["sig"] * K)
    if bw:
        img = to_bw(img)
    if spec.get("flash"):
        img = flash(img)
    img = img * spec.get("gain", 1.0)
    if spec.get("white"):
        img = img * (1 - spec["white"]) + 255.0 * spec["white"]
    if spec.get("inv"):
        img = invert_box(img, spec["inv"])
    return img


def render_first(f):
    """Bild f der ersten Haelfte (0-251)"""
    if f in SPLIT_Y:
        cut = int(round(SPLIT_Y[f] * H))
        if f == 140:
            top = layer(2, 140, dict(zb=0.30, scale=1.10))
            bot = layer(3, 140, dict(zb=0.45, scale=1.70), bw=True)
        else:
            top = layer(3, 141, dict(zb=0.45, scale=1.35, gain=1.18), bw=True)
            bot = layer(3, 141, dict(vb=0.45, scale=1.20, gain=0.85), bw=True)
        img = np.concatenate([top[:cut], bot[cut:]], axis=0)
    elif f in SPLIT_X:
        cut = int(round(SPLIT_X[f] * W))
        pn = panel()
        if f == 214:
            left = layer(5, 214, dict(zb=0.22, scale=1.08))
            img = np.concatenate([left[:, :cut], pn[:, cut:]], axis=1)
        else:
            right = layer(6, 215, dict(sig=40, gain=1.05))
            img = np.concatenate([pn[:, :cut], right[:, cut:]], axis=1)
    else:
        i = scene_of(f)
        img = layer(i, f, FX.get(f, {}), bw=f in BW)
    return np.clip(finish(img), 0, 255).astype(np.uint8)


DONE = {}


def render(f):
    if f >= END:
        return np.zeros((H, W, 3), np.uint8)
    if REP_B <= f < END:
        g = f - (REP_B - REP_A)
        if g in DONE:
            return DONE[g]
        return render_first(g)
    img = render_first(f)
    if REP_A <= f < REP_B:
        DONE[f] = img
    return img


def release(f):
    """Quelldaten von Szenen freigeben, die nicht mehr gebraucht werden"""
    i = scene_of(min(f, REP_B - 1))
    for k in list(cache):
        if k < i - 1:
            del cache[k]


def compare(frames, name="vergleich.jpg"):
    """Vorbild (oben) und Felix-Edit (unten) nebeneinander"""
    ra = ref_frames()
    cols = []
    for f in frames:
        r = cv2.resize(ra[min(f, len(ra) - 1)], (288, 384), interpolation=cv2.INTER_AREA)
        e = cv2.resize(render(f), (288, 384), interpolation=cv2.INTER_AREA)
        t = np.vstack([r, e])
        t = cv2.cvtColor(t, cv2.COLOR_RGB2BGR)
        cv2.putText(t, str(f), (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(t, str(f), (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cols.append(t)
    rows = [np.hstack(cols[k:k + 8]) for k in range(0, len(cols), 8)]
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
        args = sys.argv[2:]
        name = "vergleich.jpg"
        if args and not args[0].isdigit():
            name, args = args[0], args[1:]
        compare([int(x) for x in args], name)
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "shots":
        for i, p in enumerate(PLAN):
            d = load(i)
            print(f"{p['name']:5s} {p['scene']:10s} t={p['t']:.2f} Gesicht {d['found']}/{d['total']} "
                  f"Ausschnitt {d['ch']:.0f}x{d['ch'] * ASPECT:.0f} (x{H / d['ch']:.2f}) Quelle {d['fps']:.0f} fps "
                  f"Zwischenbilder {d['interp']}  Zoom {min(CURVES[i].values()):.2f}-{max(CURVES[i].values()):.2f}")
        sys.exit(0)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", REF, "-map", "0:v", "-map", "1:a",
         "-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=lanczos,format=yuv420p",
         "-c:v", "libx264", "-preset", "slow", "-tune", "film", "-crf", "15", "-profile:v", "high", "-level", "4.1",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
         "-af", f"afade=t=out:st={NF / FPS - 0.4:.2f}:d=0.4", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
         "-t", f"{NF / FPS}", OUT], stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(NF):
        if f < REP_B:
            release(f)
        enc.stdin.write(render(f).tobytes())
        if f % 30 == 0:
            print(f"Bild {f}/{NF} {time.time() - t0:.0f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    print("fertig", OUT, round(time.time() - t0))
