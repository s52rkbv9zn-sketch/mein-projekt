#!/usr/bin/env python3
"""Uebergaenge 1:1 wie im Vorbild: jedes Uebergangsbild einzeln vermessen und nachbilden.

Fuer jedes Bild rund um die Schnitte (3 davor bis 5 danach) und jedes Effekt-Bild wird im Vorbild gemessen:
  * Unschaerfe: Detail-Energie in 4 Frequenzbaendern (Differenz von Gauss-Stufen 0,7-11,2 px bei 288 px),
    getrennt nach waagerechten und senkrechten Kanten, relativ zu den ruhigen Bildern derselben Szene.
    Das eigene Bild wird dabei schon auf den Ziel-Kontrast gebracht (wie beim Rendern). Verhaeltnisse unter
    3 % zaehlen nicht (Rauschen/Kompression des Vorbilds), grobe Baender zaehlen mehr. So wird auch sehr
    starke Unschaerfe richtig erkannt (v1 dieser Messung: Rauschen des Vorbilds galt als Schaerfe).
  * Helligkeit, Kontrast, Farbigkeit (Lab: Mittelwert L, Streuung L, mittlere Chroma) relativ zur Szene.
Eigenes Bild: Effekte (Echo, Wellen, ...) -> weiche Gauss-Unschaerfe waagerecht sx / senkrecht sy, per
Gittersuche so gewaehlt, dass das Band-Profil dem Vorbild entspricht; Helligkeit/Kontrast/Farbe werden beim
Rendern exakt eingestellt (render.py, trans_frame). Ergebnis: trans_{EDIT}.json

    EDIT=hyunjin python3 trans.py        (bzw. EDIT=felix)
"""
import json, math, os, sys, time
import numpy as np
import cv2

os.environ["NO_TRANS"] = "1"
sys.argv = [sys.argv[0]]
import render as R

S = 288
SIG = (0.7, 1.4, 2.8, 5.6, 11.2)
WB = np.array([0.3, 0.8, 1.2, 1.2] * 2)      # grobe Baender zaehlen mehr (robust bei starker Unschaerfe)
GRID = [0, 0.6, 1.0, 1.6, 2.5, 4, 6, 9, 14, 21, 32, 48]          # sigma in px bei 576


def base_mask():
    m = R.ref_mask(S, S)
    m[:6] = False
    m[-6:] = False
    m[:, :6] = False
    m[:, -6:] = False
    return m


M0 = base_mask()


def frame_mask(f):
    """Maske fuer Bild f: ohne Spalt-Balken (geteilte Einblendung) und ohne Lichtstreifen-Zeilen"""
    m = M0.copy()
    spec = R.FX.get(f, {})
    if spec.get("split"):
        h = spec["split"][0]
        m[int(S * (0.5 - h / 2)) - 2:int(S * (0.5 + h / 2)) + 3] = False
    if spec.get("flare"):
        y0 = spec["flare"][0]
        m[max(0, int(S * (y0 - 0.07))):int(S * (y0 + 0.07))] = False
    return m


def gray(img):
    x = cv2.resize(np.clip(img, 0, 255).astype(np.uint8), (S, S), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(x, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0


def feats(g, m):
    """absolute Detail-Energie je Band (waagerecht, senkrecht) - Helligkeit/Kontrast werden vorher angeglichen"""
    G = [cv2.GaussianBlur(g, (0, 0), s) for s in SIG]
    mx, my = m[:, 1:] & m[:, :-1], m[1:, :] & m[:-1, :]
    ex, ey = [], []
    for k in range(4):
        D = G[k] - G[k + 1]
        ex.append(float(((D[:, 1:] - D[:, :-1]) ** 2)[mx].mean()))
        ey.append(float(((D[1:, :] - D[:-1, :]) ** 2)[my].mean()))
    return np.array(ex + ey) + 1e-12


FLOOR = math.log(0.03)          # darunter Rauschen/Kompression des Vorbilds -> nicht weiter unterscheiden


def gstd(g, m):
    return float(g[m].std()) + 1e-6


def lab_stats(img, m):
    x = cv2.resize(np.clip(img, 0, 255).astype(np.float32), (S, S), interpolation=cv2.INTER_AREA) / 255.0
    lab = cv2.cvtColor(x, cv2.COLOR_RGB2LAB)
    return (float(lab[..., 0][m].mean()), float(lab[..., 0][m].std()) + 1e-3,
            float(np.hypot(lab[..., 1], lab[..., 2])[m].mean()) + 1e-3)


def blur_small(g, sx, sy):
    out = g
    if sx > 0.25:
        out = cv2.GaussianBlur(out, (0, 0), sigmaX=sx * S / R.REF_W, sigmaY=1e-6)
    if sy > 0.25:
        out = cv2.GaussianBlur(out, (0, 0), sigmaX=1e-6, sigmaY=sy * S / R.REF_W)
    return out


ref = R.ref_frames()
lo_f = max(R.CUTS[0], R.INTRO_END)
targets = set()
for c in R.CUTS[1:] + ([R.CUTS[0]] if R.INTRO_END else []):
    targets |= set(range(c - 3, c + 6))
targets |= set(R.FX)
targets = sorted(f for f in targets if lo_f <= f < R.FIRST_END and f not in R.FLASH)
tset = set(targets)

scenes = {}
frames_out = {}
t0 = time.time()
for i in range(len(R.CUTS)):
    a, b = R.CUTS[i], R.seg_end(i)
    mine = [f for f in targets if a <= f < b]
    if not mine:
        continue
    body = [f for f in range(a + 3, b - 3) if f not in tset and f not in R.FLASH] or \
           [f for f in range(a, b) if f not in tset and f not in R.FLASH] or [(a + b) // 2]
    body = body[::max(1, len(body) // 6)][:6]
    # Vorbild: Szene
    rb_f = np.median([feats(gray(ref[f]), M0) for f in body], axis=0)
    rb_l = np.median([lab_stats(ref[f], M0) for f in body], axis=0)
    # eigene Szene (ohne Effekte), gleiche Bilder
    R.release(a)
    ob_imgs = [R.canvas(i, f, {}) for f in body]
    ob_f = np.median([feats(gray(x), M0) for x in ob_imgs], axis=0)
    ob_l = np.median([lab_stats(x, M0) for x in ob_imgs], axis=0)
    scenes[i] = dict(m=float(ob_l[0]), s=float(ob_l[1]), c=float(ob_l[2]))
    for f in mine:
        m = frame_mask(f)
        spec = R.FX.get(f, {})
        rg = gray(ref[f])
        rf = feats(rg, m)
        rl = lab_stats(ref[f], m)
        rbg = [gray(ref[g]) for g in body]
        rbf = np.median([feats(x, m) for x in rbg], axis=0)
        r_std = gstd(rg, m) / float(np.median([gstd(x, m) for x in rbg]))
        target = np.clip(np.log(rf / rbf), FLOOR, 2)
        img = R.apply_fx(R.canvas(i, f, {k: v for k, v in spec.items() if k not in R.NONBLUR_DROP}), i,
                         {k: v for k, v in spec.items() if k not in R.NONBLUR_DROP})
        g = gray(R.center(img))
        obg = [gray(x) for x in ob_imgs]
        obf = np.median([feats(x, m) for x in obg], axis=0)
        t_std = float(np.median([gstd(x, m) for x in obg])) * r_std      # Ziel-Kontrast (wie beim Rendern)

        def score(sx_, sy_):
            gb = blur_small(g, sx_, sy_)
            gl = (gb - float(gb[m].mean())) * (t_std / gstd(gb, m))         # Kontrast wie im fertigen Bild
            d = np.clip(np.log(feats(gl, m) / obf), FLOOR, 2) - target
            return float(np.sum(WB * d * d))

        best = None
        for sx in GRID:
            for sy in GRID:
                err = score(sx, sy)
                if best is None or err < best[0]:
                    best = (err, sx, sy)
        err, sx, sy = best
        # feiner nachsuchen (Faktor 0,8 / 1,25 um das beste Gitterpaar)
        for _ in range(2):
            for fx_ in (0.8, 1.0, 1.25):
                for fy_ in (0.8, 1.0, 1.25):
                    tx, ty = sx * fx_, sy * fy_
                    e2 = score(tx, ty)
                    if e2 < err:
                        err, bx, by = e2, tx, ty
                        sx, sy = bx, by
        frames_out[f] = dict(sx=round(sx, 3), sy=round(sy, 3), dm=round(rl[0] - float(rb_l[0]), 3),
                             rs=round(rl[1] / float(rb_l[1]), 4), rc=round(rl[2] / float(rb_l[2]), 4),
                             err=round(err, 3))
        print(f"{f:3d} Szene {i:2d}: sx {sx:6.2f} sy {sy:6.2f}  Hell {rl[0] - rb_l[0]:+6.1f}  Kontrast x{rl[1] / rb_l[1]:.2f}"
              f"  Farbe x{rl[2] / rb_l[2]:.2f}  Rest {err:.2f}  {time.time() - t0:4.0f}s", flush=True)
    json.dump(dict(frames=frames_out, scenes=scenes), open(R.TRANS_FILE, "w"), indent=0)
print("fertig", len(frames_out))
