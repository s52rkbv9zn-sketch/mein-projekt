import numpy as np
import cv2
def teal_look(img):
    """high-key look of the reference shot: airy white background, dark/neutral tones -> soft teal,
    skin / red / pink kept (slightly pastel). The colour mask is smoothed so faces stay clean."""
    x = np.clip(img, 0, 255) / 255.0
    xb = 1 - (1 - x) ** 1.9
    L = xb[..., 0] * 0.2126 + xb[..., 1] * 0.7152 + xb[..., 2] * 0.0722
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    sat = x.max(axis=2) - x.min(axis=2)
    warm = np.clip((r - b - 0.03) / 0.14, 0, 1) * np.clip((sat - 0.04) / 0.12, 0, 1)
    warm = warm * np.clip((r - g - 0.03) / 0.10, 0, 1)
    s = max(1.0, img.shape[1] * 0.006)
    warm = cv2.GaussianBlur(warm.astype(np.float32), (0, 0), s)
    warm = np.clip(warm * 1.3, 0, 1)
    teal = np.stack([0.20 + 0.78 * L ** 1.15, 0.40 + 0.59 * L ** 0.8, 0.39 + 0.60 * L ** 0.8], axis=2)
    keep = xb * 0.85 + L[..., None] * 0.15
    out = warm[..., None] * keep + (1 - warm[..., None]) * teal
    out = out * 0.93 + 0.07
    return np.clip(out, 0, 1) * 255.0
