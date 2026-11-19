#!/usr/bin/env python3
"""Felix-Konzert-Edit nach Referenz 4 (@mitanori, 576x576, 17,4 s).

Aufbau der Referenz (Bildnummern = t*30):
  * 10 Szenen (0-234), danach dieselben 10 Szenen mit denselben Momenten noch einmal (235-469),
    ab Bild 470 schwarz, Musik laeuft bis 17,4 s weiter
  * Uebergang: Unschaerfe-Blende (raus 3-4 Bilder, rein 5-6 Bilder) + leichtes Abdunkeln (je Schnitt gemessen)
  * jede Szene zoomt weich (Kamerakurve aus der Referenz, ref_camera.json)
  * dunkle Takt-Blitze (1 Bild, x0.31) in Szene B und G auf jeder Achtelnote
  * Bild 140 / 375: Schiebe-Uebergang (neues Bild schiebt sich von links rein, horizontale Wischunschaerfe)
  * Look: rose_look (tiefe Schwarztoene, rosa Lichter, kuehle Schatten)
Aufruf:  python3 render.py   |   python3 render.py frames 0 140 300
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
from rose_look import rose_look

MEDIA = os.environ.get("EDIT_MEDIA", os.path.join(FELIX, "media"))
REF = os.environ.get("REF4", os.path.join(MEDIA, "reference_konzert.mov"))
OUTDIR = os.environ.get("EDIT_OUT", os.path.join(HERE, "out"))
OUT = os.path.join(OUTDIR, "Felix_Konzert_Edit.mp4")
W = 1080
FPS = 30
K = W / 576.0                      # Referenz war 576 px breit: Unschaerfe-Werte umrechnen
NF = 523                           # 17,43 s
END = 470                          # ab hier schwarz

HALF = [0, 22, 60, 75, 97, 119, 141, 177, 190, 214]
CUTS = HALF + [c + 235 for c in HALF]
# Szene, Startzeit in der Quelle (s)
PLAN = [("glove_mic", 0.30), ("glove_x", 3.80), ("pink_up", 12.30), ("micsmile", 0.30), ("tank", 13.70),
        ("silver", 0.30), ("stg_red", 5.50), ("red_laugh", 8.00), ("glove_wide", 2.00), ("stg_thumb", 3.95)]
SHOTS = PLAN + PLAN                # zweite Haelfte: dieselben Clips und Momente wie in der Referenz


def shot_of(f):
    return max(i for i, c in enumerate(CUTS) if c <= f)


def shot_end(i):
    return CUTS[i + 1] if i + 1 < len(CUTS) else END


# ------------------------------------------------------------------ Uebergaenge (sigma @576 px, Helligkeit)
TR = {   # gemessen mit bandbegrenzter Schaerfe (ohne Ausrichtungsfehler); sehr starke Unschaerfe nach Augenmass
    0:   {0: (24, .80), 1: (12, .90), 2: (6, 1), 3: (3, 1), 4: (2, 1), 5: (1, 1)},
    22:  {-3: (1, .88), -2: (2.5, .73), -1: (4, .60),
          0: (8, .55), 1: (5, .57), 2: (3, .67), 3: (2, .80), 4: (1, .90), 5: (.5, .96)},
    60:  {-3: (2, .94), -2: (3, .91), -1: (4, .86), 0: (14, .95), 1: (9, 1), 2: (4, 1), 3: (3, 1), 4: (2, 1)},
    75:  {-3: (3, .96), -2: (4, .88), -1: (9, .84),
          0: (10, .58), 1: (7, .62), 2: (4, .73), 3: (3, .86), 4: (2, .96), 5: (1, 1)},
    97:  {-3: (1, .89), -2: (3, .78), -1: (5, .68),
          0: (10, .72), 1: (6, .74), 2: (4, .82), 3: (2, .92), 4: (2, 1), 5: (1, 1)},
    119: {-2: (3, 1), -1: (5, 1), 0: (11, .92), 1: (8, .94), 2: (4, .98), 3: (3, .97), 4: (2, .97)},
    141: {-3: (2, 1), -2: (4, 1), 0: (5, .72), 1: (4, .77), 2: (3, .80), 3: (2, .90)},
    177: {-3: (1, 1), -2: (2, 1), -1: (3, 1), 0: (2, .92), 1: (4, .97), 2: (4, .98), 3: (1, .97)},
    190: {-3: (0, .91), -2: (2, .82), -1: (4, .74),
          0: (21, .80), 1: (12, .80), 2: (6, .88), 3: (3, .96), 4: (2, 1), 5: (1, 1)},
    214: {-3: (1, .91), -2: (2, .84), -1: (5, .78),
          0: (16, .85), 1: (9, .90), 2: (5, .95), 3: (3, 1), 4: (2, 1), 5: (2, 1)},
    235: {-4: (0, .90), -3: (0, .88), -2: (0, .88), -1: (0, .90),
          0: (24, .95), 1: (12, .90), 2: (6, 1), 3: (3, 1), 4: (2, 1), 5: (1, 1)},
}
HBLUR = {141: .10, 142: .03}           # horizontale Wischunschaerfe nach dem Schiebe-Uebergang
WIPE = {140}                                     # Schiebe-Bild (links neu, rechts alt)
FLASH = {31, 39, 47, 54, 147, 154, 162, 169}     # dunkle Takt-Blitze

SPEC = {}
for base in (0, 235):                            # zweite Haelfte: dieselben Uebergaenge 235 Bilder spaeter
    for c, d in TR.items():
        if c in (0, 235):
            continue
        for o, v in d.items():
            SPEC[c + base + o] = v
for c in (0, 235):                               # Anfang (Einblenden) und Start der zweiten Haelfte
    for o, v in TR[c].items():
        SPEC[c + o] = v
HB = {f + b: v for f, v in HBLUR.items() for b in (0, 235)}
WP = {f + b for f in WIPE for b in (0, 235)}
FL = {f + b for f in FLASH for b in (0, 235)}

# ------------------------------------------------------------------ Kamerakurve aus der Referenz
REFP = {int(k): v for k, v in json.load(open(os.path.join(HERE, "ref_camera.json"))).items()}


def _fill(vals, cap=0.12):
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
    last = vals[idx[-1]]
    for k in range(idx[-1] + 1, n):
        out[k] = float(np.clip(last * 1.6 ** (k - idx[-1]), -cap, cap))
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
    if rng > math.log(1.40):
        L = L * (math.log(1.40) / rng)
    L = L - L.min() + math.log(1.02)
    for k in range(n):
        CURVE[c + k] = float(math.exp(L[k]))


def Z(f):
    i = shot_of(f)
    return CURVE[min(max(f, CUTS[i]), shot_end(i) - 1)]


# ------------------------------------------------------------------ Quellen
cache = {}


def crop_size(pre):
    m = re.findall(r"crop=(\d+):(\d+)", pre)
    return int(m[-1][0]), int(m[-1][1])


def load(i):
    key = (SHOTS[i][0], SHOTS[i][1])
    if key in cache:
        return cache[key]
    sc, src = SHOTS[i]
    clip, a, b, pre, _ = SCENES[sc]
    dur = (shot_end(i) - CUTS[i]) / FPS
    s = max(a, src - 0.1)
    e = min(b, src + dur + 0.3)
    vf = f"{BASE},{pre},hqdn3d=1.6:1.2:2.5:2.5,scale=in_color_matrix=bt709:in_range=tv:flags=lanczos,format=rgb24,showinfo"
    w, h = crop_size(pre)
    r = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", os.path.join(MEDIA, clip),
                        "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    arr = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w, 3)
    times = np.array([float(x) for x in re.findall(rb"pts_time:([0-9.]+)", r.stderr)][:len(arr)])
    if len(times) < len(arr):
        last = times[-1] if len(times) else 0.0
        times = np.concatenate([times, last + np.arange(1, len(arr) - len(times) + 1) / 60])
    small = np.stack([cv2.resize(cv2.cvtColor(x, cv2.COLOR_RGB2GRAY), (96, 96), interpolation=cv2.INTER_AREA)
                      for x in arr]).astype(np.float32)
    dif = np.abs(np.diff(small, axis=0)).mean(axis=(1, 2))
    keep = [0] + [k + 1 for k, dv in enumerate(dif) if dv > 0.18]
    cache[key] = dict(frames=arr[keep], times=times[keep], off=src - s, size=w)
    return cache[key]


def src_img(i, f):
    d = load(i)
    target = d["off"] + (f - CUTS[i]) / FPS
    k = int(np.argmin(np.abs(d["times"] - target)))
    return d["frames"][k]


def warp(img, size, scale, dx=0.0, interp=cv2.INTER_LANCZOS4):
    sc = W / size * scale
    cs, co = (size - 1) / 2.0, (W - 1) / 2.0
    M = np.array([[sc, 0, co + dx - sc * cs], [0, sc, co - sc * cs]], np.float32)
    return cv2.warpAffine(img, M, (W, W), flags=interp, borderMode=cv2.BORDER_REFLECT_101).astype(np.float32)


def shot_frame(i, f):
    """Bild der Szene i zum Zeitpunkt f mit Zoom und passender Bewegungsunschaerfe"""
    d = load(i)
    img = src_img(i, f)
    z = Z(f)
    c0, c1 = CUTS[i], shot_end(i)
    fa, fb = max(c0, f - 1), min(c1 - 1, f + 1)
    v = math.log(Z(fb) / Z(fa)) / max(1, fb - fa) * 0.5            # 180-Grad-Verschluss
    if abs(v) > 0.006:
        n = int(min(12, max(4, abs(v) * 160)))
        acc = np.zeros((W, W, 3), np.float32)
        for j in range(n):
            u = (j + 0.5) / n - 0.5
            acc += warp(img, d["size"], max(1.0, z * math.exp(v * u)), interp=cv2.INTER_LINEAR)
        return acc / n
    return warp(img, d["size"], z)


def render(f):
    if f >= END:
        return np.zeros((W, W, 3), np.uint8)
    i = shot_of(f)
    if f in WP:                                    # Schiebe-Bild: links neue Szene, rechts alte Szene
        old = cv2.GaussianBlur(shot_frame(i, f), (0, 0), 10 * K)
        new = shot_frame(i + 1, CUTS[i + 1]) * 0.7
        new = cv2.blur(new, (int(0.30 * W), 1))
        img = np.empty_like(old)
        img[:, :W // 2] = new[:, W // 2:]
        img[:, W // 2:] = old[:, :W - W // 2]
    else:
        img = shot_frame(i, f)
        sig, gain = SPEC.get(f, (0, 1.0))
        if sig > 0:
            img = cv2.GaussianBlur(img, (0, 0), sig * K)
        if f in HB:
            img = cv2.blur(img, (max(3, int(HB[f] * W)), 1))
        img = img * gain
        if f in FL:
            img = cv2.GaussianBlur(img, (0, 0), 3 * K) * 0.31
    img = rose_look(img)
    return np.clip(img, 0, 255).astype(np.uint8)


if __name__ == "__main__":
    os.makedirs(OUTDIR, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "frames":
        for f in map(int, sys.argv[2:]):
            cv2.imwrite(os.path.join(OUTDIR, f"preview_{f:03d}.png"), cv2.cvtColor(render(f), cv2.COLOR_RGB2BGR))
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
        enc.stdin.write(render(f).tobytes())
        if f % 60 == 0:
            print(f"frame {f}/{NF} {time.time() - t0:.0f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    print("done", OUT, round(time.time() - t0))
