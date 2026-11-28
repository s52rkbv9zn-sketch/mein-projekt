#!/usr/bin/env python3
"""'STAYs, you have one job...'-Video (TikTok-Trend-Format), 1080x1350 (4:5 wie das Inspo-Video), 30 fps.

Aufbau (Schnitte auf dem Takt des Sounds, 92,4 BPM, Schlaege bei 0,235 + k*0,649 s):
  0     - 65   Gruppe auf der Buehne (ganzes Bild mit unscharfem Hintergrund) + "STAYs, you have one job…"
  65    - 143  alle 8 Mitglieder nacheinander, ein Schnitt pro halbem Takt (Punch-Zoom)
  143   - 221  "Like for Felix"     (2 Felix-Clips in Zeitlupe, weiche Blende auf dem Takt)
  221   - 299  "Follow for Hyunjin" (2 Hyunjin-Clips in Zeitlupe)
  299   - 364  "Comment your bias"  3x3-Raster: alle 8 Mitglieder rund um den Text
Schrift wie TikTok "Classic": TikTok Sans SemiBold, weiss mit schwarzer Kontur, Pop-in.
Ton: Sound des Inspo-Videos, auf -14 LUFS gebracht.

Aufruf:  python3 render.py   |   python3 render.py frames 10 70 150 300 340
"""
import math, os, re, subprocess, sys, time
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TK = os.path.join(HERE, "..", "..", "edit-toolkit")
FELIX = os.path.join(HERE, "..", "felix-sorinyx")
sys.path.insert(0, TK)
sys.path.insert(0, FELIX)
from scenes import SCENES                                   # Felix-Szenen
from face_track import FaceTracker, track, smooth_track
from slowmo import double_rate
from look import cc
from dedupe import unique_indices

SKZ = os.environ.get("SKZ_MEDIA", os.path.join(HERE, "..", "skz-material", "media"))
FEL = os.environ.get("EDIT_MEDIA", os.path.join(FELIX, "media"))
SOUND = os.path.join(SKZ, "inspo_stays_skip.mov")
OUTDIR = os.environ.get("EDIT_OUT", os.path.join(HERE, "out"))
OUT = os.path.join(OUTDIR, "STAYs_one_job.mp4")
FONT = os.path.join(TK, "TikTokSans-600.ttf")
W, H, FPS = 1080, 1350, 30
NF = 364

# ------------------------------------------------------------------ Quellen
FBASE = (230, 0, 2096, 1180)          # Videobereich der Felix-Bildschirmaufnahmen


def skz(name, rot=None, safe=None):
    return dict(path=os.path.join(SKZ, name), base=None, rot=rot, safe=safe)


def fel(scene, safe):
    clip, a, b, pre, _ = SCENES[scene]
    return dict(path=os.path.join(FEL, clip), base=FBASE, rot="cw" if "transpose=1" in pre else None, safe=safe)


SRC = {
    "chan_1c":   skz("bangchan_01.mov"),
    "chan_1a":   skz("bangchan_01.mov"),
    "lk_6c":     skz("leeknow_01.mov", rot="cw", safe=(0, 600, 1180, 2330)),
    "lk_6a":     skz("leeknow_01.mov", rot="cw", safe=(0, 110, 1180, 2330)),
    "cb_3b":     skz("changbin_01.mov", safe=(300, 0, 2556, 1180)),
    "cb_3a":     skz("changbin_01.mov"),
    "hj_5a":     skz("hyunjin_01.mov"),
    "hj_5b":     skz("hyunjin_01.mov", safe=(0, 0, 2556, 1020)),
    "han_7b":    skz("han_01.mov", safe=(0, 0, 1520, 980)),
    "sm_4b":     skz("seungmin_01.mov", safe=(860, 0, 2300, 1180)),
    "sm_4a":     skz("seungmin_01.mov"),
    "in_2":      skz("in_01.mov", safe=(0, 0, 2250, 1180)),
    "fx_stgred": fel("stg_red", (290, 0, 2096, 1080)),
    "fx_laugh":  fel("red_laugh", (290, 0, 2096, 1180)),
    "fx_selfie": fel("selfie", (150, 0, 1945, 1180)),
    "fx_redhair": fel("red_hair", (290, 0, 2096, 1180)),
}

# ------------------------------------------------------------------ Zeitplan
# Schlaege (Bildnummern): 7, 26, 46, 65, 85, 104, 124, 143, 163, 182, 202, 221, 241, 260, 280, 299, 319, 338, 358
MONTAGE = [65, 75, 84, 94, 104, 114, 123, 133, 143]      # halbe Takte
SHOTS = [
    # Mitglieder-Montage (Normaltempo, Punch-Zoom)
    dict(src="chan_1c", t=9.30, speed=1.0),
    dict(src="lk_6c", t=5.08, speed=1.0),
    dict(src="cb_3b", t=2.45, speed=1.0),
    dict(src="hj_5a", t=0.30, speed=1.0),
    dict(src="han_7b", t=10.55, speed=1.0),
    dict(src="fx_stgred", t=6.20, speed=1.0),
    dict(src="sm_4a", t=0.30, speed=1.0),
    dict(src="in_2", t=0.40, speed=1.0),
]
for k, sh in enumerate(SHOTS):
    sh.update(f0=MONTAGE[k], f1=MONTAGE[k + 1], punch=True, push=(1.0, 1.03), face_frac=0.27, face_y=0.38)
SHOTS += [
    dict(src="fx_laugh", t=7.85, speed=0.5, f0=143, f1=182, push=(1.0, 1.06), face_frac=0.25, face_y=0.36),
    dict(src="fx_selfie", t=3.30, speed=0.5, f0=182, f1=221, push=(1.06, 1.0), face_frac=0.30, face_y=0.40),
    dict(src="hj_5b", t=5.56, speed=0.55, f0=221, f1=260, push=(1.0, 1.06), face_frac=0.22, face_y=0.33),
    dict(src="hj_5a", t=2.60, speed=0.5, f0=260, f1=299, push=(1.0, 1.06), face_frac=0.28, face_y=0.38),
]
GRID = [  # Reihenfolge: offizielle Reihenfolge, im Uhrzeigersinn um die Mitte gelesen zeilenweise
    dict(src="chan_1a", t=0.40), dict(src="lk_6a", t=0.50), dict(src="cb_3a", t=0.60),
    dict(src="hj_5a", t=0.90), None, dict(src="han_7b", t=4.90),
    dict(src="fx_redhair", t=4.10), dict(src="sm_4b", t=6.20, face_frac=0.22), dict(src="in_2", t=1.10),
]
GRID_F0 = 299
TEXTS = [  # (von, bis, Zeilen, Mitte-y)
    (0, 65, ["STAYs, you have one job…"], 285),
    (143, 221, ["Like for Felix"], 810),
    (221, 299, ["Follow for Hyunjin"], 810),
]
SECTION_CUTS = [65, 143, 221]                 # Zoom-Unschaerfe + Blitz
DISSOLVES = [182, 260]                        # weiche Blende im Abschnitt
PULSES = [163, 202, 241, 280]                 # kleiner Zoom-Puls auf dem Takt
TEXT_PULSES = [319, 338, 358]

# ------------------------------------------------------------------ Dekodieren + Gesicht verfolgen
TRACKER = None


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def decode(src, s, e, scale=1.0):
    vf = []
    if src["base"]:
        x, y, w, h = src["base"]
        vf.append(f"crop={w}:{h}:{x}:{y}")
    if src["rot"] == "cw":
        vf.append("transpose=1")
    vf.append("hqdn3d=1.4:1.0:2.2:2.2")
    if scale != 1.0:
        vf.append(f"scale=iw*{scale}:-2:flags=lanczos")
    vf += ["scale=in_color_matrix=bt709:in_range=tv", "format=rgb24", "showinfo"]
    r = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", src["path"],
                        "-vf", ",".join(vf), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    size = re.findall(rb"s:(\d+)x(\d+)", r.stderr)
    w, h = map(int, size[-1])
    arr = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w, 3)
    times = np.array([float(x) for x in re.findall(rb"pts_time:([0-9.]+)", r.stderr)])
    n = min(len(arr), len(times))
    arr, times = arr[:n], times[:n] + s
    keep = unique_indices(arr)
    return arr[keep], times[keep]


def content_box(frames, thr=14):
    g = np.stack([cv2.cvtColor(f[::4, ::4], cv2.COLOR_RGB2GRAY) for f in frames[:: max(1, len(frames) // 6)]])
    m = g.mean(0) > thr
    cols = np.where(m.mean(0) > 0.3)[0]
    rows = np.where(m.mean(1) > 0.3)[0]
    return cols.min() * 4, rows.min() * 4, (cols.max() + 1) * 4, (rows.max() + 1) * 4


def prepare(sh, nframes, scale=1.0):
    """Quelle laden, Zeitlupe vorbereiten, Gesicht verfolgen"""
    global TRACKER
    src = SRC[sh["src"]]
    need = nframes / FPS * sh["speed"]
    s = max(0.0, sh["t"] - 0.15)
    frames, times = decode(src, s, sh["t"] + need + 0.2, scale)
    fps = 1.0 / float(np.median(np.diff(times))) if len(times) > 2 else 60.0
    if fps < 45 and sh["speed"] < 0.8:
        frames, times = double_rate(frames, times)
    bx = content_box(frames)
    if src["safe"]:
        sx0, sy0, sx1, sy1 = (int(v * scale) for v in src["safe"])
        bx = (max(bx[0], sx0), max(bx[1], sy0), min(bx[2], sx1), min(bx[3], sy1))
    TRACKER = TRACKER or FaceTracker()
    hint = ((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) * 0.4)
    raw = track(list(frames), hint=hint, tracker=TRACKER)
    fx, fy, fh = smooth_track(times, raw, sigma_s=0.10)
    return dict(frames=frames, times=times, fx=fx, fy=fy, fh=float(np.nanmedian(raw[:, 2])), box=bx,
                found=int((~np.isnan(raw[:, 0])).sum()))


def crop_frame(d, ts, out_w, out_h, face_frac, face_y, zoom, interp=cv2.INTER_LANCZOS4):
    k = int(np.argmin(np.abs(d["times"] - ts)))
    x0, y0, x1, y1 = d["box"]
    ch = d["fh"] / face_frac
    ch = min(ch, y1 - y0, (x1 - x0) * out_h / out_w)
    ch = ch / zoom
    cw = ch * out_w / out_h
    cx = float(np.clip(d["fx"][k], x0 + cw / 2, x1 - cw / 2))
    cy = float(np.clip(d["fy"][k] + (0.5 - face_y) * ch, y0 + ch / 2, y1 - ch / 2))
    sc = out_h / ch
    M = np.array([[sc, 0, out_w / 2 - sc * cx], [0, sc, out_h / 2 - sc * cy]], np.float32)
    return cv2.warpAffine(d["frames"][k], M, (out_w, out_h), flags=interp,
                          borderMode=cv2.BORDER_REFLECT_101).astype(np.float32)


def shot_zoom(sh, f):
    n = max(1, sh["f1"] - sh["f0"] - 1)
    z0, z1 = sh["push"]
    z = z0 + (z1 - z0) * min(max((f - sh["f0"]) / n, 0), 1)
    if sh.get("punch") and sh["f0"] <= f < sh["f0"] + 6:
        z *= 1 + 0.13 * (1 - ease((f - sh["f0"]) / 5))
    for p in PULSES:
        if p <= f < p + 5:
            z *= 1 + 0.035 * (1 - ease((f - p) / 4))
    return z


def render_shot_frame(sh, d, f):
    ts = sh["t"] + (f - sh["f0"]) / FPS * sh["speed"]
    z = shot_zoom(sh, f)
    if sh.get("punch") and sh["f0"] <= f < sh["f0"] + 2:          # Zoom-Unschaerfe im Punch
        z2 = shot_zoom(sh, f + 1)
        acc = np.zeros((H, W, 3), np.float32)
        for j in range(6):
            zz = z + (z2 - z) * (j / 5) * 1.6
            acc += crop_frame(d, ts, W, H, sh["face_frac"], sh["face_y"], zz, cv2.INTER_LINEAR)
        return acc / 6
    return crop_frame(d, ts, W, H, sh["face_frac"], sh["face_y"], z)


# ------------------------------------------------------------------ Gruppe (Intro) und Raster
GROUP = os.path.join(SKZ, "gruppe_buehne_01.mov")
GROUP_BOX = (520, 40, 1900, 1046)            # Gruppe (Gesichter x 714-1714) mit Rand
INTRO_T = 7.0


def group_frames():
    src = dict(path=GROUP, base=None, rot=None, safe=None)
    frames, times = decode(src, INTRO_T, INTRO_T + 65 / FPS + 0.2)
    x0, y0, x1, y1 = GROUP_BOX
    return [f[y0:y1, x0:x1] for f in frames], times


def intro_frame(gf, gt, f):
    k = int(np.argmin(np.abs(gt - (INTRO_T + f / FPS))))
    src = gf[k]
    h, w = src.shape[:2]
    # Hintergrund: bildfuellend, stark weichgezeichnet und abgedunkelt
    s = H / h
    bg = cv2.resize(src, (int(w * s), H), interpolation=cv2.INTER_AREA)
    xo = (bg.shape[1] - W) // 2
    bg = cv2.GaussianBlur(bg[:, xo:xo + W].astype(np.float32), (0, 0), 30) * 0.5
    # Vordergrund: ganzes Bild, langsamer Zoom
    z = 1.0 + 0.05 * f / 65
    fw = W
    fh = int(round(h * W / w))
    fg = cv2.resize(src, (int(fw * z), int(fh * z)), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    cx, cy = fg.shape[1] // 2, fg.shape[0] // 2
    fg = fg[cy - fh // 2:cy - fh // 2 + fh, cx - fw // 2:cx - fw // 2 + fw]
    y0 = 790 - fh // 2
    out = bg.copy()
    out[y0:y0 + fh] = fg
    # weicher Uebergang an den Kanten des Bandes
    for i in range(14):
        a = (i + 1) / 15
        out[y0 + i] = fg[i] * a + bg[y0 + i] * (1 - a)
        out[y0 + fh - 1 - i] = fg[fh - 1 - i] * a + bg[y0 + fh - 1 - i] * (1 - a)
    return out


CELL_W, CELL_H, GUT = 360, 450, 3


def build_grid():
    """Bilder aller 8 Rasterzellen vorberechnen (kleine Aufloesung spart Speicher)"""
    n = NF - GRID_F0 + 1
    cells = []
    for g in GRID:
        if g is None:
            cells.append(None)
            continue
        sh = dict(src=g["src"], t=g["t"], speed=0.5)
        d = prepare(sh, n, scale=0.6)
        tiles = []
        for k in range(n):
            ts = g["t"] + k / FPS * 0.5
            z = 1.0 + 0.05 * k / n
            tiles.append(crop_frame(d, ts, CELL_W - 2 * GUT, CELL_H - 2 * GUT, g.get("face_frac", 0.30), 0.40, z).astype(np.uint8))
        cells.append(tiles)
        print(f"  Rasterzelle {g['src']}: Gesicht in {d['found']}/{len(d['frames'])} Bildern", flush=True)
        del d
    return cells


def grid_frame(cells, center_bg, f):
    out = np.zeros((H, W, 3), np.float32)
    k = f - GRID_F0
    order = [0, 1, 2, 3, 5, 6, 7, 8]                          # Aufbau in offizieller Reihenfolge
    for idx, tiles in enumerate(cells):
        r, c = divmod(idx, 3)
        x0, y0 = c * CELL_W + GUT, r * CELL_H + GUT
        if tiles is None:
            out[y0:y0 + CELL_H - 2 * GUT, x0:x0 + CELL_W - 2 * GUT] = center_bg
            continue
        start = 2 + 2 * order.index(idx)
        d = k - start
        if d < 0:
            continue
        tile = tiles[min(k, len(tiles) - 1)].astype(np.float32)
        a = min(1.0, (d + 1) / 3)
        s = 0.82 + 0.18 * ease(d / 4)
        th, tw = tile.shape[:2]
        if s < 0.999:
            M = cv2.getRotationMatrix2D((tw / 2, th / 2), 0, s)
            tile = cv2.warpAffine(tile, M, (tw, th), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
        region = out[y0:y0 + th, x0:x0 + tw]
        out[y0:y0 + th, x0:x0 + tw] = region * (1 - a) + tile * a
    return out


# ------------------------------------------------------------------ Text (TikTok-Stil)
def text_layer(lines, size=54, stroke=3):
    font = ImageFont.truetype(FONT, size)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    boxes = [tmp.textbbox((0, 0), ln, font=font, stroke_width=stroke) for ln in lines]
    lh = int(size * 1.18)
    w = max(b[2] - b[0] for b in boxes) + 20
    h = lh * len(lines) + 20
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, (ln, b) in enumerate(zip(lines, boxes)):
        x = (w - (b[2] - b[0])) / 2 - b[0]
        d.text((x, 10 + i * lh), ln, font=font, fill=(255, 255, 255, 255), stroke_width=stroke,
               stroke_fill=(0, 0, 0, 235))
    return np.array(img).astype(np.float32)


TEXT_CACHE = {}


def draw_text(img, lines, cy, d, pulse=1.0):
    key = tuple(lines)
    if key not in TEXT_CACHE:
        TEXT_CACHE[key] = text_layer(lines)
    t = TEXT_CACHE[key]
    if d < 0:
        return img
    a = min(1.0, (d + 1) / 3)
    s = (0.86 + 0.2 * ease(d / 3)) if d < 3 else (1.06 - 0.06 * ease((d - 3) / 3))
    s *= pulse
    th, tw = t.shape[:2]
    M = np.array([[s, 0, W / 2 - s * tw / 2], [0, s, cy - s * th / 2]], np.float32)
    lay = cv2.warpAffine(t, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    al = lay[..., 3:4] / 255.0 * a
    return img * (1 - al) + lay[..., :3] * al


# ------------------------------------------------------------------ Effekte
def zoom_blur(img, amount, n=7):
    if amount <= 0.002:
        return img
    acc = np.zeros_like(img)
    for j in range(n):
        s = 1 + amount * j / (n - 1)
        M = cv2.getRotationMatrix2D((W / 2, H / 2), 0, s)
        acc += cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return acc / n


def grade(img):
    return cc(img, sat=1.10, clarity=0.18, detail=0.25, bloom=0.06)


# ------------------------------------------------------------------ Bild fuer Bild
STATE = dict(shots={}, group=None, grid=None, center=None)


def shot_data(i):
    if i not in STATE["shots"]:
        sh = SHOTS[i]
        d = prepare(sh, sh["f1"] - sh["f0"] + 8)
        STATE["shots"][i] = d
        print(f"  {sh['src']}: Gesicht in {d['found']}/{len(d['frames'])} Bildern", flush=True)
    for k in list(STATE["shots"]):
        if k < i - 1:
            del STATE["shots"][k]
    return STATE["shots"][i]


def shot_index(f):
    for i, sh in enumerate(SHOTS):
        if sh["f0"] <= f < sh["f1"]:
            return i
    return None


def base_frame(f):
    if f < 65:
        if STATE["group"] is None:
            STATE["group"] = group_frames()
        return intro_frame(*STATE["group"], f)
    if f >= GRID_F0:
        if STATE["grid"] is None:
            STATE["shots"].clear()
            STATE["grid"] = build_grid()
            gf, gt = STATE["group"] if STATE["group"] else group_frames()
            cb = cv2.resize(gf[len(gf) // 2], (CELL_W - 2 * GUT, CELL_H - 2 * GUT), interpolation=cv2.INTER_AREA)
            STATE["center"] = cv2.GaussianBlur(cb.astype(np.float32), (0, 0), 12) * 0.35
        return grid_frame(STATE["grid"], STATE["center"], f)
    i = shot_index(f)
    sh = SHOTS[i]
    img = render_shot_frame(sh, shot_data(i), f)
    for c in DISSOLVES:                                     # weiche Blende ueber 4 Bilder
        if c - 2 <= f < c + 2:
            a = (f - (c - 2) + 0.5) / 4
            j = shot_index(c)
            other = render_shot_frame(SHOTS[j], shot_data(j), f) if f < c else \
                render_shot_frame(SHOTS[j - 1], shot_data(j - 1), f)
            img = img * (1 - a) + other * a if f < c else other * (1 - a) + img * a
    return img


def render(f):
    img = base_frame(f)
    for c in SECTION_CUTS:                                  # Zoom-Unschaerfe + Blitz an den Abschnitten
        if f in (c - 2, c - 1):
            img = zoom_blur(img, 0.07 if f == c - 2 else 0.16)
        if c <= f < c + 3:
            img = zoom_blur(img, (0.14, 0.07, 0.02)[f - c])
            img = img + 255 * (0.30, 0.12, 0.04)[f - c]
    if f == GRID_F0:
        img = img + 255 * 0.25
    img = grade(img)
    for (a, b, lines, cy) in TEXTS:
        if a <= f < b:
            img = draw_text(img, lines, cy, f - a)
    if f >= GRID_F0:
        pulse = 1.0
        for p in TEXT_PULSES:
            if p <= f < p + 5:
                pulse = 1 + 0.06 * (1 - ease((f - p) / 4))
        img = draw_text(img, ["Comment", "your bias"], H / 2, f - GRID_F0, pulse)
    return np.clip(img, 0, 255).astype(np.uint8)


if __name__ == "__main__":
    os.makedirs(OUTDIR, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "frames":
        for f in sorted(map(int, sys.argv[2:])):
            cv2.imwrite(os.path.join(OUTDIR, f"preview_{f:03d}.png"), cv2.cvtColor(render(f), cv2.COLOR_RGB2BGR))
        sys.exit(0)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", SOUND, "-map", "0:v", "-map", "1:a",
         "-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=lanczos,format=yuv420p",
         "-c:v", "libx264", "-preset", "slow", "-tune", "film", "-crf", "15", "-profile:v", "high", "-level", "4.1",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
         "-af", f"loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=out:st={NF / FPS - 0.25:.3f}:d=0.25",
         "-c:a", "aac", "-b:a", "256k", "-ar", "44100", "-movflags", "+faststart", "-t", f"{NF / FPS:.3f}", OUT],
        stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(NF):
        enc.stdin.write(render(f).tobytes())
        if f % 30 == 0:
            print(f"Bild {f}/{NF} {time.time() - t0:.0f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    print("fertig", OUT, round(time.time() - t0))
