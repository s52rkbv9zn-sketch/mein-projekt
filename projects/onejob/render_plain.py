#!/usr/bin/env python3
"""'STAYs, you have one job...' - schlichte Version (Wunsch des Nutzers):
keine Effekte (kein Zoom, keine Unschaerfe, keine Blitze, kein Pop-in, kein Farbfilter, keine Zeitlupe),
keine schnelle Folge aller 8 Mitglieder. Harte Schnitte auf dem Takt, Text ruhig eingeblendet, 12,1 s.

  0   - 84   Gruppe auf der Buehne      "STAYs, you have one job…"
  84  - 182  Felix (2 Clips, Schnitt auf dem Takt bei 143)   "Like for Felix"
  182 - 279  Hyunjin                     "Follow for Hyunjin"
  279 - 364  Gruppe (anderer Moment)     "Comment your bias"

Aufruf:  python3 render_plain.py   |   python3 render_plain.py frames 40 120 200 320
"""
import os, subprocess, sys, time
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv_backup = list(sys.argv)
sys.argv = [sys.argv[0]]
import render as R                      # Hilfsfunktionen (Dekodieren, Gesicht, Ausschnitt, Text)
sys.argv = sys.argv_backup

W, H, FPS, NF = R.W, R.H, R.FPS, 364
OUT = os.path.join(R.OUTDIR, "STAYs_one_job_v2.mp4")

SEGS = [
    dict(kind="group", f0=0, f1=84, t=7.0),
    dict(kind="shot", src="fx_laugh", t=7.80, f0=84, f1=143, face_frac=0.25, face_y=0.36),
    dict(kind="shot", src="fx_selfie", t=4.10, f0=143, f1=182, face_frac=0.30, face_y=0.40),
    dict(kind="shot", src="hj_5a", t=2.00, f0=182, f1=279, face_frac=0.28, face_y=0.38),
    dict(kind="group", f0=279, f1=364, t=2.0),
]
TEXTS = [
    (0, 84, ["STAYs, you have one job…"], 285),
    (84, 182, ["Like for Felix"], 730),
    (182, 279, ["Follow for Hyunjin"], 730),
    (279, 364, ["Comment your bias"], 285),
]

CACHE = {}


def seg_of(f):
    for i, s in enumerate(SEGS):
        if s["f0"] <= f < s["f1"]:
            return i
    return len(SEGS) - 1


def group_data(seg):
    src = dict(path=R.GROUP, base=None, rot=None, safe=None)
    frames, times = R.decode(src, seg["t"], seg["t"] + (seg["f1"] - seg["f0"]) / FPS + 0.2)
    x0, y0, x1, y1 = R.GROUP_BOX
    return [f[y0:y1, x0:x1] for f in frames], times


def group_frame(gf, gt, ts):
    """ganzes Gruppenbild in der Mitte, Rand oben/unten mit weichgezeichnetem Bild gefuellt (ruhig, ohne Zoom)"""
    k = int(np.argmin(np.abs(gt - ts)))
    src = gf[k]
    h, w = src.shape[:2]
    s = H / h
    bg = cv2.resize(src, (int(w * s), H), interpolation=cv2.INTER_AREA)
    xo = (bg.shape[1] - W) // 2
    bg = cv2.GaussianBlur(bg[:, xo:xo + W].astype(np.float32), (0, 0), 30) * 0.5
    fh = int(round(h * W / w))
    fg = cv2.resize(src, (W, fh), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    y0 = 790 - fh // 2
    out = bg.copy()
    out[y0:y0 + fh] = fg
    for i in range(14):
        a = (i + 1) / 15
        out[y0 + i] = fg[i] * a + bg[y0 + i] * (1 - a)
        out[y0 + fh - 1 - i] = fg[fh - 1 - i] * a + bg[y0 + fh - 1 - i] * (1 - a)
    return out


def data(i):
    if i not in CACHE:
        seg = SEGS[i]
        if seg["kind"] == "group":
            CACHE[i] = group_data(seg)
        else:
            sh = dict(src=seg["src"], t=seg["t"], speed=1.0)
            d = R.prepare(sh, seg["f1"] - seg["f0"] + 2)
            print(f"  {seg['src']}: Gesicht in {d['found']}/{len(d['frames'])} Bildern", flush=True)
            CACHE[i] = d
    for k in list(CACHE):
        if k < i:
            del CACHE[k]
    return CACHE[i]


def static_text(img, lines, cy):
    key = tuple(lines)
    if key not in R.TEXT_CACHE:
        R.TEXT_CACHE[key] = R.text_layer(lines)
    t = R.TEXT_CACHE[key]
    th, tw = t.shape[:2]
    x0, y0 = int(round(W / 2 - tw / 2)), int(round(cy - th / 2))
    al = t[..., 3:4] / 255.0
    region = img[y0:y0 + th, x0:x0 + tw]
    img[y0:y0 + th, x0:x0 + tw] = region * (1 - al) + t[..., :3] * al
    return img


def render(f):
    i = seg_of(f)
    seg = SEGS[i]
    ts = seg["t"] + (f - seg["f0"]) / FPS
    if seg["kind"] == "group":
        img = group_frame(*data(i), ts)
    else:
        img = R.crop_frame(data(i), ts, W, H, seg["face_frac"], seg["face_y"], 1.0)
    for a, b, lines, cy in TEXTS:
        if a <= f < b:
            img = static_text(img, lines, cy)
    return np.clip(img, 0, 255).astype(np.uint8)


if __name__ == "__main__":
    os.makedirs(R.OUTDIR, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "frames":
        for f in sorted(map(int, sys.argv[2:])):
            cv2.imwrite(os.path.join(R.OUTDIR, f"plain_{f:03d}.png"), cv2.cvtColor(render(f), cv2.COLOR_RGB2BGR))
        sys.exit(0)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", R.SOUND, "-map", "0:v", "-map", "1:a",
         "-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=lanczos,format=yuv420p",
         "-c:v", "libx264", "-preset", "slow", "-tune", "film", "-crf", "15", "-profile:v", "high", "-level", "4.1",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
         "-af", f"loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=out:st={NF / FPS - 0.25:.3f}:d=0.25",
         "-c:a", "aac", "-b:a", "256k", "-ar", "44100", "-movflags", "+faststart", "-t", f"{NF / FPS:.3f}", OUT],
        stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(NF):
        enc.stdin.write(render(f).tobytes())
        if f % 60 == 0:
            print(f"Bild {f}/{NF} {time.time() - t0:.0f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    print("fertig", OUT, round(time.time() - t0))
