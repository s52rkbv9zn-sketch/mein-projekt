#!/usr/bin/env python3
"""'home.'-Edit nach Referenz 3 (@dohwxn) mit eigenen Clips.

Aufbau der Referenz (30 fps, Bildnummern = t*30):
  * 14 harte Schnitte genau auf der Musik: CUTS
  * ganzes Video ruckelt absichtlich: neues Bild nur alle 3-4 Bilder
    (globales Raster: floor(k*3.54 + 1.75) -> 8,47 Bilder/s), Schnitte liegen ausserhalb des Rasters
  * warmer, weicher Erinnerungs-Look (edit-toolkit/home_look.py)
  * Bild 546-549: Lichtblitz / Doppelbelichtung (heller, blaeulicher, nach oben versetzter Geist)
  * ab Bild 670: letzter Clip als quadratisches Foto (70 % der Bildhoehe) mittig auf dunklem Grund
  * ab Bild 780: schwarz (Referenz zeigt dort den TikTok-Abspann), Musik klingt aus
  * optional Schriftzug (Referenz: "home." in hellem Lila, mittig) -> HOME_TEXT

Aufruf:
  python3 render.py                    -> ganzes Video nach out/home_edit.mp4
  python3 render.py frames 0 300 700   -> Vorschaubilder
Szenen: shots.py (SHOTS-Liste), Medien in media/ (siehe media.md)
"""
import math, os, re, subprocess, sys, time
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLKIT = os.path.join(HERE, "..", "..", "edit-toolkit")
sys.path.insert(0, TOOLKIT)
sys.path.insert(0, HERE)
from home_look import home_look
from shots import SHOTS, MEDIA_DIR

REF = os.environ.get("HOME_REF", os.path.join(MEDIA_DIR, "reference_home.mp4"))
OUTDIR = os.environ.get("EDIT_OUT", os.path.join(HERE, "out"))
OUT = os.path.join(OUTDIR, "home_edit.mp4")
TEXT = os.environ.get("HOME_TEXT", "")          # "" = ohne Schrift (Standard-Regel des Nutzers)
FONT = os.path.join(TOOLKIT, "PlayfairDisplay-Italic.ttf")

W, H, FPS = 1440, 1080, 30
CUTS = [0, 52, 103, 155, 227, 286, 322, 352, 407, 462, 521, 556, 597, 670]
CONTENT_END = 780
NF = 820
FLASH = {546: 1.0, 547: 0.95, 548: 0.9, 549: 0.8}
POLAROID_FROM = 670
POST_P, POST_PHI = 3.54, 1.75

assert len(SHOTS) == len(CUTS), (len(SHOTS), len(CUTS))
GRID = sorted(set(int(math.floor(k * POST_P + POST_PHI)) for k in range(int(NF / POST_P) + 2)) | set(CUTS))


def shot_index(f):
    return max(i for i, c in enumerate(CUTS) if c <= f)


def update_frame(f):
    """Bild, dessen Inhalt gerade gezeigt wird (Ruckel-Raster wie in der Referenz)."""
    c = CUTS[shot_index(f)]
    return max(u for u in GRID if c <= u <= f)


# ------------------------------------------------------------------ Quellen dekodieren
cache = {}


def load(i):
    if i in cache:
        return cache[i]
    sh = SHOTS[i]
    f0 = CUTS[i]
    f1 = CUTS[i + 1] if i + 1 < len(CUTS) else CONTENT_END
    dur = (f1 - f0) / FPS * sh.get("speed", 1.0)
    s = max(0.0, sh["t"] - 0.05)
    vf = sh["vf"] + f",scale={sh.get('size', (W, H))[0]}:{sh.get('size', (W, H))[1]}:flags=lanczos," \
         "format=rgb24,showinfo"
    cmd = ["ffmpeg", "-v", "info", "-ss", f"{s:.3f}", "-t", f"{dur + 0.3:.3f}", "-i",
           os.path.join(MEDIA_DIR, sh["clip"]), "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    r = subprocess.run(cmd, capture_output=True)
    w, h = sh.get("size", (W, H))
    arr = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w, 3)
    times = np.array([float(x) for x in re.findall(rb"pts_time:([0-9.]+)", r.stderr)][:len(arr)])
    if len(times) < len(arr):
        times = np.concatenate([times, (times[-1] if len(times) else 0) + np.arange(1, len(arr) - len(times) + 1) / 60])
    # doppelte Bilder (Bildschirmaufnahme) entfernen
    small = np.stack([cv2.resize(cv2.cvtColor(x, cv2.COLOR_RGB2GRAY), (96, 72)) for x in arr]).astype(np.float32)
    dif = np.abs(np.diff(small, axis=0)).mean(axis=(1, 2))
    keep = [0] + [k + 1 for k, dv in enumerate(dif) if dv > 0.18]
    cache[i] = dict(frames=arr[keep], times=times[keep], off=sh["t"] - s)
    return cache[i]


def src_image(i, f):
    d = load(i)
    u = update_frame(f)
    target = d["off"] + (u - CUTS[i]) / FPS * SHOTS[i].get("speed", 1.0)
    k = int(np.argmin(np.abs(d["times"] - target)))
    return d["frames"][k].astype(np.float32)


# ------------------------------------------------------------------ Bausteine
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)


def text_layer():
    if not TEXT:
        return None
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    size = int(H * 0.115)
    f = ImageFont.truetype(FONT, size)
    tw = d.textlength(TEXT, font=f)
    asc, desc = f.getmetrics()
    x = (W - tw) / 2
    y = H * 0.5 - (asc + desc) * 0.55
    d.text((x, y), TEXT, font=f, fill=(232, 206, 238, 235))
    # leicht kursiver Schwung wie in der Referenz (zusaetzliche Neigung)
    a = np.array(img).astype(np.float32)
    shear = 0.12
    M = np.array([[1, -shear, shear * H * 0.5], [0, 1, 0]], np.float32)
    a = cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_CUBIC)
    glow = cv2.GaussianBlur(a[..., 3], (0, 0), 6) * 0.25
    alpha = np.clip(a[..., 3] / 255 + glow / 255, 0, 1)[..., None]
    return a[..., :3], alpha


TEXT_LAYER = None


def polaroid(photo):
    """Foto quadratisch, 70 % der Bildhoehe, mittig auf dunklem Grund mit weichem Schatten."""
    S = int(H * 0.70)
    p = cv2.resize(photo, (S, S), interpolation=cv2.INTER_AREA)
    bg = np.full((H, W, 3), 21, np.float32)
    rr = np.sqrt(((XX - W / 2) / (W / 2)) ** 2 + ((YY - H / 2) / (H / 2)) ** 2)
    bg *= (1 - 0.35 * np.clip(rr - 0.3, 0, 1))[..., None]
    x0, y0 = (W - S) // 2, (H - S) // 2
    sh = np.zeros((H, W), np.float32)
    sh[y0:y0 + S, x0:x0 + S] = 1
    sh = cv2.GaussianBlur(sh, (0, 0), 14)
    bg *= (1 - 0.55 * sh)[..., None]
    bg[y0:y0 + S, x0:x0 + S] = p
    return bg


def flash(img, amt):
    """Doppelbelichtung: heller, blaeulicher Geist, ~10 % nach oben versetzt."""
    M = np.array([[1.03, 0, -0.015 * W], [0, 1.03, -0.12 * H]], np.float32)
    ghost = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT_101)
    gy = (ghost[..., 0] * 0.2126 + ghost[..., 1] * 0.7152 + ghost[..., 2] * 0.0722)[..., None]
    ghost = (gy * 0.6 + ghost * 0.4) * np.array([0.92, 0.98, 1.10], np.float32) + 40
    a = 0.45 * amt
    out = 255 - (255 - img) * (255 - ghost * a) / 255
    return out * (1 - 0.08 * amt) + 18 * amt


# ------------------------------------------------------------------ Bild berechnen
def render(f):
    global TEXT_LAYER
    if f >= CONTENT_END:
        return np.zeros((H, W, 3), np.uint8)
    i = shot_index(f)
    img = src_image(i, f)
    img = home_look(img, **SHOTS[i].get("look", {}))
    if f in FLASH:
        img = flash(img, FLASH[f])
    if f >= POLAROID_FROM:
        img = polaroid(img)
    elif TEXT:
        if TEXT_LAYER is None:
            TEXT_LAYER = text_layer()
        rgb, al = TEXT_LAYER
        img = img * (1 - al) + rgb * al
    return np.clip(img, 0, 255).astype(np.uint8)


if __name__ == "__main__":
    os.makedirs(OUTDIR, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "frames":
        for f in map(int, sys.argv[2:]):
            cv2.imwrite(os.path.join(OUTDIR, f"preview_{f:03d}.png"), cv2.cvtColor(render(f), cv2.COLOR_RGB2BGR))
        sys.exit(0)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-ss", "0", "-t", f"{NF / FPS}", "-i", REF, "-map", "0:v", "-map", "1:a",
         "-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=lanczos,format=yuv420p",
         "-c:v", "libx264", "-preset", "slow", "-tune", "film", "-crf", "15", "-profile:v", "high", "-level", "4.1",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
         "-af", f"afade=t=out:st={NF / FPS - 0.6:.2f}:d=0.6", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
         "-t", f"{NF / FPS}", OUT], stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(NF):
        i = shot_index(min(f, CONTENT_END - 1))
        for k in list(cache):
            if k < i:
                del cache[k]
        enc.stdin.write(render(f).tobytes())
        if f % 60 == 0:
            print(f"frame {f}/{NF} shot {i} {time.time() - t0:.0f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    print("done", OUT, round(time.time() - t0))
