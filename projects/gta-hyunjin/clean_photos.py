#!/usr/bin/env python3
"""Wasserzeichen aus den Fotos des Nutzers entfernen (Regel 1: keine fremde Schrift im Video).

Je Foto ein Suchkasten um das Zeichen; darin werden die Schriftpixel erkannt (hell auf dunkel, dunkel/hell
gegen die geglaettete Umgebung) und per Inpainting mit der Umgebung gefuellt.

    python3 clean_photos.py FOTO_ORDNER AUSGABE_ORDNER [pruefbild.jpg]
"""
import os, sys
import numpy as np
import cv2

# Kasten (x0, y0, x1, y1) und Erkennung: "hell" = Schrift heller als Schwelle, "kontrast" = Abweichung vom Median
MARKS = {
    "P1": [((568, 1452, 652, 1538), "hell", 80)],            # "JYP" auf schwarzem Shirt
    "P2": [((488, 1592, 732, 1668), "kontrast", 9, -66)],     # "dazzling days" auf weissem Shirt (Stoff von oben kopieren)
    "P3": [((315, 1040, 445, 1175), "kontrast", 13)],         # "Elaine" auf weisser Jacke (Kasten ohne Revers-Kante)
    "P5": [((110, 1470, 280, 1600), "hell", 140)],            # Unterschrift unten links
}


def mark_mask(img, box, kind, thr):
    x0, y0, x1, y1 = box
    sub = img[y0:y1, x0:x1]
    g = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    if kind == "hell":
        m = (sub.min(axis=2) > thr) if thr > 120 else (g > thr)
    else:
        med = cv2.medianBlur(g, 25).astype(np.int16)
        m = np.abs(g.astype(np.int16) - med) > thr
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    m = cv2.dilate(m, np.ones((5, 5), np.uint8))
    full = np.zeros(img.shape[:2], np.uint8)
    full[y0:y1, x0:x1] = m * 255
    return full


def main():
    src, out = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    sheet = []
    for f in sorted(os.listdir(src)):
        k = os.path.splitext(f)[0]
        img = cv2.imread(os.path.join(src, f))
        res = img.copy()
        for box, kind, thr, *clone in MARKS.get(k, []):
            m = mark_mask(img, box, kind, thr)
            if clone:
                # Grobe Helligkeit (Falten) per Inpainting glatt fuellen, feine Stoffstruktur (Rippen) von oben
                # kopieren -> kein verschmierter Fleck und keine Geisterbilder von Knoepfen
                dy = clone[0]
                rf = res.astype(np.float32)
                low = cv2.GaussianBlur(rf, (0, 0), 4)
                high = rf - low
                low_f = cv2.inpaint(np.clip(low, 0, 255).astype(np.uint8), cv2.dilate(m, np.ones((9, 9), np.uint8)), 9,
                                    cv2.INPAINT_TELEA).astype(np.float32)
                high_f = np.roll(high, -dy, axis=0)
                fill = low_f + high_f
                w = cv2.GaussianBlur((m > 0).astype(np.float32), (0, 0), 2.5)[..., None]
                w = np.clip(w * 1.8, 0, 1)
                res = np.clip(rf * (1 - w) + fill * w, 0, 255).astype(np.uint8)
            else:
                res = cv2.inpaint(res, m, 6, cv2.INPAINT_TELEA)
            x0, y0, x1, y1 = box
            pad = 30
            a = img[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad].copy()
            b = res[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
            mm = m[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
            a[mm > 0] = (0.5 * a[mm > 0] + np.array([0, 0, 127])).astype(np.uint8)
            t = np.hstack([a, b])
            sheet.append(cv2.resize(t, (int(t.shape[1] * 220 / t.shape[0]), 220)))
        cv2.imwrite(os.path.join(out, f), res, [cv2.IMWRITE_JPEG_QUALITY, 97])
    if len(sys.argv) > 3 and sheet:
        w = max(s.shape[1] for s in sheet)
        cv2.imwrite(sys.argv[3], np.vstack([np.pad(s, ((0, 4), (0, w - s.shape[1]), (0, 0))) for s in sheet]))


if __name__ == "__main__":
    main()
