#!/usr/bin/env python3
"""Vorbild (Referenz 11, GTA-VI-Edit, 1024x576, 30 fps) Bild fuer Bild vermessen -> JSON-Dateien fuer build_data.py.

    python3 analyse/measure.py VORBILD.mp4 MESS_ORDNER [schritte]
schritte (Komma-getrennt, Standard alle): faces,bands,flow,logo,window

  faces   Gesichter je Bild 0-340 (YuNet auf 2x vergroessertem Bild)  -> faces_dense.json  [cx, cy, h, score]
  bands   Oberkante des lila Bandes (Teil 1-2) und Keil-Kante (Teil 3): Lila-Maske, je Spalte erster
          Wechsel Lila -> Nicht-Lila, Gerade per RANSAC                     -> bands.json {t: {top: [m, b, n, N], bot: ...}}
  flow    Himmelsbewegung (Farneback-Fluss auf Himmelspixeln: blau-lila, hell, mit Struktur) -> skyflow.json
  logo    Logo-Massstab/Mitte je Bild 200-249 (Masken-Vorlagensuche, Vorlage = Logo aus Bild 233/234) -> vifit.json
  window  VI-Fenster je Bild 190-232: Flaechen-Lila (glatt, Farbabstand < 20) gegen VI-Umriss,
          Grobsuche (Massstab, Mitte) + Nelder-Mead                      -> vifit2.json
Bildnummer = Index nach ffmpeg fps=30:start_time=0 (= round(pts*30)).
"""
import os, sys, json, subprocess
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "edit-toolkit"))
PUR = np.array([47.6, 12.3, 33.7], np.float32)        # Hintergrund-Lila (BGR)
BOX = (286, 130, 430, 334)                             # Logo-Kasten bei Bild 234


def decode(path, out_npy):
    if os.path.exists(out_npy):
        return np.load(out_npy, mmap_mode="r")
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-vf", "fps=30:start_time=0,scale=1024:576", "-f", "rawvideo",
           "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, 576, 1024, 3)
    np.save(out_npy, a)
    return np.load(out_npy, mmap_mode="r")


def faces(a, out):
    from face_track import FaceTracker
    ft = FaceTracker(score=0.55)
    res = {}
    for i in range(0, min(341, len(a))):
        big = cv2.resize(np.ascontiguousarray(a[i][..., ::-1]), (2048, 1152), interpolation=cv2.INTER_CUBIC)
        res[i] = [[round(cx / 2, 1), round(cy / 2, 1), round(fh / 2, 1), round(sc, 2)]
                  for cx, cy, fw, fh, sc in ft.detect(big, max_side=2048)]
    json.dump(res, open(os.path.join(out, "faces_dense.json"), "w"))


def _ransac(xs, ys, it=400, tol=3.0, rng=np.random.default_rng(0)):
    if len(xs) < 20:
        return None
    best = None
    for _ in range(it):
        i, j = rng.choice(len(xs), 2, replace=False)
        if xs[i] == xs[j]:
            continue
        m = (ys[j] - ys[i]) / (xs[j] - xs[i])
        b = ys[i] - m * xs[i]
        inl = np.abs(ys - (m * xs + b)) < tol
        if best is None or inl.sum() > best[0]:
            best = (inl.sum(), inl)
    n, inl = best
    A = np.vstack([xs[inl], np.ones(inl.sum())]).T
    m, b = np.linalg.lstsq(A, ys[inl], rcond=None)[0]
    return float(m), float(b), int(n), len(xs)


def bands(a, out):
    res = {}
    for t in list(range(6, 228, 3)) + list(range(258, 340, 2)):
        P = np.linalg.norm(a[t].astype(np.float32) - PUR, axis=2) < 26
        H, W = P.shape
        xt, yt, xb, yb = [], [], [], []
        for x in range(0, W, 4):
            col = P[:, x]
            if col[0] and col[1]:
                y = np.argmax(~col)
                if y > 0 and not col[y:y + 8].any():
                    xt.append(x); yt.append(y)
            if col[-1] and col[-2]:
                y = H - 1 - np.argmax(~col[::-1])
                if y < H - 1 and not col[max(0, y - 8):y + 1].any():
                    xb.append(x); yb.append(y)
        res[t] = dict(top=_ransac(np.array(xt, float), np.array(yt, float)) if xt else None,
                      bot=_ransac(np.array(xb, float), np.array(yb, float)) if xb else None, purple=float(P.mean()))
    json.dump(res, open(os.path.join(out, "bands.json"), "w"))


def flow(a, out):
    q = 0.5
    small = lambda t: cv2.resize(np.ascontiguousarray(a[t]), None, fx=q, fy=q, interpolation=cv2.INTER_AREA)
    res = {}
    prev = small(10)
    pg = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    for t in range(11, 206):
        cur = small(t)
        cg = cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY)
        fl = cv2.calcOpticalFlowFarneback(pg, cg, None, 0.5, 4, 21, 4, 7, 1.5, 0)
        f = prev.astype(np.int32)
        sky = (f[..., 0] - f[..., 1] > 30) & (f.sum(2) > 240)
        tex = np.hypot(cv2.Sobel(pg, cv2.CV_32F, 1, 0), cv2.Sobel(pg, cv2.CV_32F, 0, 1)) > 20
        m = cv2.erode((sky & tex).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        if m.sum() > 200:
            ys, xs = np.nonzero(m)
            dx, dy = fl[ys, xs, 0], fl[ys, xs, 1]
            A = np.vstack([np.concatenate([xs, ys]), np.concatenate([np.ones_like(xs), np.zeros_like(xs)]),
                           np.concatenate([np.zeros_like(ys), np.ones_like(ys)])]).T.astype(np.float64)
            sol = np.linalg.lstsq(A, np.concatenate([dx, dy]).astype(np.float64), rcond=None)[0]
            res[t] = dict(n=int(m.sum()), med=[float(np.median(dx)) / q, float(np.median(dy)) / q], k=float(sol[0]))
        prev, pg = cur, cg
    json.dump(res, open(os.path.join(out, "skyflow.json"), "w"))


def logo_template(a):
    x, y, w, h = BOX
    crop = np.mean([a[t][y:y + h, x:x + w].astype(np.float32) for t in (233, 234)], 0)
    d = np.linalg.norm(crop - PUR, axis=2)
    solid = cv2.morphologyEx((d > 16).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    ff = solid.copy()
    cv2.floodFill(ff, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 2)
    filled = ((ff != 2) | (solid > 0)).astype(np.float32)
    alpha = np.maximum(np.clip((d - 8) / 22, 0, 1), cv2.erode(filled, np.ones((3, 3), np.uint8)))
    return crop, alpha, filled


def logo(a, out):
    T0, A0, _ = logo_template(a)
    H0, W0 = A0.shape
    res = {}
    for t in range(200, 250):
        f = np.ascontiguousarray(a[t]).astype(np.float32)
        best = None
        for s in np.exp(np.linspace(np.log(0.08), np.log(1.06), 90)):
            w, h = int(round(W0 * s)), int(round(H0 * s))
            if w < 12:
                continue
            T = cv2.resize(T0, (w, h), interpolation=cv2.INTER_AREA)
            M = (cv2.resize(A0, (w, h), interpolation=cv2.INTER_AREA) > 0.9).astype(np.float32)
            if M.sum() < 30:
                continue
            r = cv2.matchTemplate(f, T, cv2.TM_SQDIFF, mask=np.dstack([M] * 3))
            mn, _, loc, _ = cv2.minMaxLoc(r)
            sc = mn / (M.sum() * 3)
            if best is None or sc < best[0]:
                best = (sc, s, loc[0] + w / 2, loc[1] + h / 2)
        res[t] = dict(logo=[float(v) for v in best[1:]], logo_err=float(best[0]))
    json.dump(res, open(os.path.join(out, "vifit.json"), "w"))


def window(a, out):
    from scipy.optimize import minimize
    _, _, V = logo_template(a)
    H0, W0 = V.shape
    q = 0.25
    valid = np.ones((144, 256), np.float32)
    valid[125:, 225:] = 0                                          # TikTok-Zeichen

    def pm(t):
        f = np.ascontiguousarray(a[t]).astype(np.float32)
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        mu = cv2.blur(g, (7, 7))
        sd = np.sqrt(np.maximum(cv2.blur(g * g, (7, 7)) - mu * mu, 0))
        P = ((np.linalg.norm(f - PUR, axis=2) < 20) & (sd < 3.5)).astype(np.float32)
        return cv2.resize(P, (256, 144), interpolation=cv2.INTER_AREA)

    def cost(p, P):
        s, cx, cy = p
        if s <= 0.3:
            return 1.0
        M = np.array([[s * q, 0, q * (cx - s * W0 / 2)], [0, s * q, q * (cy - s * H0 / 2)]], np.float32)
        Wm = cv2.warpAffine(V, M, (256, 144), flags=cv2.INTER_LINEAR, borderValue=0)
        return float((np.abs((1 - Wm) - P) * valid).sum() / valid.sum())

    res = {}
    for t in range(190, 233):
        P = pm(t)
        best = (9, None)
        for s in np.exp(np.linspace(np.log(0.85), np.log(9.0), 36)):
            for cx in np.arange(-200, 1250, 40):
                for cy in np.arange(-150, 750, 40):
                    c = cost((s, cx, cy), P)
                    if c < best[0]:
                        best = (c, (s, cx, cy))
        p0 = best[1]
        r = minimize(cost, p0, args=(P,), method="Nelder-Mead", options=dict(
            xatol=0.1, fatol=1e-6, maxiter=800,
            initial_simplex=[p0, [p0[0] * 1.05, p0[1], p0[2]], [p0[0], p0[1] + 15, p0[2]], [p0[0], p0[1], p0[2] + 15]]))
        res[t] = [float(v) for v in r.x] + [float(r.fun), float(P.mean())]
    json.dump(res, open(os.path.join(out, "vifit2.json"), "w"))


def main():
    ref, out = sys.argv[1:3]
    steps = sys.argv[3].split(",") if len(sys.argv) > 3 else ["faces", "bands", "flow", "logo", "window"]
    os.makedirs(out, exist_ok=True)
    a = decode(ref, os.path.join(out, "ref.npy"))
    for s in steps:
        print("Messung:", s, flush=True)
        globals()[s](a, out)


if __name__ == "__main__":
    main()
