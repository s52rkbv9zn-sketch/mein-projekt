#!/usr/bin/env python3
"""Schrift neu setzen (die anderen Schriften hier nur zum Vergleichen; Pakete fonts-texgyre, fonts-urw-base35,
fonts-roboto, fonts-dejavu-extra): Woerter mit einer echten Schriftart rendern und an die Lage im Vorbild anpassen.

Ein Wort = Text + Schrift + Groesse (Hoehe), waagerechte Streckung sx, Laufweite (tracking, in em),
Lage (x, y der Grundlinie links) und Drehung (0 / 90 / -90 Grad). Gerendert wird mit PIL in hoher
Aufloesung und dann affin in das Zielbild gelegt (weiche, saubere Kanten).
"""
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

import os
_TK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "edit-toolkit")
FONTS = {
    "heros":      "/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyreheros-regular.otf",
    "heros_cn":   "/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyreheroscn-regular.otf",
    "nimbus":     "/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf",
    # schmale Helvetica wie im Vorbild (URW, AGPL mit Font-Ausnahme) - liegt im edit-toolkit
    "nimbus_nar": os.path.join(_TK, "NimbusSansNarrow-Regular.otf"),
    "liberation": "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "roboto_cn":  "/usr/share/fonts/truetype/roboto/unhinted/RobotoCondensed-Regular.ttf",
    "roboto":     "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf",
    "dejavu_cn":  "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
    "inter":      "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
    "free":       "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
}
BASE = 400          # Render-Groesse (px pro em) fuer die hochaufgeloeste Vorlage
_cache = {}


def font(name, size=BASE):
    key = (name, size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(FONTS.get(name, name), size)
    return _cache[key]


def layout(text, fname, tracking=0.0, size=BASE):
    """x-Position (px bei size) jedes Zeichens, inkl. Unterschneidung, plus Laufweite"""
    f = font(fname, size)
    xs = [f.getlength(text[:i]) + tracking * size * i for i in range(len(text))]
    return xs, f.getlength(text) + tracking * size * (len(text) - 1)


def render_word(text, fname, tracking=0.0, size=BASE, letters=None):
    """Hochaufgeloeste Vorlage: Alpha-Bild (float 0..1), Ursprung = Grundlinie links bei (pad, pad + ascent).
    letters: Menge der Zeichen-Indizes, die gezeichnet werden (None = alle). Rueckgabe: (alpha, ox, oy)"""
    f = font(fname, size)
    asc, desc = f.getmetrics()
    xs, width = layout(text, fname, tracking, size)
    pad = int(0.2 * size)
    w = int(width + 2 * pad + size * 0.2)
    h = int(asc + desc + 2 * pad)
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    for i, ch in enumerate(text):
        if letters is not None and i not in letters:
            continue
        d.text((pad + xs[i], pad), ch, font=f, fill=255)
    return np.asarray(img, np.float32) / 255.0, pad, pad + asc


def place(alpha, ox, oy, size, height_px, sx, x, y, rot, out_shape, base=BASE):
    """Vorlage ins Zielbild legen: Schriftgroesse height_px (px pro em im Ziel), waagerechte Streckung sx,
    Grundlinie links bei (x, y) im Ziel, Drehung rot (Grad, gegen den Uhrzeigersinn, um den Ankerpunkt)."""
    k = height_px / base
    c, s = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    # Vorlage (u, v) -> relativ zum Anker: ((u-ox)*k*sx, (v-oy)*k) -> drehen -> + (x, y)
    A = np.array([[k * sx * c, k * s], [-k * sx * s, k * c]], np.float64)
    t = np.array([x, y]) - A @ np.array([ox, oy])
    M = np.hstack([A, t[:, None]]).astype(np.float32)
    return cv2.warpAffine(alpha, M, (out_shape[1], out_shape[0]), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def soft_iou(a, b):
    return float(np.minimum(a, b).sum() / (np.maximum(a, b).sum() + 1e-6))
