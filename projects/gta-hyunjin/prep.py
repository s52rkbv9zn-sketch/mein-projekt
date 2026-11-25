#!/usr/bin/env python3
"""Bilder fuer das GTA-VI-Edit vorbereiten (Referenz 11).

1. Hyunjin-Fotos (vom Nutzer) freistellen lassen (Masken kommen fertig mit), auf doppelte Groesse bringen,
   am Bildrand abgeschnittene Koerper weiterfuehren (Schulter/Arm/Oberkoerper, damit im Video keine geraden
   Schnittkanten zu sehen sind) und im GTA-Ladebild-Stil zeichnen: flache Farbflaechen, Tusche-Linien,
   Abendlicht (Schatten lila, Lichter warm), dunkle Kontur um die Figur.
2. Hintergruende wie im Vorbild malen: Abendhimmel mit Kokospalmen (Hauptbild), Keil-Himmel (blau/pfirsich),
   drei Kachel-Hintergruende (blau-rosa mit Palmen, Sonnenuntergang mit Strand, violett-orange mit Palmen).

    python3 prep.py FOTO_ORDNER MASKEN_ORDNER AUSGABE_ORDNER
FOTO_ORDNER: A.jpg ... E.jpg, MASKEN_ORDNER: A_mask.png ... (0..255); fehlt eine PNG, wird masken.json genommen
(Umrisse: GrabCut mit nachgezeichneten Vielecken als harte Grenze, bei A der dunkle Hintergrund neben dem Hals entfernt)
Ausgabe: A.png ... E.png (RGBA, 2x), faces.json (Gesicht je Bild in Ausgabe-Pixeln),
         sky_main.png, sky_wedge.png, panel_B.png, panel_C.png, panel_R.png
"""
import os, sys, json
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "edit-toolkit"))
sys.path.insert(0, HERE)

KEYS = "ABCDE"
UP = 2.0                       # Fotos auf doppelte Groesse (Linien werden in der Endgroesse scharf gezeichnet)
K = 1.875                      # Vorbild 1024x576 -> Ausgabe 1920x1080


# ---------------------------------------------------------------- Figuren

def extend_cutout(photo, mask, face_h, pads):
    """Am Bildrand abgeschnittenen Koerper weiterfuehren.
    pads = (links, rechts, unten) in Pixeln. Die Silhouette waechst an den Seiten wie eine Schulter
    (schnell breiter, dann senkrecht), unten geht sie gerade weiter. Farbe per Inpainting (weich),
    nach aussen leicht abgedunkelt."""
    H, W = mask.shape
    pl, pr, pb = pads
    NH, NW = H + pb, W + pl + pr
    m = mask.astype(np.float32) / 255.0
    M = np.zeros((NH, NW), np.float32)
    M[:H, pl:pl + W] = m
    known = np.zeros((NH, NW), bool)
    known[:H, pl:pl + W] = m > 0.5
    if pb:
        M[H:, pl:pl + W] = m[H - 1][None, :]
    wmax, lw = 0.22 * face_h, 0.14 * face_h
    for side in ("L", "R"):
        width = pr if side == "R" else pl
        if width <= 0:
            continue
        col = M[:, pl + W - 1] if side == "R" else M[:, pl]
        touch = np.nonzero(col > 0.5)[0]
        if len(touch) == 0:
            continue
        y0 = touch[0]
        for y in range(y0, NH):
            if col[y] <= 0.5:
                continue
            w = int(min(width, wmax * (1 - np.exp(-(y - y0) / lw)) + 2))
            if side == "R":
                M[y, pl + W:pl + W + w] = 1.0
            else:
                M[y, pl - w:pl] = 1.0
    ext = ~np.zeros((NH, NW), bool)
    ext[:H, pl:pl + W] = False
    Ms = cv2.GaussianBlur(M, (0, 0), 2.5)
    M = np.where(ext, Ms, M)
    img = np.zeros((NH, NW, 3), np.uint8)
    img[:H, pl:pl + W] = photo
    f = 4
    sw, sh = NW // f, NH // f
    small = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA)
    ks = cv2.resize(known.astype(np.float32), (sw, sh), interpolation=cv2.INTER_AREA) > 0.999
    inp = cv2.inpaint(small, (~ks).astype(np.uint8), 7, cv2.INPAINT_TELEA).astype(np.float32)
    near = cv2.GaussianBlur(inp, (0, 0), 1.5)
    far = cv2.GaussianBlur(inp, (0, 0), 0.12 * face_h / f)          # weiche Flaeche statt Schlieren
    dist = cv2.distanceTransform((~known).astype(np.uint8), cv2.DIST_L2, 5)
    wfar = np.clip(cv2.resize(dist, (sw, sh), interpolation=cv2.INTER_AREA) / (0.15 * face_h), 0, 1)[..., None]
    inp = near * (1 - wfar) + far * wfar
    big = cv2.resize(inp, (NW, NH), interpolation=cv2.INTER_CUBIC)
    shade = 1 - 0.35 * np.clip(dist / (0.9 * face_h), 0, 1)
    out = np.where(known[..., None], img.astype(np.float32), big * shade[..., None])
    return np.clip(out, 0, 255).astype(np.uint8), np.clip(M * 255, 0, 255).astype(np.uint8)


def gta_look(img, mask, s):
    """img BGR uint8, mask 0..255, s = Strichstaerke (1 = Foto mit ~1300 px) -> gezeichnete Figur + Alpha"""
    x = img.copy()
    d = int(round(9 * s)) | 1
    for _ in range(3):
        x = cv2.bilateralFilter(x, d, 38, 7 * s)
    fg = mask > 128
    Z = x[fg].reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    sel = Z[np.random.default_rng(1).choice(len(Z), min(len(Z), 60000), replace=False)]
    _, _, cen = cv2.kmeans(sel, 20, None, crit, 2, cv2.KMEANS_PP_CENTERS)
    flat = x.reshape(-1, 3).astype(np.float32)
    lab = np.empty(len(flat), np.int32)
    for i in range(0, len(flat), 1 << 20):
        ch = flat[i:i + (1 << 20)]
        lab[i:i + (1 << 20)] = np.argmin(((ch[:, None, :] - cen[None]) ** 2).sum(2), 1)
    q = cen[lab].reshape(x.shape).astype(np.uint8)
    out = cv2.addWeighted(q, 0.62, x, 0.38, 0).astype(np.float32)
    g = cv2.cvtColor(cv2.GaussianBlur(x, (0, 0), 1.0 * s), cv2.COLOR_BGR2GRAY)
    e = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, int(11 * s) | 1, 6)
    e = cv2.GaussianBlur(e, (0, 0), 0.8 * s) / 255.0
    out = out * (0.40 + 0.60 * e[..., None])
    y = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    sh = (1 - y)[..., None] ** 2
    hi = y[..., None] ** 2
    out = out + sh * np.array([16, -4, 8], np.float32) + hi * np.array([-30, 6, 34], np.float32)   # BGR: Schatten kaum lila, Lichter warm
    out = np.clip(out, 0, 255).astype(np.uint8)
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.25, 0, 255)                                       # kraeftigere Farben
    hsv[..., 2] = 255.0 * (hsv[..., 2] / 255.0) ** 0.82                                      # heller wie im Vorbild
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    out = np.clip((out - 6) * 1.05 + 5, 0, 255)
    k = int(round(7 * s)) | 1
    m = (mask > 128).astype(np.uint8)
    ring = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) - m
    alpha = np.clip(mask.astype(np.float32) / 255.0 + ring.astype(np.float32), 0, 1)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.8 * s)
    col = np.where(ring[..., None] > 0, np.array([34, 10, 22], np.float32), out)
    return col.astype(np.uint8), alpha


def make_figure(photo, mask, face):
    """face = (cx, cy, h) im Foto. Rueckgabe RGBA (2x, erweitert) und Gesicht in diesen Pixeln."""
    h, w = mask.shape
    big = cv2.resize(photo, (int(w * UP), int(h * UP)), interpolation=cv2.INTER_LANCZOS4)
    mb = cv2.resize(mask, (int(w * UP), int(h * UP)), interpolation=cv2.INTER_LINEAR)
    mb = cv2.GaussianBlur(mb, (0, 0), 1.0)
    fh = face[2] * UP
    al = mb > 128
    pads = (int(0.8 * fh) if al[:, 0].any() else 0, int(0.8 * fh) if al[:, -1].any() else 0,
            int(1.3 * fh) if al[-1].any() else 0)
    ext, m2 = extend_cutout(big, mb, fh, pads)
    s = UP * max(h, w) / 1300.0
    col, alpha = gta_look(ext, m2, s)
    rgba = np.dstack([col, (alpha * 255).astype(np.uint8)])
    return rgba, (face[0] * UP + pads[0], face[1] * UP, fh)


# ---------------------------------------------------------------- Himmel und Palmen

def _bez(p0, p1, p2, u):
    u = np.asarray(u)[:, None]
    return (1 - u) ** 2 * p0 + 2 * (1 - u) * u * p1 + u ** 2 * p2


def draw_palm(canvas, base, height, lean, rng, n_fronds=12):
    """Kokospalme als Silhouette (255) in ein uint8-Bild: gebogener Stamm, Wedel mit vielen haengenden
    Fiederblaettchen (spitze Dreiecke), oben ein dichter Schopf."""
    x0, y0 = base
    top = np.array([x0 + lean * height, y0 - height], np.float32)
    ctrl = np.array([x0 + lean * height * 0.15 + rng.normal(0, 0.04) * height, y0 - height * 0.55], np.float32)
    u = np.linspace(0, 1, 80)
    sp = _bez(np.array([x0, y0], np.float32), ctrl, top, u)
    tg = np.gradient(sp, axis=0)
    tg /= np.linalg.norm(tg, axis=1, keepdims=True) + 1e-6
    nr = np.stack([-tg[:, 1], tg[:, 0]], 1)
    wid = height * (0.040 * (1 - u) + 0.020 * u)[:, None]
    poly = np.concatenate([sp + nr * wid / 2, (sp - nr * wid / 2)[::-1]])
    cv2.fillPoly(canvas, [np.round(poly * 4).astype(np.int32)], 255, lineType=cv2.LINE_AA, shift=2)
    angs = np.linspace(-195, 15, n_fronds) + rng.normal(0, 7, n_fronds)
    for a in angs:
        a = np.deg2rad(a)
        d = np.array([np.cos(a), np.sin(a)], np.float32)
        L = height * rng.uniform(0.36, 0.50)
        side = abs(np.cos(a))
        droop = 0.15 + 0.55 * side + rng.uniform(-0.05, 0.1)
        p1 = top + d * L * 0.55 + np.array([0, -L * 0.18 * (1 - 0.3 * side)], np.float32)
        p2 = top + np.array([d[0] * L, d[1] * L * 0.45 + droop * L], np.float32)
        uu = np.linspace(0, 1, 60)
        spn = _bez(top, p1, p2, uu)
        t2 = np.gradient(spn, axis=0)
        t2 /= np.linalg.norm(t2, axis=1, keepdims=True) + 1e-6
        polys = []
        for i in range(3, 60, 2):
            uf = uu[i]
            ln = L * 0.24 * np.sin(np.pi * min(1.0, uf * 1.05)) ** 0.7 * (1 - 0.35 * uf)
            if ln < 2:
                continue
            for sgn in (1, -1):
                ang = np.deg2rad(52) * sgn
                c, s_ = np.cos(ang), np.sin(ang)
                dv = np.array([t2[i, 0] * c - t2[i, 1] * s_, t2[i, 0] * s_ + t2[i, 1] * c])
                dv = dv + np.array([0, 0.75])
                dv /= np.linalg.norm(dv)
                w0 = max(1.0, L * 0.013)
                b0 = spn[i] - t2[i] * w0
                b1 = spn[i] + t2[i] * w0
                tip = spn[i] + dv * ln
                polys.append(np.round(np.array([b0, b1, tip]) * 4).astype(np.int32))
        cv2.fillPoly(canvas, polys, 255, lineType=cv2.LINE_AA, shift=2)
        cv2.polylines(canvas, [np.round(spn * 4).astype(np.int32)], False, 255, max(1, int(L * 0.016)),
                      lineType=cv2.LINE_AA, shift=2)
    cv2.circle(canvas, tuple(int(v) for v in top), int(height * 0.035), 255, -1, lineType=cv2.LINE_AA)


def gradient(h, w, stops, axis=0):
    """stops: [(pos 0..1, (B,G,R)), ...] entlang axis (0 = senkrecht)"""
    n = h if axis == 0 else w
    pos = np.linspace(0, 1, n)
    g = np.stack([np.interp(pos, [s[0] for s in stops], [s[1][c] for s in stops]) for c in range(3)], 1)
    g = g.astype(np.float32)
    return np.broadcast_to(g[:, None, :], (h, w, 3)).copy() if axis == 0 else np.broadcast_to(g[None], (h, w, 3)).copy()


def add_clouds(img, rng, n, y_rng, col, strength, scale):
    h, w = img.shape[:2]
    cl = np.zeros((h, w), np.float32)
    for _ in range(n):
        cy = rng.uniform(*y_rng) * h
        cx = rng.uniform(0, w)
        cv2.ellipse(cl, (int(cx), int(cy)), (int(rng.uniform(120, 420) * scale), int(rng.uniform(5, 16) * scale)),
                    rng.uniform(-3, 3), 0, 360, rng.uniform(0.4, 1.0), -1, lineType=cv2.LINE_AA)
    cl = cv2.GaussianBlur(cl, (0, 0), 10 * scale)
    a = np.clip(cl * strength, 0, 0.6)[..., None]
    return img * (1 - a) + np.array(col, np.float32) * a


def add_palms(img, rng, palms, color, alpha, ss=2):
    """palms: [(x, y_base, height, lean, n_fronds), ...] in Bildpixeln"""
    h, w = img.shape[:2]
    can = np.zeros((h * ss, w * ss), np.uint8)
    for x, yb, hg, lean, nf in palms:
        draw_palm(can, (x * ss, yb * ss), hg * ss, lean, rng, nf)
    m = cv2.resize(can, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    m = cv2.GaussianBlur(m, (0, 0), 0.6)
    if callable(color):
        col = color(h, w)
    else:
        col = np.broadcast_to(np.array(color, np.float32), (h, w, 3))
    a = (m * alpha)[..., None]
    return img * (1 - a) + col * a


def add_birds(img, pts, size, col):
    for x, y in pts:
        s = size
        pts1 = np.array([[x - s, y - s * 0.35], [x - s * 0.45, y - s * 0.5], [x, y]], np.float32)
        pts2 = np.array([[x, y], [x + s * 0.45, y - s * 0.5], [x + s, y - s * 0.35]], np.float32)
        for p in (pts1, pts2):
            cv2.polylines(img, [np.round(p * 4).astype(np.int32)], False, col, max(1, int(s * 0.18)),
                          lineType=cv2.LINE_AA, shift=2)
    return img


def grain(img, rng, amount=3.0):
    return img + rng.normal(0, amount, img.shape[:2])[..., None].astype(np.float32)


def palm_tint(top, bottom):
    def f(h, w):
        t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        return np.broadcast_to(np.array(top, np.float32) * (1 - t) + np.array(bottom, np.float32) * t, (h, w, 3))
    return f


def sky_main(seed=3):
    """Himmel fuer Teil 1-2: Streifen zwischen den lila Baendern. Karten-Koordinaten in Ausgabe-Pixeln:
    Breite 5200, Hoehe 1200; Oberkante des Streifens bei y=82, Unterkante bei y=82+552*K."""
    rng = np.random.default_rng(seed)
    w, h = 5200, 1200
    top, G = 82, 552 * K
    stops = [(0.0, (158, 110, 144)), (0.04, (161, 114, 149)), (0.11, (165, 118, 160)), (0.19, (166, 121, 170)),
             (0.26, (165, 124, 178)), (0.34, (167, 126, 186)), (0.42, (168, 132, 195)), (0.49, (166, 130, 199)),
             (0.57, (165, 129, 204)), (0.64, (165, 125, 211)), (0.72, (163, 144, 232)), (0.80, (152, 158, 243)),
             (0.87, (140, 166, 247)), (0.95, (131, 157, 237)), (1.0, (126, 150, 228))]
    stops = [((top + p * G) / h, c) for p, c in stops]
    stops = [(0.0, stops[0][1])] + stops + [(1.0, stops[-1][1])]
    img = gradient(h, w, stops)
    img = add_clouds(img, rng, 40, ((top + 0.45 * G) / h, (top + 0.9 * G) / h), (175, 160, 245), 0.9, 1.6)
    img = add_clouds(img, rng, 18, ((top + 0.15 * G) / h, (top + 0.5 * G) / h), (180, 140, 200), 0.6, 1.6)
    yb = top + G + 30
    far = [(x, yb, rng.uniform(0.55, 0.75) * G, rng.uniform(-0.12, 0.12), 11) for x in np.arange(150, w, 520) + rng.normal(0, 90, 10)]
    img = add_palms(img, rng, far, palm_tint((150, 96, 150), (150, 120, 190)), 0.45)
    near = [(x, yb + 40, rng.uniform(0.85, 1.05) * G, rng.uniform(-0.18, 0.18), 13) for x in np.arange(420, w, 900) + rng.normal(0, 120, 6)]
    img = add_palms(img, rng, near, palm_tint((112, 64, 118), (118, 84, 140)), 0.88)
    img = add_birds(img, [(1700, top + 0.62 * G), (1745, top + 0.66 * G), (3300, top + 0.55 * G)], 16, (110, 80, 120))
    img = grain(img, rng, 2.5)
    return np.clip(img, 0, 255).astype(np.uint8)


def sky_wedge(seed=5):
    """Himmel im Keil (Teil 3): links rosa-lila, Mitte pfirsich-gelb, rechts blau; grosse Palmen. 1920x1080."""
    rng = np.random.default_rng(seed)
    w, h = 2100, 1180
    xs = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    ys = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    horiz = [(0.0, (150, 98, 168)), (0.25, (150, 140, 215)), (0.45, (160, 185, 240)), (0.62, (165, 150, 200)),
             (0.75, (166, 118, 120)), (1.0, (176, 130, 74))]
    img = np.stack([np.interp(xs[0], [s[0] for s in horiz], [s[1][c] for s in horiz]) for c in range(3)], 1)
    img = np.broadcast_to(img[None], (h, w, 3)).astype(np.float32).copy()
    glow = np.exp(-(((xs - 0.48) / 0.28) ** 2 + ((ys - 0.82) / 0.35) ** 2))[..., None]
    img = img * (1 - 0.55 * glow) + np.array([185, 220, 250], np.float32) * 0.55 * glow
    top = np.clip(1 - ys / 0.5, 0, 1)[..., None] * np.clip((xs - 0.3) / 0.4, 0, 1)[..., None]
    img = img * (1 - 0.35 * top) + np.array([170, 120, 90], np.float32) * 0.35 * top
    img = add_clouds(img, rng, 16, (0.55, 0.9), (190, 200, 245), 0.6, 1.4)
    palms = [(700, h + 30, 0.60 * h, 0.05, 13), (1500, h + 40, 0.66 * h, -0.07, 14), (160, h + 20, 0.48 * h, 0.1, 11),
             (2000, h + 20, 0.55 * h, 0.05, 12)]
    img = add_palms(img, rng, palms, palm_tint((105, 58, 112), (125, 75, 140)), 0.8)
    img = grain(img, rng, 2.5)
    return np.clip(img, 0, 255).astype(np.uint8)


def panel_bg(kind, seed):
    """Kachel-Hintergruende 640x1110 (etwas groesser als die Kachel 632x1080)."""
    rng = np.random.default_rng(seed)
    w, h = 700, 1180
    if kind == "B":
        stops = [(0.0, (172, 80, 72)), (0.1, (177, 87, 82)), (0.25, (145, 77, 113)), (0.38, (148, 80, 139)),
                 (0.55, (150, 110, 190)), (0.75, (155, 160, 226)), (1.0, (161, 175, 230))]
        img = gradient(h, w, stops)
        img = add_clouds(img, rng, 10, (0.45, 0.85), (175, 170, 240), 0.6, 1.2)
        img = add_palms(img, rng, [(80, h + 20, 0.75 * h, 0.08, 12), (560, h + 30, 0.6 * h, -0.1, 11)],
                        palm_tint((120, 60, 110), (130, 90, 150)), 0.7)
    elif kind == "C":
        stops = [(0.0, (155, 168, 242)), (0.14, (140, 178, 247)), (0.25, (126, 186, 249)), (0.36, (117, 185, 250)),
                 (0.47, (111, 188, 248)), (0.58, (127, 193, 248)), (0.66, (150, 205, 250)), (0.70, (200, 205, 230)),
                 (0.73, (215, 200, 205)), (0.76, (180, 226, 252)), (1.0, (178, 219, 246))]
        img = gradient(h, w, stops)
        img = add_clouds(img, rng, 12, (0.3, 0.65), (170, 210, 252), 0.7, 1.2)
        img = add_palms(img, rng, [(40, int(0.72 * h), 0.35 * h, 0.15, 11)], palm_tint((120, 110, 170), (130, 130, 190)), 0.5)
    else:
        stops = [(0.0, (140, 62, 70)), (0.12, (145, 75, 115)), (0.24, (148, 88, 154)), (0.35, (150, 99, 183)),
                 (0.5, (130, 130, 215)), (0.6, (109, 158, 229)), (0.72, (162, 160, 217)), (1.0, (170, 165, 220))]
        img = gradient(h, w, stops)
        img = add_clouds(img, rng, 10, (0.45, 0.75), (150, 170, 245), 0.6, 1.2)
        img = add_palms(img, rng, [(600, h + 30, 0.8 * h, -0.08, 13), (150, h + 20, 0.55 * h, 0.1, 11)],
                        palm_tint((112, 58, 110), (125, 85, 140)), 0.75)
    img = grain(img, rng, 2.5)
    return np.clip(img, 0, 255).astype(np.uint8)


def mask_from_json(k):
    """Freistellung aus masken.json (Umriss-Vielecke, im Repo) statt PNG"""
    d = json.load(open(os.path.join(HERE, "masken.json")))[k]
    m = np.zeros((d["size"][1], d["size"][0]), np.uint8)
    for p in d["polys"]:
        if not p["hole"]:
            cv2.fillPoly(m, [np.array(p["pts"], np.int32)], 255, lineType=cv2.LINE_AA)
    for p in d["polys"]:
        if p["hole"]:
            cv2.fillPoly(m, [np.array(p["pts"], np.int32)], 0, lineType=cv2.LINE_AA)
    return m


def main():
    src, msk, out = sys.argv[1:4]
    only = sys.argv[4] if len(sys.argv) > 4 else "figures,skies"
    os.makedirs(out, exist_ok=True)
    if "figures" in only:
        from face_track import FaceTracker
        ft = FaceTracker(score=0.5)
        fj = os.path.join(out, "faces.json")
        faces = json.load(open(fj)) if os.path.exists(fj) else {}
        keys = os.environ.get("KEYS", KEYS)
        for k in (keys.split(",") if "," in keys else list(keys)):
            img = cv2.imread(os.path.join(src, f"{k}.jpg"))
            mp = os.path.join(msk, f"{k}_mask.png")
            if os.path.exists(mp):
                m = cv2.imread(mp, 0)
            elif k in json.load(open(os.path.join(HERE, "masken.json"))):
                m = mask_from_json(k)
            else:                                            # neue Fotos: nur die KI-Matte (keine Vielecke noetig)
                m = (cv2.imread(os.path.join(os.environ["MATTE"], f"{k}_alpha.png"), 0) > 128).astype(np.uint8) * 255
            fs = ft.detect(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), max_side=1600)
            cx, cy, fw, fh, sc = max(fs, key=lambda f: f[4])
            mat = os.environ.get("MATTE")                    # Ordner mit K_alpha.png / K_fgr.png aus matte.py
            if mat:
                import figures
                ra = cv2.imread(os.path.join(mat, f"{k}_alpha.png"), 0)
                rf = cv2.imread(os.path.join(mat, f"{k}_fgr.png"))
                rgba, face = figures.make_figure(k, img, ra, rf, m, (cx, cy, fh))
            else:
                rgba, face = make_figure(img, m, (cx, cy, fh))
            cv2.imwrite(os.path.join(out, f"{k}.png"), rgba)
            faces[k] = [round(float(v), 1) for v in face]
            print("Figur", k, rgba.shape, "Gesicht", faces[k], flush=True)
        json.dump(faces, open(os.path.join(out, "faces.json"), "w"))
    if "skies" in only:
        cv2.imwrite(os.path.join(out, "sky_main.png"), sky_main())
        cv2.imwrite(os.path.join(out, "sky_wedge.png"), sky_wedge())
        for kind, seed in (("B", 11), ("C", 12), ("R", 13)):
            cv2.imwrite(os.path.join(out, f"panel_{kind}.png"), panel_bg(kind, seed))
        print("Himmel fertig", flush=True)


if __name__ == "__main__":
    main()
