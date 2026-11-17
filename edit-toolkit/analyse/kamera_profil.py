#!/usr/bin/env python3
"""Misst fuer jedes Bild eines Videos die Kamerabewegung zum Vorbild:
Zoom (Skalierung), Drehung (Grad) und Verschiebung (Pixel bei 288 px Breite) + Guete (cc).

    python3 kamera_profil.py VIDEO profil.json [--maske hintergrund]

WICHTIG (Ausrichtung): dekodiert wird mit fps=30:start_time=0, d.h. ab t=0 mit konstanter
Bildrate aufgefuellt. Deshalb ist der Index im Ergebnis == Bildnummer im fertigen Edit
(t = n/30), auch wenn das Video (z.B. TikTok-Export) erst bei 0,161 s beginnt.
(Frueherer Fehler: mit einem +5-Versatz gerechnet -> alle Schnitte lagen 5 Bilder daneben.)
Das Ergebnis enthaelt fuer Bild n die Bewegung von n-1 nach n.

Vorzeichen: zoom > 1 = Inhalt wird groesser (Zoom hinein); Winkel > 0 = Drehung im Uhrzeigersinn
auf dem Bildschirm; tx > 0 = Inhalt wandert nach rechts, ty > 0 = nach unten.
Werte mit cc < 0.8 (stark verschwommene Uebergangsbilder) sind unzuverlaessig.

Tipp: Kopf-/Koerperbewegungen der Person verfaelschen Drehung und Zoom. Mit
--maske hintergrund wird nur der Bildrand (Hintergrund) gemessen.
"""
import json, subprocess, sys
import numpy as np
import cv2

N = 288


def load(path, fps=30):
    d = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps}:start_time=0,scale={N}:{N},format=gray",
                        "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(d, np.uint8).reshape(-1, N, N)


def make_mask(kind):
    m = np.zeros((N, N), np.uint8)
    if kind == "hintergrund":
        m[0:int(N * .30), :] = 255
        m[:, 0:int(N * .22)] = 255
        m[:, int(N * .80):] = 255
        m[int(N * .08):, int(N * .25):int(N * .75)] = 0
    else:   # Bildmitte ohne Raender (TikTok-Wasserzeichen)
        m[int(N * .06):int(N * .86), int(N * .13):int(N * .87)] = 255
    return m


def sim(a, b, mask):
    A = cv2.GaussianBlur(a, (0, 0), 1.2).astype(np.float32) / 255
    B = cv2.GaussianBlur(b, (0, 0), 1.2).astype(np.float32) / 255
    w = np.eye(2, 3, dtype=np.float32)
    try:
        a2, b2, m2 = (cv2.resize(x, (N // 2, N // 2)) for x in (A, B, mask))
        _, w2 = cv2.findTransformECC(a2, b2, w.copy(), cv2.MOTION_AFFINE,
                                     (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 80, 1e-5), m2, 3)
        w2[:, 2] *= 2
        cc, w = cv2.findTransformECC(A, B, w2, cv2.MOTION_AFFINE,
                                     (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 80, 1e-6), mask, 3)
    except cv2.error:
        return None
    M = w[:, :2]
    s = float(np.sqrt(abs(np.linalg.det(M))))
    ang = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    c = np.array([N / 2, N / 2])
    t = w[:, 2] - c + M @ c
    return s, ang, float(t[0]), float(t[1]), float(cc)


def main():
    path, out = sys.argv[1], sys.argv[2]
    kind = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--maske" else "mitte"
    fr = load(path)
    mask = make_mask(kind)
    prof = {str(i): sim(fr[i - 1], fr[i], mask) for i in range(1, len(fr))}
    json.dump(prof, open(out, "w"))
    print(f"{len(fr)} Bilder gemessen -> {out}")


if __name__ == "__main__":
    main()
