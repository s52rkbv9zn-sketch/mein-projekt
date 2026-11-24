#!/bin/bash
# Text-Masken aus dem Vorbild (Referenz 9, "Beggin'") neu berechnen (~8 min, ~3 GB Speicher).
# Aufruf: ./make_masks.sh [Vorbild.mp4] [Ausgabeordner]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REF="${1:-$HERE/../felix-sorinyx/media/reference_beggin.mp4}"
OUT="${2:-$HERE/masks}"
LAST=663                       # letztes Bild mit Inhalt fuer die Erkennung (664/665: fast schwarz, Maske von 663)
mkdir -p "$OUT/pass1"
# 1. Lauf ohne Bewegungsausgleich: liefert nur die Vorlage fuer die Bewegungsmessung
MEDIAN=5 REL_SIGMA=1.0 KEEP_RAW=1 python3 "$HERE/text_mask.py" "$REF" "$OUT/pass1" $LAST
# 2. Bewegung der Textebene messen (liegt auch fertig im Repo: text_drift.npz)
if [ ! -f "$HERE/text_drift.npz" ]; then
  python3 "$HERE/text_drift.py" "$REF" "$OUT/pass1/sure.npy" "$HERE/text_drift.npz" $LAST
fi
# 3. Endgueltige Masken in ruhenden Text-Koordinaten
DRIFT="$HERE/text_drift.npz" MEDIAN=3 REL_SIGMA=0.5 python3 "$HERE/text_mask.py" "$REF" "$OUT" $LAST
rm -rf "$OUT/pass1"
echo "Masken fertig in $OUT (masks.npy, state.npy, gains.npy)"
