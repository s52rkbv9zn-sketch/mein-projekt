#!/usr/bin/env python3
"""Gleicht die Unschaerfe-Staerken der Uebergaenge (hb, vb, sig, zb) Bild fuer Bild an das Vorbild an.

Mass: Schaerfe = Energie der feinen Details (Graustufen 512x288, Bild minus Gauss 1,5), ohne Raender,
TikTok-Zeichen und Schrift des Vorbilds. Ziel je Uebergangsbild: Verhaeltnis Schaerfe(Bild) / Schaerfe
(ruhige Bilder derselben Szene) wie im Vorbild. Fuer das eigene Bild wird dasselbe Bild ohne Effekte als
Bezug genommen (Ringe zaehlen nicht mit). Suche per Halbierung im log-Bereich. Ergebnis: fx_cal.json (render.py laedt es).

    NO_CAL=1 python3 calibrate.py
"""
import json, math, os, sys, time
import numpy as np
import cv2

os.environ["NO_CAL"] = "1"
sys.argv_orig = list(sys.argv)
sys.argv = [sys.argv[0]]
import render as R

M = np.zeros((288, 512), bool)
M[10:278, 10:502] = True
M[:38, :65] = False          # TikTok-Zeichen oben links
M[235:, 440:] = False        # TikTok-Zeichen unten rechts
M[235:282, 185:330] = False  # Schrift des Editors unten Mitte


def sharp(img):
    g = cv2.cvtColor(cv2.resize(np.clip(img, 0, 255).astype(np.uint8), (512, 288), interpolation=cv2.INTER_AREA),
                     cv2.COLOR_RGB2GRAY).astype(np.float32)
    hp = g - cv2.GaussianBlur(g, (0, 0), 1.5)
    return float(np.mean(hp[M] ** 2))


ref = R.ref_frames()
RS = {f: sharp(ref[f]) for f in range(R.NF)}


def ref_ratio(f):
    i = R.seg_of(f)
    a, b = R.CUTS[i], R.seg_end(i)
    body = [g for g in range(a + 3, b - 3) if g not in R.FX] or list(range(a, b))
    return RS[f] / float(np.median([RS[g] for g in body]))


RANGE = {"hb": (0.002, 1.5), "vb": (0.002, 1.5), "sig": (0.3, 80.0), "zb": (0.01, 1.2)}
# optional: nur bestimmte Bilder neu messen (python3 calibrate.py 371 372 ...), Rest bleibt erhalten
only = [int(x) for x in sys.argv_orig[1:]] if len(sys.argv_orig) > 1 else None
cal = json.load(open(R.CAL_FILE)) if (only and os.path.exists(R.CAL_FILE)) else {}
frames = sorted(f for f, s in R.FX.items() if any(k in s for k in R.BLUR_KEYS) and (not only or f in only))
t0 = time.time()


def search(f, i, can, s0, spec, kind, target):
    """Staerke von kind so, dass Schaerfe(Bild)/s0 = target. None = nicht erreichbar."""
    def ratio(p):
        sp = dict(spec)
        sp[kind] = p
        return sharp(R.finish(R.apply_fx(can, i, sp))) / s0
    if ratio(0.0) <= target:
        return 0.0
    lo, hi = math.log(RANGE[kind][0]), math.log(RANGE[kind][1])
    for _ in range(9):
        mid = (lo + hi) / 2
        if ratio(math.exp(mid)) > target:
            lo = mid
        else:
            hi = mid
    val = math.exp((lo + hi) / 2)
    return None if val > 0.9 * RANGE[kind][1] else val


CAP = {"hb": 0.15, "vb": 0.15, "zb": 0.6}      # darueber: Wisch begrenzen, Rest per Gauss
for f in frames:
    R.release(f)
    spec = {k: v for k, v in R.FX[f].items() if k != "ring"}     # Ringe zaehlen nicht mit (eigene Schaerfe)
    for k in R.BLUR_KEYS:                                         # alte Kalibrierung nicht mitnehmen
        if k in spec and k != next(kk for kk in R.BLUR_KEYS if kk in spec):
            spec.pop(k)
    kind = next(k for k in R.BLUR_KEYS if k in spec)
    i = R.seg_of(f)
    can = R.canvas(i, f, spec)
    s0 = sharp(R.finish(R.apply_fx(can, i, {k: v for k, v in spec.items() if k == "zoom"})))
    target = min(1.0, ref_ratio(f))
    val = search(f, i, can, s0, spec, kind, target)
    cap = None if "hg" in spec else CAP.get(kind)
    if val is not None and (cap is None or val <= cap):
        res = {kind: round(val, 4)}
    elif kind in ("hb", "vb", "zb"):
        fixed = 0.5 if kind == "zb" else 0.12
        sp2 = dict(spec)
        sp2[kind] = fixed
        v2 = search(f, i, can, s0, sp2, "sig", target)
        res = {kind: fixed, "sig": round(v2 if v2 is not None else 8.0, 3)}
    else:
        res = {kind: spec[kind]}
    cal[str(f)] = res
    print(f"{f:3d} {kind:3s} Ziel {target:5.3f} -> {res}  {time.time() - t0:5.0f}s", flush=True)
    json.dump(cal, open(R.CAL_FILE, "w"), indent=0)
print("fertig", len(cal))
