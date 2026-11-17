#!/usr/bin/env python3
"""Findet Schlaege (Onsets) in der Tonspur und gibt die passende Schnitt-Bildnummer aus.

    python3 beats.py VIDEO_ODER_AUDIO [von_s bis_s] [--fps 30]

Ausgabe je Schlag: Zeit, Staerke und Schnittbild = floor(t * fps).
Regel aus der Praxis: Der Schnitt liegt auf dem Bild, in dem der Schlag passiert
(also 0-33 ms VOR dem hoerbaren Schlag). Ton minimal nach dem Bild wirkt synchron,
Ton vor dem Bild wirkt "zu spaet geschnitten".

Zusaetzlich: geschaetztes Tempo (BPM) und die Baender (Kick < 150 Hz, Snare/Mitten, Hi-Hat > 4 kHz),
damit man sieht, welches Instrument den Schlag macht (z.B. reiner Trommel-Break).
"""
import math, subprocess, sys
import numpy as np
from scipy.signal import find_peaks


def load_audio(path, sr=22050):
    d = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                       capture_output=True).stdout
    return np.frombuffer(d, np.int16).astype(np.float32) / 32768, sr


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fps = 30
    if "--fps" in sys.argv:
        fps = float(sys.argv[sys.argv.index("--fps") + 1])
        args = [a for a in args if a != sys.argv[sys.argv.index("--fps") + 1]]
    path = args[0]
    t0 = float(args[1]) if len(args) > 1 else 0.0
    t1 = float(args[2]) if len(args) > 2 else 1e9
    x, sr = load_audio(path)
    hop, n = 128, 1024
    fr = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * np.hanning(n)
    mag = np.abs(np.fft.rfft(fr, axis=1))
    freqs = np.fft.rfftfreq(n, 1 / sr)
    logm = np.log1p(200 * mag)
    t = (np.arange(len(mag)) * hop + n / 2) / sr

    def flux(lo, hi):
        m = (freqs >= lo) & (freqs < hi)
        return np.concatenate([[0], np.maximum(0, np.diff(logm[:, m], axis=0)).sum(1)])

    sel = (t > t0) & (t < t1)
    f_all = flux(30, 11000)
    z = (f_all - np.median(f_all[sel])) / (np.std(f_all[sel]) + 1e-9)
    pk, _ = find_peaks(np.where(sel, z, 0), height=1.5, distance=int(0.12 * sr / hop))
    bands = {"kick": flux(30, 150), "mitte": flux(150, 2000), "hihat": flux(4000, 11000)}
    for k in bands:
        b = bands[k]
        bands[k] = (b - np.median(b[sel])) / (np.std(b[sel]) + 1e-9)
    print(f"{'Zeit':>7s} {'Staerke':>7s}  Schnittbild  kick mitte hihat")
    for p in pk:
        print(f"{t[p]:7.3f} {z[p]:7.1f}  {math.floor(t[p] * fps):11d}  "
              + " ".join(f"{bands[k][p]:4.1f}" for k in ("kick", "mitte", "hihat")))
    if len(pk) > 2:
        d = np.diff(t[pk])
        q = np.median(d)
        bpm = 60 / q
        while bpm < 90:
            bpm *= 2
        while bpm > 180:
            bpm /= 2
        print(f"\nmittlerer Abstand {q:.3f} s  ->  ca. {bpm:.0f} BPM")


if __name__ == "__main__":
    main()
