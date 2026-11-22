"""Zeitlupe fuer 30-fps-Quellen: Zwischenbild genau in der Mitte zweier echter Bilder berechnen.

Optischer Fluss (DIS, OpenCV) in beide Richtungen, dann beide Bilder zur Mitte verschieben und
mischen (Naeherung wie bei "Super SloMo": F_t0 = -t(1-t) F01 + t^2 F10,  F_t1 = (1-t)^2 F01 - t(1-t) F10).
Fuer ruhige Bewegungen sehr sauber; bei schnellen Bewegungen / Verdeckungen koennen weiche Schlieren
entstehen -> fuer Zeitlupe bevorzugt ruhige Momente waehlen.

    from slowmo import double_rate
    frames2, times2 = double_rate(frames, times)     # doppelt so viele Bilder, Zeiten in der Mitte

    from slowmo import resample                      # besser bei ungleichmaessigem Bildtakt (siehe unten)
    frames2, times2 = resample(frames, times, gewuenschte_zeiten)

Ungleichmaessiger Bildtakt: Manche Aufnahmen (TV-Mitschnitte, bearbeitete Fancams) liefern neue Bilder mal
nach 17, mal nach 33 oder 67 ms. double_rate setzt nur EIN Bild in jede Luecke -> in Zeitlupe ruckelt es
(gemessen: Wechsel-Unruhe 0,6-0,8 statt 0,1-0,2). resample() erzeugt fuer jede gewuenschte Zeit genau ein Bild:
echtes Bild, wenn eines (fast) genau dort liegt, sonst Zwischenbild mit passendem Anteil t. Das Zeitraster
wird dabei um bis zu eine halbe Bilddauer verschoben, damit moeglichst viele echte Bilder getroffen werden.
"""
import numpy as np
import cv2

_DIS = None


def _flow(a, b):
    global _DIS
    if _DIS is None:
        _DIS = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    return _DIS.calc(a, b, None)


def _flows(f0, f1, scale):
    g0 = cv2.cvtColor(cv2.resize(f0, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
    g1 = cv2.cvtColor(cv2.resize(f1, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
    return _flow(g0, g1), _flow(g1, g0)


def midframe(f0, f1, scale=0.5, t=0.5, flows=None):
    h, w = f0.shape[:2]
    F01, F10 = flows if flows is not None else _flows(f0, f1, scale)
    Ft0 = -t * (1 - t) * F01 + t * t * F10
    Ft1 = (1 - t) * (1 - t) * F01 - t * (1 - t) * F10
    Ft0 = cv2.resize(Ft0, (w, h), interpolation=cv2.INTER_LINEAR) / scale
    Ft1 = cv2.resize(Ft1, (w, h), interpolation=cv2.INTER_LINEAR) / scale
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    w0 = cv2.remap(f0, gx + Ft0[..., 0], gy + Ft0[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    w1 = cv2.remap(f1, gx + Ft1[..., 0], gy + Ft1[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    out = w0.astype(np.float32) * (1 - t) + w1.astype(np.float32) * t
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def double_rate(frames, times):
    """frames: Array (n, h, w, 3) RGB uint8 mit echten (nicht doppelten) Bildern, times: Zeiten in s."""
    out, ts = [], []
    for k in range(len(frames)):
        out.append(frames[k])
        ts.append(times[k])
        if k + 1 < len(frames):
            out.append(midframe(frames[k], frames[k + 1]))
            ts.append((times[k] + times[k + 1]) / 2)
    return np.stack(out), np.array(ts)


def resample(frames, times, t_out, scale=0.75, tol=0.0025, sharpen=True):
    """Bilder genau zu den Zeiten t_out (Sekunden, aufsteigend) liefern.
    frames/times: echte (entdoppelte) Bilder mit ihren Zeiten. Rueckgabe: (Bilder, t_out)."""
    times = np.asarray(times, np.float64)
    t_out = np.asarray(t_out, np.float64)
    step = float(np.median(np.diff(t_out))) if len(t_out) > 1 else 1 / 60
    # Raster so verschieben, dass moeglichst viele gewuenschte Zeiten auf echte Bilder fallen
    best, best_n = 0.0, -1
    for d in np.arange(-step / 2, step / 2 + 1e-9, 0.0005):
        j = np.clip(np.searchsorted(times, t_out + d), 1, len(times) - 1)
        near = np.minimum(np.abs(times[j] - (t_out + d)), np.abs(times[j - 1] - (t_out + d)))
        n = int((near <= tol).sum())
        if n > best_n or (n == best_n and abs(d) < abs(best)):
            best, best_n = d, n
    out, cache = [], {}
    for ts in t_out + best:
        j = int(np.searchsorted(times, ts))
        if j < len(times) and abs(times[j] - ts) <= tol:
            out.append(frames[j])
            continue
        if j > 0 and abs(times[j - 1] - ts) <= tol:
            out.append(frames[j - 1])
            continue
        if j <= 0:
            out.append(frames[0])
            continue
        if j >= len(times):
            out.append(frames[-1])
            continue
        a = j - 1
        if a not in cache:
            cache = {a: _flows(frames[a], frames[j], scale)}
        w = float((ts - times[a]) / (times[j] - times[a]))
        mid = midframe(frames[a], frames[j], scale=scale, t=w, flows=cache[a])
        out.append(match_detail(mid, frames[a], frames[j]) if sharpen else mid)
    return np.stack(out), t_out


def _detail(img):
    g = cv2.cvtColor(cv2.resize(img, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY).astype(np.float32)
    return float(np.mean((g - cv2.GaussianBlur(g, (0, 0), 1.0)) ** 2)) + 1e-6


def match_detail(mid, f0, f1):
    """Zwischenbilder sind etwas weicher als echte Bilder -> Schaerfe pulsiert im Wechsel.
    Feine Details so weit anheben, dass sie zu den beiden echten Nachbarbildern passen."""
    want = 0.5 * (_detail(f0) + _detail(f1))
    have = _detail(mid)
    if have >= want:
        return mid
    k = float(np.clip(np.sqrt(want / have) - 1.0, 0.0, 0.8))
    x = mid.astype(np.float32)
    x = x + k * (x - cv2.GaussianBlur(x, (0, 0), 1.0))
    return np.clip(x + 0.5, 0, 255).astype(np.uint8)
