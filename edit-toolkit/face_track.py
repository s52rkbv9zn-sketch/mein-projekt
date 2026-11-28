"""Gesicht finden und weich verfolgen, damit die Person immer mittig im Bild bleibt.

Nutzt YuNet (OpenCV Model Zoo, models/face_detection_yunet_2023mar.onnx).

    from face_track import FaceTracker, track, smooth_track
    ft = FaceTracker()
    raw = track(frames_rgb, hint=(cx, cy), tracker=ft)        # pro Bild (cx, cy, h) oder NaN
    cx, cy, fh = smooth_track(times, raw, sigma_s=0.15)      # geglaettet, Luecken gefuellt

Bei mehreren Gesichtern im Bild wird das Gesicht verfolgt, das am naechsten am Hinweis
(z. B. Bildmitte des alten Ausschnitts) bzw. am vorherigen Treffer liegt; groessere Gesichter
werden bevorzugt.
"""
import os
import numpy as np
import cv2

MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "face_detection_yunet_2023mar.onnx")


class FaceTracker:
    def __init__(self, score=0.6):
        self.det = cv2.FaceDetectorYN.create(MODEL, "", (320, 320), score, 0.3, 5000)

    def detect(self, img_rgb, max_side=1000):
        """Liste von (cx, cy, w, h, score) in Bildkoordinaten"""
        h, w = img_rgb.shape[:2]
        s = min(1.0, max_side / max(h, w))
        small = cv2.resize(img_rgb, (int(round(w * s)), int(round(h * s))), interpolation=cv2.INTER_AREA)
        self.det.setInputSize((small.shape[1], small.shape[0]))
        _, faces = self.det.detect(cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
        if faces is None:
            return []
        out = []
        for f in faces:
            x, y, fw, fh = (float(v) / s for v in f[:4])
            out.append((x + fw / 2, y + fh / 2, fw, fh, float(f[-1])))
        return out


def track(frames, hint, tracker=None, max_jump=0.25):
    """frames: Liste RGB-Bilder. hint: (cx, cy) Startpunkt. Rueckgabe: Array (n, 3) cx, cy, h (NaN = nicht gefunden)."""
    tracker = tracker or FaceTracker()
    n = len(frames)
    out = np.full((n, 3), np.nan, np.float32)
    H = frames[0].shape[0]
    prev = np.array(hint, np.float32)
    prev_h = None
    misses = 0
    for i, im in enumerate(frames):
        faces = tracker.detect(im)
        best, best_cost = None, None
        for cx, cy, fw, fh, sc in faces:
            d = np.hypot(cx - prev[0], cy - prev[1]) / H
            size_pen = 0.0 if prev_h is None else abs(np.log(fh / prev_h))
            cost = d + 0.3 * size_pen - 0.05 * (fh / H) - 0.05 * sc
            if best_cost is None or cost < best_cost:
                best, best_cost = (cx, cy, fh), cost
        jump_ok = best is not None and (prev_h is None or np.hypot(best[0] - prev[0], best[1] - prev[1]) / H < max_jump)
        # nach einem Schnitt in der Quelle (2 Bilder ohne passenden Treffer): auf das groesste Gesicht neu einrasten
        relock = best is not None and not jump_ok and misses >= 2
        if relock:
            best = max(((cx, cy, fh) for cx, cy, fw, fh, sc in faces), key=lambda z: z[2])
        if jump_ok or relock:
            out[i] = best
            prev = np.array(best[:2], np.float32)
            prev_h = best[2]
            misses = 0
        else:
            misses += 1
    return out


def smooth_track(times, raw, sigma_s=0.15):
    """Luecken linear fuellen und mit einem Gauss-Fenster (in Sekunden) glaetten."""
    t = np.asarray(times, np.float64)
    res = []
    for c in range(raw.shape[1]):
        v = raw[:, c].astype(np.float64)
        ok = ~np.isnan(v)
        if not ok.any():
            res.append(np.full(len(t), np.nan))
            continue
        v = np.interp(t, t[ok], v[ok])
        w = np.exp(-0.5 * ((t[:, None] - t[None, :]) / sigma_s) ** 2)
        res.append((w @ v) / w.sum(1))
    return [np.asarray(r, np.float32) for r in res]
