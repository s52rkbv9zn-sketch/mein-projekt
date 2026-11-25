#!/usr/bin/env python3
"""Messwerte aus dem Vorbild (Referenz 11) in glatte Kurven je Bild umrechnen -> ref_data.json.

Eingaben (aus den Mess-Skripten in analyse/, alle im Vorbild-Massstab 1024x576, Bildnummer = round(pts*30)):
  faces_dense.json  Gesichter je Bild (YuNet, 2x vergroessert): [cx, cy, h, score]
  bands.json        Oberkante des lila Bandes (y = b + m*x) je 3. Bild, Teil 1-2; Keil-Kante Teil 3
  skyflow.json      Bewegung des Himmels (optischer Fluss) je Bild, Teil 1-2
  vifit.json        Logo: Massstab/Mitte je Bild (Vorlagensuche)
  vifit2.json       VI-Fenster: Massstab/Mitte je Bild

    python3 build_data.py MESS_ORDNER ref_data.json
"""
import sys, json
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.interpolate import PchipInterpolator

NF = 339


def series(samples, t0, t1, sigma=0.0):
    """samples {t: v} -> Werte fuer t0..t1 (linear verbunden, aussen festgehalten, dann geglaettet)"""
    ts = np.array(sorted(samples), float)
    vs = np.array([samples[t] for t in sorted(samples)], float)
    tt = np.arange(t0, t1 + 1)
    v = np.interp(tt, ts, vs)
    if sigma > 0:
        v = gaussian_filter1d(v, sigma, mode="nearest")
    return {int(t): float(x) for t, x in zip(tt, v)}


def pchip(keys, t0, t1):
    ts = np.array(sorted(keys), float)
    f = PchipInterpolator(ts, [keys[t] for t in sorted(keys)], extrapolate=False)
    tt = np.arange(t0, t1 + 1)
    v = f(np.clip(tt, ts[0], ts[-1]))
    return {int(t): float(x) for t, x in zip(tt, v)}


def follow(d, start_t, start, t_end, max_d=0.35, size_rng=(0.8, 1.25), ok=lambda t, f: True):
    out = {}
    p = np.array(start, float)
    for t in range(start_t, t_end + 1):
        best = None
        for f in d.get(t, []):
            if not ok(t, f):
                continue
            dist = np.hypot(f[0] - p[0], f[1] - p[1]) / p[2]
            r = f[2] / p[2]
            if dist < max_d and size_rng[0] < r < size_rng[1] and (best is None or dist < best[0]):
                best = (dist, f)
        if best is not None:
            out[t] = best[1][:3]
            p = np.array(best[1][:3], float)
    return out


def spline_fit(samples, t0, t1, step):
    """Ausgleichs-Spline (kubisch, Knoten alle `step` Bilder) durch die Messpunkte -> glatte Kurve ohne
    das Zittern der Gesichtssuche, die Bewegungsform (Anlauf/Abbremsen) bleibt."""
    from scipy.interpolate import LSQUnivariateSpline
    ts = np.array(sorted(samples), float)
    vs = np.array([samples[int(t)] for t in ts], float)
    if len(ts) < 8:
        return series(samples, t0, t1, 0.0)
    knots = np.arange(ts[0] + step, ts[-1] - step / 2, step)
    f = LSQUnivariateSpline(ts, vs, knots, k=3)
    tt = np.arange(t0, t1 + 1)
    return {int(t): float(f(np.clip(t, ts[0], ts[-1]))) for t in tt}


def role(raw, pre=None, post=None, t0=0, t1=NF - 1, sx=1.2, sh=2.5, fixed_h=None, kx=9, kh=24):
    """raw {t: (x,y,h)} plus Formeln vor/nach dem gemessenen Bereich -> {t: [x,y,h]}"""
    xs, ys, hs = {}, {}, {}
    ta, tb = min(raw), max(raw)
    for t in range(t0, t1 + 1):
        if t < ta and pre:
            v = pre(t)
        elif t > tb and post:
            v = post(t, raw[tb])
        elif ta <= t <= tb and t in raw:
            v = raw[t]
        else:
            continue
        xs[t], ys[t], hs[t] = v
    X, Y, Hh = spline_fit(xs, t0, t1, kx), spline_fit(ys, t0, t1, kx), spline_fit(hs, t0, t1, kh)
    return {t: [X[t], Y[t], fixed_h if fixed_h else Hh[t]] for t in range(t0, t1 + 1)}


EASE = [0, 0.032, 0.069, 0.118, 0.178, 0.254, 0.341, 0.435, 0.533, 0.630, 0.715, 0.796, 0.856, 0.905, 0.944,
        0.974, 0.989, 0.997, 0.999, 1.0]          # Kachel-Bewegung (gemessen an der B-Kachel, Bild 299-318)


def ease(k):
    return float(np.interp(k, np.arange(len(EASE)), EASE))


def main():
    M, out = sys.argv[1:3]
    d = {int(k): v for k, v in json.load(open(f"{M}/faces_dense.json")).items()}
    R = {}
    # --- Teil 1-2: Personen
    a1 = follow(d, 6, (124, 107, 222), 204)
    v0 = (np.array(a1[9]) - np.array(a1[6])) / 3
    R["A1"] = role(a1, pre=lambda t: list(np.array(a1[6]) + v0 * (t - 6) * np.array([1, 1, 0])),
                   post=lambda t, last: last, t0=0, t1=232)
    b1 = follow(d, 63, (948, 108, 208), 108)
    R["B1"] = role(b1, pre=lambda t: [948 + 14 * (63 - t) + 0.47 * (63 - t) ** 2, 108, 205],
                   post=lambda t, last: [last[0] + 1.5 * (t - 108) + 0.6 * max(0, t - 125) ** 2, last[1] + 0.8 * (t - 108), last[2]],
                   t0=45, t1=150, sh=4, fixed_h=200)
    c1 = follow(d, 93, (73.6, 145, 201), 210)
    R["C1"] = role(c1, pre=lambda t: [73.6 + 21 * (t - 93), 145 + 1.5 * (93 - t), 203], post=lambda t, last: last,
                   t0=75, t1=232, sh=3)
    dx = {124: 1200, 126: 1150, 129: 1050, 132: 965, 135: 887, 138: 810, 141: 757, 144: 728, 147: 709, 150: 706,
          153: 710, 156: 712, 159: 726, 162: 758, 165: 777, 168: 806, 171: 825, 174: 854, 177: 870, 180: 876,
          183: 886, 186: 888, 190: 886, 232: 886}
    dy = {124: 205, 135: 205, 150: 196, 165: 203, 180: 210, 190: 210, 232: 210}
    dh = {124: 318, 150: 316, 165: 305, 180: 296, 190: 294, 232: 294}
    X, Y, Hh = pchip(dx, 124, 232), pchip(dy, 124, 232), pchip(dh, 124, 232)
    Xs = spline_fit({t: X[t] for t in range(124, 233)}, 124, 232, 9)
    R["D1"] = {t: [Xs[t], Y[t], Hh[t]] for t in range(124, 233)}
    e1 = follow(d, 168, (66, 419, 235), 199, size_rng=(0.85, 1.18), ok=lambda t, f: f[1] > 330)
    R["E1"] = role(e1, pre=lambda t: [65 + 26 * (t - 168), 419 + 4.5 * (168 - t), 242], post=lambda t, last: last,
                   t0=155, t1=232, sx=1.0, fixed_h=242)
    # --- Teil 3: A vor dem Keil, dann die drei Kacheln
    a3x = pchip({262: -230, 266: -160, 272: -45, 276: 30, 282: 100, 288: 183, 294: 262, 300: 318, 306: 362, 312: 400,
                 318: 425, 330: 450}, 262, 330)
    R["A3"] = {t: [a3x[t], 186.0, 218.0] for t in range(262, 331)}
    eB = {t: 576 - 594.5 * ease(t - 299) for t in range(296, NF)}
    eC = {t: 595 * ease(t - 308.5) for t in range(306, NF)}
    eR = {t: 576 - 596 * ease(t - 316.1) for t in range(313, NF)}
    R["BP"] = {t: [233.0, eB[t] + 97, 127.0] for t in eB}
    R["CP"] = {t: [572.5, eC[t] - 503, 116.0] for t in eC}
    R["RP"] = {t: [831.0, eR[t] + 225, 192.0] for t in eR}
    # --- Hintergrund-Karte (Himmel zwischen den lila Baendern)
    bands = {int(k): v for k, v in json.load(open(f"{M}/bands.json")).items()}
    ms = {t: bands[t]["top"][0] for t in bands if 6 <= t <= 195}
    bs = {t: bands[t]["top"][1] for t in bands if 6 <= t <= 195}
    ms[0], bs[0] = 0.0, 27.0
    m = series(pchip(ms, 0, 232), 0, 232, 1.5)
    b = series(pchip(bs, 0, 232), 0, 232, 1.5)
    kk = {0: 1.02, 6: 1.01, 12: 1.0, 24: 0.953, 36: 0.936, 48: 0.888, 54: 0.840, 66: 0.791, 78: 0.777, 90: 0.757,
          102: 0.678, 114: 0.643, 129: 0.623, 144: 0.54, 165: 0.504, 186: 0.48, 232: 0.48}
    k = pchip(kk, 0, 232)
    flow = {int(t): v for t, v in json.load(open(f"{M}/skyflow.json")).items()}
    sx, acc = {10: 0.0}, 0.0
    for t in range(11, 166):
        acc += flow[t]["med"][0] if t in flow else 0.0
        sx[t] = acc
    sx[0] = sx[10] - 2.0 * 10
    s165 = sx[165]
    sx.update({175: s165 + 50, 186: s165 + 80, 196: s165 + 88, 232: s165 + 88})
    xc = spline_fit(series(sx, 0, 232, 0.0), 0, 232, 12)
    card = {t: dict(m=m[t], b=b[t], k=k[t], xc=512 + xc[t]) for t in range(0, 233)}
    # --- VI-Fenster und Logo
    w2 = {int(t): v for t, v in json.load(open(f"{M}/vifit2.json")).items()}
    lns = {t: float(np.log(w2[t][0])) for t in range(202, 233)}
    for t in range(186, 202):
        lns[t] = 0.894 + 0.0377 * (202 - t)
    lns = series(lns, 186, 232, 1.0)
    cxs = {t: w2[t][1] for t in range(202, 233)}
    cys = {t: w2[t][2] for t in range(202, 233)}
    cxs[186], cys[186] = 480.0, 309.0
    cx, cy = series(cxs, 186, 232, 3.0), series(cys, 186, 232, 3.0)
    for t in range(226, 233):                                   # zum Logo-Mittelpunkt hin
        u = (t - 225) / 7
        cx[t] = cx[t] * (1 - u) + 501 * u
        cy[t] = cy[t] * (1 - u) + 297 * u
    win = {t: dict(s=float(np.exp(lns[t])), cx=cx[t], cy=cy[t]) for t in range(186, 233)}
    w1 = {int(t): v for t, v in json.load(open(f"{M}/vifit.json")).items()}
    lls = {t: float(np.log(w1[t]["logo"][0])) for t in range(200, 233)}
    for t in range(194, 200):
        lls[t] = float(np.log(0.104)) - 0.11 * (200 - t)
    lls[233] = 0.0
    lls = series(lls, 194, 233, 0.8)
    fade_logo = {233: 1.0, 234: 1.0, 235: 0.90, 236: 0.805, 237: 0.71, 238: 0.615, 239: 0.515, 240: 0.414, 241: 0.33,
                 242: 0.246, 243: 0.165, 244: 0.087, 245: 0.04, 246: 0.008}
    logo = {}
    for t in range(196, 247):
        s = float(np.exp(lls[t])) if t <= 233 else 1.0
        x = max(501.0, 523.5 - 0.68 * (t - 200)) if t <= 233 else 501.0
        y = 297.5 - 0.5 * np.clip((t - 200) / 33, 0, 1)
        a = 0.5 if t == 196 else (1.0 if t <= 234 else fade_logo[t])
        logo[t] = dict(s=s, cx=x, cy=float(y), a=a)
    # --- Keil (Teil 3): y = 0.384 x + b
    wedge = {int(t): v["top"][1] for t, v in bands.items() if 258 <= int(t) <= 318 and v["top"]}
    wedge.update({246: 590.0, 248: 584.0, 250: 575.0, 252: 562.0, 254: 547.0, 256: 529.0, 338: -35.8})
    wedge = series(pchip(wedge, 246, NF - 1), 246, NF - 1, 0.6)
    # --- Blenden
    fin = [0, 0.017, 0.027, 0.048, 0.096, 0.162, 0.26, 0.347, 0.474, 0.62, 0.787, 0.963, 1.0]
    fout = {329: 1.0, 330: 0.919, 331: 0.706, 332: 0.481, 333: 0.321, 334: 0.177, 335: 0.110, 336: 0.034,
            337: 0.014, 338: 0.0}
    fade = {t: (fin[t] if t < len(fin) else fout.get(t, 1.0)) for t in range(NF)}
    data = dict(nf=NF, roles={r: {str(t): v for t, v in tr.items()} for r, tr in R.items()},
                card={str(t): v for t, v in card.items()}, win={str(t): v for t, v in win.items()},
                logo={str(t): v for t, v in logo.items()}, wedge={str(t): v for t, v in wedge.items()},
                fade={str(t): v for t, v in fade.items()}, wedge_slope=0.384,
                panels=dict(B=[0, 337], C=[337, 685], R=[685, 1024]),
                panel_edges=dict(B={str(t): v for t, v in eB.items()}, C={str(t): v for t, v in eC.items()},
                                 R={str(t): v for t, v in eR.items()}))
    json.dump(data, open(out, "w"), separators=(",", ":"))
    print("ok", {r: (min(tr), max(tr)) for r, tr in R.items()})


if __name__ == "__main__":
    main()
