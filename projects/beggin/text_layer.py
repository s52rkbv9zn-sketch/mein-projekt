#!/usr/bin/env python3
"""Neu gesetzte Schrift je Bild zeichnen: Woerter aus words_fit.json (Schrift, Groesse, Lage, Drehung, sichtbarer
Bereich je Bild) in ruhenden Text-Koordinaten rendern und mit der gemessenen Bewegung der Textebene
(text_drift.npz) an die Stelle im Bild schieben. Ergebnis: weiche Alpha-Maske (0..1) in Ausgabegroesse.

    L = TextLayer("words_fit.json", "text_drift.npz", out_w=1920, out_h=1080)
    a = L.frame(t)          # float32 (out_h, out_w)
"""
import json
import numpy as np
import cv2

import typeset as T

REF_W, REF_H = 1024, 576
FONT = "nimbus_nar"


class TextLayer:
    def __init__(self, fit_json, drift_npz, out_w=1920, out_h=1080, edge=0.6):
        self.words = json.load(open(fit_json))
        self.C = np.load(drift_npz)["C"]
        self.W, self.H = out_w, out_h
        self.s = out_w / REF_W
        self.edge = edge                     # Breite der weichen Schnittkante (px im Ausgabebild)
        self.cache = {}

    def _word(self, w):
        """Wort einmal in Ausgabe-Aufloesung (ruhende Koordinaten) rendern: enger Ausschnitt + Lage-Karte u"""
        key = w["id"]
        if key in self.cache:
            return self.cache[key]
        size = w["size"] * self.s
        al, ox, oy = T.render_word(w["text"], FONT, 0.0, size=int(round(size)))
        k = size / round(size)
        hh, ww = al.shape
        U = ((np.arange(ww, dtype=np.float32) - ox) / round(size))[None, :].repeat(hh, 0) + 10.0
        # Lage im Ausgabebild (ruhend) - Ausschnitt um das Wort
        x, y = w["x"] * self.s, w["y"] * self.s
        c, sn = np.cos(np.radians(w["rot"])), np.sin(np.radians(w["rot"]))
        A = np.array([[k * w["sx"] * c, k * sn], [-k * w["sx"] * sn, k * c]])
        corners = np.array([[0, 0], [ww, 0], [0, hh], [ww, hh]], float) - [ox, oy]
        pc = corners @ A.T + [x, y]
        x0, y0 = np.floor(pc.min(0)).astype(int) - 3
        x1, y1 = np.ceil(pc.max(0)).astype(int) + 3
        t = np.array([x - x0, y - y0]) - A @ np.array([ox, oy])
        M = np.hstack([A, t[:, None]]).astype(np.float32)
        size_wh = (int(x1 - x0), int(y1 - y0))
        pa = cv2.warpAffine(al, M, size_wh, flags=cv2.INTER_LINEAR)
        pu = cv2.warpAffine(U, M, size_wh, flags=cv2.INTER_LINEAR) - 10.0
        du = 1.0 / (size * w["sx"])          # em je Ausgabe-Pixel entlang der Schreibrichtung
        self.cache[key] = (pa, pu, (int(x0), int(y0)), du)
        return self.cache[key]

    def canon(self, t):
        """Textmaske in ruhenden Koordinaten (Ausgabegroesse) fuer Bild t"""
        out = np.zeros((self.H, self.W), np.float32)
        for w in self.words:
            if not (w["f0"] <= t <= w["f1"]):
                continue
            v = w["vis"][t - w["f0"]]
            if v is None:
                continue
            pa, pu, (x0, y0), du = self._word(w)
            a = pa
            ua, ub = v
            if ua > -1e8 or ub < 1e8:
                e = self.edge * du
                clip = np.clip((pu - ua) / e + 0.5, 0, 1) * np.clip((ub - pu) / e + 0.5, 0, 1)
                a = pa * clip
            h, ww = a.shape
            xa, ya = max(0, x0), max(0, y0)
            xb, yb = min(self.W, x0 + ww), min(self.H, y0 + h)
            if xb <= xa or yb <= ya:
                continue
            sub = a[ya - y0:yb - y0, xa - x0:xb - x0]
            np.maximum(out[ya:yb, xa:xb], sub, out=out[ya:yb, xa:xb])
        return out

    def frame(self, t):
        """Textmaske im Bild t (Ausgabegroesse): ruhende Maske mit der Bewegung der Textebene verschoben"""
        tc = min(t, len(self.C) - 1)
        S = np.diag([self.s, self.s, 1.0])
        M = (S @ self.C[tc] @ np.linalg.inv(S))[:2].astype(np.float32)
        return cv2.warpAffine(self.canon(t), M, (self.W, self.H), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0)
