#!/usr/bin/env python3
"""Felix-Konzert-Edit v2 nach Referenz 4 (@mitanori, 576x576, 17,4 s).

Nutzer-Wuensche (v2):
  * Felix immer in Zeitlupe wie in der Referenz -> 60-fps-Quellen mit halber Geschwindigkeit
    (jedes echte Einzelbild wird gezeigt, keine erfundenen Zwischenbilder)
  * Felix immer mittig -> Gesicht wird pro Bild erkannt (face_track.py) und weich verfolgt
  * weichere Uebergaenge -> Unschaerfe am Bild abgeglichen (staerker als v1) + Farben jeder Szene
    an die passende Referenz-Szene angeglichen (kleinere Farbspruenge am Schnitt)

Aufbau wie Referenz: 10 Szenen (0-234), dieselben 10 Szenen noch einmal (235-469), danach schwarz.
Aufruf:  python3 render.py   |   python3 render.py frames 0 140 300   |   python3 render.py shots
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

MEDIA = os.environ.get("EDIT_MEDIA", os.path.join(FELIX, "media"))
REF = os.environ.get("REF4", os.path.join(MEDIA, "reference_konzert.mov"))
OUTDIR = os.environ.get("EDIT_OUT", os.path.join(HERE, "out"))
OUT = os.path.join(OUTDIR, "Felix_Konzert_Edit_v2.mp4")
W, FPS = 1080, 30
K = W / 576.0
NF, END = 523, 470

HALF = [0, 22, 60, 75, 97, 119, 141, 177, 190, 214]
CUTS = HALF + [c + 235 for c in HALF]

# Szene, Startzeit in der Quelle, Tempo (0.5 = halbe Geschwindigkeit bei 60-fps-Quelle)
PLAN = [
    dict(scene="glove_mic",  t=0.25,  speed=0.5),   # A  Nahaufnahme, singt
    dict(scene="glove_x",    t=5.20,  speed=0.5),   # B  Handschuhe vor dem Gesicht (Takt-Blitze)
    dict(scene="bear",       t=0.80,  speed=0.5),   # C  laechelt
    dict(scene="micsmile",   t=1.80,  speed=0.5),   # D  am Mikro, laechelt
    dict(scene="brick",      t=13.40, speed=0.5),   # E  heller Hintergrund, laechelt
    dict(scene="pink_up",    t=13.10, speed=0.5),   # F  Nahaufnahme, Blick zur Seite
    dict(scene="glove_wide", t=2.00,  speed=0.5),   # G  Bewegung (Takt-Blitze)
    dict(scene="blue_up",    t=0.40,  speed=0.5),   # H  kurz, Blick in die Kamera
    dict(scene="silver",     t=1.40,  speed=0.7),   # I  dunkel, ruhig (41-fps-Quelle -> 0.7)
    dict(scene="glove_x",    t=4.10,  speed=0.5),   # J  Arme ausgebreitet
]
SHOTS = PLAN + PLAN
# Bereiche ohne Untertitel / Logos / schwarze Raender (Koordinaten nach Videobereich + ggf. Drehung)
SAFE = {
    "clip8.mov": (0, 0, 2096, 995),
    "clip5.mov": (0, 80, 1180, 1950),
    "clip7.mov": (0, 0, 1180, 1350),
    "clip12.mov": (0, 0, 1820, 1000),
    "clip13.mov": (175, 0, 1550, 1180),
    "clip2.mov": (220, 80, 1950, 1000),
    "clip10.mov": (0, 0, 2096, 1180),
}
# eingeblendete Schrift, die im Bereich liegt und weggerechnet wird (x0, y0, x1, y1)
PATCHES = {
    "clip5.mov": [(64, 926, 162, 1170)],          # ">> She"-Einblendung am linken Rand (gemessen)
}
# Gesicht in der Referenz-Szene: (x, y) als Anteil, Gesichtshoehe als Anteil  (gemessen mit YuNet)
REF_FACE = [(.50, .33, .385), (.50, .38, .292), (.50, .34, .299), (.50, .30, .266), (.50, .27, .288),
            (.50, .34, .334), (.50, .27, .253), (.50, .32, .304), (.50, .30, .341), (.50, .29, .251)]
FRAME_WIDER = 0.78           # etwas weiter als Referenz -> weniger Hochskalieren, bessere Qualitaet
MIN_SIDE = 600


def shot_of(f):
    return max(i for i, c in enumerate(CUTS) if c <= f)


def shot_end(i):
    return CUTS[i + 1] if i + 1 < len(CUTS) else END


# ------------------------------------------------------------------ Uebergaenge (sigma bei 576 px, Helligkeit)
TR = {
    0:   {0: (20, .80), 1: (12, .90), 2: (7, 1), 3: (4, 1), 4: (2.5, 1), 5: (1.5, 1)},
    22:  {-3: (1.5, .88), -2: (3.5, .73), -1: (6, .60),
          0: (14, .55), 1: (9, .57), 2: (6, .67), 3: (4, .80), 4: (2.5, .90), 5: (1.5, .96)},
    60:  {-3: (1.5, .94), -2: (3, .91), -1: (5, .86), 0: (14, .95), 1: (9, 1), 2: (5, 1), 3: (3, 1), 4: (2, 1)},
    75:  {-3: (2, .96), -2: (4, .88), -1: (7, .84),
          0: (14, .58), 1: (9, .62), 2: (6, .73), 3: (4, .86), 4: (2.5, .96), 5: (1.5, 1)},
    97:  {-3: (1.5, .89), -2: (3.5, .78), -1: (6, .68),
          0: (16, .72), 1: (10, .74), 2: (6, .82), 3: (4, .92), 4: (2.5, 1), 5: (1.5, 1)},
    119: {-3: (1.5, 1), -2: (3, 1), -1: (5, 1), 0: (16, .92), 1: (9, .94), 2: (5, .98), 3: (3, .97), 4: (2, .97)},
    141: {-3: (2, 1), -2: (4, 1), 0: (6, .72), 1: (4, .77), 2: (3, .80), 3: (2, .90)},
    177: {-3: (2, 1), -2: (4, 1), -1: (8, 1), 0: (5, .92), 1: (4, .97), 2: (3, .98), 3: (1.5, .97)},
    190: {-3: (1.5, .91), -2: (3, .82), -1: (6, .74),
          0: (20, .80), 1: (13, .80), 2: (7, .88), 3: (4, .96), 4: (2.5, 1), 5: (1.5, 1)},
    214: {-3: (1.5, .91), -2: (3, .84), -1: (6, .78),
          0: (18, .85), 1: (11, .90), 2: (7, .95), 3: (4, 1), 4: (2.5, 1), 5: (1.5, 1)},
    235: {-4: (1, .90), -3: (2, .88), -2: (4, .88), -1: (7, .90),
          0: (20, .95), 1: (12, .90), 2: (7, 1), 3: (4, 1), 4: (2.5, 1), 5: (1.5, 1)},
}
SPEC = {}
for base in (0, 235):
    for c, d in TR.items():
        if c in (0, 235):
            continue
        for o, v in d.items():
            SPEC[c + base + o] = v
for c in (0, 235):
    for o, v in TR[c].items():
        SPEC[c + o] = v
HB = {f + b: v for f, v in {141: .10, 142: .03}.items() for b in (0, 235)}
WP = {140, 375}
FL = {f + b for f in (31, 39, 47, 54, 147, 154, 162, 169) for b in (0, 235)}

# ------------------------------------------------------------------ Kamerakurve (Zoom) aus der Referenz
REFP = {int(k): v for k, v in json.load(open(os.path.join(HERE, "ref_camera.json"))).items()}
ZMAX = 1.25


def _fill(vals, cap=0.10):
    n = len(vals)
    out = [0.0] * n
    idx = [k for k in range(1, n) if vals[k] is not None]
    if not idx:
        return out
    for k in idx:
        out[k] = vals[k]
    for k in range(1, idx[0]):
        out[k] = float(np.clip(vals[idx[0]] * 1.5 ** (idx[0] - k), -cap, cap))
    for a, b in zip(idx, idx[1:]):
        for k in range(a + 1, b):
            out[k] = vals[a] + (vals[b] - vals[a]) * (k - a) / (b - a)
    for k in range(idx[-1] + 1, n):
        out[k] = float(np.clip(vals[idx[-1]] * 1.6 ** (k - idx[-1]), -cap, cap))
    return out


CURVE = {}
for i, c in enumerate(CUTS):
    n = shot_end(i) - c
    vals = [None] * n
    for k in range(1, n):
        r = REFP.get(c + k)
        if r and r[4] >= 0.8 and abs(math.log(r[0])) <= 0.12:
            vals[k] = math.log(r[0])
    L = np.cumsum(_fill(vals))
    rng = L.max() - L.min()
    if rng > math.log(ZMAX):
        L = L * (math.log(ZMAX) / rng)
    L = L - L.min()
    for k in range(n):
        CURVE[c + k] = float(math.exp(L[k]))


def Z(f):
    i = shot_of(f)
    return CURVE[min(max(f, CUTS[i]), shot_end(i) - 1)]


# ------------------------------------------------------------------ Quellen, Gesichtsverfolgung, Farben
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
    small = np.stack([cv2.resize(cv2.cvtColor(x, cv2.COLOR_RGB2GRAY), (96, 96), interpolation=cv2.INTER_AREA)
                      for x in arr]).astype(np.float32)
    dif = np.abs(np.diff(small, axis=0)).mean(axis=(1, 2))
    keep = [0] + [k + 1 for k, dv in enumerate(dif) if dv > 0.18]
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


def load(i):
    global TRACKER
    p = SHOTS[i]
    key = (p["scene"], p["t"])
    if key in cache:
        return cache[key]
    clip, a, b, pre, _ = SCENES[p["scene"]]
    rot = "transpose=1" in pre
    n = shot_end(i) - CUTS[i]
    need = n / FPS * p["speed"]
    s = max(a, p["t"] - 0.12)
    e = min(b, p["t"] + need + 0.15)
    frames, times = _decode(clip, rot, s, e)
    m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", pre)[-1]
    cw, ch, cx0, cy0 = map(int, m)
    TRACKER = TRACKER or FaceTracker()
    raw = track(list(frames), hint=(cx0 + cw / 2, cy0 + ch / 2), tracker=TRACKER)
    fx, fy, fh = smooth_track(times, raw, sigma_s=0.12)
    found = int((~np.isnan(raw[:, 0])).sum())
    j = i % 10
    side = float(np.nanmedian(raw[:, 2]) / (REF_FACE[j][2] * FRAME_WIDER))
    x0, y0, x1, y1 = SAFE[clip]
    side = float(np.clip(side, MIN_SIDE, min(x1 - x0, y1 - y0)))
    # Ausschnitt so klein halten, dass Felix im sicheren Bereich IMMER mittig sitzen kann
    yf = REF_FACE[j][1]
    lim = min(np.percentile(2 * np.minimum(fx - x0, x1 - fx), 5),
              np.percentile((fy - y0) / yf, 5),
              np.percentile((y1 - fy) / (1 - yf), 5))
    side = float(max(0.75 * MIN_SIDE, min(side, lim)))
    cache[key] = dict(frames=frames, times=times, fx=fx, fy=fy, side=side, safe=(x0, y0, x1, y1),
                      found=found, total=len(frames), lab=None)
    return cache[key]


def src_index(i, f):
    d = load(i)
    ts = SHOTS[i]["t"] + (f - CUTS[i]) / FPS * SHOTS[i]["speed"]
    return int(np.argmin(np.abs(d["times"] - ts)))


def crop_geometry(i, f, side):
    """Ausschnitt so, dass das Gesicht waagerecht in der Mitte und senkrecht wie in der Referenz sitzt"""
    d = load(i)
    k = src_index(i, f)
    j = i % 10
    x0, y0, x1, y1 = d["safe"]
    side = min(side, x1 - x0, y1 - y0)
    cx = float(d["fx"][k])
    cy = float(d["fy"][k]) + (0.5 - REF_FACE[j][1]) * side
    cx = float(np.clip(cx, x0 + side / 2, x1 - side / 2))
    cy = float(np.clip(cy, y0 + side / 2, y1 - side / 2))
    return k, cx, cy, side


def warp_crop(img, cx, cy, side, interp=cv2.INTER_LANCZOS4):
    sc = W / side
    M = np.array([[sc, 0, (W - 1) / 2 - sc * cx], [0, sc, (W - 1) / 2 - sc * cy]], np.float32)
    return cv2.warpAffine(img, M, (W, W), flags=interp, borderMode=cv2.BORDER_REFLECT_101).astype(np.float32)


def shot_frame(i, f):
    d = load(i)
    z = Z(f)
    k, cx, cy, side = crop_geometry(i, f, d["side"] / z)
    img = d["frames"][k]
    c0, c1 = CUTS[i], shot_end(i)
    fa, fb = max(c0, f - 1), min(c1 - 1, f + 1)
    v = math.log(Z(fb) / Z(fa)) / max(1, fb - fa) * 0.5
    if abs(v) > 0.006:
        n = int(min(12, max(4, abs(v) * 160)))
        acc = np.zeros((W, W, 3), np.float32)
        for jj in range(n):
            u = (jj + 0.5) / n - 0.5
            acc += warp_crop(img, cx, cy, side / math.exp(v * u), interp=cv2.INTER_LINEAR)
        return acc / n
    return warp_crop(img, cx, cy, side)


# Farbangleichung an die Referenz-Szene (Lab: Mittelwert/Streuung)
REF_ARR = None
REF_STATS = {}
STRENGTH = np.array([0.45, 0.6, 0.6], np.float32)


def _lab(img):
    return cv2.cvtColor(np.clip(img, 0, 255).astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)


def ref_stats(j):
    global REF_ARR
    if j in REF_STATS:
        return REF_STATS[j]
    if REF_ARR is None:
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", REF, "-vf", "fps=30:start_time=0", "-frames:v", "240",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        REF_ARR = np.frombuffer(r.stdout, np.uint8).reshape(-1, 576, 576, 3)
    mask = np.ones((576, 576), bool)
    mask[:90, :150] = False
    mask[470:, 450:] = False
    mask[500:, 200:380] = False
    a, b = HALF[j] + 6, (HALF[j + 1] if j + 1 < 10 else 235) - 4
    lab = np.concatenate([_lab(REF_ARR[f])[mask] for f in range(a, b, 2)])
    REF_STATS[j] = (lab.mean(0), lab.std(0) + 1e-3)
    return REF_STATS[j]


def shot_stats(i):
    d = load(i)
    if d["lab"] is None:
        fs = np.linspace(CUTS[i] + 4, shot_end(i) - 4, 6).astype(int)
        lab = np.concatenate([_lab(cv2.resize(shot_frame(i, f), (256, 256), interpolation=cv2.INTER_AREA)).reshape(-1, 3)
                              for f in fs])
        d["lab"] = (lab.mean(0), lab.std(0) + 1e-3)
    return d["lab"]


def color_match(img, i):
    ms, ss = shot_stats(i)
    mt, st = ref_stats(i % 10)
    ratio = np.clip(st / ss, 0.75, 1.35)
    lab = _lab(img)
    tgt = (lab - ms) * ratio + mt
    lab = lab + (tgt - lab) * STRENGTH
    rgb = cv2.cvtColor(lab.astype(np.float32), cv2.COLOR_LAB2RGB)
    return np.clip(rgb, 0, 1) * 255.0


def finish(img, soften=0.22, glow=0.08):
    x = np.clip(img, 0, 255) / 255.0
    x = x * (1 - soften) + cv2.GaussianBlur(x, (0, 0), 1.4) * soften
    b = cv2.GaussianBlur(np.clip(x - 0.55, 0, None), (0, 0), 16)
    x = 1 - (1 - x) * (1 - glow * 2.2 * b)
    return np.clip(x, 0, 1) * 255.0


def graded(i, f):
    return color_match(shot_frame(i, f), i)


def render(f):
    if f >= END:
        return np.zeros((W, W, 3), np.uint8)
    i = shot_of(f)
    if f in WP:
        old = cv2.GaussianBlur(graded(i, f), (0, 0), 10 * K)
        new = cv2.blur(graded(i + 1, CUTS[i + 1]) * 0.7, (int(0.30 * W), 1))
        img = np.empty_like(old)
        img[:, :W // 2] = new[:, W // 2:]
        img[:, W // 2:] = old[:, :W - W // 2]
    else:
        img = graded(i, f)
        sig, gain = SPEC.get(f, (0, 1.0))
        if sig > 0:
            img = cv2.GaussianBlur(img, (0, 0), sig * K)
        if f in HB:
            img = cv2.blur(img, (max(3, int(HB[f] * W)), 1))
        img = img * gain
        if f in FL:
            img = cv2.GaussianBlur(img, (0, 0), 3 * K) * 0.31
    return np.clip(finish(img), 0, 255).astype(np.uint8)


def release_before(i):
    keep = {(SHOTS[j]["scene"], SHOTS[j]["t"]) for j in range(i, min(i + 2, len(SHOTS)))}
    for key in list(cache):
        if key not in keep:
            del cache[key]


if __name__ == "__main__":
    os.makedirs(OUTDIR, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "frames":
        for f in map(int, sys.argv[2:]):
            cv2.imwrite(os.path.join(OUTDIR, f"preview_{f:03d}.png"), cv2.cvtColor(render(f), cv2.COLOR_RGB2BGR))
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "shots":
        for i in range(10):
            d = load(i)
            print(f"shot {i} {SHOTS[i]['scene']:10s} t={SHOTS[i]['t']:.2f} faces {d['found']}/{d['total']} side {d['side']:.0f}")
        sys.exit(0)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{W}", "-r", str(FPS), "-i", "-",
         "-i", REF, "-map", "0:v", "-map", "1:a",
         "-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=lanczos,format=yuv420p",
         "-c:v", "libx264", "-preset", "slow", "-tune", "film", "-crf", "15", "-profile:v", "high", "-level", "4.1",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
         "-af", f"afade=t=out:st={NF / FPS - 0.4:.2f}:d=0.4", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
         "-t", f"{NF / FPS}", OUT], stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(NF):
        if f < END:
            release_before(shot_of(f))
        enc.stdin.write(render(f).tobytes())
        if f % 60 == 0:
            print(f"frame {f}/{NF} {time.time() - t0:.0f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    print("done", OUT, round(time.time() - t0))
