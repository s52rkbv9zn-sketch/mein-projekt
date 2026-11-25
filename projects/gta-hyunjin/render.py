#!/usr/bin/env python3
"""GTA-VI-Edit mit Hyunjin nach Referenz 11 (TikTok, 1024x576, 11,3 s ohne TikTok-Abspann).

Ablauf des Vorbilds (Bildnummer bei 30 fps):
  0-12     Einblenden aus Lila
  12-192   Teil 1-2: schraeg liegender Abendhimmel zwischen lila Baendern, darauf gezeichnete Figuren
           (A gross, B kommt von rechts, C von links, Nahaufnahme D von rechts, Nahaufnahme E von links),
           alles schwenkt/zoomt weich (Bewegung je Figur aus den Gesichtern des Vorbilds gemessen)
  192-232  das Bild schrumpft in ein VI-foermiges Fenster, das GTA-VI-Logo waechst in der Mitte heran
  233-246  Logo auf Lila, ab 235 ausblenden
  250-318  Himmels-Keil schiebt sich schraeg von unten links herein, A gleitet davor von links nach rechts
  299-334  drei Kacheln: B von unten, C von oben, D von unten, dann Ausblenden nach Lila (330-338)

    ASSETS=... REF=vorbild.mp4 OUT=GTA_Hyunjin_Edit.mp4 python3 render.py
    SCALE=0.5 FRAMES=0,30,60 SHEET=out.jpg python3 render.py     # Vorschau einzelner Bilder
Daten: ref_data.json (build_data.py), Bilder: prep.py (Figuren, Himmel), logo.py (Logo).
"""
import os, sys, json, subprocess
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.environ["ASSETS"]
REF = os.environ.get("REF", "")
OUT = os.environ.get("OUT", "GTA_Hyunjin_Edit.mp4")
SCALE = float(os.environ.get("SCALE", "1"))
W, H = int(round(1920 * SCALE)), int(round(1080 * SCALE))
KX = W / 1024.0                       # Vorbild-Pixel -> Ausgabe-Pixel
SK = W / 1920.0                       # Bild-Pixel der Hintergruende (fuer 1920 gemalt) -> Ausgabe
D = json.load(open(os.path.join(HERE, "ref_data.json")))
NF = D["nf"]
PUR_C = np.array([49.5, 12.5, 34.2], np.float32)
ROLE_ASSET = dict(A1="A", B1="B", C1="C", D1="D", E1="B", A3="A", BP="E", CP="C", RP="D")
# In den Kacheln muss das Foto bis unter die Kachel reichen (sonst sieht man die weitergefuehrte Koerperflaeche):
MIN_H = dict(CP=192.0)
# Feinabgleich je Rolle (calibrate.py): Gesicht im fertigen Bild genau auf die Spur des Vorbilds.
# [ox, oy, f]: Versatz in Gesichtshoehen und Groessenfaktor
_cp = os.path.join(HERE, "role_corr.json")
ROLE_CORR = json.load(open(_cp)) if os.path.exists(_cp) else {}
ORDER12 = ["B1", "A1", "C1", "D1", "E1"]              # hinten -> vorne


def premul_pyramid(rgba):
    """uint8 RGBA -> Liste (Stufe, vormultipliziertes float32-Bild), Stufen 1, 1/2, 1/4, 1/8"""
    a = rgba[..., 3:].astype(np.float32) / 255.0
    pm = np.concatenate([rgba[..., :3].astype(np.float32) * a, a * 255.0], 2)
    pm = np.clip(pm, 0, 255).astype(np.uint8)
    levels = [(1.0, pm)]
    for i in range(3):
        lv, im = levels[-1]
        levels.append((lv / 2, cv2.resize(im, (max(1, im.shape[1] // 2), max(1, im.shape[0] // 2)), interpolation=cv2.INTER_AREA)))
    return levels


def warp_layer(levels, scale, M_of_level):
    """Passende Stufe waehlen und in die Ausgabe warpen. M_of_level(lv) -> 2x3-Matrix fuer diese Stufe.
    Rueckgabe: (rgb_pm float32 HxWx3, alpha float32 HxW) oder None"""
    best = levels[0]
    for lv, im in levels:
        if scale / lv <= 1.0001:
            best = (lv, im)
    lv, im = best
    s = scale / lv
    M = M_of_level(lv)
    flags = cv2.INTER_CUBIC if s > 1.05 else cv2.INTER_LINEAR
    out = cv2.warpAffine(im, M, (W, H), flags=flags, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    out = out.astype(np.float32)
    return out[..., :3], out[..., 3] / 255.0


def over(dst, rgb_pm, a):
    dst *= (1 - a)[..., None]
    dst += rgb_pm


class Figures:
    def __init__(self):
        faces = json.load(open(os.path.join(ASSETS, "faces.json")))
        self.f = {k: np.array(v, np.float64) for k, v in faces.items()}
        self.lv = {k: premul_pyramid(cv2.imread(os.path.join(ASSETS, f"{k}.png"), cv2.IMREAD_UNCHANGED)) for k in "ABCDE"}

    def layer(self, key, x, y, h):
        """Figur key so legen, dass ihr Gesicht bei (x, y) [Vorbild-Pixel] mit Hoehe h liegt"""
        fx, fy, fh = self.f[key]
        s = h * KX / fh
        X, Y = x * KX, y * KX

        def M(lv):
            sl = s / lv
            return np.array([[sl, 0, X - sl * fx * lv], [0, sl, Y - sl * fy * lv]], np.float32)
        return warp_layer(self.lv[key], s, M)


def purple_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r2 = ((xx - W / 2) / (W / 2)) ** 2 * 0.5 + ((yy - H / 2) / (H / 2)) ** 2 * 0.5
    bg = np.empty((H, W, 3), np.float32)
    bg[..., 0] = PUR_C[0] * (1 - 0.16 * r2)
    bg[..., 1] = PUR_C[1] * (1 - 0.16 * r2)
    bg[..., 2] = PUR_C[2] * (1 - 0.06 * r2)
    return bg


class Scene:
    def __init__(self):
        self.fig = Figures()
        self.bg = purple_bg()
        sky = cv2.imread(os.path.join(ASSETS, "sky_main.png"))
        hh = sky.shape[0]
        top, G = 82, 552 * 1.875
        rows = np.arange(hh, dtype=np.float32)
        a = np.clip(np.minimum(rows - top + 0.5, top + G - rows + 0.5), 0, 1)
        rgba = np.dstack([sky, np.broadcast_to((a * 255).astype(np.uint8)[:, None], sky.shape[:2])])
        self.sky = premul_pyramid(rgba)
        self.sky_anchor = (sky.shape[1] / 2, top)
        wedge = cv2.imread(os.path.join(ASSETS, "sky_wedge.png"))
        self.wedge = cv2.warpAffine(wedge, np.array([[SK, 0, -90 * SK], [0, SK, -50 * SK]], np.float32), (W, H),
                                    flags=cv2.INTER_AREA if SK < 1 else cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
        self.panel_bg = {}
        for k in "BCR":
            im = cv2.imread(os.path.join(ASSETS, f"panel_{k}.png"))
            self.panel_bg[k] = premul_pyramid(np.dstack([im, np.full(im.shape[:2], 255, np.uint8)]))
        logo = cv2.imread(os.path.join(ASSETS, "logo.png"), cv2.IMREAD_UNCHANGED)
        self.logo = premul_pyramid(logo)
        self.logo_c = (logo.shape[1] / 2, logo.shape[0] / 2)
        lj = json.load(open(os.path.join(ASSETS, "logo.json")))
        self.vi_polys = [np.array(p, np.float64) for p in lj["polys"]]

    # ---------------------------------------------------------- Teile
    def card(self, t, out):
        c = D["card"][str(t)]
        m, b, k, xc = c["m"], c["b"], c["k"], c["xc"]
        th = np.arctan(m)
        cs, sn = np.cos(th), np.sin(th)
        X0, Y0 = xc * KX, (b + m * xc) * KX
        u0, v0 = self.sky_anchor
        sc = k * SK

        def M(lv):
            s = sc / lv
            uu, vv = u0 * lv, v0 * lv
            return np.array([[s * cs, -s * sn, X0 - s * (cs * uu - sn * vv)],
                             [s * sn, s * cs, Y0 - s * (sn * uu + cs * vv)]], np.float32)
        rgb, a = warp_layer(self.sky, sc, M)
        over(out, rgb, a)

    def track(self, role, t):
        tr = D["roles"][role].get(str(t))
        if tr is None:
            return None
        x, y, h = tr
        ox, oy, f = ROLE_CORR.get(role, (0.0, 0.0, 1.0))
        f = max(f, MIN_H.get(role, 0.0) / h)
        return x - ox * h * f, y - oy * h * f, h * f

    def person(self, role, t, out, clip=None):
        tr = self.track(role, t)
        if tr is None:
            return
        rgb, a = self.fig.layer(ROLE_ASSET[role], *tr)
        if clip is not None:
            rgb = rgb * clip[..., None]
            a = a * clip
        over(out, rgb, a)

    def vi_window(self, t):
        w = D["win"].get(str(t))
        if w is None:
            return None
        can = np.zeros((H, W), np.uint8)
        pts = [np.round(((p * w["s"] + np.array([w["cx"], w["cy"]])) * KX) * 16).astype(np.int32) for p in self.vi_polys]
        cv2.fillPoly(can, pts, 255, lineType=cv2.LINE_AA, shift=4)
        return can.astype(np.float32) / 255.0

    def logo_layer(self, t, out):
        L = D["logo"].get(str(t))
        if L is None or L["a"] <= 0:
            return
        sc = L["s"] * SK
        X, Y = L["cx"] * KX, L["cy"] * KX
        cx, cy = self.logo_c

        def M(lv):
            s = sc / lv
            return np.array([[s, 0, X - s * cx * lv], [0, s, Y - s * cy * lv]], np.float32)
        rgb, a = warp_layer(self.logo, sc, M)
        over(out, rgb * L["a"], a * L["a"])

    def wedge_layer(self, t, out):
        b = D["wedge"].get(str(t))
        if b is None or b >= 590:
            return
        sl = D["wedge_slope"]
        can = np.zeros((H, W), np.uint8)
        p = np.array([[0, b * KX], [W, (sl * 1024 + b) * KX], [W, H + 4], [0, H + 4]], np.float64)
        cv2.fillPoly(can, [np.round(p * 16).astype(np.int32)], 255, lineType=cv2.LINE_AA, shift=4)
        a = can.astype(np.float32) / 255.0
        out *= (1 - a)[..., None]
        out += self.wedge * a[..., None]

    def panel(self, key, role, t, out):
        e = D["panel_edges"][key].get(str(t))
        if e is None:
            return
        x0, x1 = D["panels"][key]
        y0 = e - 595 if key == "C" else e
        y1 = y0 + 596
        if y1 <= 0 or y0 >= 576:
            return
        can = np.zeros((H, W, 3), np.float32)
        # Hintergrund: Bildpunkt (34, 32) = linke obere Kachel-Ecke
        X, Y = x0 * KX, y0 * KX

        def M(lv):
            s = SK / lv
            return np.array([[s, 0, X - s * 34 * lv], [0, s, Y - s * 32 * lv]], np.float32)
        rgb, a = warp_layer(self.panel_bg[key], SK, M)
        over(can, rgb, a)
        rgb, a = self.fig.layer(ROLE_ASSET[role], *self.track(role, t))
        over(can, rgb, a)
        # Kachel-Rechteck mit weicher 1-px-Kante
        xs = np.arange(W, dtype=np.float32) + 0.5
        ys = np.arange(H, dtype=np.float32) + 0.5
        mx = np.clip(np.minimum(xs - x0 * KX, x1 * KX - xs) + 0.5, 0, 1)
        my = np.clip(np.minimum(ys - y0 * KX, y1 * KX - ys) + 0.5, 0, 1)
        if x1 >= 1024:
            mx = np.clip(xs - x0 * KX + 0.5, 0, 1)
        if x0 <= 0:
            mx = np.clip(x1 * KX - xs + 0.5, 0, 1)
        m = my[:, None] * mx[None, :]
        out *= (1 - m)[..., None]
        out += can * m[..., None]

    # ---------------------------------------------------------- ein Bild
    def frame(self, t):
        out = self.bg.copy()
        if t <= 232:
            self.card(t, out)
            for r in ORDER12:
                self.person(r, t, out)
            wm = self.vi_window(t)
            if wm is not None:
                out[:] = out * wm[..., None] + self.bg * (1 - wm)[..., None]
            self.logo_layer(t, out)
        else:
            self.wedge_layer(t, out)
            self.person("A3", t, out)
            self.panel("B", "BP", t, out)
            self.panel("C", "CP", t, out)
            self.panel("R", "RP", t, out)
            self.logo_layer(t, out)
        f = D["fade"][str(t)]
        if f < 1:
            out[:] = self.bg * (1 - f) + out * f
        rng = np.random.default_rng(t)
        out += rng.normal(0, 1.2, (H, W, 1)).astype(np.float32)
        return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def main():
    sc = Scene()
    frames = os.environ.get("FRAMES")
    if frames:
        idx = [int(v) for v in frames.split(",")]
        tiles = []
        for t in idx:
            im = sc.frame(t)
            cv2.putText(im, str(t), (12, int(40 * SCALE) + 10), 0, 1.2 * SCALE + 0.4, (0, 255, 255), 2)
            tiles.append(im)
            if os.environ.get("PNG_DIR"):
                cv2.imwrite(os.path.join(os.environ["PNG_DIR"], f"f_{t:04d}.png"), im)
        if os.environ.get("SHEET"):
            cols = int(os.environ.get("COLS", "4"))
            while len(tiles) % cols:
                tiles.append(np.zeros_like(tiles[0]))
            sheet = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
            cv2.imwrite(os.environ["SHEET"], sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
        return
    dur = NF / 30.0
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", "30", "-i", "-"]
    if REF:
        cmd += ["-i", REF, "-map", "0:v", "-map", "1:a", "-af", f"afade=t=out:st={dur - 0.35:.3f}:d=0.35",
                "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for t in range(NF):
        p.stdin.write(sc.frame(t).tobytes())
        if t % 30 == 0:
            print("Bild", t, "/", NF, flush=True)
    p.stdin.close()
    p.wait()
    print("fertig:", OUT)


if __name__ == "__main__":
    main()
