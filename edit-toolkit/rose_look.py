"""'Rose'-Look (Referenz 4, Konzert-Edit @mitanori): tiefe Schwarztoene, weiche Lichter,
rosa-pinke Lichter und kuehl-magenta Schatten, leicht weich.

Gemessen an der Referenz (Lab, pro Szene):
  * Schwarz tief (L p0.5 ~ 0-2), Lichter nicht ausgebrannt (L p99.5 ~ 75-98)
  * Lichter rosa: a +6..+12, Schatten kuehl-magenta: a +3, b -1..-13
  * Saettigung mittel (HSV-S 0.17-0.49), Bild eher weich als knackig
"""
import numpy as np
import cv2


def _curve():
    x = np.linspace(0, 1, 4096, dtype=np.float32)
    y = np.clip((x - 0.02) / (0.985 - 0.02), 0, 1)       # tiefe Schwarztoene
    y = y - 0.07 * y ** 4                                 # weiche Schulter in den Lichtern
    s = y * y * (3 - 2 * y)
    y = 0.8 * y + 0.2 * s                                 # leichte S-Kurve
    return np.clip(y, 0, 1).astype(np.float32)


CURVE = _curve()


def rose_look(img, sat=0.92, pink=1.0, soften=0.30, glow=0.08):
    """img: float32 RGB 0..255 -> float32 RGB 0..255"""
    x = np.clip(img, 0, 255) / 255.0
    if soften > 0:
        x = x * (1 - soften) + cv2.GaussianBlur(x, (0, 0), 1.4) * soften
    x = CURVE[(x * 4095).astype(np.int32)]
    y = (x[..., 0] * 0.2126 + x[..., 1] * 0.7152 + x[..., 2] * 0.0722)[..., None]
    x = y + (x - y) * sat
    hi = y ** 1.6
    sh = (1 - y) ** 2 * np.clip(y * 6, 0, 1)              # nur echte Schatten, Schwarz bleibt schwarz
    x = x + pink * (hi * np.array([0.040, -0.012, 0.022], np.float32)
                    + sh * np.array([0.006, -0.006, 0.020], np.float32))
    if glow > 0:
        b = cv2.GaussianBlur(np.clip(x - 0.55, 0, None), (0, 0), 16)
        x = 1 - (1 - x) * (1 - glow * 2.2 * b)
    return np.clip(x, 0, 1) * 255.0
