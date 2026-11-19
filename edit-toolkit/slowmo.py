"""Zeitlupe fuer 30-fps-Quellen: Zwischenbild genau in der Mitte zweier echter Bilder berechnen.

Optischer Fluss (DIS, OpenCV) in beide Richtungen, dann beide Bilder zur Mitte verschieben und
mischen (Naeherung wie bei "Super SloMo": F_t0 = -t(1-t) F01 + t^2 F10,  F_t1 = (1-t)^2 F01 - t(1-t) F10).
Fuer ruhige Bewegungen sehr sauber; bei schnellen Bewegungen / Verdeckungen koennen weiche Schlieren
entstehen -> fuer Zeitlupe bevorzugt ruhige Momente waehlen.

    from slowmo import double_rate
    frames2, times2 = double_rate(frames, times)     # doppelt so viele Bilder, Zeiten in der Mitte
"""
import numpy as np
import cv2

_DIS = None


def _flow(a, b):
    global _DIS
    if _DIS is None:
        _DIS = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    return _DIS.calc(a, b, None)


def midframe(f0, f1, scale=0.5, t=0.5):
    h, w = f0.shape[:2]
    g0 = cv2.cvtColor(cv2.resize(f0, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
    g1 = cv2.cvtColor(cv2.resize(f1, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
    F01 = _flow(g0, g1)
    F10 = _flow(g1, g0)
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
