#!/usr/bin/env python3
"""Jedes Wort aus words.py mit echter Schrift (Nimbus Sans Narrow = schmale Helvetica) an die Text-Masken des
Vorbilds anpassen und messen, wann welcher Buchstabe sichtbar ist.

Ablauf je Wort (in "ruhenden" Text-Koordinaten, dort steht der Text still, siehe text_drift.py):
  1. Zielbild = Anteil der Bilder im Wortbereich, in denen ein Punkt Text ist (Eintippen/Blinken zaehlen mit).
  2. Suche: Wort in ~60 Groessen (und ggf. beiden Drehrichtungen) rendern, Kreuzkorrelation ueber das ganze
     Bild, die besten Treffer nach Ueberdeckung (IoU im Umfeld) bewerten - so passt ein kurzes Wort nicht in
     einen Teil eines grossen.
  3. Feinanpassung (Groesse, waagerechte Streckung, Lage) auf maximale Ueberdeckung.
  4. Schon angepasste, gleichzeitig sichtbare Woerter werden vor der Suche aus dem Zielbild entfernt.
  5. Je Bild und Buchstabe: Anteil der Buchstabenflaeche, die im Vorbild Text ist -> sichtbar ja/nein
     (mit Hysterese; Eintippen = Buchstaben kommen nacheinander, Blinken = alle kurz weg).

    python3 fit_words.py MASKEN_ORDNER [AUSGABE.json]
MASKEN_ORDNER: enthaelt masks_canon.npy (aus text_mask.py mit DRIFT).
"""
import json, os, sys
import numpy as np
import cv2
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import typeset as T
from words import WORDS

FONT = "nimbus_nar"
SEARCH = 0.5                      # Suche in halber Aufloesung
SIZES = [24 * 1.05 ** k for k in range(64)]      # Schriftgroesse (px pro em, volle Aufloesung) 24 ... ~520


def word_template(text, rot, size, scale=1.0, sx=1.0, letters=None):
    """Wort als Alpha-Bild (eng zugeschnitten) + Ankerpunkt (Grundlinie links) darin"""
    al, ox, oy = T.render_word(text, FONT, 0.0, letters=letters)
    k = size * scale / T.BASE
    c, s = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    A = np.array([[k * sx * c, k * s], [-k * sx * s, k * c]])
    h, w = al.shape
    corners = np.array([[0, 0], [w, 0], [0, h], [w, h]], float) - [ox, oy]
    pc = corners @ A.T
    x0, y0 = np.floor(pc.min(0)) - 2
    x1, y1 = np.ceil(pc.max(0)) + 2
    t = -np.array([x0, y0]) - A @ np.array([ox, oy])
    M = np.hstack([A, t[:, None]]).astype(np.float32)
    out = cv2.warpAffine(al, M, (int(x1 - x0), int(y1 - y0)), flags=cv2.INTER_LINEAR)
    return out, (-x0, -y0)              # Anker in Vorlagen-Koordinaten


def place_word(text, rot, size, sx, x, y, shape, letters=None):
    al, ox, oy = T.render_word(text, FONT, 0.0, letters=letters)
    return T.place(al, ox, oy, T.BASE, size, sx, x, y, rot, shape)


def window_iou(tpl_full, target, pad=0.25):
    ys, xs = np.where(tpl_full > 0.3)
    if len(xs) == 0:
        return 0.0
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    px, py = int((x1 - x0) * pad) + 3, int((y1 - y0) * pad) + 3
    x0, y0 = max(0, x0 - px), max(0, y0 - py)
    x1, y1 = min(target.shape[1], x1 + px), min(target.shape[0], y1 + py)
    return T.soft_iou(tpl_full[y0:y1, x0:x1], target[y0:y1, x0:x1])


def search(text, rots, target, hint=None):
    """grobe Suche: beste (Groesse, Drehung, Lage) nach Ueberdeckung"""
    hint = hint or {}
    if "box" in hint:                                  # nur im angegebenen Bereich suchen
        x0, y0, x1, y1 = hint["box"]
        keep = np.zeros_like(target)
        keep[y0:y1, x0:x1] = 1
        target = target * keep
    smin, smax = hint.get("size", (0, 1e9))
    small = cv2.resize(target, None, fx=SEARCH, fy=SEARCH, interpolation=cv2.INTER_AREA)
    cands = []
    for rot in rots:
        for size in [z for z in SIZES if smin <= z <= smax]:
            tpl, (ax, ay) = word_template(text, rot, size, SEARCH)
            if tpl.shape[0] >= small.shape[0] - 2 or tpl.shape[1] >= small.shape[1] - 2 or tpl.sum() < 4:
                continue
            res = cv2.matchTemplate(small, tpl, cv2.TM_CCORR_NORMED)
            res = np.nan_to_num(res, nan=0.0, posinf=0.0, neginf=0.0)
            for _ in range(5):                         # 5 beste Stellen je Groesse
                _, v, _, (mx, my) = cv2.minMaxLoc(res)
                if v <= 0.3:
                    break
                cands.append((v, rot, size, (mx + ax) / SEARCH, (my + ay) / SEARCH))
                cv2.rectangle(res, (mx - tpl.shape[1] // 3, my - tpl.shape[0] // 3),
                              (mx + tpl.shape[1] // 3, my + tpl.shape[0] // 3), -1, -1)
    cands.sort(key=lambda c: -c[0])
    best = None
    for v, rot, size, x, y in cands[:120]:
        pl = place_word(text, rot, size, 1.0, x, y, target.shape)
        sc = window_iou(pl, target)
        if best is None or sc > best[0]:
            best = (sc, rot, size, x, y)
    return best


def refine(text, rot, size, x, y, target):
    def f(p):
        pl = place_word(text, rot, p[0], p[1], p[2], p[3], target.shape)
        return -window_iou(pl, target, pad=0.15)
    r = minimize(f, [size, 1.0, x, y], method="Nelder-Mead",
                 options=dict(xatol=0.05, fatol=1e-4, maxiter=600,
                              initial_simplex=[[size, 1.0, x, y], [size * 1.04, 1.0, x, y], [size, 1.04, x, y],
                                               [size, 1.0, x + size * 0.02, y], [size, 1.0, x, y + size * 0.02]]))
    return -r.fun, r.x


def u_map(w, shape, size=None):
    """je Bildpunkt: Lage entlang der Schreibrichtung des Wortes in em (0 = Wortanfang, ohne Streckung)"""
    al, ox, oy = T.render_word(w["text"], FONT, 0.0)
    h, ww = al.shape
    U = ((np.arange(ww, dtype=np.float32) - ox) / T.BASE)[None, :].repeat(h, 0) + 10.0   # +10: 0 = Rand
    pl_u = T.place(U, ox, oy, T.BASE, w["size"], w["sx"], w["x"], w["y"], w["rot"], shape)
    pl_a = T.place(al, ox, oy, T.BASE, w["size"], w["sx"], w["x"], w["y"], w["rot"], shape)
    return pl_a, pl_u - 10.0


FULL, HIDDEN = (-1e9, 1e9), None


def intervals(w, masks, blink):
    """je Bild: sichtbarer Bereich des Wortes entlang der Schreibrichtung (ua, ub) in em, oder None.
    Im Vorbild erscheinen Woerter mit einem Wisch von rechts (erst nur der rechte Teil, gerade Kante mitten
    durch einen Buchstaben), Woerter werden eingetippt (BE -> BEGGIN) und blinken (1-2 Bilder weg)."""
    shape = masks.shape[1:]
    al, U = u_map(w, shape)
    glyph = al > 0.5
    ys, xs = np.where(glyph)
    u = U[ys, xs]
    step = 0.02                                        # em je Abschnitt
    b = np.floor((u - u.min()) / step).astype(int)
    nb = b.max() + 1
    gw = np.bincount(b, minlength=nb).astype(np.float32)
    u_lo = u.min()
    hits = [np.asarray(masks[t])[ys, xs] > 127 for t in range(w["f0"], w["f1"] + 1)]
    fr = np.array([h.mean() for h in hits])
    # typische Ueberdeckung, wenn das Wort ganz da ist (kleine Woerter: Masken des Vorbilds luechenhaft)
    ref = float(np.percentile(fr[fr > 0.05], 90)) if (fr > 0.05).any() else 1.0
    ref = min(1.0, max(ref, 0.3))
    res = []
    for mt, frac in zip(hits, fr):
        mw = np.bincount(b, weights=mt.astype(np.float32), minlength=nb)
        cov = np.where(gw > 0, mw / np.maximum(gw, 1), np.nan)
        # leere Abschnitte (zwischen Buchstaben) bekommen den Wert der Nachbarn
        idx = np.where(~np.isnan(cov))[0]
        cov = np.interp(np.arange(nb), idx, cov[idx])
        cov = np.convolve(cov, np.ones(3) / 3, mode="same")
        if frac >= 0.80 * ref:
            res.append(FULL)
            continue
        on = cov >= 0.5 * ref
        if frac < 0.12 * ref or on.sum() < 3:
            res.append(HIDDEN)
            continue
        # laengster zusammenhaengender sichtbarer Abschnitt (Luecken < 0,15 em schliessen)
        gap = int(0.15 / step)
        runs, start, last = [], None, None
        for i, v in enumerate(on):
            if v:
                if start is None:
                    start = i
                elif i - last > gap:
                    runs.append((start, last))
                    start = i
                last = i
        if start is not None:
            runs.append((start, last))
        a, bb = max(runs, key=lambda r: r[1] - r[0])
        ua = u_lo + a * step
        ub = u_lo + (bb + 1) * step
        # links/rechts ohne Schnitt, wenn der Abschnitt bis an den Wortrand reicht
        if a * step < 0.12:
            ua = -1e9
        if (nb - 1 - bb) * step < 0.12:
            ub = 1e9
        res.append((float(ua), float(ub)))
    # Aufraeumen (Masken kleiner Woerter sind luechenhaft). Vor dem ersten vollen Bild bleiben Eintippen
    # (vorderer Teil) und Wisch (hinterer Teil) wie gemessen. Danach bis zum letzten erkannten Bild:
    #  * Teil-Zustaende -> voll (ein Buchstabe "verschwindet" im Vorbild nicht einfach)
    #  * 1-2 Bilder weg = Blinken (bleibt), laengere Luecken = Messfehler -> voll
    full_idx = [k for k, r in enumerate(res) if r == FULL]
    if full_idx:
        k0 = full_idx[0]
        k1 = [k for k, r in enumerate(res) if r is not None][-1]
        k = k0
        while k <= k1:
            if res[k] is None:
                e = k
                while e <= k1 and res[e] is None:
                    e += 1
                if e - k >= 3:
                    for q in range(k, e):
                        res[q] = FULL
                k = e
                continue
            if res[k] != FULL:
                res[k] = FULL
            k += 1
    return res


def main():
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "words_fit.json")
    masks = np.load(os.path.join(src, "masks_canon.npy"), mmap_mode="r")
    n, h, w_ = masks.shape
    fitted = []
    # Gierig: immer das Wort festlegen, das gerade am besten passt (eindeutigster Treffer), es aus dem Zielbild
    # der gleichzeitig sichtbaren Woerter entfernen und deren Suche wiederholen. So nimmt kein kurzes Wort
    # ("of", "i") oder ein kleines langes ("HEART") den Platz eines anderen Wortes ein.
    def target_for(k):
        text, rot, f0, f1 = WORDS[k][:4]
        f1 = min(f1, n - 1)
        tg = np.mean([np.asarray(masks[t]) > 127 for t in range(f0, f1 + 1)], axis=0).astype(np.float32)
        for o in fitted:
            if min(o["f1"], f1) - max(o["f0"], f0) >= 2:
                fp = place_word(o["text"], o["rot"], o["size"], o["sx"], o["x"], o["y"], (h, w_))
                tg *= 1 - cv2.dilate((fp > 0.3).astype(np.uint8), np.ones((5, 5), np.uint8))
        return tg

    def run_search(k):
        text, rot, f0, f1 = WORDS[k][:4]
        hint = WORDS[k][4] if len(WORDS[k]) > 4 else None
        tg = target_for(k)
        if hint and "box" in hint:
            x0, y0, x1, y1 = hint["box"]
            box = np.zeros_like(tg)
            box[y0:y1, x0:x1] = 1
            tg = tg * box
        return search(text, [rot] if rot is not None else [90, -90], tg, hint), tg

    # Bilder, in denen im Vorbild kurz der ganze Text weg ist (Blinken): Flaeche << Nachbarn
    area = np.array([(np.asarray(masks[t]) > 127).sum() for t in range(n)], np.float32)
    blink = np.zeros(n + 2, bool)
    for t in range(n):
        nb_ = [area[q] for q in (t - 3, t - 2, t + 2, t + 3) if 0 <= q < n]
        blink[t] = area[t] < 0.25 * max(1.0, float(np.median(nb_)))

    todo = {k: run_search(k) for k in range(len(WORDS))}
    while todo:
        k = max(todo, key=lambda q: todo[q][0][0])
        (sc, r_, size, x, y), tg = todo.pop(k)
        text, rot, f0, f1 = WORDS[k][:4]
        f1 = min(f1, n - 1)
        sc2, p = refine(text, r_, size, x, y, tg)
        word = dict(id=k, text=text, rot=r_, f0=f0, f1=f1, size=float(p[0]), sx=float(p[1]),
                    x=float(p[2]), y=float(p[3]), iou=round(float(sc2), 3))
        word["vis"] = intervals(word, masks, blink)
        fitted.append(word)
        on = np.array([v is not None for v in word["vis"]])
        first = int(np.argmax(on)) + f0 if on.any() else -1
        last = f1 - int(np.argmax(on[::-1])) if on.any() else -1
        print(f"{k:2d} {text:9s} rot {r_:+4d}  Groesse {p[0]:6.1f} sx {p[1]:.3f}  Lage ({p[2]:6.1f},{p[3]:6.1f})"
              f"  IoU {sc2:.3f}  sichtbar {first}-{last}", flush=True)
        for q in list(todo):
            o0, o1 = WORDS[q][2], min(WORDS[q][3], n - 1)
            if min(o1, f1) - max(o0, f0) >= 2:
                todo[q] = run_search(q)
    fitted.sort(key=lambda w: w["id"])
    json.dump(fitted, open(out, "w"), indent=0)
    print("gespeichert:", out)


if __name__ == "__main__":
    main()
