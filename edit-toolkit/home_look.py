"""'home.'-Look (Referenz 3, @dohwxn): weiche, warme Erinnerungs-Optik.

Gemessen an der Referenz (Lab, pro Szene):
  * Schwarz leicht angehoben (L p0.5 ~ 4-14), Lichter weich (L p99.5 ~ 92-97)
  * Saettigung niedrig bis mittel (HSV-S 0.18-0.33)
  * Schatten leicht warm/rosa (a +3..+5, b +2..+4), Lichter warm-gelb (a +4..+8, b +9..+20)
  * weich, leicht dunstig (wenig Mikrokontrast), kein sichtbares Korn
"""
import numpy as np
import cv2


def _curve():
    x = np.linspace(0, 1, 4096, dtype=np.float32)
    y = 0.045 + x * (0.965 - 0.045)                 # Schwarz anheben, Weiss leicht absenken
    y = 0.5 + (y - 0.5) * 0.94                      # etwas weniger Kontrast
    y = y ** 0.97                                   # Mitten minimal heller
    return np.clip(y, 0, 1).astype(np.float32)


CURVE = _curve()


def home_look(img, sat=0.80, warm=1.0, haze=0.10, soften=0.6):
    """img: float32 RGB 0..255 -> float32 RGB 0..255"""
    x = np.clip(img, 0, 255) / 255.0
    # 1) etwas weicher (Mikrokontrast runter, wie in der Referenz)
    if soften > 0:
        x = x * (1 - soften * 0.35) + cv2.GaussianBlur(x, (0, 0), 1.2) * (soften * 0.35)
    # 2) Tonkurve: angehobene Schwarztoene, weiche Lichter
    x = CURVE[(x * 4095).astype(np.int32)]
    # 3) Saettigung runter
    y = (x[..., 0] * 0.2126 + x[..., 1] * 0.7152 + x[..., 2] * 0.0722)[..., None]
    x = y + (x - y) * sat
    # 4) Farbstich: Schatten warm-rosa, Lichter warm-gelb
    sh = (1 - y) ** 2
    hi = y ** 1.5
    x = x + warm * (sh * np.array([0.020, 0.004, 0.012], np.float32)
                    + hi * np.array([0.040, 0.012, -0.045], np.float32))
    # 5) Dunst / leichter Glow (Screen-Mischung mit weichgezeichneter Kopie)
    if haze > 0:
        b = cv2.GaussianBlur(x, (0, 0), 18)
        x = 1 - (1 - x) * (1 - haze * b)
    return np.clip(x, 0, 1) * 255.0
