#!/usr/bin/env python3
"""„Beggin'“-Lyric-Edit (Referenz 9) mit Stray Kids im Hintergrund. 1920x1080, 30 fps, 666 Bilder (22,2 s).

Das Vorbild: Nahaufnahme einer Frau, darueber grosse Lyric-Woerter. Im Takt wechselt das ganze Bild zwischen
"normal" und "verwaschen" (50 % fast-Weiss: W(x) = A*x + B); die Woerter zeigen immer den umgekehrten Zustand
(Text "ausgestanzt"). Am Ende Abblende nach Schwarz.

Hier: Flackern, Abblende und Ton 1:1 aus dem Vorbild (Zustand je Bild aus text_mask.py). Die Schrift ist NEU
GESETZT (Wunsch des Nutzers: die herausgerechnete Schrift war zu ausgefranst): schmale Helvetica (Nimbus Sans
Narrow), jedes Wort an Lage/Groesse/Drehung des Vorbilds angepasst, Wisch/Eintippen/Blinken je Bild gemessen
(fit_words.py -> words_fit.json), Gleiten der Textebene aus text_drift.npz (text_layer.py),
nur der Hintergrund ist neu: die 8 Mitglieder im Wechsel (Schnitt nur auf einem Flacker-Wechsel, alle 0,4-1,5 s),
in Zeitlupe (0,5x wie die ruhige Nahaufnahme im Vorbild), Gesicht mittig, leichter Zoom, CC-Filter.

    python3 render.py                      # ganzes Video
    python3 render.py frames 0 230 450     # Einzelbilder als PNG (Kontrolle)
    python3 render.py sheet                # Uebersicht: Anfang/Mitte/Ende jeder Szene
Umgebung: BEGGIN_REF (Vorbild, fuer Ton und Farbmessung),
EDIT_OUT (Ausgabeordner).
"""
import json, os, re, subprocess, sys, time
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
TK = os.path.join(HERE, "..", "..", "edit-toolkit")
FELIX = os.path.join(HERE, "..", "felix-sorinyx")
sys.path.insert(0, TK)
from face_track import FaceTracker, track, smooth_track
from slowmo import resample
from look import cc
from dedupe import unique_indices
from text_layer import TextLayer

SKZ = os.environ.get("SKZ_MEDIA", os.path.join(HERE, "..", "skz-material", "media"))
FEL = os.environ.get("EDIT_MEDIA", os.path.join(FELIX, "media"))
# Schrift: neu gesetzt (words_fit.json aus fit_words.py, Bewegung text_drift.npz); Flacker-Zustand und Abblende
# des Vorbilds je Bild (ref_state.json aus text_mask.py)
FIT_JSON = os.path.join(HERE, "words_fit.json")
DRIFT_NPZ = os.path.join(HERE, "text_drift.npz")
STATE_JSON = os.path.join(HERE, "ref_state.json")
REF = os.environ.get("BEGGIN_REF", os.path.join(FEL, "reference_beggin.mp4"))
OUTDIR = os.environ.get("EDIT_OUT", os.path.join(HERE, "out"))
OUT = os.path.join(OUTDIR, "SKZ_Beggin_Edit.mp4")
W, H, FPS = 1920, 1080, 30
NF = 666                      # Bild 666 = TikTok-Abspann im Vorbild; der Song endet bei 22,20 s
AUDIO_END = 22.19

# Verwaschen-Modell (gemessen im Vorbild, je Kanal RGB)
WA = np.array([0.496, 0.529, 0.512], np.float32)
WB = np.array([117.7, 113.5, 115.9], np.float32)

# ------------------------------------------------------------------ Quellen
# Alle Bildschirmaufnahmen: 2556x1180 (quer). Querformat-Videos liegen bei x 230-2326, Hochformat-Videos in der
# Mitte (wird automatisch erkannt). safe = erlaubter Bereich (ohne Untertitel, Logos, Wasserzeichen), volle Koordinaten.


def skz(name, rot=None, safe=None):
    return dict(path=os.path.join(SKZ, name), rot=rot, safe=safe)


def fel(name, safe=None):
    return dict(path=os.path.join(FEL, name), rot=None, safe=safe)


SRC = {
    "bc_1a":   skz("bangchan_01.mov"),                                  # Hochformat, Stadion, Mikro
    "bc_1b":   skz("bangchan_01.mov"),                                  # Hochformat, gestreiftes Hemd
    "bc_1c":   skz("bangchan_01.mov"),                                  # Hochformat, Lederjacke, lacht
    "lk_6d":   skz("leeknow_01.mov", safe=(230, 0, 2060, 1180)),        # tuerkise Haare (TALKER-Logo rechts unten)
    "lk_6c":   skz("leeknow_01.mov", rot="cw", safe=(0, 600, 1180, 2330)),   # grauer Anzug, warmes Licht
    "lk_6a":   skz("leeknow_01.mov", rot="cw", safe=(0, 110, 1180, 2330)),   # blond, winkt
    "cb_3a":   skz("changbin_01.mov"),                                  # Hand an der Wange
    "cb_3b":   skz("changbin_01.mov", safe=(345, 0, 2326, 1180)),       # lila ('aurora' links)
    "cb_3c":   skz("changbin_01.mov"),                                  # Kapuze, rote Spinde
    "hj_vlog":  skz("hyunjin_02.mov", safe=(230, 0, 2150, 1000)),       # Untertitel + Logo unten
    "hj_stage": skz("hyunjin_03.mov", safe=(470, 0, 1980, 1180)),       # Buehne, Logos oben
    "hj_heart": skz("hyunjin_05.mov", safe=(230, 0, 2150, 1000)),
    "hj_hood":  skz("hyunjin_04.mov", safe=(230, 0, 2030, 1180)),
    "hj_crest": skz("hyunjin_05.mov", safe=(470, 90, 2286, 1150)),     # heller Rahmen, "Paper Tale"-Zeichen oben links
    "hj_mirror": skz("hyunjin_01.mov", safe=(346, 0, 2208, 1180)),
    "han_7b":  skz("han_01.mov", safe=(230, 0, 2010, 980)),             # Untertitel unten, RACHA-Logo oben rechts
    "sm_4a":   skz("seungmin_01.mov"),
    "sm_4b":   skz("seungmin_01.mov", safe=(230, 130, 2326, 1180)),     # kleiner Text oben links
    "in_2":    skz("in_01.mov", safe=(230, 0, 2060, 1180)),             # TALKER-Logo rechts unten
    "fx_shoot_red": fel("clip10.mov"),
    "fx_selfie": fel("clip12.mov", safe=(380, 0, 2175, 1180)),
    "fx_brick":  fel("clip10.mov"),
    "fx_fur":    fel("clip4.mov", safe=(230, 0, 2326, 925)),            # Untertitel unten (2 Zeilen)
}

# ------------------------------------------------------------------ Ablauf
# Schnitte nur auf Flacker-Wechseln des Vorbilds (dort springt ohnehin das ganze Bild).
# member: wer ist drauf (laut Nutzer/Manifest). t = Startzeit in der Quelle, speed 0.5 = Zeitlupe.
PLAN = [
    dict(f0=0,   src="bc_1c",  t=9.20, who="Bang Chan"),
    dict(f0=25,  src="lk_6d",  t=10.55, who="Lee Know"),
    dict(f0=47,  src="cb_3a",  t=0.60, who="Changbin"),        # Schnitt in der Quelle bei 0,55 s
    dict(f0=70,  src="hj_vlog", t=2.20, who="Hyunjin"),
    dict(f0=94,  src="han_7b", t=10.56, who="Han"),           # Schnitt in der Quelle bei 10,53 s
    dict(f0=116, src="fx_shoot_red", t=6.80, who="Felix"),
    dict(f0=145, src="sm_4b",  t=5.75, who="Seungmin"),
    dict(f0=163, src="in_2",   t=0.15, who="I.N"),
    dict(f0=184, src="bc_1a",  t=0.90, who="Bang Chan"),
    dict(f0=217, src="fx_selfie", t=3.20, who="Felix"),        # "beggin'" (Titel, 1,2 s)
    dict(f0=254, src="lk_6c",  t=5.15, who="Lee Know"),
    dict(f0=271, src="cb_3b",  t=2.90, who="Changbin"),
    dict(f0=292, src="hj_stage", t=2.00, who="Hyunjin"),
    dict(f0=316, src="han_7b", t=8.55, who="Han"),
    dict(f0=344, src="sm_4a",  t=0.30, who="Seungmin"),
    dict(f0=370, src="in_2",   t=0.85, who="I.N"),
    dict(f0=397, src="bc_1b",  t=3.00, who="Bang Chan"),
    dict(f0=424, src="lk_6a",  t=0.45, who="Lee Know"),
    dict(f0=436, src="hj_crest", t=10.30, speed=0.45, who="Hyunjin"),   # lange verwaschene Strecke (1,5 s), vor 11,02 s
    dict(f0=482, src="cb_3c",  t=5.63, who="Changbin"),        # Foto-Blitze in der Quelle ab 6,35 s
    dict(f0=517, src="han_7b", t=11.30, who="Han"),
    dict(f0=538, src="fx_brick", t=12.20, who="Felix"),
    dict(f0=565, src="sm_4b",  t=6.60, who="Seungmin"),
    dict(f0=598, src="in_2",   t=1.55, who="I.N"),
    dict(f0=623, src="hj_mirror", t=2.00, who="Hyunjin"),
    dict(f0=650, src="fx_fur", t=4.20, who="Felix"),
]
for k, sh in enumerate(PLAN):
    sh["f1"] = PLAN[k + 1]["f0"] if k + 1 < len(PLAN) else NF
    sh.setdefault("speed", 0.5)
    sh.setdefault("face_frac", 0.36)       # Gesichtshoehe / Bildhoehe (Vorbild: sehr nah, hier etwas weiter wegen Qualitaet)
    sh.setdefault("face_y", 0.44)          # Gesichtsmitte (Anteil der Bildhoehe von oben)
    sh.setdefault("push", (1.0, 1.04))     # sanfter Zoom durch jede Szene
MAX_UP = 2.1                               # hoechstens so stark vergroessern (Hochformat-Quellen sind schmal)

# ------------------------------------------------------------------ Dekodieren + Gesicht verfolgen
TRACKER = None


def decode(src, s, e):
    vf = []
    if src["rot"] == "cw":
        vf.append("transpose=1")
    vf += ["hqdn3d=1.2:1.0:2.0:2.0", "scale=in_color_matrix=bt709:in_range=tv", "format=rgb24", "showinfo"]
    r = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", src["path"],
                        "-vf", ",".join(vf), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    size = re.findall(rb"s:(\d+)x(\d+)", r.stderr)
    w, h = map(int, size[-1])
    arr = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w, 3)
    times = np.array([float(x) for x in re.findall(rb"pts_time:([0-9.]+)", r.stderr)])
    n = min(len(arr), len(times))
    arr, times = arr[:n], times[:n] + s
    keep = unique_indices(arr)
    return arr[keep], times[keep]


def content_box(frames, thr=14):
    g = np.stack([cv2.cvtColor(f[::4, ::4], cv2.COLOR_RGB2GRAY) for f in frames[:: max(1, len(frames) // 6)]])
    m = g.mean(0) > thr
    cols = np.where(m.mean(0) > 0.3)[0]
    rows = np.where(m.mean(1) > 0.3)[0]
    return cols.min() * 4, rows.min() * 4, (cols.max() + 1) * 4, (rows.max() + 1) * 4


def prepare(sh):
    """Quelle laden, gleichmaessige Zeitlupe (echte Bilder zur richtigen Zeit), Gesicht verfolgen"""
    global TRACKER
    src = SRC[sh["src"]]
    n = sh["f1"] - sh["f0"]
    t_out = sh["t"] + np.arange(n) / FPS * sh["speed"]
    frames, times = decode(src, max(0.0, sh["t"] - 0.2), t_out[-1] + 0.25)
    # Warnung: Schnitt oder Blitz in der Quelle innerhalb der Szene (ergibt Doppelbilder / Flackern)
    use = np.where((times >= t_out[0] - 0.02) & (times <= t_out[-1] + 0.02))[0]
    if len(use) > 2:
        g = np.stack([cv2.resize(cv2.cvtColor(frames[i], cv2.COLOR_RGB2GRAY), (192, 88),
                                 interpolation=cv2.INTER_AREA).astype(np.float32) for i in use])
        dif = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))
        if dif.max() > 15:
            print(f"  ACHTUNG {sh['src']} t={sh['t']}: Schnitt/Blitz in der Quelle bei "
                  f"{times[use[int(np.argmax(dif)) + 1]]:.2f} s (Aenderung {dif.max():.0f})", flush=True)
    frames, _ = resample(frames, times, t_out)
    bx = content_box(frames)
    if src["rot"] is None:                         # Querformat: Video liegt bei x 230-2326 (Rand nie mitnehmen)
        bx = (max(bx[0], 230), bx[1], min(bx[2], 2326), bx[3])
    if src["safe"]:
        sx0, sy0, sx1, sy1 = src["safe"]
        bx = (max(bx[0], sx0), max(bx[1], sy0), min(bx[2], sx1), min(bx[3], sy1))
    TRACKER = TRACKER or FaceTracker()
    hint = ((bx[0] + bx[2]) / 2, bx[1] + (bx[3] - bx[1]) * 0.4)
    raw = track(list(frames), hint=hint, tracker=TRACKER)
    fx, fy, fh = smooth_track(np.arange(n) / FPS, raw, sigma_s=0.25)
    found = int((~np.isnan(raw[:, 0])).sum())
    if found == 0:
        fx = np.full(n, (bx[0] + bx[2]) / 2, np.float32)
        fy = np.full(n, bx[1] + (bx[3] - bx[1]) * 0.4, np.float32)
    # Person mittig: der Ausschnitt darf nur so breit sein, dass das Gesicht in jedem Bild der Szene
    # waagerecht in der Mitte stehen kann (sonst klebt es am Rand des erlaubten Bereichs)
    margin = float(np.min(np.minimum(fx - bx[0], bx[2] - fx)))
    return dict(frames=frames, fx=fx, fy=fy, fh=float(np.nanmedian(raw[:, 2])) if found else 300.0, box=bx,
                found=found, ch_center=max(2.0 * margin * H / W, 1.0))


def crop_frame(d, k, face_frac, face_y, zoom):
    x0, y0, x1, y1 = d["box"]
    ch = d["fh"] / face_frac
    ch = min(ch, d["ch_center"])
    ch = max(ch, H / MAX_UP)
    ch = min(ch, y1 - y0, (x1 - x0) * H / W)
    ch = ch / zoom
    cw = ch * W / H
    cx = float(np.clip(d["fx"][k], x0 + cw / 2, x1 - cw / 2))
    cy = float(np.clip(d["fy"][k] + (0.5 - face_y) * ch, y0 + ch / 2, y1 - ch / 2))
    sc = H / ch
    M = np.array([[sc, 0, W / 2 - sc * cx], [0, sc, H / 2 - sc * cy]], np.float32)
    return cv2.warpAffine(d["frames"][k], M, (W, H), flags=cv2.INTER_LANCZOS4,
                          borderMode=cv2.BORDER_REFLECT_101).astype(np.float32)


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def shot_frame(sh, d, f):
    k = f - sh["f0"]
    n = max(1, sh["f1"] - sh["f0"] - 1)
    z0, z1 = sh["push"]
    z = z0 + (z1 - z0) * (0.3 * (k / n) + 0.7 * ease_io(k / n))
    return crop_frame(d, k, sh["face_frac"], sh["face_y"], z)


# ------------------------------------------------------------------ Farbe
def lab_stats(img):
    x = cv2.resize(np.clip(img, 0, 255).astype(np.float32), (320, 180), interpolation=cv2.INTER_AREA) / 255.0
    lab = cv2.cvtColor(x, cv2.COLOR_RGB2LAB).reshape(-1, 3)
    return lab.mean(0), lab.std(0) + 1e-3


def grade(img, match):
    """CC-Filter, dann Farben teilweise an die (unverwaschene) Nahaufnahme des Vorbilds angleichen"""
    x = cc(img, sat=1.18, clarity=0.22, detail=0.40, bloom=0.10)
    if match is None:
        return x
    (m_s, s_s), (m_r, s_r), k = match
    lab = cv2.cvtColor(np.clip(x, 0, 255).astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)
    for c in range(3):
        tgt_m = m_s[c] + k[c] * (m_r[c] - m_s[c])
        tgt_s = s_s[c] * (1 + k[c] * (s_r[c] / s_s[c] - 1))
        lab[..., c] = (lab[..., c] - m_s[c]) * (tgt_s / s_s[c]) + tgt_m
    lab[..., 0] = np.clip(lab[..., 0], 0, 100)
    return np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB) * 255.0, 0, 255)


MATCH_K = np.array([0.45, 0.35, 0.35], np.float32)     # L, a, b: wie stark an das Vorbild angleichen


# ------------------------------------------------------------------ Vorbild-Daten
def load_ref():
    d = json.load(open(STATE_JSON))
    state = np.array(d["state"], bool)
    gains = np.array(d["gains"], np.float32)
    text = TextLayer(FIT_JSON, DRIFT_NPZ, W, H)              # neu gesetzte Schrift in Ausgabegroesse
    text_ref = TextLayer(FIT_JSON, DRIFT_NPZ, 1024, 576)     # dieselbe in Vorbild-Groesse (Farbmessung)
    return text, text_ref, state, gains


def frame_params(text, state, gains, f):
    """Schrift (Alpha 0..1), Zustand und Helligkeit (Abblende) fuer Bild f. Nach dem letzten gemessenen Bild:
    Schrift/Zustand vom letzten Bild, Helligkeit laeuft weiter gegen Schwarz (Vorbild: 664-666 fast schwarz)."""
    last = len(state) - 1
    g = float(gains[min(f, last)])
    if f > last:
        g = max(0.0, float(gains[last]) - 0.07 * (f - last))
    return text.frame(min(f, last)), bool(state[min(f, last)]), g


def ref_vivid_stats(text_ref, state, f0, f1):
    """Farbstatistik der Nahaufnahme im Vorbild (verwaschene Bilder zurueckgerechnet), Bilder f0..f1"""
    cap = cv2.VideoCapture(REF)
    stats = []
    cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    for f in range(f0, f1):
        ok, bgr = cap.read()
        if not ok:
            break
        if f % 3:
            continue
        img = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
        m = (text_ref.frame(min(f, len(state) - 1)) > 0.5)[..., None]
        washed = state[min(f, len(state) - 1)]
        # Bildpunkte im Zustand "verwaschen" zurueckrechnen
        is_w = np.where(m, not washed, washed)
        img = np.where(is_w, (img - WB) / WA, img)
        stats.append(lab_stats(img))
    cap.release()
    if not stats:
        return None
    return np.mean([s[0] for s in stats], 0), np.mean([s[1] for s in stats], 0)


# ------------------------------------------------------------------ Zusammensetzen
def compose(bg, a, washed, gain):
    """bg: Hintergrund (float RGB 0..255, W x H). a: neu gesetzte Schrift (Alpha 0..1, W x H)."""
    wash = bg * WA + WB
    a = np.clip(a, 0, 1)[..., None]
    base, txt = (wash, bg) if washed else (bg, wash)
    out = base * (1 - a) + txt * a
    if gain < 0.999:
        out = out * gain
    return out


def render(which=None, sheet=False):
    text, text_ref, state, gains = load_ref()
    os.makedirs(OUTDIR, exist_ok=True)
    frames_wanted = set(which) if which else None
    proc = None
    if frames_wanted is None and not sheet:
        tmp = os.path.join(OUTDIR, "_video.mp4")
        proc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                                 "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "15",
                                 "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
                                 "-color_trc", "bt709", "-vf", "scale=out_color_matrix=bt709:out_range=tv",
                                 "-movflags", "+faststart", tmp], stdin=subprocess.PIPE)
    sheet_tiles = []
    t0 = time.time()
    only = {int(x) for x in os.environ.get("ONLY", "").split(",") if x.strip()}
    for sh in PLAN:
        if only and sh["f0"] not in only:
            continue
        fr = list(range(sh["f0"], sh["f1"]))
        if frames_wanted is not None:
            fr = [f for f in fr if f in frames_wanted]
            if not fr:
                continue
        if sheet:
            fr = [sh["f0"], (sh["f0"] + sh["f1"]) // 2, sh["f1"] - 1]
        d = prepare(sh)
        rs = ref_vivid_stats(text_ref, state, sh["f0"], sh["f1"])
        own = [lab_stats(cc(shot_frame(sh, d, f), sat=1.18, clarity=0.22, detail=0.40, bloom=0.10))
               for f in (sh["f0"], (sh["f0"] + sh["f1"]) // 2, sh["f1"] - 1)]
        match = None if rs is None else ((np.mean([o[0] for o in own], 0), np.mean([o[1] for o in own], 0)), rs, MATCH_K)
        print(f"{sh['f0']:3d}-{sh['f1']:3d} {sh['who']:9s} {sh['src']:12s} Gesicht {d['found']}/{len(d['frames'])}"
              f"  Bereich {d['box']}  {time.time() - t0:5.0f}s", flush=True)
        for f in fr:
            bg = grade(shot_frame(sh, d, f), match)
            a, washed, gain = frame_params(text, state, gains, f)
            out = np.clip(compose(bg, a, washed, gain), 0, 255).astype(np.uint8)
            if proc:
                proc.stdin.write(out.tobytes())
            elif sheet:
                tile = cv2.resize(cv2.cvtColor(out, cv2.COLOR_RGB2BGR), (480, 270), interpolation=cv2.INTER_AREA)
                cv2.putText(tile, f"{f} {sh['who']} {sh['src']}", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
                sheet_tiles.append(tile)
            else:
                cv2.imwrite(os.path.join(OUTDIR, f"frame_{f:03d}.png"), cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
        del d
    if sheet:
        rows = [np.hstack(sheet_tiles[i:i + 3]) for i in range(0, len(sheet_tiles), 3)]
        half = len(rows) // 2
        cv2.imwrite(os.path.join(OUTDIR, "sheet_a.jpg"), np.vstack(rows[:half]), [cv2.IMWRITE_JPEG_QUALITY, 82])
        cv2.imwrite(os.path.join(OUTDIR, "sheet_b.jpg"), np.vstack(rows[half:]), [cv2.IMWRITE_JPEG_QUALITY, 82])
        return
    if proc:
        proc.stdin.close()
        proc.wait()
        # Ton: Song des Vorbilds bis kurz vor dem TikTok-Abspann-Ton, auf -14 LUFS
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", tmp, "-i", REF, "-map", "0:v", "-map", "1:a",
                        "-af", f"atrim=0:{AUDIO_END},afade=t=out:st={AUDIO_END - 0.04}:d=0.04,"
                               "loudnorm=I=-14:TP=-1.0:LRA=11,aresample=48000",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", OUT],
                       check=True)
        os.remove(tmp)
        print("fertig:", OUT, f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "frames":
        render([int(x) for x in sys.argv[2:]])
    elif len(sys.argv) > 1 and sys.argv[1] == "sheet":
        render(sheet=True)
    else:
        render()
