"""Doppelte Bilder aus Bildschirmaufnahmen entfernen, ohne echte (ruhige) Bewegung zu verlieren.

Bildschirmaufnahmen laufen mit 60 Bildern/s; ein 30-fps-Video erscheint darin als A A B B C C ...,
ein 24-fps-Video als A A A B B C C C ...  Ein fester Schwellwert (z. B. 0,18) wirft bei sehr ruhigen
Szenen (Gesicht spricht, Person steht) echte Bilder weg -> ruckelt. Daher:

    Bild i ist ein Duplikat, wenn seine Aenderung zum Vorgaenger klein ist (< 0,06) UND
    deutlich kleiner als die Aenderungen der Nachbarn (< 0,35 x Maximum der Nachbar-Aenderungen).

    keep = unique_indices(frames)          # frames: Liste/Array von Bildern (RGB oder Grau)
"""
import numpy as np
import cv2


def frame_diffs(frames, size=96):
    small = []
    for f in frames:
        g = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY) if f.ndim == 3 else f
        small.append(cv2.resize(g, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32))
    small = np.stack(small)
    return np.abs(np.diff(small, axis=0)).mean(axis=(1, 2))


def unique_indices(frames, abs_max=0.06, rel=0.35):
    d = frame_diffs(frames)
    keep = [0]
    for i, v in enumerate(d):
        nb = [d[j] for j in (i - 1, i + 1) if 0 <= j < len(d)]
        m = max(nb) if nb else 0.0
        dup = v < abs_max and v < rel * m
        if v < 0.004:                       # praktisch identisch
            dup = True
        if not dup:
            keep.append(i + 1)
    return keep
