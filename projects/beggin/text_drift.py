#!/usr/bin/env python3
"""Bewegung der Textebene im Vorbild messen (der Text gleitet langsam, ~0,1-0,2 px pro Bild, oben und unten
etwas verschieden - daher affin).

Ohne diese Messung bleibt die Text-Maske zwischen zwei Wechseln an der alten Stelle stehen ("eingefroren") und
springt dann - Buchstaben werden auf einer Seite duenner. Messung: Alle 4 Bilder ein Anker a. Vorlage = Rand der
vorlaeufigen Text-Maske von Bild a; sie wird auf die Kantenbilder (Minimum der Farbkanaele) der Bilder a..a+8
ausgerichtet (affin, jeweils vom vorigen Ergebnis aus). Bewegung t -> t+1 = W(t+1) * W(t)^-1 (gleiche Vorlage,
deren eigener Versatz kuerzt sich). Alle Anker, die ein Bildpaar abdecken, werden gemittelt; unplausible
Spruenge (Textwechsel) verworfen und aus den Nachbarn ergaenzt, dann leicht geglaettet.
Ergebnis: C[t] (3x3) bildet "ruhende" Text-Koordinaten (= Bild 0) auf Bild t ab.

    python3 text_drift.py VORBILD.mp4|BILDER.npy MASKEN.npy AUSGABE.npz [letztes_bild]
MASKEN.npy: vorlaeufige Masken aus einem ersten Lauf von text_mask.py (ohne DRIFT), z. B. sure.npy.
"""
import sys
import numpy as np
import cv2

K3 = np.ones((3, 3), np.uint8)
STRIDE, SPAN = 4, 8
PTS = np.array([[300, 150, 1], [724, 150, 1], [512, 288, 1], [300, 430, 1], [724, 430, 1]], np.float64).T


def grad_map(img):
    g = cv2.GaussianBlur(img.min(axis=2).astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1)
    return cv2.GaussianBlur(np.sqrt(gx * gx + gy * gy), (0, 0), 1.0)


def boundary_map(m):
    m = (m > 127).astype(np.uint8)
    b = (cv2.dilate(m, K3) - cv2.erode(m, K3)).astype(np.float32)
    return cv2.GaussianBlur(b, (0, 0), 1.5)


def to3(w):
    return np.vstack([w, [0, 0, 1]]).astype(np.float64)


def ecc(tmpl, img, init):
    w = init.astype(np.float32).copy()
    try:
        cc, w = cv2.findTransformECC(tmpl, img, w, cv2.MOTION_AFFINE,
                                     (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 80, 1e-5), None, 5)
    except cv2.error:
        return None, 0.0
    return w, cc


def disp(M):
    """Verschiebung (px) an 5 Textpunkten durch Bewegung M"""
    return (M @ PTS)[:2] - PTS[:2]


def main():
    if sys.argv[1].endswith(".npy"):
        frames = np.load(sys.argv[1], mmap_mode="r")
    else:
        from text_mask import load
        frames = load(sys.argv[1], int(sys.argv[4]) if len(sys.argv) > 4 else 10 ** 6)
    masks = np.load(sys.argv[2], mmap_mode="r")
    n = min(len(frames), len(masks))
    h, w = frames.shape[1:3]
    y0, y1, x0, x1 = int(0.10 * h), int(0.90 * h), int(0.15 * w), int(0.85 * w)
    S = np.array([[1, 0, x0], [0, 1, y0], [0, 0, 1]], np.float64)
    Si = np.linalg.inv(S)
    grads = {}

    def G(t):
        if t not in grads:
            grads[t] = grad_map(np.asarray(frames[t]))[y0:y1, x0:x1]
            for k in [k for k in grads if k < t - SPAN - 2]:
                del grads[k]
        return grads[t]

    est = [[] for _ in range(n - 1)]                  # je Paar: Liste von Bewegungen (3x3)
    for a in range(0, n - 1, STRIDE):
        m = np.asarray(masks[a])
        if (m > 127).sum() < 400:
            continue
        tm = boundary_map(m)[y0:y1, x0:x1]
        W = {}
        init = np.eye(2, 3, dtype=np.float32)
        for t in range(a, min(n, a + SPAN + 1)):
            wt, cc = ecc(tm, G(t), init)
            if wt is None or cc < 0.40:
                break
            W[t] = S @ to3(wt) @ Si
            init = wt
        for t in range(a, min(n - 1, a + SPAN)):
            if t in W and t + 1 in W:
                est[t].append(W[t + 1] @ np.linalg.inv(W[t]))
        if a % 40 == 0:
            print("Anker", a, flush=True)
    # je Paar mitteln (Parameter), unplausible verwerfen
    M = np.tile(np.eye(3), (n - 1, 1, 1))
    ok = np.zeros(n - 1, bool)
    for t in range(n - 1):
        good = [e for e in est[t] if np.abs(disp(e)).max() < 0.8]
        if len(good):
            M[t] = np.mean(good, axis=0)
            ok[t] = True
    # Luecken (Textwechsel, kein Text) aus den Nachbarn ergaenzen, dann glaetten (sigma 2 Bilder)
    P = (M - np.eye(3))[:, :2, :].reshape(n - 1, 6)
    idx = np.where(ok)[0]
    if len(idx):
        for k in range(6):
            P[~ok, k] = np.interp(np.where(~ok)[0], idx, P[ok, k])
    Ps = np.empty_like(P)
    tt = np.arange(n - 1)
    for t in range(n - 1):
        wgt = np.exp(-0.5 * ((tt - t) / 2.0) ** 2)
        wgt[np.abs(tt - t) > 6] = 0
        Ps[t] = (P * wgt[:, None]).sum(0) / wgt.sum()
    Mi = np.tile(np.eye(3), (n - 1, 1, 1))
    Mi[:, :2, :] += Ps.reshape(n - 1, 2, 3)
    C = [np.eye(3)]
    for t in range(n - 1):
        C.append(Mi[t] @ C[-1])
    np.savez(sys.argv[3], C=np.array(C), M=Mi, ok=ok)
    print("fertig", n, "Paare ok:", int(ok.sum()))


if __name__ == "__main__":
    main()
