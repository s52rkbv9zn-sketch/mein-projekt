#!/usr/bin/env python3
"""GTA-VI-Logo aus dem Vorbild (Referenz 11) herausloesen.

Bild 233/234 des Vorbilds (fps=30, start_time=0) zeigt das fertige Logo auf Lila. Das Logo wird freigestellt
(Abstand zur Hintergrundfarbe, Loecher gefuellt), der lila Saum herausgerechnet und auf Ausgabegroesse
(x1,875) gebracht. Dazu die Umrissform der Buchstaben V und I als Vieleck (fuer das schrumpfende VI-Fenster).

    python3 logo.py VORBILD.mp4 AUSGABE_ORDNER
Ausgabe: logo.png (RGBA, vormultipliziert nein), logo.json (Mitte im Vorbild bei Massstab 1, Vieleck)
"""
import sys, os, json, subprocess
import numpy as np
import cv2

PUR = np.array([47.6, 12.3, 33.7], np.float32)        # Hintergrund-Lila (BGR) im Vorbild
BOX = (286, 130, 430, 334)                             # x, y, w, h um das Logo (Bild 234, 1024x576)
K = 1.875


def frames(path, idx):
    n = max(idx) + 1
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-vf", "fps=30:start_time=0,scale=1024:576", "-frames:v", str(n),
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, 576, 1024, 3)
    return [a[i] for i in idx]


def main():
    ref, out = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    fr = frames(ref, [233, 234])
    x, y, w, h = BOX
    crop = np.mean([f[y:y + h, x:x + w].astype(np.float32) for f in fr], 0)
    d = np.linalg.norm(crop - PUR, axis=2)
    solid = (d > 16).astype(np.uint8)
    solid = cv2.morphologyEx(solid, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    ff = solid.copy()
    cv2.floodFill(ff, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 2)
    filled = ((ff != 2) | (solid > 0)).astype(np.float32)
    soft = np.clip((d - 8) / 22, 0, 1)
    alpha = np.maximum(soft, cv2.erode(filled, np.ones((3, 3), np.uint8)))
    alpha = np.maximum(alpha, filled * 0.0)
    a3 = np.maximum(alpha, 1e-3)[..., None]
    col = np.clip((crop - (1 - alpha[..., None]) * PUR) / a3, 0, 255)
    col = np.where(alpha[..., None] > 0.05, col, PUR)
    # Ausgabegroesse
    W2, H2 = int(round(w * K)), int(round(h * K))
    colb = cv2.resize(col, (W2, H2), interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(colb, (0, 0), 1.3)
    colb = np.clip(colb + 0.6 * (colb - blur), 0, 255)
    ab = np.clip(cv2.resize(alpha, (W2, H2), interpolation=cv2.INTER_CUBIC), 0, 1)
    cv2.imwrite(os.path.join(out, "logo.png"), np.dstack([colb, ab * 255]).astype(np.uint8))
    # VI-Umriss: die gefuellte Flaeche ohne den Schriftzug-Ueberstand -> grosser Umriss reicht fuers Fenster
    cnts, _ = cv2.findContours((filled > 0.5).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    polys = []
    for c in cnts:
        if cv2.contourArea(c) < 200:
            continue
        c = cv2.approxPolyDP(c, 0.8, True)[:, 0, :].astype(np.float32)
        polys.append([[float(px - w / 2), float(py - h / 2)] for px, py in c])
    json.dump(dict(center=[x + w / 2, y + h / 2], size=[w, h], polys=polys), open(os.path.join(out, "logo.json"), "w"))
    print("Logo", (W2, H2), "Umrisse", [len(p) for p in polys])


if __name__ == "__main__":
    main()
