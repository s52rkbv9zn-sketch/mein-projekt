#!/usr/bin/env python3
"""Edits nach Vorbild 7 und 8 (576x576, 30 fps) - ein Programm, Auswahl per EDIT=hyunjin | felix | spam | spamfelix.

EDIT=hyunjin  Vorbild 7a (rotes Buehnen-Edit, Cowboyhut): Intro 0-143 (EIN Clip, Einblendung aus Schwarz,
              zwei Lichtblitze), Weissblitz 144, Hauptteil 145-355 mit 13 Szenen (dunkle Unschaerfe-Dips,
              waagerechter Wisch, Lichtblitze, Schwarz-Weiss-Szene, rote Wellen-Verzerrung, Weissblitze),
              356-567 = 144-355 noch einmal, 568-601 schwarz.
EDIT=felix    Vorbild 7b: Michael-Jackson-Intro 0-150 wird UNVERAENDERT aus dem Vorbild uebernommen (nur
              TikTok-Zeichen/Name und die blinkenden Punkte in der Mitte weggerechnet). Danach Felix: 6 Szenen
              151-315 mit dunklen Wisch-Uebergaengen und Zoom-Pulsen + Lichtblitz auf den Schlaegen,
              316-479 = 151-314 noch einmal, 480-509 Weiss blendet ins Schwarze aus.
EDIT=spam     Vorbild 8 ("Spam my phone"-Trend) mit Hyunjin: 11 Szenen, harte Schnitte, ohne Text, natuerliche Farben.
EDIT=spamfelix  dasselbe mit Felix.
Beide: Zoom/Drehung je Bild aus dem Vorbild, Unschaerfe-Staerken per calibrate.py gemessen, Farben je Szene
und Helligkeit Bild fuer Bild ans Vorbild angeglichen, Person mittig (Gesichtserkennung), gleichmaessiger Takt.

Aufruf:  EDIT=felix python3 render.py | ... render.py frames 160 204 | ... render.py vergleich name.jpg 151 204
         ... render.py shots
"""
import json, math, os, re, subprocess, sys, time
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLKIT = os.path.join(HERE, "..", "..", "edit-toolkit")
FELIX = os.path.join(HERE, "..", "felix-sorinyx")
SKZ = os.path.join(HERE, "..", "skz-material")
sys.path.insert(0, TOOLKIT)
sys.path.insert(0, FELIX)
from face_track import FaceTracker, track, smooth_track
from slowmo import resample
from dedupe import unique_indices
from look import cc

EDIT = os.environ.get("EDIT", "hyunjin")
OUTDIR = os.environ.get("EDIT_OUT", os.path.join(HERE, "out"))
W, H, FPS = 1080, 1080, 30
ASPECT = W / H
REF_W, REF_H = 576, 576
K = W / float(REF_W)              # Pixelwerte wurden bei 576 px Breite gemessen
BASE = "crop=2096:1180:230:0"
SPEED = 1.0
MIN_CH = 560
FX = {}


def _fx(frames, **kw):
    for f in frames:
        FX.setdefault(f, {}).update(kw)


# Hyunjin-Szenen (projects/skz-material, Kennungen im Manifest), fuer EDIT=hyunjin und EDIT=spam
HJ_SCENES = {
    "concert":    ("hyunjin_06.mov", 0.00, 5.00, "crop=990:990:560:0", "stage"),     # H6a Fancam (eine Person)
    "concert_mic": ("hyunjin_06.mov", 10.20, 11.96, "crop=990:990:560:0", "stage"),   # H6b singt
    "stage_look": ("hyunjin_03.mov", 0.00, 6.08, "crop=1180:1180:458:0", "stage"),   # H3a Buehne
    "stage_calm": ("hyunjin_03.mov", 6.08, 10.37, "crop=1180:1180:458:0", "stage"),  # H3b ruhiger Moment
    "green_pose": ("hyunjin_04.mov", 8.50, 10.37, "crop=1020:1020:800:0", "bright"),  # H4d gruene Weste
    "glasses":    ("hyunjin_05.mov", 0.00, 1.52, "crop=1090:1090:250:0", "bright"),   # H5a Brille (vor Sticker)
    "crest":      ("hyunjin_05.mov", 10.18, 11.66, "crop=1060:1060:700:90", "cool"),  # H5c Fotoshooting
    "hood":       ("hyunjin_04.mov", 3.90, 7.06, "crop=1180:1180:300:0", "cool"),     # H4b Kapuze, Haende
    "vlog":       ("hyunjin_02.mov", 0.00, 8.54, "crop=1000:1000:560:0", "warm"),     # H2a schwarze Weste
    "cap":        ("hyunjin_04.mov", 0.00, 3.90, "crop=1180:1180:300:0", "cool"),     # H4a Kapuze + Kappe
    "heart":      ("hyunjin_05.mov", 4.03, 10.18, "crop=1000:1000:500:0", "bright"),  # H5b Herz-Haende
    "hoodie":     ("hyunjin_04.mov", 11.55, 12.86, "crop=1000:1000:550:0", "cool"),   # H4f graue Kapuzenjacke
    "mirror":     ("hyunjin_01.mov", 0.00, 5.53, "crop=1180:1180:460:0", "warm"),     # H1 Spiegel-Selfie
    "green_cam":  ("hyunjin_04.mov", 10.37, 11.55, "crop=1020:1020:800:0", "bright"), # H4e gruene Weste, Kamera vorne
}
HJ_SAFE = {
    "concert": (214, 0, 1881, 990), "concert_mic": (360, 0, 1735, 990), "stage_look": (240, 0, 1750, 1180),
    "stage_calm": (240, 0, 1750, 1180), "green_pose": (0, 0, 2096, 1020), "glasses": (0, 0, 1340, 1090),
    "crest": (40, 90, 2056, 1150), "hood": (0, 0, 1800, 1180), "vlog": (0, 0, 1920, 1000),
    "cap": (0, 0, 1800, 960), "heart": (0, 0, 1920, 1000), "hoodie": (0, 0, 2096, 1180),
    "mirror": (116, 0, 1978, 1180), "green_cam": (0, 0, 2096, 1020),
}

# Felix-Szenen (projects/felix-sorinyx/scenes.py): sichere Bereiche je Clip (ohne Untertitel/Logos), fuer felix/spamfelix
FX_SAFE = {
    "clip2.mov": (220, 80, 1950, 1000), "clip3.mov": (520, 0, 2096, 1180), "clip4.mov": (0, 0, 2096, 900),
    "clip5.mov": (0, 80, 1180, 1950), "clip6.mov": (290, 0, 2096, 1080), "clip7.mov": (290, 0, 2096, 1180),
    "clip9.mov": (0, 0, 2096, 960), "clip10.mov": (0, 0, 2096, 1180), "clip12.mov": (0, 0, 2096, 1000),
    "clip13.mov": (0, 0, 2096, 1020),
}
FX_SAFE_SCENE = {"selfie": (150, 0, 1945, 1180)}
FX_PATCHES = {"clip5.mov": [(64, 926, 162, 1170)]}


if EDIT == "hyunjin":
    REF = os.path.join(FELIX, "media", "reference_rot.mp4")
    MEDIA = os.environ.get("EDIT_MEDIA", os.path.join(SKZ, "media"))
    OUT = os.path.join(OUTDIR, "Hyunjin_Rot_Edit_v5.mp4")
    SCENES = HJ_SCENES
    SAFE = {}
    SAFE_SCENE = HJ_SAFE
    PATCHES = {}
    INTRO_END = 0
    CUTS = [0, 145, 170, 184, 209, 221, 231, 237, 249, 275, 287, 315, 328, 336]
    FIRST_END = 356
    PLAN = [
        dict(scene="concert",     t=0.05,  speed=0.98, face=(0.33, 0.16)),  # Intro: EIN Clip
        dict(scene="stage_look",  t=0.40,  face=(0.30, 0.17)),             # S1
        dict(scene="green_pose",  t=8.80,  face=(0.28, 0.20)),             # S2 hell
        dict(scene="glasses",     t=0.40,  face=(0.30, 0.18)),             # S3 Sonnenbrille -> Brille
        dict(scene="concert_mic", t=11.00, face=(0.30, 0.17)),             # S4 (ruhigster Moment)
        dict(scene="stage_calm",  t=6.70,  face=(0.30, 0.16)),             # S5
        dict(scene="crest",       t=10.50, face=(0.30, 0.16)),             # S6 Schwarz-Weiss
        dict(scene="concert",     t=3.00,  face=(0.28, 0.18)),             # S7
        dict(scene="hood",        t=4.20,  face=(0.30, 0.24)),             # S8 Nahaufnahme, Haende
        dict(scene="vlog",        t=2.20,  face=(0.30, 0.18)),             # S9
        dict(scene="stage_look",  t=2.10,  face=(0.30, 0.20)),             # S10 Buehne, Handschuh, Blick in die Kamera
        dict(scene="heart",       t=8.75,  face=(0.26, 0.16)),             # S11 hell (ruhigster Moment der Herz-Haende)
        dict(scene="hoodie",      t=11.70, face=(0.22, 0.18)),             # S12
        dict(scene="mirror",      t=2.00,  face=(0.30, 0.20)),             # S13
    ]
    FLASH = {144: 1.0, 230: 1.0, 335: 0.85}
    REP = (144, 356, 568)            # 356-567 = 144-355
    END_EDIT, NF = 568, 602          # danach schwarz (Musik laeuft), ab 602 TikTok-Abspann im Vorbild
    END_MODE = "black"
    DAMP_Z, DAMP_R, ZMAX, RMAX = 0.8, 0.3, 1.40, 2.5
    OVERLAYS = [(0, 0, 130, 105), (455, 488, 576, 576), (225, 520, 355, 562)]   # TikTok, Name, Editor-Zeichen
    # ---- Uebergaenge (Bildnummern wie im Vorbild; Unschaerfe-Staerken per calibrate.py)
    for _f in range(0, 31):
        _fx([_f], gain=((_f + 1) / 31.0) ** 1.6)                    # Einblendung aus Schwarz
    _fx([49], gain=1.45)
    _fx([59], gain=1.3)                                            # Lichtblitze im Intro
    _fx(range(145, 153), sig=3)                                    # nach dem Weissblitz scharf werden
    _fx([169], hb=0.03)
    _fx([170, 171], hb=0.08)
    _fx([172, 173], sig=2)
    _fx([182], sig=2)
    _fx([183], sig=10)
    _fx([184], vb=0.2, gain=0.6)
    _fx([185], sig=4)
    _fx([187], gain=1.6)
    _fx([192], gain=1.8)
    _fx([193], gain=2.0)                                           # Lichtblitze
    _fx(range(205, 209), sig=1.5)
    _fx([209], sig=10, gain=0.5)
    _fx([210, 211], sig=3)
    _fx([220], sig=1)
    _fx([221], sig=10, gain=0.5)
    _fx([222], vb=0.1)
    _fx(range(223, 228), sig=3)
    _fx(range(231, 237), bw=1.0)
    _fx([236], gain=0.55)
    _fx([237], wave=(0.05, 0.07, 0.0))                             # Ausschlag ~5 % der Breite (am Vorbild gemessen)
    _fx([238], wave=(0.035, 0.07, 0.5))
    # Geisterbild-Echo: vergroesserte, halb durchsichtige Kopie (Vorbild 145-148, 251-253, 287-288, 313-314, 329-330)
    for _f, _a, _s in [(145, .45, 1.28), (146, .35, 1.22), (147, .22, 1.16), (148, .10, 1.10),
                       (251, .25, 1.20), (252, .20, 1.15), (253, .10, 1.10), (287, .30, 1.20), (288, .15, 1.12),
                       (313, .15, 1.15), (314, .30, 1.22), (329, .30, 1.20), (330, .15, 1.12)]:
        _fx([_f], echo=(_a, _s))
    _fx([183], flare=(0.235, 1.0))                                 # waagerechter Lichtstreifen (Vorbild 183)
    for _f, _a in [(250, .035), (251, .03), (252, .015)]:
        _fx([_f], ripple=(_a, 0.33))                               # fluessige Wellen (Vorbild 250-252)
    _fx([239], sig=1.5)
    _fx(range(246, 249), sig=2)
    _fx([249], hb=0.1, gain=0.3)
    _fx([250, 251, 252], hb=0.05)
    _fx([273, 274], sig=2)
    _fx([275], sig=12, gain=0.2)
    _fx([276, 277], sig=4)
    _fx(range(285, 292), sig=2)
    _fx(range(311, 315), sig=2)
    _fx([326, 327], vb=0.03)
    _fx([328], vb=0.15, gain=0.6)
    _fx(range(329, 332), sig=2)
    _fx(range(336, 339), sig=2)
    _fx([353, 354], sig=2)
    _fx([355], hb=0.08)
elif EDIT == "spam":
    # Referenz 8 ("Spam my phone if ... is your bias"): 11 Szenen, harte Schnitte, keine eigenen Effekte,
    # normales Tempo, natuerliche Farben. Text des Vorbilds weggelassen (Wunsch des Nutzers).
    REF = os.path.join(FELIX, "media", "reference_spam.mp4")
    MEDIA = os.environ.get("EDIT_MEDIA", os.path.join(SKZ, "media"))
    OUT = os.path.join(OUTDIR, "Hyunjin_Spam_Edit_v2.mp4")
    SCENES = HJ_SCENES
    SAFE = {}
    SAFE_SCENE = HJ_SAFE
    PATCHES = {}
    INTRO_END = 0
    CUTS = [0, 55, 82, 104, 155, 219, 271, 320, 366, 429, 457]
    FIRST_END = 538
    PLAN = [   # face = (Gesicht senkrecht, Gesichtshoehe) - nach dem Vorbild, Nahaufnahmen etwas weiter (Qualitaet)
        dict(scene="green_pose", t=8.52,  speed=0.98, face=(0.32, 0.25)),   # 1  laechelt, hell (Vorbild: filmt im Park)
        dict(scene="mirror",     t=2.00,  face=(0.34, 0.28)),   # 2  Spiegel-Selfie (Vorbild: lacht am Tisch)
        dict(scene="green_cam",  t=10.45, face=(0.35, 0.22)),   # 3  hinter der Kamera (Vorbild: Kamera hoch)
        dict(scene="cap",        t=2.20,  face=(0.46, 0.34)),   # 4  Selfie mit Kappe (ganze Kappe sichtbar)
        dict(scene="vlog",       t=2.20,  face=(0.42, 0.50)),   # 5  Nahaufnahme (Vorbild: Nahaufnahme)
        dict(scene="stage_look", t=2.10,  face=(0.33, 0.35)),   # 6  Blick in die Kamera
        dict(scene="heart",      t=8.45,  face=(0.37, 0.24)),   # 7  Herz-Haende (Vorbild: lacht)
        dict(scene="crest",      t=10.24, speed=0.92, face=(0.40, 0.40)),   # 8  Fotoshooting, nah
        dict(scene="stage_calm", t=6.18,  face=(0.30, 0.26)),   # 9  Buehne, Blick in die Kamera (endet vor der Ueberblendung bei 8,37 s)
        dict(scene="glasses",    t=0.40,  face=(0.30, 0.33)),   # 10 Brille
        dict(scene="hood",       t=4.20,  face=(0.42, 0.50)),   # 11 Kapuze, Haende am Gesicht (Schluss)
    ]
    FLASH = {}
    REP = None
    END_EDIT, NF = 538, 538          # ab 538 TikTok-Abspann im Vorbild (Musik endet bei 17,76 s)
    END_MODE = "black"
    DAMP_Z, DAMP_R, ZMAX, RMAX = 0.0, 0.0, 1.0, 0.0    # keine eigene Kamerabewegung (Vorbild: nur harte Schnitte)
    OVERLAYS = [(0, 0, 130, 105), (455, 488, 576, 576), (140, 430, 436, 525)]   # TikTok-Zeichen, Text "Spam my phone"
    PLAIN = True                     # Trend-Video: keine Farb-/Helligkeitsangleichung an andere Personen
elif EDIT == "spamfelix":
    # Referenz 8 wie EDIT=spam (gleicher Ton, gleiche harten Schnitte, kein Text), nur mit Felix.
    # Szenen nach Art der Vorbild-Szene gewaehlt (Ausschnitt/Stimmung), Gesichtslage wie in der Hyunjin-Version.
    from scenes import SCENES
    REF = os.path.join(FELIX, "media", "reference_spam.mp4")
    MEDIA = os.environ.get("EDIT_MEDIA", os.path.join(FELIX, "media"))
    OUT = os.path.join(OUTDIR, "Felix_Spam_Edit.mp4")
    SAFE = FX_SAFE
    SAFE_SCENE = FX_SAFE_SCENE
    PATCHES = FX_PATCHES
    INTRO_END = 0
    CUTS = [0, 55, 82, 104, 155, 219, 271, 320, 366, 429, 457]
    FIRST_END = 538
    PLAN = [
        dict(scene="brick",     t=12.00, face=(0.34, 0.30)),   # 1  Fotoshooting, laechelt (Vorbild: filmt im Park)
        dict(scene="eat",       t=1.80,  face=(0.34, 0.28)),   # 2  isst Mango (Vorbild: lacht am Tisch; ab 2,75 s Untertitel neben dem Kopf)
        dict(scene="shoot_cam", t=9.50,  face=(0.35, 0.22)),   # 3  Kamera im Bild (Vorbild: Kamera hoch)
        dict(scene="bear",      t=0.30,  face=(0.27, 0.26)),   # 4  Baerenmuetze (Vorbild: Selfie mit Kappe; weiter = schaerfer)
        dict(scene="selfie",    t=3.30,  face=(0.42, 0.50)),   # 5  Selfie nah (Vorbild: Selfie ganz nah)
        dict(scene="shoot_sit", t=2.50,  face=(0.33, 0.35)),   # 6  sitzt, Blick zur Seite (Vorbild: Greenscreen)
        dict(scene="red_laugh", t=7.80,  face=(0.37, 0.24)),   # 7  lacht (Vorbild: lacht draussen)
        dict(scene="shoot_red", t=6.80,  face=(0.40, 0.40)),   # 8  Lederjacke nah (Vorbild: Lederjacke nah)
        dict(scene="coffee",    t=7.40,  face=(0.34, 0.30)),   # 9  Kaffee mit Strohhalm (nach dem Schnitt der Quelle bei 7,30 s)
        dict(scene="pink_kiss", t=7.65,  face=(0.36, 0.33)),   # 10 rosa Haare, Kussmund (Vorbild: Muetze, Hand am Kopf)
        dict(scene="fur",       t=5.00,  face=(0.32, 0.42)),   # 11 pinkes Fell, nah (Schluss)
    ]
    FLASH = {}
    REP = None
    END_EDIT, NF = 538, 538
    END_MODE = "black"
    DAMP_Z, DAMP_R, ZMAX, RMAX = 0.0, 0.0, 1.0, 0.0
    OVERLAYS = [(0, 0, 130, 105), (455, 488, 576, 576), (140, 430, 436, 525)]
    PLAIN = True
else:
    from scenes import SCENES
    REF = os.path.join(FELIX, "media", "reference_mj.mp4")
    MEDIA = os.environ.get("EDIT_MEDIA", os.path.join(FELIX, "media"))
    OUT = os.path.join(OUTDIR, "Felix_MJ_Edit_v3.mp4")
    SAFE = FX_SAFE
    SAFE_SCENE = FX_SAFE_SCENE
    PATCHES = FX_PATCHES
    INTRO_END = 151                  # 0-150: Intro wie im Vorbild, aber mit Felix (Wunsch des Nutzers)
    # Vorbild-Intro: EIN Clip in Schwarz-Weiss, laeuft und friert auf den Schlaegen ein ("Video laedt"),
    # waehrend des Einfrierens die roten/tuerkisen Lade-Punkte in der Mitte (gemessen)
    INTRO_CLIP = dict(scene="suit", t0=0.95, face=(0.38, 0.34))
    INTRO_RUNS = [(1, 19), (39, 54), (73, 90), (109, 118), (130, 140)]     # Bilder mit Bewegung
    INTRO_RAMP = {145: 0.15, 146: 0.30, 147: 0.35, 148: 0.40, 149: 0.65, 150: 1.0}
    INTRO_DOTS = [(19, 38), (55, 72), (90, 108), (119, 129), (141, 150)]   # Lade-Punkte sichtbar
    INTRO_BAR = {144: .002, 145: .007, 146: .014, 147: .024, 148: .036, 149: .043, 150: .125}
    INTRO_TONE = (32.4, 20.0)        # Lab-Helligkeit Mittel/Streuung des Vorbild-Intros
    CUTS = [151, 173, 191, 234, 252, 271]
    FIRST_END = 316
    PLAN = [
        dict(scene="red_laugh", t=7.80,  face=(0.30, 0.40)),               # C1 laechelt (Nahaufnahme)
        dict(scene="bear",      t=0.30,  face=(0.30, 0.30)),               # C2 laechelt (Anzug ist jetzt im Intro)
        dict(scene="brick",     t=12.60, face=(0.40, 0.38)),               # C3 laechelt, Zoom-Pulse
        dict(scene="stg_flip",  t=3.30,  speed=0.85, face=(0.28, 0.20)),   # C4 Tanz / Drehung
        dict(scene="shoot_sit", t=4.40,  face=(0.28, 0.22)),               # C5 steht, ernst
        dict(scene="stg_thumb", t=3.90,  speed=0.85, face=(0.24, 0.26)),   # C6 tanzt, Takt-Blitze
    ]
    FLASH = {}
    REP = (151, 316, 480)            # 316-479 = 151-314
    END_EDIT, NF = 480, 510          # 480-509 Weiss -> Schwarz, ab 510 TikTok-Abspann im Vorbild
    END_MODE = "white_fade"
    DAMP_Z, DAMP_R, ZMAX, RMAX = 0.9, 0.3, 1.45, 2.5
    OVERLAYS = [(0, 0, 125, 102), (455, 488, 576, 576)]
    _fx([151], hb=0.1, bw=0.8)
    _fx([152], hb=0.1, bw=0.5)
    _fx(range(153, 158), sig=4)
    for _f, _h, _v in [(151, .345, 152), (152, .194, 110), (153, .139, 90), (154, .102, 76), (155, .073, 64),
                       (156, .054, 53), (157, .036, 43), (158, .012, 33), (159, .005, 30)]:
        _fx([_f], split=(_h, _v))
    _fx([169, 170], sig=2)
    _fx([171, 172], hb=0.05)
    _fx([173], hb=0.05)
    _fx([174, 175, 176], sig=4)
    _fx([190], sig=2)
    _fx(range(191, 196), hb=0.05)
    _fx(range(202, 208), hb=0.03)
    _fx([204], gain=1.4)
    _fx([216, 217], hb=0.03)
    _fx([216], gain=1.25)
    _fx([225, 226], hb=0.03)
    _fx([225], gain=1.35)
    _fx([231], sig=2)
    _fx([232, 233], hb=0.05)
    _fx([234], sig=8, bw=0.3)
    _fx(range(235, 239), sig=4)
    _fx([248, 249], sig=3)
    _fx([250, 251], hb=0.05)
    _fx([252], hb=0.05)
    _fx([253], vb=0.03)
    _fx([270], vb=0.05)
    _fx(range(271, 275), sig=4)
    _fx([280, 281], sig=2)
    _fx([282], sig=3, gain=1.3)
    _fx([283], vb=0.03)
    _fx([284], sig=2)
    _fx(range(293, 297), vb=0.03)
    _fx([293], gain=1.3)
    _fx(range(301, 304), vb=0.03)
    _fx([304], sig=3, gain=1.3)
    _fx([305], sig=2)
    _fx([314, 315], sig=3)

INTRO_CLIP = globals().get("INTRO_CLIP")
PLAIN = globals().get("PLAIN", False)
BLUR_KEYS = ("hb", "vb", "sig", "zb")
TRANS_FILE = os.path.join(HERE, f"trans_{EDIT}.json")
TRANS, TRANS_SCENE = {}, {}
# Von Hand am Vorbild-Bild gesetzt, wo die Messung unsicher ist (sehr dunkle Ausblend-Bilder, Spalt-Bild)
TRANS_OVERRIDE = {
    "felix": {151: (8, 24), 248: (2, 2), 249: (4, 4), 250: (7, 7), 251: (10, 10), 314: (3, 3), 315: (6, 6)},
    "hyunjin": {49: (0, 2), 221: (3, 12)},
}
if os.path.exists(TRANS_FILE) and not os.environ.get("NO_TRANS"):
    _t = json.load(open(TRANS_FILE))
    TRANS = {int(k): v for k, v in _t["frames"].items()}
    TRANS_SCENE = {int(k): v for k, v in _t["scenes"].items()}
    for _f, (_sx, _sy) in TRANS_OVERRIDE.get(EDIT, {}).items():
        if _f in TRANS:
            TRANS[_f]["sx"], TRANS[_f]["sy"] = _sx, _sy
CAL_FILE = os.path.join(HERE, f"fx_cal_{EDIT}.json")
if os.path.exists(CAL_FILE) and not os.environ.get("NO_CAL"):
    for _k, _v in json.load(open(CAL_FILE)).items():
        FX.setdefault(int(_k), {}).update(_v)


def ref_mask(w, h):
    """True = Bildbereich ohne TikTok-Zeichen / Namen / Editor-Zeichen des Vorbilds (in Groesse w x h)"""
    m = np.ones((h, w), bool)
    for (x0, y0, x1, y1) in OVERLAYS:
        m[int(y0 * h / REF_H):int(math.ceil(y1 * h / REF_H)), int(x0 * w / REF_W):int(math.ceil(x1 * w / REF_W))] = False
    return m


# ------------------------------------------------------------------ Kamera: Zoom + Drehung aus dem Vorbild (gedaempft)
CAM_NAME = "spam" if EDIT.startswith("spam") else EDIT          # gleiche Vorbild-Kamera fuer spam/spamfelix
REFP = {int(k): v for k, v in json.load(open(os.path.join(HERE, f"ref_camera_{CAM_NAME}.json"))).items()}


def seg_of(f):
    return max(i for i, c in enumerate(CUTS) if c <= f)


def seg_end(i):
    return CUTS[i + 1] if i + 1 < len(CUTS) else FIRST_END


def _series(i, idx, damp, lim):
    a, b = CUTS[i], seg_end(i)
    vals = {}
    for f in range(a + 1, b + 2):
        r = REFP.get(f)
        if r and r[4] >= 0.85 and f not in (a, b) and abs(math.log(r[0])) <= 0.25 and abs(r[1]) <= 8:
            vals[f] = (math.log(r[0]) if idx == 0 else r[1]) * damp
    known = sorted(vals)
    seq = []
    for f in range(a + 1, b + 2):
        if f in vals:
            seq.append(vals[f])
        else:
            lo = [k for k in known if k < f]
            hi = [k for k in known if k > f]
            seq.append(vals[lo[-1]] if lo else (vals[hi[0]] if hi else 0.0))
    L = np.concatenate([[0.0], np.cumsum(seq)])
    return {a + k: float(v) for k, v in enumerate(L)}


CAM = []
for _i in range(len(CUTS)):
    lz = _series(_i, 0, DAMP_Z, ZMAX)
    rt = _series(_i, 1, DAMP_R, RMAX)
    fs = sorted(lz)
    z = np.array([lz[f] for f in fs])
    if z.max() - z.min() > math.log(ZMAX):
        z = z * math.log(ZMAX) / (z.max() - z.min())
    z = z - z.min()
    r = np.array([rt[f] for f in fs])
    r = r - r.mean()
    if np.abs(r).max() > RMAX:
        r = r * RMAX / np.abs(r).max()
    CAM.append({f: (float(math.exp(zz)), float(rr)) for f, zz, rr in zip(fs, z, r)})
    CAM[-1][fs[0] - 1] = CAM[-1][fs[0]]
    CAM[-1][fs[0] - 2] = CAM[-1][fs[0]]


def camera(i, f):
    c = CAM[i]
    f = min(max(f, min(c)), max(c))
    return c[f]


# ------------------------------------------------------------------ Quellen, Gesichtsverfolgung
TRACKER = None
cache = {}


def _decode(clip, rot, s, e):
    vf = f"{BASE}," + ("transpose=1," if rot else "") + \
         "hqdn3d=1.6:1.2:2.5:2.5,scale=in_color_matrix=bt709:in_range=tv,format=rgb24,showinfo"
    h, w = (2096, 1180) if rot else (1180, 2096)
    r = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", os.path.join(MEDIA, clip),
                        "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    arr = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w, 3)
    times = np.array([float(x) for x in re.findall(rb"pts_time:([0-9.]+)", r.stderr)])
    n = min(len(arr), len(times))
    arr, times = arr[:n], times[:n]
    keep = unique_indices(arr)
    arr = arr[keep]
    if clip in PATCHES:
        arr = arr.copy()
        for (px0, py0, px1, py1) in PATCHES[clip]:
            mx0, my0, mx1, my1 = max(0, px0 - 60), max(0, py0 - 60), min(w, px1 + 60), min(h, py1 + 60)
            mask = np.zeros((my1 - my0, mx1 - mx0), np.uint8)
            mask[py0 - my0:py1 - my0, px0 - mx0:px1 - mx0] = 255
            for a in arr:
                a[my0:my1, mx0:mx1] = cv2.inpaint(np.ascontiguousarray(a[my0:my1, mx0:mx1]), mask, 9, cv2.INPAINT_TELEA)
    return arr, times[keep] + s


def ts_of(i, f):
    return PLAN[i]["t"] + (f - CUTS[i]) / FPS * PLAN[i].get("speed", SPEED)


def load(i):
    global TRACKER
    if i in cache:
        return cache[i]
    p = PLAN[i]
    clip, a, b, pre, _ = SCENES[p["scene"]]
    rot = "transpose=1" in pre
    s = max(a, ts_of(i, CUTS[i] - 4) - 0.10)
    e = min(b, ts_of(i, seg_end(i) + 4) + 0.12)
    frames, times = _decode(clip, rot, s, e)
    src_fps = 1.0 / float(np.median(np.diff(times))) if len(times) > 2 else 60.0
    want = [min(max(ts_of(i, f), float(times[0])), float(times[-1])) for f in range(CUTS[i] - 4, seg_end(i) + 4)]
    n_real = len(frames)
    frames, times = resample(frames, times, want)
    m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", pre)[-1]
    cw0, ch0, cx0, cy0 = map(int, m)
    TRACKER = TRACKER or FaceTracker()
    raw = track(list(frames), hint=(cx0 + cw0 / 2, cy0 + ch0 / 2), tracker=TRACKER)
    fx, fy, fh = smooth_track(times, raw, sigma_s=0.18)
    found = int((~np.isnan(raw[:, 0])).sum())
    x0, y0, x1, y1 = SAFE_SCENE.get(p["scene"]) or SAFE.get(clip, (0, 0, 2096, 1180))
    yf, hf = p["face"]
    ch = float(np.nanmedian(raw[:, 2]) / hf)
    ch_max = min(y1 - y0, (x1 - x0) / ASPECT)
    yf_top, yf_bot = max(0.15, yf - 0.08), min(0.6, yf + 0.08)
    lim = min(np.percentile(2 * np.minimum(fx - x0, x1 - fx), 5) / ASPECT,
              np.percentile((fy - y0) / yf_top, 5), np.percentile((y1 - fy) / (1 - yf_bot), 5))
    ch = float(np.clip(ch, MIN_CH, min(ch_max, max(lim, MIN_CH))))
    cache[i] = dict(frames=frames, times=times, fx=fx, fy=fy, ch=ch, safe=(x0, y0, x1, y1), found=found,
                    total=n_real, fps=src_fps, lab=None)
    return cache[i]


def src_index(i, f):
    d = load(i)
    return int(np.argmin(np.abs(d["times"] - ts_of(i, f))))


def _cover(theta_deg):
    t = math.radians(abs(theta_deg))
    return math.cos(t) + math.sin(t) * max(ASPECT, 1 / ASPECT)


def warp(img, cx, cy, ch, ang, pad=0.0, interp=cv2.INTER_LANCZOS4):
    """Ausschnitt (Mitte cx,cy, Hoehe ch, 16:9) um ang Grad gedreht -> Leinwand (W, H) * (1 + 2 pad)"""
    wc, hc = int(round(W * (1 + 2 * pad))), int(round(H * (1 + 2 * pad)))
    sc = H / ch
    M = cv2.getRotationMatrix2D((cx, cy), -ang, sc)
    M[0, 2] += (wc - 1) / 2 - cx
    M[1, 2] += (hc - 1) / 2 - cy
    return cv2.warpAffine(img, M, (wc, hc), flags=interp, borderMode=cv2.BORDER_REFLECT_101).astype(np.float32)


def geometry(i, f, extra=1.0, sub=0.0):
    """Ausschnitt fuer Bild f (+ Bruchteil sub fuer Bewegungsunschaerfe)"""
    d = load(i)
    p = PLAN[i]
    x0, y0, x1, y1 = d["safe"]
    fa = int(math.floor(f + sub))
    w_ = f + sub - fa
    z0, r0 = camera(i, fa)
    z1, r1 = camera(i, fa + 1)
    z = math.exp(math.log(z0) * (1 - w_) + math.log(z1) * w_) * extra
    ang = r0 * (1 - w_) + r1 * w_
    cov = _cover(ang)
    ch = min(d["ch"] / z, (y1 - y0) / cov, (x1 - x0) / ASPECT / cov)
    cw = ch * ASPECT
    k = src_index(i, f)
    half_w, half_h = cw * cov / 2, ch * cov / 2
    cx = float(np.clip(d["fx"][k], x0 + half_w, x1 - half_w))
    cy = float(np.clip(d["fy"][k] + (0.5 - p["face"][0]) * ch, y0 + half_h, y1 - half_h))
    return k, cx, cy, ch, ang


def cam(i, f, pad=0.0, extra=1.0):
    d = load(i)
    k, cx, cy, ch, ang = geometry(i, f, extra)
    img = d["frames"][k]
    za, ra = camera(i, f - 1)
    zb_, rb = camera(i, f + 1)
    vz = abs(math.log(zb_ / za)) / 2
    vr = abs(rb - ra) / 2
    n = int(min(10, max(1, vz * 120 + vr * 3)))
    if n <= 1:
        return warp(img, cx, cy, ch, ang, pad)
    acc = None
    for j in range(n):
        u = ((j + 0.5) / n - 0.5) * 0.5                            # 180-Grad-Verschluss
        _, cx_, cy_, ch_, ang_ = geometry(i, f, extra, u)
        w_ = warp(img, cx_, cy_, ch_, ang_, pad, interp=cv2.INTER_LINEAR)
        acc = w_ if acc is None else acc + w_
    return acc / n


# ------------------------------------------------------------------ Farben: CC + Angleichung an die Vorbild-Szene
REF_ARR = None
REF_STATS = {}
MEAN_STRENGTH = np.array([0.90, 0.95, 0.95], np.float32)    # Mittelwert (Helligkeit, Farbstich) fast ganz wie Vorbild
STD_STRENGTH = np.array([0.70, 0.80, 0.80], np.float32)     # Kontrast/Saettigung etwas weniger (Qualitaet)


def _lab(img):
    return cv2.cvtColor(np.clip(img, 0, 255).astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)


def ref_frames():
    global REF_ARR
    if REF_ARR is None:
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", REF, "-vf", "fps=30:start_time=0", "-frames:v", str(NF),
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        REF_ARR = np.frombuffer(r.stdout, np.uint8).reshape(-1, REF_H, REF_W, 3)
    return REF_ARR


def ref_stats(i):
    if i in REF_STATS:
        return REF_STATS[i]
    ra = ref_frames()
    mask = ref_mask(REF_W // 2, REF_H // 2)
    a, b = CUTS[i] + 3, seg_end(i) - 3
    fs = ([f for f in range(a, max(a + 1, b), 2) if f not in FX and f not in FLASH] or
          [f for f in range(CUTS[i], seg_end(i)) if f not in FLASH])
    lab = np.concatenate([_lab(cv2.resize(ra[f], (REF_W // 2, REF_H // 2)))[mask] for f in fs])
    REF_STATS[i] = (lab.mean(0), lab.std(0) + 1e-3)
    return REF_STATS[i]


def base_look(img):
    return cc(img, sat=1.0, clarity=0.12, detail=0.25, bloom=0.05)


def shot_stats(i):
    d = load(i)
    if d["lab"] is None:
        fs = np.linspace(CUTS[i] + 2, seg_end(i) - 2, 5).astype(int)
        lab = np.concatenate([_lab(cv2.resize(base_look(cam(i, f)), (256, int(256 / ASPECT)), interpolation=cv2.INTER_AREA)).reshape(-1, 3)
                              for f in fs])
        d["lab"] = (lab.mean(0), lab.std(0) + 1e-3)
    return d["lab"]


RED_PULL = 0.5 if EDIT == "hyunjin" else 0.0     # Vorbild 7a ist durchgehend rot: Farbtoene Richtung Rot ziehen


def hue_to_red(img, k):
    """Farbtoene Richtung Rot ziehen (lila/magenta und orange werden roter), nur bei farbigen Pixeln"""
    hsv = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV_FULL)
    h = hsv[..., 0].astype(np.float32)
    dh = np.where(h > 128, h - 256, h)
    w = np.clip(hsv[..., 1].astype(np.float32) / 80.0, 0, 1)
    hsv[..., 0] = np.mod(np.round(dh * (1 - k * w)), 256).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB_FULL).astype(np.float32)


def grade(img, i):
    img = base_look(img)
    if PLAIN:                                         # natuerliche Farben (nur sanfter CC-Filter)
        return img
    ms, ss = shot_stats(i)
    mt, st = ref_stats(i)
    ratio = 1 + (np.clip(st / ss, 0.4, 1.5) - 1) * STD_STRENGTH
    m_eff = ms + (mt - ms) * MEAN_STRENGTH
    lab = m_eff + (_lab(img) - ms) * ratio
    out = np.clip(cv2.cvtColor(lab.astype(np.float32), cv2.COLOR_LAB2RGB), 0, 1) * 255.0
    return hue_to_red(out, RED_PULL) if RED_PULL > 0 else out


# Helligkeit Bild fuer Bild wie im Vorbild (Verlauf innerhalb der Szene, Blitze, Abdunkeln vor dem Schnitt)
REF_LUM = None
LUM_STRENGTH, LUM_MAX = 0.8, 30.0


def ref_lum(f):
    """mittlere Lab-Helligkeit des Vorbild-Bildes f (ohne TikTok-Zeichen/Schrift), innerhalb der Szene leicht geglaettet"""
    global REF_LUM
    if REF_LUM is None:
        ra = ref_frames()
        sw, shh = 128, int(round(128 * REF_H / REF_W))
        m = ref_mask(sw, shh)
        raw = np.array([_lab(cv2.resize(x, (sw, shh), interpolation=cv2.INTER_AREA))[..., 0][m].mean() for x in ra])
        srcl = raw.copy()
        bad = [f for f in list(FLASH) + list(TRANS) if 0 < f < len(srcl)]
        good = np.array([f for f in range(len(srcl)) if f not in set(bad)])
        if len(good) > 1 and bad:                          # Blitze/Uebergaenge nicht in die Nachbarbilder verschmieren
            srcl[bad] = np.interp(bad, good, raw[good])
        REF_LUM = raw.copy()
        for i in range(len(CUTS)):
            a, b = CUTS[i], min(seg_end(i), len(raw))
            seg = srcl[a:b]
            if len(seg) > 3:
                k = np.exp(-0.5 * (np.arange(-3, 4) / 1.0) ** 2)
                pad = np.pad(seg, 3, mode="edge")
                REF_LUM[a:b] = np.convolve(pad, k / k.sum(), mode="valid")
    return float(REF_LUM[min(f, len(REF_LUM) - 1)])


def match_lum(img, f):
    """Helligkeit ans Vorbild-Bild angleichen: dunkler = Richtung Schwarz skalieren, heller = Richtung Weiss"""
    x = np.clip(img, 0, 255).astype(np.float32)
    cur = float(_lab(cv2.resize(x, (128, int(round(128 / ASPECT))), interpolation=cv2.INTER_AREA))[..., 0].mean())
    shift = float(np.clip((ref_lum(f) - cur) * LUM_STRENGTH, -LUM_MAX, LUM_MAX))
    if abs(shift) < 0.5:
        return img
    lab = _lab(x)
    if shift < 0:
        lab[..., 0] *= (cur + shift) / max(cur, 1e-3)
    else:
        lab[..., 0] = 100 - (100 - lab[..., 0]) * (100 - cur - shift) / max(100 - cur, 1e-3)
    return np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), 0, 1) * 255.0


def finish(img, soften=0.15, glow=0.10):
    x = np.clip(img, 0, 255) / 255.0
    x = x * (1 - soften) + cv2.GaussianBlur(x, (0, 0), 1.4) * soften
    b = cv2.GaussianBlur(np.clip(x - 0.55, 0, None), (0, 0), 20)
    x = 1 - (1 - x) * (1 - glow * 2.2 * b)
    return np.clip(x, 0, 1) * 255.0


# ------------------------------------------------------------------ Effekt-Bausteine
RING_GAIN = 0.85


def center(img):
    hc, wc = img.shape[:2]
    if hc == H and wc == W:
        return img
    oy, ox = (hc - H) // 2, (wc - W) // 2
    return img[oy:oy + H, ox:ox + W]


def hblur(img, L):
    n = int(round(L * W))
    return img if n < 2 else cv2.blur(img, (min(n, 3 * W), 1), borderType=cv2.BORDER_REFLECT)


def vblur(img, L):
    n = int(round(L * H))
    return img if n < 2 else cv2.blur(img, (1, min(n, 3 * H)), borderType=cv2.BORDER_REFLECT)


def zoom_blur(canvas, amount, cy=0.42):
    if amount < 0.01:
        return canvas
    h, w = canvas.shape[:2]
    py = (h - H) / 2 + cy * H
    n = int(min(24, max(5, amount * 40)))
    acc = np.zeros_like(canvas)
    for j in range(n):
        s = math.exp(amount * ((j + 0.5) / n - 0.5))
        M = np.array([[s, 0, (1 - s) * (w - 1) / 2], [0, s, (1 - s) * py]], np.float32)
        acc += cv2.warpAffine(canvas, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return acc / n


_RING_KER = {}


def ring_layer(img, strength, radius=12.0, face=None):
    """Ring-Bokeh (Vorbild 66-69, 269-273, 350-352, 431-433, 478-480, 649-651, 794-796, 837-839, 869-871):
    an hellen Detail-Spitzen erscheinen einzelne duenne Ringe (Radius ~12 px bei 1024) mit Rot/Blau-Saum,
    in Ketten entlang heller Kanten. Das Gesicht wird geschont (face = (Hoehe, Groesse) als Anteil)."""
    r = radius * K
    key = round(r, 2)
    if key not in _RING_KER:
        t = max(1.8, 0.20 * r)
        n = int(math.ceil(r + 2 * t))
        yy, xx = np.mgrid[-n:n + 1, -n:n + 1].astype(np.float32)
        d = np.sqrt(xx * xx + yy * yy)
        _RING_KER[key] = (np.exp(-0.5 * ((d - r) / (t / 2)) ** 2).astype(np.float32), n)
    spr, n = _RING_KER[key]
    x = np.clip(img, 0, 255) / 255.0
    q = 4
    sm = cv2.resize(x, (W // q, H // q), interpolation=cv2.INTER_AREA)
    lum = sm[..., 0] * 0.2126 + sm[..., 1] * 0.7152 + sm[..., 2] * 0.0722
    det = np.clip(lum - cv2.GaussianBlur(lum, (0, 0), 3), 0, None) * np.clip((lum - 0.2) / 0.3, 0, 1)
    if face is not None:
        fy, fh = face
        yy, xx = np.mgrid[0:H // q, 0:W // q].astype(np.float32)
        e = ((xx - W / (2 * q)) / (0.8 * fh * H / q)) ** 2 + ((yy - fy * H / q) / (0.95 * fh * H / q)) ** 2
        det = det * (1 - 0.92 * np.exp(-e))
    sp = max(2, int(round(0.75 * r / q)))
    dil = cv2.dilate(det, np.ones((2 * sp + 1, 2 * sp + 1), np.uint8))
    ys, xs = np.where((det >= dil) & (det > 0.012))
    ring = np.zeros((H + 2 * n, W + 2 * n, 3), np.float32)
    if len(ys):
        v = det[ys, xs]
        order = np.argsort(-v)[: int(30 + 110 * strength)]
        vmax = float(np.percentile(v[order], 85)) + 1e-6
        for k_ in order:
            cy, cx = int(ys[k_] * q + q // 2) + n, int(xs[k_] * q + q // 2) + n
            col = 0.4 + 0.6 * sm[ys[k_], xs[k_]]
            ring[cy - n:cy + n + 1, cx - n:cx + n + 1] += spr[..., None] * col[None, None, :] * min(1.0, v[k_] / vmax)
    ring = ring[n:n + H, n:n + W]
    sh = 1.3 * K
    ring[..., 0] = cv2.warpAffine(ring[..., 0], np.float32([[1, 0, sh], [0, 1, 0]]), (W, H), borderMode=cv2.BORDER_REFLECT)
    ring[..., 2] = cv2.warpAffine(ring[..., 2], np.float32([[1, 0, -sh], [0, 1, 0]]), (W, H), borderMode=cv2.BORDER_REFLECT)
    return np.clip(ring * strength * RING_GAIN, 0, 1)


def stretch(img, x0, s, mirror):
    """waagerecht strecken ab x0 (Vorbild 371-374); gespiegelt -> V-Form um x0"""
    xs = np.arange(W, dtype=np.float32)
    X0 = x0 * W
    src = X0 + np.abs(xs - X0) / s if mirror else np.where(xs < X0, xs, X0 + (xs - X0) / s)
    mapx = np.repeat(src[None, :].astype(np.float32), H, axis=0)
    mapy = np.repeat(np.arange(H, dtype=np.float32)[:, None], W, axis=1)
    return cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def bend(img, A, vs):
    """Woelbung: Mitte nach unten gebogen, senkrecht gestreckt (Vorbild 375-379)"""
    u = np.linspace(-1, 1, W, dtype=np.float32)
    off = A * H * (1 - u * u)
    yy = np.arange(H, dtype=np.float32)[:, None]
    mapy = (H / 2 + (yy - H / 2 - off[None, :]) / vs).astype(np.float32)
    mapx = np.repeat(np.arange(W, dtype=np.float32)[None, :], H, axis=0)
    return cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def hourglass(img, m0, m1):
    """Sanduhr: in der Mitte schmal zusammengedrueckt, oben/unten breit, Seiten schwarz (Vorbild 567-570)"""
    yy = np.linspace(-1, 1, H, dtype=np.float32)[:, None]
    m = m0 + m1 * np.abs(yy)
    xs = np.arange(W, dtype=np.float32)[None, :]
    mapx = (W / 2 + (xs - W / 2) / m).astype(np.float32)
    mapy = np.repeat(np.arange(H, dtype=np.float32)[:, None], W, axis=1)
    return cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def glitch(img, k):
    """senkrechte Streifen: Spalten in Bloecken versetzt (322)"""
    if k <= 0:
        return img
    rng = np.random.default_rng(322)
    out = img.copy()
    x = 0
    while x < W:
        w_ = int(rng.integers(40, 180))
        sh = int(rng.integers(-120, 120) * k)
        out[:, x:x + w_] = np.roll(img[:, x:x + w_], sh, axis=0)
        x += w_
    return out


def echo(img, a, s, cy):
    """Geisterbild: um das Gesicht vergroesserte Kopie, halb durchsichtig darueber"""
    h, w = img.shape[:2]
    py = (h - H) / 2 + cy * H
    M = np.array([[s, 0, (1 - s) * (w - 1) / 2], [0, s, (1 - s) * py]], np.float32)
    z = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return img * (1 - a) + z * a


def ripple(img, amp, lam):
    """fluessige Wellen: waagerechte Linien werden wellig (senkrechte Verschiebung je Spalte)"""
    xs = np.arange(W, dtype=np.float32)[None, :] / W
    dy = amp * H * (np.sin(2 * np.pi * xs / lam) + 0.5 * np.sin(2 * np.pi * xs / (0.43 * lam) + 1.3))
    mapy = (np.arange(H, dtype=np.float32)[:, None] + dy).astype(np.float32)
    mapx = np.repeat(np.arange(W, dtype=np.float32)[None, :], H, axis=0)
    return cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def flare(img, y0, k):
    """waagerechter Lichtstreifen mit zwei hellen Punkten (Vorbild 7a, Bild 183)"""
    yy = np.arange(H, dtype=np.float32)[:, None] / H
    xx = np.arange(W, dtype=np.float32)[None, :] / W
    line = np.exp(-0.5 * ((yy - y0) / 0.008) ** 2) * (0.55 + 0.45 * np.exp(-0.5 * ((xx - 0.5) / 0.3) ** 2))
    spots = sum(np.exp(-0.5 * (((xx - x0) / 0.05) ** 2 + ((yy - y0) / 0.03) ** 2)) for x0 in (0.32, 0.62))
    glow = 0.25 * np.exp(-0.5 * ((yy - y0) / 0.06) ** 2)
    add = np.clip(line + 0.8 * spots + glow, 0, 1.5) * k * 255.0
    return img + add[..., None] * np.array([1.0, 0.92, 0.95], np.float32)


def split(img, hgt, val, c=0.5):
    """geteilte Einblendung: Bild in der Mitte auseinandergeschoben, Spalt mit Grau gefuellt (Vorbild 7b, 151-159)"""
    gap = int(round(hgt * H))
    if gap < 1:
        return img
    g1, g2, yc = gap // 2, gap - gap // 2, int(round(c * H))
    out = np.empty_like(img)
    out[:yc - g1] = img[g1:yc]
    out[yc - g1:yc + g2] = float(val)
    out[yc + g2:] = img[yc:H - g2]
    return out


def aniso(img, sx, sy):
    """weiche Unschaerfe, waagerecht sx / senkrecht sy (px bei 576) - Gauss statt Kasten: keine Doppelbilder"""
    out = img
    one = np.ones((1, 1), np.float32)
    if sx > 0.25:
        s_ = sx * K
        k = cv2.getGaussianKernel(int(2 * math.ceil(3 * s_) + 1), s_).astype(np.float32)
        out = cv2.sepFilter2D(out, -1, k, one, borderType=cv2.BORDER_REFLECT)
    if sy > 0.25:
        s_ = sy * K
        k = cv2.getGaussianKernel(int(2 * math.ceil(3 * s_) + 1), s_).astype(np.float32)
        out = cv2.sepFilter2D(out, -1, one, k, borderType=cv2.BORDER_REFLECT)
    return out


_LMASK = None


def lab_stats(img):
    """mittlere Helligkeit, Kontrast (Streuung L) und Farbigkeit (mittlere Chroma), ohne Overlay-Bereiche"""
    global _LMASK
    if _LMASK is None:
        _LMASK = ref_mask(128, 128)
    x = cv2.resize(np.clip(img, 0, 255).astype(np.float32), (128, 128), interpolation=cv2.INTER_AREA) / 255.0
    lab = cv2.cvtColor(x, cv2.COLOR_RGB2LAB)
    L = lab[..., 0][_LMASK]
    c = np.hypot(lab[..., 1], lab[..., 2])[_LMASK]
    return float(L.mean()), float(L.std()) + 1e-3, float(c.mean()) + 1e-3


def apply_levels(img, m_t, s_t, c_t):
    m_c, s_c, c_c = lab_stats(img)
    lab = cv2.cvtColor(np.clip(img, 0, 255).astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)
    lab[..., 0] = (lab[..., 0] - m_c) * float(np.clip(s_t / s_c, 0.25, 4.0)) + m_t
    lab[..., 1:] *= float(np.clip(c_t / c_c, 0.0, 4.0))
    return np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), 0, 1) * 255.0


NONBLUR_DROP = BLUR_KEYS + ("gain", "white", "split", "flare")


def trans_frame(i, f):
    """Uebergangsbild mit gemessenen Werten: Effekte -> weiche Unschaerfe -> Licht -> Helligkeit/Kontrast/Farbe -> Spalt"""
    spec = FX.get(f, {})
    t = TRANS[f]
    sc = TRANS_SCENE[i]
    img = layer(i, f, {k: v for k, v in spec.items() if k not in NONBLUR_DROP})
    img = aniso(img, t["sx"], t["sy"])
    img = apply_levels(img, sc["m"] + t["dm"], sc["s"] * t["rs"], sc["c"] * t["rc"])
    if spec.get("flare"):
        img = flare(img, *spec["flare"])
    if spec.get("split"):
        img = split(img, *spec["split"])
    return img


def wave(img, amp, period, phase):
    """rote Wellen-Verzerrung (Vorbild 7a, 237-238): jede Zeile im Zickzack waagerecht verschoben"""
    yy = np.arange(H, dtype=np.float32)[:, None] / H / period + phase
    tri = 2 * np.abs(2 * (yy - np.floor(yy + 0.5))) - 1                 # Dreieck -1..1
    mapx = (np.arange(W, dtype=np.float32)[None, :] + amp * W * tri).astype(np.float32)
    mapy = np.repeat(np.arange(H, dtype=np.float32)[:, None], W, axis=1)
    return cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def canvas(i, f, spec):
    pad = 0.18 if spec.get("zb", 0) > 0.01 else 0.0
    return grade(cam(i, f, pad=pad, extra=spec.get("zoom", 1.0)), i)


def apply_fx(img, i, spec):
    rings = (ring_layer(center(img), spec["ring"], spec.get("ring_r", 12.0), PLAN[i]["face"])
             if spec.get("ring") else None)
    if spec.get("zb", 0) > 0.01 and img.shape[0] > H:
        img = zoom_blur(img, spec["zb"], PLAN[i]["face"][0])
    img = center(img)
    if spec.get("st"):
        img = stretch(img, *spec["st"])
    if spec.get("bend"):
        img = bend(img, *spec["bend"])
    if spec.get("hg"):
        img = hourglass(img, *spec["hg"])
    if spec.get("wave"):
        img = wave(img, *spec["wave"])
    if spec.get("ripple"):
        img = ripple(img, *spec["ripple"])
    if spec.get("echo"):
        img = echo(img, *spec["echo"], PLAN[i]["face"][0])
    if spec.get("hb"):
        img = hblur(img, spec["hb"])
    if spec.get("vb"):
        img = vblur(img, spec["vb"])
    if spec.get("sig", 0) > 0.3:
        img = cv2.GaussianBlur(img, (0, 0), spec["sig"] * K)
    if spec.get("glitch"):                                    # nach der Unschaerfe: Streifen bleiben sichtbar
        img = glitch(img, spec["glitch"])
    if spec.get("bw"):                                        # Schwarz-Weiss (teilweise)
        y = (img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114)[..., None]
        img = img * (1 - spec["bw"]) + y * spec["bw"]
    if rings is not None:
        img = 255.0 * (1 - (1 - np.clip(img / 255.0, 0, 1)) * (1 - rings))
    img = img * spec.get("gain", 1.0)
    if spec.get("white"):
        img = img * (1 - spec["white"]) + 255.0 * spec["white"]
    return img


def layer(i, f, spec):
    return apply_fx(canvas(i, f, spec), i, spec)


INTRO = {}
RENDERED = {}
REF_FULL = None


def intro_frame(f):
    """Intro: mit INTRO_CLIP (Felix) nachgebaut, sonst Bild f des Vorbilds (TikTok-Zeichen weggerechnet)"""
    if INTRO_CLIP:
        return felix_intro(f)
    ra = ref_frames()
    img = ra[f].copy()
    mask = np.zeros((REF_H, REF_W), np.uint8)
    x0, y0, x1, y1 = OVERLAYS[0]
    mask[y0:y1, x0:x1] = 255
    box = img[255:320, 250:330]                                     # Punkte in der Bildmitte (farbig im S/W-Bild)
    hsv = cv2.cvtColor(box, cv2.COLOR_RGB2HSV)
    dots = (hsv[..., 1] > 70).astype(np.uint8) * 255
    if dots.any():
        mask[255:320, 250:330] = cv2.dilate(dots, np.ones((7, 7), np.uint8))
    img = cv2.inpaint(img, mask, 7, cv2.INPAINT_TELEA)
    big = cv2.resize(img, (W, H), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    big = big + 0.35 * (big - cv2.GaussianBlur(big, (0, 0), 1.6))
    return np.clip(big, 0, 255).astype(np.uint8)


INTRO_DATA = {}


def intro_speed(f):
    if f in INTRO_RAMP:
        return INTRO_RAMP[f]
    return 1.0 if any(a <= f <= b for a, b in INTRO_RUNS) else 0.0


def intro_times():
    ts, t = [], INTRO_CLIP["t0"]
    for f in range(INTRO_END):
        t += intro_speed(f) / FPS if f > 0 else 0.0
        ts.append(t)
    return ts


def intro_load():
    global TRACKER
    if INTRO_DATA:
        return INTRO_DATA
    clip, a, b, pre, _ = SCENES[INTRO_CLIP["scene"]]
    ts = intro_times()
    s, e = max(a, ts[0] - 0.1), min(b, ts[-1] + 0.12)
    frames, times = _decode(clip, "transpose=1" in pre, s, e)
    want = sorted(set(round(min(max(t, float(times[0])), float(times[-1])), 5) for t in ts))
    frames, times = resample(frames, times, want)
    m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", pre)[-1]
    cw0, ch0, cx0, cy0 = map(int, m)
    TRACKER = TRACKER or FaceTracker()
    raw = track(list(frames), hint=(cx0 + cw0 / 2, cy0 + ch0 / 2), tracker=TRACKER)
    fx, fy, fh = smooth_track(times, raw, sigma_s=0.25)
    x0, y0, x1, y1 = SAFE_SCENE.get(INTRO_CLIP["scene"]) or SAFE.get(clip, (0, 0, 2096, 1180))
    yf, hf = INTRO_CLIP["face"]
    ch = float(np.clip(np.nanmedian(raw[:, 2]) / hf, MIN_CH, min(y1 - y0, (x1 - x0) / ASPECT)))
    INTRO_DATA.update(frames=frames, times=np.asarray(times), fx=fx, fy=fy, ch=ch, safe=(x0, y0, x1, y1), ts=ts,
                      found=int((~np.isnan(raw[:, 0])).sum()))
    # Tonwerte wie im Vorbild-Intro: ganze Helligkeitsverteilung angleichen (eine Kurve fuer das ganze Intro)
    ra = ref_frames()
    m = ref_mask(144, 144)
    m[60:84, 60:84] = False                                                    # Lade-Punkte
    ref_l = np.concatenate([_lab(cv2.resize(ra[f], (144, 144), interpolation=cv2.INTER_AREA))[..., 0][m]
                            for f in range(0, 144, 3)])
    # S/W-Tonkurve wie im Vorbild-Intro: Gesicht klar sichtbar (Haut ~50), helle Flaechen hellgrau (~72, nicht
    # grell weiss), Anzug fast schwarz. Ankerpunkte aus den eigenen Bildern (Gesichtsbereich per Gesichtserkennung).
    own, face = [], []
    for f in range(0, INTRO_END, 10):
        L = intro_gray_l(f)
        own.append(L[::4, ::4].ravel())
        fh = 0.5 * INTRO_CLIP["face"][1] * H
        cy = INTRO_CLIP["face"][0] * H
        face.append(L[int(cy - 0.6 * fh):int(cy + 0.6 * fh), int(W / 2 - 0.45 * fh):int(W / 2 + 0.45 * fh)].ravel())
    own, face = np.concatenate(own), np.concatenate(face)
    p2, p98, fm = float(np.percentile(own, 2)), float(np.percentile(own, 98)), float(np.median(face))
    xs = [0.0, p2, fm, p98, 100.0]
    ys = [0.0, 3.0, 48.0, 64.0, 68.0]                                          # helle Flaechen grau wie die Wand im Vorbild
    order = np.argsort(xs)
    INTRO_DATA["curve"] = (np.array(xs)[order], np.array(ys)[order])
    return INTRO_DATA


def intro_gray_l(f):
    """Felix-Bild des Intros als Graustufen-Helligkeit (Lab L, 0-100), Gesicht wie im Vorbild platziert"""
    d = INTRO_DATA
    t = d["ts"][f]
    k = int(np.argmin(np.abs(d["times"] - t)))
    x0, y0, x1, y1 = d["safe"]
    ch = d["ch"]
    cw = ch * ASPECT
    cx = float(np.clip(d["fx"][k], x0 + cw / 2, x1 - cw / 2))
    cy = float(np.clip(d["fy"][k] + (0.5 - INTRO_CLIP["face"][0]) * ch, y0 + ch / 2, y1 - ch / 2))
    img = warp(d["frames"][k], cx, cy, ch, 0.0)                               # ohne Farbfilter: keine abgeschnittenen Lichter
    return _lab(img)[..., 0]


def loading_dots(img, f):
    """TikTok-Lade-Punkte (rot/tuerkis) in der Bildmitte, tauschen alle 18 Bilder die Seite (Vorbild 7b)"""
    run = next(((a, b) for a, b in INTRO_DOTS if a <= f <= b), None)
    if run is None:
        return img
    ph = 2 * math.pi * (f - run[0]) / 18.0
    depth = math.sin(ph)                                             # > 0: tuerkis vorne
    xr, xc = 0.5 - 0.015 * math.cos(ph), 0.5 + 0.015 * math.cos(ph)
    rr = 0.014 * (1 - 0.45 * max(depth, 0.0))
    rc = 0.014 * (1 - 0.45 * max(-depth, 0.0))
    red, cyan = ((xr, rr), (254, 44, 85)), ((xc, rc), (37, 244, 238))
    dots = [red, cyan] if depth > 0 else [cyan, red]                  # hinterer Punkt zuerst, vorderer darueber
    up = 4
    out = img.astype(np.float32)
    for (x, r), col in dots:
        cx, cy, rad = x * W, 0.5 * H, r * W
        x0, y0 = int(cx - rad - 3), int(cy - rad - 3)
        size = int(2 * rad + 7)
        m = np.zeros((size * up, size * up), np.uint8)
        cv2.circle(m, (int((cx - x0) * up), int((cy - y0) * up)), int(rad * up), 255, -1, cv2.LINE_AA)
        m = cv2.resize(m, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32)[..., None] / 255.0
        reg = out[y0:y0 + size, x0:x0 + size]
        out[y0:y0 + size, x0:x0 + size] = reg * (1 - m) + np.array(col, np.float32) * m
    return out


def felix_intro(f):
    d = intro_load()
    L = np.interp(intro_gray_l(f), *d["curve"]).astype(np.float32)
    lab = np.stack([L, np.zeros_like(L), np.zeros_like(L)], axis=2)
    img = np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), 0, 1) * 255.0
    img = finish(img)
    img = loading_dots(img, f)
    bar = int(round(INTRO_BAR.get(f, 0.0) * H))
    if bar > 0:                                                       # Bild rutscht nach unten, oben schwarz
        img = np.concatenate([np.zeros((bar, W, 3), np.float32), img[:H - bar]], axis=0)
    return np.clip(img, 0, 255).astype(np.uint8)


def end_frame(f):
    if END_MODE == "black":
        return np.zeros((H, W, 3), np.uint8)
    ra = ref_frames()                                                # Weiss blendet ins Schwarze (Farbe wie Vorbild)
    c = ra[min(f, len(ra) - 1)][100:450, 100:450].reshape(-1, 3).mean(0)
    return np.ones((H, W, 3), np.uint8) * np.clip(c, 0, 255).astype(np.uint8)[None, None, :]


def render(f):
    if f in RENDERED:
        return RENDERED[f]
    if REP and REP[1] <= f < REP[2]:                                 # zweiter Durchgang = erster Durchgang
        return render(f - (REP[1] - REP[0]))
    if f >= END_EDIT:
        return end_frame(f)
    if f < INTRO_END:
        return intro_frame(f)
    if f in FLASH:
        out = np.full((H, W, 3), int(round(255 * FLASH[f])), np.uint8)
    else:
        i = seg_of(f)
        if f in TRANS:
            out = np.clip(finish(trans_frame(i, f)), 0, 255).astype(np.uint8)
        else:
            img = layer(i, f, FX.get(f, {}))
            out = np.clip(finish(img, 0.05, 0.04) if PLAIN else finish(match_lum(img, f)), 0, 255).astype(np.uint8)
    if REP and REP[0] <= f < REP[0] + (REP[2] - REP[1]):
        RENDERED[f] = out
    return out


def release(f):
    if f < CUTS[0] or f >= FIRST_END:
        return
    i = seg_of(f)
    for k in list(cache):
        if k < i:
            del cache[k]


def compare(frames, name):
    ra = ref_frames()
    cols = []
    for f in frames:
        r = cv2.resize(ra[min(f, len(ra) - 1)], (288, 288), interpolation=cv2.INTER_AREA)
        e = cv2.resize(render(f), (288, 288), interpolation=cv2.INTER_AREA)
        t = cv2.cvtColor(np.vstack([r, e]), cv2.COLOR_RGB2BGR)
        cv2.putText(t, str(f), (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(t, str(f), (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cols.append(t)
    rows = [np.hstack(cols[k:k + 8]) for k in range(0, len(cols), 8)]
    wmax = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, wmax - r.shape[1]), (0, 0))) for r in rows]
    cv2.imwrite(os.path.join(OUTDIR, name), np.vstack(rows))


if __name__ == "__main__":
    os.makedirs(OUTDIR, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "frames":
        for f in map(int, sys.argv[2:]):
            cv2.imwrite(os.path.join(OUTDIR, f"preview_{f:03d}.png"), cv2.cvtColor(render(f), cv2.COLOR_RGB2BGR))
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "vergleich":
        compare([int(x) for x in sys.argv[3:]], sys.argv[2])
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "shots":
        for i, p in enumerate(PLAN):
            d = load(i)
            zs = [camera(i, f)[0] for f in range(CUTS[i], seg_end(i))]
            rs = [camera(i, f)[1] for f in range(CUTS[i], seg_end(i))]
            print(f"{i + 1:2d} {p['scene']:10s} t={p['t']:5.2f} Gesicht {d['found']}/{len(d['frames'])} "
                  f"Ausschnitt {d['ch']:.0f}px (x{H / d['ch']:.2f}) {d['fps']:.0f}fps  Zoom {min(zs):.2f}-{max(zs):.2f} "
                  f"Drehung {min(rs):+.1f}..{max(rs):+.1f}")
            del cache[i]
        sys.exit(0)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", REF, "-map", "0:v", "-map", "1:a",
         "-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=lanczos,format=yuv420p",
         "-c:v", "libx264", "-preset", "slow", "-tune", "film", "-crf", "16", "-profile:v", "high", "-level", "4.2",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
         "-af", f"atrim=0:{NF / FPS - 0.05:.3f},loudnorm=I=-14:TP=-1.5:LRA=11,"
                f"afade=t=out:st={NF / FPS - 0.65:.3f}:d=0.6",
         "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-t", f"{NF / FPS:.3f}", OUT], stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(NF):
        release(f)
        enc.stdin.write(render(f).tobytes())
        if f % 60 == 0:
            print(f"Bild {f}/{NF} {time.time() - t0:.0f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    print("fertig", OUT, round(time.time() - t0))
