#!/bin/bash
# Text-Masken aus dem Vorbild (Referenz 9, "Beggin'") neu berechnen und die Schrift daran neu setzen
# (~12 min, ~3 GB Speicher). Fuer render.py reichen danach words_fit.json, text_drift.npz und ref_state.json.
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
# 4. Schrift neu setzen: jedes Wort aus words.py an die Masken anpassen (Lage, Groesse, Wisch/Eintippen/Blinken)
python3 "$HERE/fit_words.py" "$OUT" "$HERE/words_fit.json"
# 5. Flacker-Zustand und Abblende je Bild fuer render.py
python3 - "$OUT" "$HERE/ref_state.json" <<'PY'
import json, sys, numpy as np
o = sys.argv[1]
json.dump(dict(info="Referenz 9: Zustand je Bild (1 = verwaschen) und Helligkeit der Abblende, aus text_mask.py",
               state=np.load(o + "/state.npy").astype(int).tolist(),
               gains=np.load(o + "/gains.npy").astype(float).round(4).tolist()), open(sys.argv[2], "w"))
PY
echo "Fertig: $OUT (Masken), words_fit.json, ref_state.json"
