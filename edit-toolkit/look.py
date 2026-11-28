"""'CC' look modelled on the reference edit the user liked:
deep blacks, punchy contrast, strong saturation, warm highlights / cool shadows,
strong clarity + crisp detail, soft highlight glow."""
import numpy as np
import cv2

def _lut():
    x = np.linspace(0, 1, 4096, dtype=np.float32)
    x = np.clip((x - 0.018) / (0.975 - 0.018), 0, 1)          # black point down, white point up
    x = x ** 1.06                                           # moodier mid-tones
    s = x * x * (3 - 2 * x)                                 # S-curve
    x = 0.60 * x + 0.40 * s
    return x.astype(np.float32)
LUT = _lut()

def cc(img, sat=1.30, clarity=0.30, detail=0.55, bloom=0.12):
    """img: float32 RGB 0..255 (H, W, 3) -> float32 RGB 0..255"""
    x = np.clip(img, 0, 255) / 255.0
    # tone curve (per channel keeps colours rich)
    x = LUT[(x * 4095).astype(np.int32)]
    y = (x[..., 0] * 0.2126 + x[..., 1] * 0.7152 + x[..., 2] * 0.0722)[..., None]
    # saturation / vibrance (less boost on already saturated pixels)
    chroma = np.abs(x - y).max(axis=2, keepdims=True)
    k = 1 + (sat - 1) * (1 - 0.5 * np.clip(chroma / 0.5, 0, 1))
    x = y + (x - y) * k
    # split toning: cool teal shadows, warm orange highlights
    sh = (1 - y) ** 3
    hi = y ** 2
    x = x + sh * np.array([-0.020, 0.003, 0.026], np.float32) + hi * np.array([0.030, 0.008, -0.030], np.float32)
    x = np.clip(x, 0, 1)
    # clarity (large radius local contrast on luminance)
    y = (x[..., 0] * 0.2126 + x[..., 1] * 0.7152 + x[..., 2] * 0.0722)
    yb = cv2.GaussianBlur(y, (0, 0), 14)
    y2 = np.clip(y + clarity * (y - yb), 0, 1)
    x = x * ((y2 + 1e-4) / (y + 1e-4))[..., None]
    # fine detail sharpening
    xb = cv2.GaussianBlur(x, (0, 0), 1.1)
    x = x + detail * (x - xb)
    # soft glow from the highlights
    yh = np.clip(x - 0.62, 0, None)
    x = x + bloom * cv2.GaussianBlur(yh, (0, 0), 16) * 2.2
    return np.clip(x, 0, 1) * 255.0
