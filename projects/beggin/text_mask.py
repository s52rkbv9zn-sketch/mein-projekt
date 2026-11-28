#!/usr/bin/env python3
"""Text-Maske aus einem Lyric-Edit herausloesen, dessen Hintergrund im Takt zwischen "verwaschen" (50 % Weiss)
und "normal" wechselt und dessen Text immer den umgekehrten Zustand zeigt (Referenz 9, "Beggin'").

Modell (gemessen): verwaschen = A * normal + B  (A ~ 0.50-0.53, B ~ 114-118 je Kanal, also 50 % fast-Weiss).
Jeder Bildpunkt p hat je Bild t einen Zustand s_t(p) (verwaschen/normal). Text = Zustand weicht vom Bild ab.

Zwischen zwei aufeinanderfolgenden Bildern gilt fuer jeden Punkt eine von drei Beziehungen:
  gleich            I1 ~ I0                     (Zustand bleibt)
  wird normal       I0 ~ W(I1)                  (s0 = verwaschen, s1 = normal)
  wird verwaschen   I1 ~ W(I0)                  (s0 = normal,     s1 = verwaschen)
Die beste Beziehung (mit Abstand) setzt den Zustand neu; sonst wird er weitergegeben. Das laeuft einmal
vorwaerts und einmal rueckwaerts; je Bild zaehlt die Richtung mit dem juengsten sicheren Ereignis.
So werden auch Woerter erkannt, die genau beim Flackern erscheinen, und Animationen (Wisch, Tippen).

    python3 text_mask.py REF.mp4 AUSGABE_ORDNER  [letztes_bild]
Ausgabe: masks.npy (uint8 0/255, Bilder x 576 x 1024), state.npy (globaler Zustand je Bild, 1 = verwaschen)
"""
import os, subprocess, sys
import numpy as np
import cv2

A = np.array([0.496, 0.529, 0.512], np.float32)
B = np.array([117.7, 113.5, 115.9], np.float32)
THR = 40.0          # Mindestabstand (Summe ueber 3 Kanaele) fuer ein sicheres Ereignis
THR_LOOSE = 24.0    # lockere Schwelle (nur zum Auffuellen der Buchstaben neben sicherem Text)
MAX_AGE = 60
MEDIAN = int(os.environ.get("MEDIAN", 3))            # Glaettung der Rohmaske (5 frisst duenne Striche kleiner Woerter)
REL_SIGMA = float(os.environ.get("REL_SIGMA", 1.0))  # Glaettung der Beziehungs-Abstaende (kleiner = duenne Striche bleiben)


def wash(x):
    return x * A + B


def load(path, last):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", "fps=30:start_time=0", "-frames:v", str(last + 1),
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    w, h = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                                    "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip().split(",")[:2])
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w, 3)


def global_state(frames):
    st = []
    for x in frames:
        s = cv2.resize(x, (128, 72), interpolation=cv2.INTER_AREA).astype(np.float32).mean(axis=2)
        st.append(np.percentile(s, 30) > 80)
    return np.array(st)


def undo_fade(frames, ref_level=127.0):
    """Am Ende blendet das Vorbild nach Schwarz aus (das letzte verwaschene Bild wird Bild fuer Bild dunkler).
    Helligkeit dieser Bilder zurueckrechnen, damit die Zustands-Erkennung weiter funktioniert.
    Rueckgabe: Bilder, Gain je Bild (1 = normal). Nur der zusammenhaengende Abfall am Ende zaehlt."""
    p30 = np.array([np.percentile(cv2.resize(x, (128, 72), interpolation=cv2.INTER_AREA).astype(np.float32).mean(axis=2), 30)
                    for x in frames])
    gains = np.ones(len(frames), np.float32)
    bright = np.where(p30 >= 120)[0]
    if len(bright):
        t = int(bright[-1]) + 1
        while t < len(frames) and p30[t] < p30[t - 1] - 2 and p30[t] > 20:
            gains[t] = p30[t] / ref_level
            t += 1
    out = frames.copy() if (gains < 1).any() else frames
    for t in np.where(gains < 1)[0]:
        out[t] = np.clip(frames[t].astype(np.float32) / gains[t], 0, 255).astype(np.uint8)
    return out, gains


def relation(i0, i1):
    """Rueckgabe: beste Beziehung (0 = gleich, 1 = wird normal W->V, 2 = wird verwaschen V->W) und Abstand zur zweitbesten"""
    i0 = i0.astype(np.float32)
    i1 = i1.astype(np.float32)
    r = np.stack([np.abs(i1 - i0).sum(2), np.abs(i0 - wash(i1)).sum(2), np.abs(i1 - wash(i0)).sum(2)])
    if REL_SIGMA > 0:
        r = np.stack([cv2.GaussianBlur(x, (0, 0), REL_SIGMA) for x in r])
    order = np.argsort(r, axis=0)
    srt = np.take_along_axis(r, order, axis=0)
    return order[0].astype(np.int8), np.minimum(srt[1] - srt[0], 255).astype(np.uint8)


def track(best, margin, thr, S, frames):
    """Zustand je Punkt vorwaerts und rueckwaerts verfolgen. Rueckgabe: sicherer und lockerer Text je Bild."""
    n = len(frames)
    h, w = frames.shape[1:3]
    s_f = np.empty((n, h, w), np.bool_)
    age_f = np.empty((n, h, w), np.uint8)
    s_f[0] = np.where(frames[0].min(axis=2) < 100, False, S[0])          # True = verwaschen
    age_f[0] = MAX_AGE
    for t in range(n - 1):
        r = np.where(margin[t] > thr, best[t], -1)
        s = s_f[t].copy()
        s[r == 1] = False
        s[r == 2] = True
        s_f[t + 1] = s
        a = np.minimum(age_f[t].astype(np.int16) + 1, MAX_AGE).astype(np.uint8)
        a[(r == 1) | (r == 2)] = 0
        age_f[t + 1] = a
    s_b = np.empty((n, h, w), np.bool_)
    age_b = np.empty((n, h, w), np.uint8)
    s_b[-1] = np.where(frames[-1].min(axis=2) < 100, False, S[-1])
    age_b[-1] = MAX_AGE
    for t in range(n - 2, -1, -1):
        r = np.where(margin[t] > thr, best[t], -1)
        s = s_b[t + 1].copy()
        s[r == 1] = True                             # Bild t war verwaschen
        s[r == 2] = False
        s_b[t] = s
        a = np.minimum(age_b[t + 1].astype(np.int16) + 1, MAX_AGE).astype(np.uint8)
        a[(r == 1) | (r == 2)] = 0
        age_b[t] = a
    sure = np.empty((n, h, w), np.uint8)
    loose = np.empty((n, h, w), np.uint8)
    for t in range(n):
        tf = s_f[t] != S[t]
        tb = s_b[t] != S[t]
        okf = age_f[t] < MAX_AGE
        okb = age_b[t] < MAX_AGE
        # sicher: beide Richtungen stimmen zu (hat eine noch kein Ereignis gesehen, zaehlt die andere)
        txt = np.where(okf & okb, tf & tb, np.where(okf, tf, np.where(okb, tb, False)))
        sure[t] = cv2.medianBlur(txt.astype(np.uint8) * 255, MEDIAN)
        # locker: die Richtung mit dem juengsten Ereignis zaehlt
        lo = np.where(age_f[t] <= age_b[t], tf, tb) & (okf | okb)
        loose[t] = cv2.medianBlur(lo.astype(np.uint8) * 255, MEDIAN)
    return sure, loose


def stabilize(frames, C):
    """Bilder in "ruhende" Text-Koordinaten umrechnen (C[t]: ruhend -> Bild t, aus text_drift.py)"""
    n, h, w = frames.shape[:3]
    out = np.empty_like(frames)
    for t in range(n):
        out[t] = cv2.warpAffine(np.ascontiguousarray(frames[t]), C[t][:2].astype(np.float32), (w, h),
                                flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    return out


def smooth_final(masks):
    """Kleine Loecher schliessen und Kanten glaetten (kleine Woerter sind sonst ausgefranst)"""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    out = np.empty_like(masks)
    for t in range(len(masks)):
        out[t] = cv2.medianBlur(cv2.morphologyEx(masks[t], cv2.MORPH_CLOSE, k), 5)
    return out


def unstabilize(masks, C):
    """Masken zurueck in Bildkoordinaten (weiche Kanten, Text gleitet wie im Vorbild)"""
    n, h, w = masks.shape
    out = np.empty_like(masks)
    for t in range(n):
        out[t] = cv2.warpAffine(masks[t], C[t][:2].astype(np.float32), (w, h), flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return out


def main():
    ref, out = sys.argv[1], sys.argv[2]
    last = int(sys.argv[3]) if len(sys.argv) > 3 else None
    os.makedirs(out, exist_ok=True)
    C = np.load(os.environ["DRIFT"])["C"] if os.environ.get("DRIFT") else None
    raw_s, raw_l = os.path.join(out, "sure_raw.npy"), os.path.join(out, "loose_raw.npy")
    if os.environ.get("FROM_RAW") and os.path.exists(raw_s):
        # Stufe 1 schon gerechnet: nur Aufraeumen/Vervollstaendigen neu (schnell zum Feineinstellen)
        sure = np.load(raw_s)
        loose = np.load(raw_l)
        S = np.load(os.path.join(out, "state.npy")).astype(bool)
        gains = np.load(os.path.join(out, "gains.npy"))
    else:
        frames = load(ref, last if last is not None else 10 ** 6)
        frames, gains = undo_fade(frames)
        n = len(frames)
        if C is not None:
            frames = stabilize(frames, C)
        S = global_state(frames)
        h, w = frames.shape[1:3]
        best = np.empty((n - 1, h, w), np.int8)
        margin = np.empty((n - 1, h, w), np.uint8)
        for t in range(n - 1):
            best[t], margin[t] = relation(frames[t], frames[t + 1])
        sure, _ = track(best, margin, THR, S, frames)            # streng: wenig Stoerungen
        _, loose = track(best, margin, THR_LOOSE, S, frames)     # locker: vollstaendige Buchstaben
        del best, margin, frames
        np.save(os.path.join(out, "state.npy"), S.astype(np.uint8))
        np.save(os.path.join(out, "gains.npy"), gains)
        if os.environ.get("KEEP_RAW"):
            np.save(raw_s, sure)
            np.save(raw_l, loose)
    n = len(sure)
    if C is not None:
        C = C[:n]
    sure = clean(sure, C)
    for t in range(n):
        # lockere Maske nur direkt neben sicher erkanntem Text verwenden
        near = cv2.dilate(sure[t], np.ones((31, 31), np.uint8)) > 0
        loose[t] = np.where(near & (loose[t] > 127), 255, sure[t]).astype(np.uint8)
    masks = complete(sure, loose, k=int(os.environ.get("COMPLETE_K", 12)), frac=float(os.environ.get("COMPLETE_FRAC", 0.34)))
    if os.environ.get("KEEP_RAW"):
        np.save(os.path.join(out, "sure.npy"), sure)
        np.save(os.path.join(out, "loose.npy"), loose)
    del loose
    masks = smooth_final(masks)
    if C is not None:
        np.save(os.path.join(out, "masks_canon.npy"), masks)
        masks = unstabilize(masks, C)
    np.save(os.path.join(out, "masks.npy"), masks)
    print("fertig", n, "Bilder")


def _align(m_t, m_u, scale=4):
    """Lage des Textes in Bild u relativ zu Bild t (der Text gleitet langsam und zoomt leicht): 2x3-Matrix
    fuer cv2.warpAffine(m_u, M, ..., WARP_INVERSE_MAP) in voller Aufloesung, oder None."""
    h, w = m_t.shape
    a = cv2.GaussianBlur(cv2.resize(m_t, (w // scale, h // scale), interpolation=cv2.INTER_AREA).astype(np.float32) / 255, (0, 0), 1.5)
    b = cv2.GaussianBlur(cv2.resize(m_u, (w // scale, h // scale), interpolation=cv2.INTER_AREA).astype(np.float32) / 255, (0, 0), 1.5)
    warp = np.eye(2, 3, dtype=np.float32)
    try:
        cc, warp = cv2.findTransformECC(a, b, warp, cv2.MOTION_AFFINE,
                                        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-5), None, 3)
    except cv2.error:
        return None
    if cc < 0.7 or abs(warp[0, 0] - 1) > 0.05 or abs(warp[1, 1] - 1) > 0.05 or abs(warp[0, 1]) > 0.05 or abs(warp[1, 0]) > 0.05:
        return None
    warp[:, 2] *= scale
    return warp


def complete(masks, votes=None, k=12, step=2, frac=0.34):
    """Buchstaben vervollstaendigen: Der Text gleitet langsam (bis ~15 px in 2 s) und die Frau dahinter bewegt
    sich. Wo der Hintergrund fast weiss ist, zeigt das Vorbild keinen Unterschied -> dort fehlen Teile.
    Je Bild werden die Nachbarbilder (+-k) passgenau auf die Textlage ausgerichtet; ein Punkt gehoert zum Text,
    wenn er in mindestens frac der Bilder gesetzt ist, in denen dasselbe Wort vorkommt (nur innerhalb der
    Wortbereiche dieses Bildes - so bleiben Blinken, Eintippen und neue Woerter erhalten)."""
    n, h, w = masks.shape
    votes = masks if votes is None else votes                # Stimmen (z. B. lockere Maske), Lage aus der sicheren
    out = np.zeros_like(masks)
    for t in range(n):
        mt = masks[t]
        if mt.max() == 0:
            continue
        boxes = cv2.dilate(mt, np.ones((9, 21), np.uint8))
        num, lab, stats, _ = cv2.connectedComponentsWithStats((boxes > 0).astype(np.uint8), 8)
        cnt = ((votes[t] > 127) & (boxes > 0)).astype(np.float32)
        used = np.ones(num, np.float32)
        acc = np.zeros((h, w), np.float32)
        for u in range(max(0, t - k), min(n, t + k + 1), step):
            if u == t or masks[u].max() == 0:
                continue
            M = _align(mt, masks[u])
            if M is None:
                continue
            mu = cv2.warpAffine(masks[u], M, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP) > 127
            vu = mu if votes is masks else \
                cv2.warpAffine(votes[u], M, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP) > 127
            for c in range(1, num):
                x, y, ww, hh, _ = stats[c]
                reg = lab[y:y + hh, x:x + ww] == c
                own = (mt[y:y + hh, x:x + ww] > 127) & reg
                ov = (mu[y:y + hh, x:x + ww] & own).sum()
                if ov < 0.6 * max(1, own.sum()):
                    continue                                  # Wort in Bild u nicht (ganz) da
                acc[y:y + hh, x:x + ww] += (vu[y:y + hh, x:x + ww] & reg)
                used[c] += 1
        need = np.zeros((h, w), np.float32)
        need[:] = 1e9
        for c in range(1, num):
            x, y, ww, hh, _ = stats[c]
            reg = lab[y:y + hh, x:x + ww] == c
            need[y:y + hh, x:x + ww][reg] = max(1.0, frac * used[c])
        res = (cnt + acc) >= need
        res = res | ((mt > 127) & (used[lab] < 3))          # zu wenig Vergleichsbilder: so lassen wie erkannt
        out[t] = res.astype(np.uint8) * 255
    return out


# Bereiche mit TikTok-Zeichen des Vorbilds (bei 1024 x 576): dort ist nie Text
LOGO_BOXES = [(0, 0, 150, 100), (930, 505, 1024, 576)]
# Text steht im Vorbild immer in diesem Bereich (gemessen: x 0,20-0,80, y 0,18-0,82 der Bildgroesse)
TEXT_AREA = (0.17, 0.12, 0.83, 0.88)


def clean(raw, C=None):
    """Stoerflecken entfernen: Text beruehrt nie den Bildrand, steht immer mehrere Bilder still und
    besteht aus Buchstaben (kleine Teile nur nahe bei Buchstaben, z. B. i-Punkte, Apostrophe).
    C: Bewegung der Textebene (dann liegen die Masken in ruhenden Text-Koordinaten)."""
    n, h, w = raw.shape
    rawb = raw > 127
    ax0, ay0, ax1, ay1 = TEXT_AREA
    area_m = np.zeros((h, w), np.uint8)
    area_m[int(ay0 * h):int(ay1 * h), int(ax0 * w):int(ax1 * w)] = 1
    for (x0, y0, x1, y1) in LOGO_BOXES:
        area_m[y0:y1, x0:x1] = 0
    for t in range(n):
        if C is None:
            rawb[t] &= area_m > 0
        else:
            rawb[t] &= cv2.warpAffine(area_m, C[t][:2].astype(np.float32), (w, h),
                                      flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP) > 0
    out = np.zeros_like(raw)
    for t in range(n):
        num, lab, stats, _ = cv2.connectedComponentsWithStats(rawb[t].astype(np.uint8), 8)
        keep = np.zeros(num, bool)
        for k in range(1, num):
            x, y, ww, hh, area = stats[k]
            if x <= 2 or y <= 2 or x + ww >= w - 2 or y + hh >= h - 2:
                continue                                     # beruehrt den Rand -> Hintergrund
            if area < 12:
                continue
            comp = lab[y:y + hh, x:x + ww] == k
            def ov(u):
                return float(rawb[u, y:y + hh, x:x + ww][comp].mean()) if 0 <= u < n else 0.0
            # Woerter blinken im Vorbild (1-2 Bilder aus, dann wieder da): dieselbe Form muss innerhalb von
            # 3 Bildern noch einmal vorkommen. Zufaellige Flecken tun das nicht.
            if max(ov(u) for u in (t - 3, t - 2, t - 1, t + 1, t + 2, t + 3)) < 0.6:
                continue
            keep[k] = True
        m = keep[lab]
        # kleine Teile (i-Striche, i-Punkte, Apostrophe, kleine Woerter) nur in Wortgruppen behalten, die
        # zusammen genug Flaeche haben: Gruppen = Teile mit hoechstens ~24 px waagerechtem / 12 px senkrechtem Abstand
        kept = keep[lab]
        grp_n, grp = cv2.connectedComponents(cv2.dilate(kept.astype(np.uint8), np.ones((13, 25), np.uint8)), connectivity=8)
        grp_area = np.bincount(grp[kept], minlength=grp_n)
        big = np.zeros(num, bool)
        big[1:] = (stats[1:, cv2.CC_STAT_AREA] >= 300) & keep[1:]
        m = big[lab] | (kept & (grp_area[grp] >= 500))
        m = cv2.morphologyEx(m.astype(np.uint8) * 255, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        out[t] = m
    return out


if __name__ == "__main__":
    main()
