#!/usr/bin/env python3
"""Gesichter im fertigen Edit an die Spuren des Vorbilds angleichen (Lage und Groesse je Rolle).

Rendert Pruefbilder in Vorbild-Groesse (1024x576), sucht Gesichter wie beim Vorbild (YuNet, 2x vergroessert)
und verbessert role_corr.json: f' = f / (gemessen/Soll), Versatz o' = o + d/(h*f). Zwei Durchgaenge reichen.

    ASSETS=... python3 calibrate.py [Durchgaenge]
"""
import os, sys, json
import numpy as np
import cv2

os.environ["SCALE"] = str(1024 / 1920)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "edit-toolkit"))
from face_track import FaceTracker

# Grosse Nahaufnahme D: YuNet liefert dort zwei verschiedene Kaesten (Stirn/Kinn) -> Werte von Hand festgelegt
# (Sichtvergleich mit dem Vorbild), nicht automatisch nachfuehren.
FROZEN = set()
CHECKS = dict(A1=[24, 48, 72, 96, 120, 150], B1=[72, 84, 96, 105], C1=[105, 120, 150, 186], D1=[150, 170, 190],
              E1=[180, 190, 200], A3=[290, 300, 310], BP=[318, 326], CP=[326, 330], RP=[330, 334])


def run_once(ft):
    import importlib
    import render
    importlib.reload(render)
    sc = render.Scene()
    corr = dict(render.ROLE_CORR)
    cache, report = {}, {}
    for role, ts in CHECKS.items():
        ms = []
        for t in ts:
            if t not in cache:
                im = sc.frame(t)
                big = cv2.resize(im, (2048, 1152), interpolation=cv2.INTER_CUBIC)
                cache[t] = [(cx / 2, cy / 2, fh / 2) for cx, cy, fw, fh, s in
                            ft.detect(cv2.cvtColor(big, cv2.COLOR_BGR2RGB), max_side=2048)]
            tx, ty, th = render.D["roles"][role][str(t)]
            best = min(cache[t], key=lambda f: np.hypot(f[0] - tx, f[1] - ty), default=None)
            if best is None or np.hypot(best[0] - tx, best[1] - ty) > 0.6 * th:
                continue
            ms.append((best[0] - tx, best[1] - ty, best[2] / th, th))
        if not ms:
            report[role] = None
            continue
        ms = [v for v in ms if 0.7 < v[2] < 1.4]                       # unplausible Kaesten weg
        if not ms or role in FROZEN:
            report[role] = None
            continue
        m = np.median(np.array(ms), 0)
        ox, oy, f = corr.get(role, (0.0, 0.0, 1.0))
        h = m[3]
        # je Durchgang nur behutsam nachfuehren (Gesichtskaesten schwanken bei grossen Gesichtern stark)
        dxr = float(np.clip(m[0] / (h * f), -0.05, 0.05))
        dyr = float(np.clip(m[1] / (h * f), -0.05, 0.05))
        corr[role] = [float(ox + dxr), float(oy + dyr), float(f / np.clip(m[2], 0.92, 1.08))]
        report[role] = [round(float(v), 3) for v in m[:3]]
    return corr, report


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    ft = FaceTracker(score=0.5)
    for i in range(n):
        corr, rep = run_once(ft)
        print("Durchgang", i + 1, "Abweichung (dx, dy, Groesse):", rep, flush=True)
        json.dump(corr, open(os.path.join(HERE, "role_corr.json"), "w"), indent=1)
    print(json.dumps(corr))


if __name__ == "__main__":
    main()
