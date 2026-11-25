"""Figuren v2 fuer das GTA-VI-Edit: praezise freigestellt, sauber gemalt, Seiten sauber weitergefuehrt.

* Freistellung: KI-Matte (matte.py, RobustVideoMatting) fuer Haare und Kanten, das alte Umriss-Vieleck
  (masken.json) als grobe Grenze (nichts weit ausserhalb) und zum Fuellen innerer Luecken
  (z. B. heller Mantel, den die KI halb durchsichtig macht). Wo die KI Kleidung fuer Hintergrund haelt
  (roter Mantel vor rotem Stuhl), kommen feste Zusatzflaechen dazu (ADD).
* Kantenfarbe aus der KI-Vordergrundschaetzung, damit keine Hintergrundfarbe in den Haaren bleibt.
* Malstil ohne Farbflecken: kantenerhaltende Glaettung (Haut glatt), Feindetail zurueck, duenne Linien (XDoG),
  warme Lichter, Schatten leicht lila, kraeftigere Farben; duenne dunkle Kontur um die feste Silhouette.
* Wo der Koerper am Fotorand abgeschnitten ist und im Edit sichtbar waere (EXTEND), geht er gespiegelt
  weiter: Stoffstruktur bleibt scharf, Rand als glatte Kurve (Schulter, dann senkrecht), leicht abgedunkelt.
  Unten wird nichts verlaengert: Die Fotos sind den Rollen so zugeteilt, dass ihr unterer Rand ausserhalb liegt.
"""
import numpy as np
import cv2

UP = 2.0
EXTEND = dict(A=("R",), D=("L",), E=("L",))
ADD = dict(B=[[(0, 1088), (45, 1066), (95, 1036), (132, 1012), (152, 1002), (152, 1574), (0, 1574)]])
# Farbschimmer vom Hintergrund am Rand (Foto B: rotes Licht vom Stuhl auf den Haaren) im Kopfbereich herausnehmen
DESPILL = dict(B=dict(y_max=990, band=34), P5=dict(y_max=720, band=30))


def ell(n):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))


def combine_alpha(key, rvm, old):
    a = rvm.astype(np.float32) / 255.0
    om = (old > 128).astype(np.uint8)
    inner = cv2.erode(om, ell(31)) > 0
    a = np.where(inner & (a > 0.2), 1.0, a)
    near = cv2.GaussianBlur(cv2.dilate(om, ell(61)).astype(np.float32), (0, 0), 8)
    a = a * near
    for poly in ADD.get(key, []):
        m = np.zeros_like(a)
        cv2.fillPoly(m, [np.array(poly, np.int32)], 1.0, lineType=cv2.LINE_AA)
        a = np.maximum(a, cv2.GaussianBlur(m, (0, 0), 1.5))
    return np.clip(a, 0, 1)


def edge_colors(photo, fgr, a):
    """Kantenfarben ohne Hintergrund: KI-Vordergrundfarbe, dann Farbe vom festen Inneren in den Saum
    hineinziehen (gewichtete Unschaerfe), damit z. B. kein roter Stuhl in den Haarspitzen bleibt."""
    w = np.clip((a - 0.5) / 0.4, 0, 1)[..., None]
    col = photo.astype(np.float32) * w + fgr.astype(np.float32) * (1 - w)
    inner = (a > 0.92).astype(np.float32)
    num = cv2.GaussianBlur(col * inner[..., None], (0, 0), 7)
    den = cv2.GaussianBlur(inner, (0, 0), 7)[..., None]
    prop = num / np.maximum(den, 1e-3)
    k = np.clip((a - 0.25) / 0.65, 0, 1)[..., None]                 # je durchsichtiger, desto mehr Innenfarbe
    k = np.where(den > 0.02, k, 1.0)
    col = col * k + prop * (1 - k)
    return col.clip(0, 255).astype(np.uint8)


def extend_side(col, a, side, fh, y_face):
    """Koerper an einer Seite gespiegelt weiterfuehren. col uint8 BGR, a float 0..1 (gleiche Groesse).
    Rueckgabe: col, a, Verschiebung der x-Koordinaten (Polster links)"""
    H, W = a.shape
    e = W - 1 if side == "R" else 0
    rowok = a[:, e] > 0.5
    rowok[:int(y_face)] = False
    rows = np.nonzero(rowok)[0]
    if len(rows) == 0:
        return col, a, 0
    y0 = rows[0]
    wd, L = 0.16 * fh, 0.07 * fh
    pad = int(wd) + 4
    d = np.arange(1, pad + 1)
    src = (W - 1 - d) if side == "R" else d                       # Spiegelung an der Randspalte
    pc = col[:, src].astype(np.float32)
    pa = a[:, src]
    yy = np.arange(H, dtype=np.float32)
    w = np.where(yy >= y0, wd * (1 - np.exp(-(yy - y0) / L)), 0.0)
    ap = np.clip(w[:, None] - d[None, :] + 0.5, 0, 1) * rowok[:, None] * pa
    pc *= (1 - 0.12 * d / wd)[None, :, None]
    pc = pc.clip(0, 255).astype(np.uint8)
    if side == "R":
        return np.concatenate([col, pc], 1), np.concatenate([a, ap], 1), 0
    return np.concatenate([pc[:, ::-1], col], 1), np.concatenate([ap[:, ::-1], a], 1), pad


def paint(img, s):
    """sauberer Malstil (img BGR uint8, s = Massstab ~ Bildgroesse/1300)"""
    x = img.astype(np.float32) / 255.0
    base = cv2.edgePreservingFilter(img, flags=cv2.RECURS_FILTER, sigma_s=22 * s, sigma_r=0.16).astype(np.float32) / 255.0
    detail = x - cv2.GaussianBlur(x, (0, 0), 1.0 * s)
    out = base + 0.55 * detail
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    g1 = cv2.GaussianBlur(g, (0, 0), 0.8 * s)
    g2 = cv2.GaussianBlur(g, (0, 0), 1.6 * 0.8 * s)
    dg = g1 - 0.985 * g2
    lines = np.where(dg < -0.006, 1 + np.tanh(55 * (dg + 0.006)), 1.0)
    out = out * (0.55 + 0.45 * lines[..., None])
    y = cv2.cvtColor(np.clip(out, 0, 1), cv2.COLOR_BGR2GRAY)[..., None]
    out = out + (1 - y) ** 2 * np.array([0.05, -0.01, 0.03], np.float32) + y ** 2 * np.array([-0.09, 0.02, 0.11], np.float32)
    out8 = (np.clip(out, 0, 1) * 255).astype(np.uint8)
    hsv = cv2.cvtColor(out8, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.18, 0, 255)
    hsv[..., 2] = 255.0 * (hsv[..., 2] / 255.0) ** 0.88
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def outline(col, a, s):
    solid = (cv2.GaussianBlur(a, (0, 0), 1.2 * s) > 0.5).astype(np.uint8)
    r = max(1, int(round(1.6 * s)))
    ring = (cv2.dilate(solid, ell(2 * r + 1)) - solid).astype(np.float32)
    ring = cv2.GaussianBlur(ring, (0, 0), 0.6 * s) * 0.75
    dark = np.array([34, 10, 22], np.float32)
    colf = col.astype(np.float32)
    # Kontur unter die Figur legen: Figur ueber Kontur
    a_out = a + ring * (1 - a)
    c_out = (colf * a[..., None] + dark * (ring * (1 - a))[..., None]) / np.maximum(a_out, 1e-4)[..., None]
    return c_out.clip(0, 255).astype(np.uint8), a_out


def make_figure(key, photo, rvm_alpha, rvm_fgr, old_mask, face):
    """face = (cx, cy, h) im Foto -> RGBA (2x, ggf. seitlich verlaengert) und Gesicht in diesen Pixeln"""
    a = combine_alpha(key, rvm_alpha, old_mask)
    col = edge_colors(photo, rvm_fgr, a)
    ds = DESPILL.get(key)
    if ds:
        dist = cv2.distanceTransform((a > 0.5).astype(np.uint8), cv2.DIST_L2, 5)
        band = np.clip(1 - (dist - ds["band"] * 0.6) / (ds["band"] * 0.4), 0, 1)
        band[ds["y_max"]:] = 0
        c = col.astype(np.float32)
        lim = np.maximum(c[..., 0], c[..., 1]) * 1.15 + 10
        r = np.minimum(c[..., 2], lim)
        c[..., 2] = c[..., 2] * (1 - band) + r * band
        col = c.clip(0, 255).astype(np.uint8)
    h, w = a.shape
    big = cv2.resize(col, (int(w * UP), int(h * UP)), interpolation=cv2.INTER_LANCZOS4)
    ab = np.clip(cv2.resize(a, (int(w * UP), int(h * UP)), interpolation=cv2.INTER_CUBIC), 0, 1)
    fx, fy, fh = face[0] * UP, face[1] * UP, face[2] * UP
    for side in EXTEND.get(key, ()):
        big, ab, sh = extend_side(big, ab, side, fh, fy)
        fx += sh
    s = UP * max(h, w) / 1300.0
    # Rand straffen: weicher Dunst an Haarspitzen wirkt vor dem Himmel schmutzig -> klare, glatte Kante
    ab = cv2.GaussianBlur(ab.astype(np.float32), (0, 0), 0.8)
    t = np.clip((ab - 0.28) / 0.44, 0, 1)
    ab = t * t * (3 - 2 * t)
    col2 = paint(big, s)
    col3, a3 = outline(col2, ab, s)
    return np.dstack([col3, (a3 * 255).clip(0, 255).astype(np.uint8)]), (fx, fy, fh)
