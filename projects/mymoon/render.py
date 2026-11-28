#!/usr/bin/env python3
"""„my moon“-Edit mit Hyunjin und Felix (Vorlage: TikTok mit schwarz-weisser Lilie, Bildschirmaufnahme des Nutzers).

Vorlage (gemessen, Aufnahme 07832aff, Videobereich x 0-1180, y 737-1570 = Seitenverhaeltnis 1,417):
  * Hintergrund wechselt auf den Schlaegen zwischen Schwarz, Grau-Rampe und Weiss (light.json, Bild fuer Bild),
  * links wird Text getippt: graue Punkte "...", kleine schwarze Punkte, "my", "my moon", "my / moon, / my",
    danach weisse Punkte (text_fit.json: Helvetica, an jedes Wort angepasst),
  * rechts eine schwarz-weisse Lilie (blendet am Anfang ein, am Ende aus).
Wunsch des Nutzers: Licht/Farben und Text links gleich lassen, Blume weg, dafuer Hyunjin und Felix.
Umsetzung: statt der Lilie Hyunjin/Felix in kontrastreichem Schwarz-Weiss, im Lichtkegel rechts, der weich in
den Hintergrund (schwarz oder weiss) uebergeht. Schnitte auf den Schlaegen, Zeitlupe 0,5x, leichter Zoom.
Nach dem Vorlagen-Teil (bis Bild 130) Weiss-Blitze auf den drei staerksten Schlaegen, Ausblenden am Ende.

    python3 render.py            # ganzes Video
    python3 render.py frames 40 60 100 300
"""
import json, os, re, subprocess, sys, time
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
TK = os.path.join(HERE, "..", "..", "edit-toolkit")
sys.path.insert(0, TK)
sys.path.insert(0, os.path.join(HERE, "..", "beggin"))
from face_track import FaceTracker, track, smooth_track
from slowmo import resample
from dedupe import unique_indices
import typeset as T

SKZ = os.path.join(HERE, "..", "skz-material", "media")
FEL = os.path.join(HERE, "..", "felix-sorinyx", "media")
REF = os.environ.get("MYMOON_REF", os.path.join(FEL, "reference_mymoon.mov"))
OUTDIR = os.environ.get("EDIT_OUT", os.path.join(HERE, "out"))
OUT = os.path.join(OUTDIR, "Hyunjin_Felix_MyMoon_Edit.mp4")
W, H, FPS = 1440, 1016, 30
NF = 616
REF_X0, REF_Y0, REF_W = 0, 737, 1180          # Videobereich in der Aufnahme
KS = W / REF_W                                 # Aufnahme-Pixel -> Ausgabe-Pixel
FONT = "heros"                                  # Helvetica (TeX Gyre Heros), leicht schmal gezogen (sx ~0,85-0,9)

# ------------------------------------------------------------------ Quellen (volle Koordinaten 2556x1180)


def src(path, safe=None):
    return dict(path=path, safe=safe)


SRC = {
    "fx_shoot_red": src(os.path.join(FEL, "clip10.mov")),
    "fx_fur":       src(os.path.join(FEL, "clip4.mov"), (230, 0, 2326, 925)),
    "fx_selfie":    src(os.path.join(FEL, "clip12.mov"), (380, 0, 2175, 1180)),
    "fx_brick":     src(os.path.join(FEL, "clip10.mov")),
    "hj_vlog":      src(os.path.join(SKZ, "hyunjin_02.mov"), (230, 0, 2150, 1000)),
    "hj_hood":      src(os.path.join(SKZ, "hyunjin_04.mov"), (230, 0, 2030, 1180)),
    "hj_stage":     src(os.path.join(SKZ, "hyunjin_03.mov"), (470, 0, 1980, 1180)),
    "hj_mirror":    src(os.path.join(SKZ, "hyunjin_01.mov"), (346, 0, 2208, 1180)),
}

# Szenen: Schnitte auf den Schlaegen der Tonspur (beats.py). Intro = EIN Clip (Felix), dann abwechselnd.
PLAN = [
    dict(f0=0,   src="fx_shoot_red", t=6.00, who="Felix"),
    dict(f0=130, src="hj_vlog",      t=2.20, who="Hyunjin"),
    dict(f0=209, src="fx_fur",       t=4.20, who="Felix"),
    dict(f0=277, src="hj_hood",      t=4.20, who="Hyunjin"),
    dict(f0=344, src="fx_selfie",    t=3.30, who="Felix"),
    dict(f0=397, src="hj_stage",     t=0.40, who="Hyunjin"),
    dict(f0=471, src="fx_brick",     t=12.30, who="Felix"),
    dict(f0=516, src="hj_mirror",    t=2.00, who="Hyunjin"),
]
for k, sh in enumerate(PLAN):
    sh["f1"] = PLAN[k + 1]["f0"] if k + 1 < len(PLAN) else NF
    sh.setdefault("speed", 0.5)
    sh.setdefault("face_h", 0.30)          # Gesichtshoehe / Bildhoehe (Lilie fuellt rechts gut die halbe Hoehe)
    sh.setdefault("face_xy", (0.70, 0.40))  # Gesichtsmitte im Bild (rechts, wo die Lilie war)
    sh.setdefault("push", (1.0, 1.05))
MAX_UP = 1.45

# ------------------------------------------------------------------ Licht und Text der Vorlage
LIGHT = json.load(open(os.path.join(HERE, "light.json")))
BG = np.array(LIGHT["bg"], np.float32)          # Hintergrund 0..255 je Bild (Vorlage bis 139, danach schwarz)
GAIN = np.array(LIGHT["gain"], np.float32)      # Helligkeit der Person (Einblenden wie die Lilie, Ausblenden)
FLASH = [(397, 411), (471, 485), (516, 530)]     # zusaetzliche Weiss-Blitze auf den drei staerksten Schlaegen
for a, b in FLASH:
    BG[a:b] = 255.0
TEXT = json.load(open(os.path.join(HERE, "text_fit.json")))


def text_state(f):
    """Rueckgabe: Liste (Schluessel, Helligkeit 0..255, Alpha-Faktor je Punkt oder None)"""
    if f < 9:
        return []
    if f <= 73:
        # graue Punkte: der rechte erscheint zuerst (9), die anderen ab 14; Helligkeit 26 -> 53
        lum = float(np.interp(f, [9, 18, 34, 45], [26, 28, 48, 53]))
        return [("dots_grey:...", lum, (0.0 if f < 14 else min(1.0, (f - 13) / 3.0), 0.0 if f < 14 else min(1.0, (f - 13) / 3.0), 1.0))]
    if f <= 78:
        return [("dots_small:...", 2.0, None)]
    if f <= 92:
        return [("my1:my", 1.0, None)]
    if f <= 108:
        return [("my1:my", 1.0, None), ("moon1:moon", 1.0, None)]
    if f <= 121:
        return [("C:my:0", 1.0, None), ("C:moon,:1", 1.0, None), ("C:my:2", 1.0, None)]
    if f <= 126:
        return []
    lum = 0.0 if BG[f] > 128 else 255.0          # weisse Punkte auf Schwarz, schwarze auf Weiss (Blitze)
    return [("dots_white:...", lum, None)]


_text_cache = {}


def word_alpha(key, dots=None):
    """Wort in Ausgabegroesse rendern (Alpha 0..1, volle Bildgroesse)"""
    ck = (key, dots)
    if ck in _text_cache:
        return _text_cache[ck]
    q = TEXT[key]
    size = q["size"] * KS
    S = int(round(size))
    letters = None
    if dots is not None:
        letters = {i for i, v in enumerate(dots) if v > 0}
    al, ox, oy = T.render_word(q["text"], FONT, 0.0, size=S, letters=letters)
    x = (q["x"] - REF_X0) * KS
    y = (q["y"]) * KS                       # y in text_fit.json ist relativ zum Videobereich (Aufnahme-y - 737)
    a = T.place(al, ox, oy, S, size, q["sx"], x, y, 0, (H, W), base=S)
    _text_cache[ck] = a
    return a


def text_layer(f):
    """Rueckgabe: (Alpha, Helligkeit) der Schrift fuer Bild f"""
    alpha = np.zeros((H, W), np.float32)
    lum = np.zeros((H, W), np.float32)
    for key, l, dots in text_state(f):
        if dots is not None:
            a = np.zeros((H, W), np.float32)
            for i, v in enumerate(dots):
                if v > 0:
                    a = np.maximum(a, word_alpha(key, tuple(1 if j == i else 0 for j in range(3))) * v)
        else:
            a = word_alpha(key)
        lum = np.where(a > alpha, l, lum)
        alpha = np.maximum(alpha, a)
    return alpha, lum


# ------------------------------------------------------------------ Quelle laden, Gesicht verfolgen
TRACKER = None


def decode(path, s, e):
    vf = ["hqdn3d=1.2:1.0:2.0:2.0", "scale=in_color_matrix=bt709:in_range=tv", "format=rgb24", "showinfo"]
    r = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", path,
                        "-vf", ",".join(vf), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    size = re.findall(rb"s:(\d+)x(\d+)", r.stderr)
    w, h = map(int, size[-1])
    arr = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w, 3)
    times = np.array([float(x) for x in re.findall(rb"pts_time:([0-9.]+)", r.stderr)])
    n = min(len(arr), len(times))
    arr, times = arr[:n], times[:n] + s
    keep = unique_indices(arr)
    return arr[keep], times[keep]


def prepare(sh):
    global TRACKER
    s = SRC[sh["src"]]
    n = sh["f1"] - sh["f0"]
    t_out = sh["t"] + np.arange(n) / FPS * sh["speed"]
    frames, times = decode(s["path"], max(0.0, sh["t"] - 0.2), t_out[-1] + 0.25)
    use = np.where((times >= t_out[0] - 0.02) & (times <= t_out[-1] + 0.02))[0]
    if len(use) > 2:
        g = np.stack([cv2.resize(cv2.cvtColor(frames[i], cv2.COLOR_RGB2GRAY), (192, 88),
                                 interpolation=cv2.INTER_AREA).astype(np.float32) for i in use])
        dif = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))
        if dif.max() > 15:
            print(f"  ACHTUNG {sh['src']} t={sh['t']}: Schnitt/Blitz in der Quelle bei "
                  f"{times[use[int(np.argmax(dif)) + 1]]:.2f} s (Aenderung {dif.max():.0f})", flush=True)
    frames, _ = resample(frames, times, t_out)
    x0, y0, x1, y1 = s["safe"] or (230, 0, 2326, 1180)
    x0, x1 = max(x0, 230), min(x1, 2326)                 # Querformat-Video liegt bei x 230-2326
    TRACKER = TRACKER or FaceTracker()
    raw = track(list(frames), hint=((x0 + x1) / 2, y0 + (y1 - y0) * 0.4), tracker=TRACKER)
    fx, fy, _ = smooth_track(np.arange(n) / FPS, raw, sigma_s=0.30)
    found = int((~np.isnan(raw[:, 0])).sum())
    fh = float(np.nanmedian(raw[:, 2])) if found else 300.0
    # Belichtung: Gesichtsbereich (Median-Helligkeit) auf ~150 bringen - die Lilie der Vorlage leuchtet hell
    vals = []
    for k in range(0, n, max(1, n // 6)):
        gx, gy, r = int(fx[k]), int(fy[k]), int(fh * 0.35)
        g = cv2.cvtColor(frames[k], cv2.COLOR_RGB2GRAY)[max(0, gy - r):gy + r, max(0, gx - r):gx + r]
        if g.size:
            vals.append(float(np.median(g)))
    # als Gamma statt Verstaerkung: Mitten heller/dunkler, Lichter brennen nicht aus (blonde Haare!)
    med = float(np.clip((np.median(vals) if vals else 150.0) / 255.0, 0.08, 0.92))
    expo = float(np.clip(np.log(150.0 / 255.0) / np.log(med), 0.55, 1.25))
    return dict(frames=frames, fx=fx, fy=fy, fh=fh, safe=(x0, y0, x1, y1), found=found, expo=expo)


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def person(sh, d, f):
    """Person in Schwarz-Weiss (0..255) + Maske (Lichtkegel, 0..1), Ausgabegroesse"""
    k = f - sh["f0"]
    n = max(1, sh["f1"] - sh["f0"] - 1)
    z0, z1 = sh["push"]
    z = z0 + (z1 - z0) * (0.3 * (k / n) + 0.7 * ease_io(k / n))
    x0, y0, x1, y1 = d["safe"]
    ch = d["fh"] / sh["face_h"]
    ch = max(ch, H / MAX_UP)
    ch = min(ch, y1 - y0) / z
    sc = H / ch
    fxo, fyo = sh["face_xy"]
    cx = float(d["fx"][k]) - (fxo - 0.5) * W / sc          # Bildmitte so, dass das Gesicht bei fxo steht
    cy = float(d["fy"][k]) - (fyo - 0.5) * ch
    # oben/unten/rechts im erlaubten Bereich bleiben (links darf es ins Schwarze laufen - dort ist die Maske 0)
    cy = float(np.clip(cy, y0 + ch / 2, y1 - ch / 2))
    cx = min(cx, x1 - W / sc / 2)
    M = np.array([[sc, 0, W / 2 - sc * cx], [0, sc, H / 2 - sc * cy]], np.float32)
    img = d["frames"][k]
    gray = 255.0 * (cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0) ** d["expo"]
    valid = np.zeros(gray.shape, np.float32)
    valid[y0:y1, x0:x1] = 1.0
    gray = cv2.warpAffine(gray, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    valid = cv2.warpAffine(valid, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    # Lichtkegel um Kopf und Schultern, weich; links (Text) frei
    fxp = W / 2 + sc * (float(d["fx"][k]) - cx)
    fyp = H / 2 + sc * (float(d["fy"][k]) - cy)
    fhp = d["fh"] * sc
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ex = (xx - fxp) / (2.1 * fhp)
    ey = (yy - (fyp + 0.9 * fhp)) / (2.8 * fhp)
    m = np.clip(1.0 - (ex * ex + ey * ey), 0, 1) ** 0.7
    gate = np.clip((xx - 0.40 * W) / (0.17 * W), 0, 1)
    gate = gate * gate * (3 - 2 * gate)
    m = m * gate * np.clip(cv2.erode(valid, np.ones((9, 9), np.uint8)), 0, 1)
    m = cv2.GaussianBlur(m, (0, 0), 6)
    return grade_bw(gray), m


def grade_bw(g):
    """kontrastreiches Schwarz-Weiss wie die Lilie: tiefe Schwaerzen, helle Lichter, klare Details"""
    x = np.clip(g / 255.0, 0, 1)
    x = np.clip((x - 0.04) / 0.90, 0, 1) ** 1.08
    s = x * x * (3 - 2 * x)
    x = 0.45 * x + 0.55 * s
    b = cv2.GaussianBlur(x, (0, 0), 12)
    x = np.clip(x + 0.35 * (x - b), 0, 1)                   # Klarheit
    d = cv2.GaussianBlur(x, (0, 0), 1.0)
    x = np.clip(x + 0.45 * (x - d), 0, 1)                   # feine Details
    return x * 255.0


# ------------------------------------------------------------------ Bild zusammensetzen
RNG = np.random.default_rng(7)


def grain(f):
    """leichtes Filmkorn + vereinzelte Staubkoerner (wie die Staub-Struktur in der Vorlage), je 2 Bilder neu"""
    rng = np.random.default_rng(1000 + f // 2)
    n = rng.normal(0, 3.0, (H // 2, W // 2)).astype(np.float32)
    n = cv2.resize(n, (W, H), interpolation=cv2.INTER_LINEAR)
    dust = np.zeros((H, W), np.float32)
    for _ in range(rng.integers(6, 14)):
        x, y = int(rng.uniform(0, W)), int(rng.uniform(0, H))
        r = rng.uniform(0.8, 2.2)
        cv2.circle(dust, (x, y), int(round(r)), 1.0, -1, lineType=cv2.LINE_AA)
    if rng.uniform() < 0.25:                                # feiner Kratzer
        x = int(rng.uniform(0.1, 0.9) * W)
        cv2.line(dust, (x, int(rng.uniform(0, H * 0.5))), (x + int(rng.normal(0, 6)), int(rng.uniform(H * 0.5, H))),
                 0.6, 1, lineType=cv2.LINE_AA)
    return n, dust


def text_dust(f, a):
    """Staub wie in der Vorlage: kleine Flecken in den Buchstaben (Hintergrundfarbe) und Punkte daneben"""
    if a.max() < 0.5:
        return a, None
    rng = np.random.default_rng(5000 + f // 2)
    ys, xs = np.where(a > 0.5)
    holes = np.zeros_like(a)
    for _ in range(int(min(40, len(xs) / 900))):
        i = rng.integers(len(xs))
        cv2.circle(holes, (int(xs[i]), int(ys[i])), int(rng.integers(1, 3)), 1.0, -1, lineType=cv2.LINE_AA)
    if rng.uniform() < 0.35:                                # feiner senkrechter Kratzer durch einen Buchstaben
        i = rng.integers(len(xs))
        cv2.line(holes, (int(xs[i]), int(ys[i]) - 40), (int(xs[i]) + 2, int(ys[i]) + 40), 0.8, 1, lineType=cv2.LINE_AA)
    specks = np.zeros_like(a)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    for _ in range(int(rng.integers(8, 20))):
        x = int(rng.uniform(x0 - 40, x1 + 60))
        y = int(rng.uniform(y0 - 40, y1 + 60))
        cv2.circle(specks, (x, y), int(rng.integers(1, 3)), 1.0, -1, lineType=cv2.LINE_AA)
    return np.clip(a * (1 - holes) + specks * 0.8, 0, 1), True


def compose(f, p, m):
    bg = float(BG[min(f, len(BG) - 1)])
    g = float(GAIN[min(f, len(GAIN) - 1)])
    out = bg * (1 - m) + p * m * g + bg * m * (1 - g)
    a, lum = text_layer(f)
    if a.max() > 0.5:
        a2, _ = text_dust(f, a)
        lum = np.where(a2 > a, float(lum[a > 0.5].mean()), lum)
        a = a2
    out = out * (1 - a) + lum * a
    n, dust = grain(f)
    out = out + n
    dc = 0.0 if bg > 128 else 255.0
    out = out * (1 - 0.7 * dust) + dc * 0.7 * dust
    return np.clip(out, 0, 255)


def render(which=None):
    os.makedirs(OUTDIR, exist_ok=True)
    proc = None
    if which is None:
        tmp = os.path.join(OUTDIR, "_video.mp4")
        proc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}",
                                 "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "15",
                                 "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
                                 "-color_trc", "bt709", "-movflags", "+faststart", tmp], stdin=subprocess.PIPE)
    t0 = time.time()
    for sh in PLAN:
        fr = list(range(sh["f0"], sh["f1"]))
        if which is not None:
            fr = [f for f in fr if f in which]
            if not fr:
                continue
        d = prepare(sh)
        print(f"{sh['f0']:3d}-{sh['f1']:3d} {sh['who']:8s} {sh['src']:13s} Gesicht {d['found']}/{len(d['frames'])}"
              f"  Gamma {d['expo']:.2f}  {time.time() - t0:5.0f}s", flush=True)
        for f in fr:
            p, m = person(sh, d, f)
            out = compose(f, p, m).astype(np.uint8)
            if proc:
                proc.stdin.write(out.tobytes())
            else:
                cv2.imwrite(os.path.join(OUTDIR, f"frame_{f:03d}.png"), out)
        del d
    if proc:
        proc.stdin.close()
        proc.wait()
        dur = NF / FPS
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", tmp, "-i", REF, "-map", "0:v", "-map", "1:a",
                        "-af", f"atrim=0:{dur:.3f},loudnorm=I=-14:TP=-1.0:LRA=11,afade=t=out:st={dur - 0.7:.3f}:d=0.7,"
                               "aresample=48000",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", OUT],
                       check=True)
        os.remove(tmp)
        print("fertig:", OUT, f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "frames":
        render({int(x) for x in sys.argv[2:]})
    else:
        render()
