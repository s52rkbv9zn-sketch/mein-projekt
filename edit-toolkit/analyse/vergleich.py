#!/usr/bin/env python3
"""Qualitaetskontrolle: Referenz und eigenes Edit Bild fuer Bild nebeneinander + Messwerte.

    python3 vergleich.py REFERENZ.mp4 EDIT.mp4 ausgabe_ordner  BILD [BILD ...]   [--vor 3 --nach 4]

Fuer jede angegebene Bildnummer (z.B. die Schnittbilder) entsteht ein Streifen
"oben Referenz / unten Edit" von BILD-vor bis BILD+nach (Bildnummern = t*30, siehe kamera_profil.py).

Zusaetzlich auf der Konsole:
 * Ruckel-Check fuer beide Videos (ungleichmaessige Bewegung, doppelte Bilder)
 * Zoom-Geschwindigkeit pro Bild am Schnitt (wenn kamera_profil-Dateien existieren, sonst ueberspringen)
"""
import os, subprocess, sys
import numpy as np
import cv2

T = 200


def decode(path, size, fmt="bgr24", ch=3):
    d = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps=30:start_time=0,scale={size}:{size}",
                        "-f", "rawvideo", "-pix_fmt", fmt, "-"], capture_output=True).stdout
    a = np.frombuffer(d, np.uint8)
    return a.reshape(-1, size, size, ch) if ch > 1 else a.reshape(-1, size, size)


def ruckel(path, nmax=None):
    a = decode(path, 192, "gray", 1).astype(np.float32)[:nmax]
    d = np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))
    dup = int((d < 0.6).sum())
    r = []
    for i in range(1, len(d)):
        lo, hi = sorted((d[i - 1], d[i]))
        if 2 < hi < 25:
            r.append(lo / hi)
    uneven = int((np.array(r) < 0.25).sum())
    return dup, uneven, float(np.median(d))


def main():
    opts = {"--vor": 3, "--nach": 4}
    args = []
    it = iter(sys.argv[1:])
    for a in it:
        if a in opts:
            opts[a] = int(next(it))
        else:
            args.append(a)
    ref, edit, outdir = args[:3]
    frames = [int(x) for x in args[3:]]
    os.makedirs(outdir, exist_ok=True)
    R = decode(ref, T)
    E = decode(edit, T)
    for c in frames:
        top, bot = [], []
        for f in range(c - opts["--vor"], c + opts["--nach"] + 1):
            for arr, lst, col in ((R, top, (0, 255, 255)), (E, bot, (0, 255, 0))):
                im = arr[f].copy() if 0 <= f < len(arr) else np.zeros((T, T, 3), np.uint8)
                cv2.putText(im, str(f), (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
                lst.append(im)
        cv2.imwrite(os.path.join(outdir, f"vergleich_{c:04d}.jpg"), np.vstack([np.hstack(top), np.hstack(bot)]))
    n = len(E) - 15          # gleiche Laenge vergleichen (ohne Endkarte / Ausblendung)
    for name, p in (("Referenz", ref), ("Edit", edit)):
        dup, uneven, med = ruckel(p, n)
        print(f"{name:8s}: doppelte Bilder {dup:3d}   ungleichmaessige Stellen {uneven:3d}   Bewegung (Median) {med:.1f}")
    print(f"Streifen gespeichert in {outdir}")


if __name__ == "__main__":
    main()
