# Effekt- und Übergangs-Katalog

Gemessen am Referenz-Edit von @sorinyx (Han / Stray Kids, Song mit ca. 136 BPM), Bild für Bild.
Umgesetzt in `projects/felix-sorinyx/render.py` (Stand v15, vom Nutzer abgenommen).

Alle Zeiten in **Bildern bei 30 fps** (Bild n = n/30 s). „Schnittbild“ = erstes Bild des neuen Clips.
Offsets wie `-2`, `0`, `+1` beziehen sich auf das Schnittbild.

---

## 1. Bausteine (Parameter im Renderer)

| Kürzel | Bedeutung | Typische Werte |
|---|---|---|
| `L` + `d` | Streifen-Bewegungsunschärfe (Box-Blur), Länge = L × Bildbreite; Richtung `v` vertikal, `h` horizontal, `d` diagonal 45° | 0,03 (Hauch) … 0,50 (voll verwischt) |
| `sig` | weiche Gauß-Unschärfe (Pixel bei 1080 px) | 1 … 40 |
| `mul` | Helligkeit / Abdunkeln | 0,15 (fast schwarz) … 0,9 |
| `echo` | Doppelbild: dieselbe Aufnahme 1,18× vergrößert, um (−10 %, −3 %) versetzt, überblendet | 0,10 … 0,45 |
| `cout` / `cin` | schwarzer Kreis wächst über das alte Bild / neues Bild erscheint im Kreis (Radius × Bildbreite, harte Kante) | 0,006 … 0,55 |
| `vig` | zusätzliche Randabdunkelung | 0,1 … 0,5 |
| `expo`, `glow`, `leak` | Belichtung ×, Leuchten heller Stellen, warmer Lichtfleck oben rechts | |
| Kamera | Zoom pro Bild aus der Referenz gemessen (`ref_camera.json`) + Bewegungsunschärfe passend zur Zoom-Geschwindigkeit (180°-Verschluss, in starken Übergangsbildern 360°) | |

---

## 2. Kamerabewegung – der Hauptgrund, warum es „flüssig“ wirkt

* Jeder Clip zoomt **durchgehend**: 2–5 % pro Bild (Mittel 2,3 %), die Richtung wechselt pro Clip (rein / raus).
* Vor dem Schnitt **beschleunigt** die Bewegung (Beispiel: +1,4 → +1,7 → +6,7 % pro Bild).
* Am Schnitt kehrt die Richtung um, so wie in der Referenz. In schnellen Abschnitten läuft der Zoom dagegen in dieselbe Richtung weiter.
* **Fehler, den ich vorher gemacht hatte:** Ich hatte zu langsam gezoomt (~0,9 %/Bild), und die Richtung kippte kurz vor und nach jedem Schnitt. Das wirkte abgehackt.
* Grenzen: Zoom maximal 1,42× (sonst wird das Bild unscharf), minimal 1,0 (keine gespiegelten Ränder).
* Drehungen aus der Messung **nicht** übernehmen. Sie stammen meist von Kopf- oder Körperbewegungen. Prüfen lässt sich das mit `kamera_profil.py --maske hintergrund`.
* Ergebnis: Korrelation mit der Referenz 0,87 (vorher 0,34), gleiche mittlere Zoom-Geschwindigkeit.

---

## 3. Übergänge der Referenz (Teil 1; Teil 2 = dieselben Effekte 214 Bilder später)

| Schnittbild | Typ | Ablauf |
|---|---|---|
| 117 (3,90 s) | Intro → Clip 1 | siehe Abschnitt 4 |
| 131 | horizontale Zoom-Streifen | −2/−1 diagonale Streifen, leicht dunkler · 0: starke horizontale Streifen (L .45), Helligkeit .48 · +1 Streifen + leichtes Echo · +2 fast scharf |
| 143 | leicht | 0: kurze diagonale Streifen (L .08), +1 fast scharf |
| 159 | tief, vertikal + Echo | −3…−1 vertikale Streifen L .05/.30/.50, bis Helligkeit .2 · 0: L .25, .5 · +2…+4 Echo .45/.40/.28 |
| 173 | tiefer Dunkel-Übergang | −2: L .30 · −1/0: L .45/.40 + sig 3, Helligkeit .35 · +1/+2 diagonal ausklingend |
| 186 | vertikal, mittel | −1: L .40, .6 · 0: L .35, .7 |
| 199 | vertikal → weich | −1: L .45, .55 · 0: sig 4 · +1: sig 2 |
| 211 | tief | −2: sig 1,5 · −1: L .50 + sig 6, Helligkeit .35 · 0…+2 diagonal ausklingend |
| 226 | horizontal + Echo | in den hellen Teal-Clip, Echo .40/.25 bei +2/+3 |
| 239 | **schwarzer Kreis** | Kreis wächst über 5 Bilder: Radius .006 → .023 → .054 → .12 → .283 × Breite, harte Kante, rein schwarz; dabei Rand abdunkeln (vig .1/.28/.5) und leicht hineinzoomen · 0: neues Bild **im** Kreis (cin .40) mit vertikalen Streifen · +1: cin .55 · +2 fast scharf |
| 252 | vertikal, mittel | −1: L .50, .75 · 0: L .20 + sig 2 |
| 264 | weich + langes Echo | 0: sig 5 · +2…+6 Echo .32 → .10 |
| 279–330 | schneller Teil | in der Referenz harte Schnitte mit Lichtfleck/Belichtung, **bei uns auf Trommelschläge umgebaut** (Abschnitt 5) |
| 331 | Start Teil 2 | Einblendung aus dem Dunkeln wie bei 117 |

Teal-Clip (226–238): heller High-Key-Look (`teal_look.py`) passend zum Kreis.

---

## 4. Intro (Bild 0–116) – immer nur EIN Clip

* **Stotter-Sprünge im selben Clip** an den Flacker-Beats: Sprünge bei Bild 48, 52, 53, 59, 65, 85 (`INTRO_SEG`).
* **Schwarz-Weiß-Flackern** für 2–3 Bilder: 45–47, 50–51, 55–56, 59–61.
* **Zoom-Stöße** aus der Referenz-Kamerakurve (bis 1,5×): Schübe von +3 bis +4,7 % pro Bild bei 0,6–0,8 s und 2,1–3,3 s.
* **Farbe blendet weich aus** ab Bild 101 (Sättigung nach Referenzkurve 0,26 → 0,04 bis Bild 116). Kein harter Sprung auf S/W.
* **Lichtblitz**: Bild 111 stark, 112 schwach, als weißer Streifen am linken Rand.
* **Übergang in Clip 1** (Bild 111–127):
  * **Kippen:** Drehung 0 → −9,2° (gegen den Uhrzeigersinn) über die Bilder 111–116. Dabei rutscht das Bild etwa 5 % nach oben und 1 % nach links. Gemessen am Hintergrund (Lautsprecher), nicht an der Person.
  * **Wellen-Shake („kleiner Shake, ohne dass das Bild wackelt“):** Eine feine Wellenverzerrung beginnt bei Bild 113 mit 0,1 % der Breite. Bei 117–119 erreicht sie 0,5 % und klingt bis 127 aus. Wellenlängen: 0,45 × Breite plus eine feine von 0,09 ×. Die Phase springt in jedem Bild. In der Referenz erkennt man den Effekt an einer gewellten dunklen Kante am rechten Bildrand und an welligen Lautsprecher-Linien. Bleib dezent, sonst wirkt das Gesicht „flüssig“.
  * Bild 117 ist fast schwarz und sehr weich (sig 40, Helligkeit .32). Bild 118 ist weich unscharf mit kurzen diagonalen Streifen. 119–120 klingen aus.
  * Der neue Clip kommt um +5° gedreht herein und dreht sich bis Bild 120 an seinen Platz zurück, in derselben Richtung wie das Kippen.

---

## 5. Trommel-Break 9,15–10,90 s (Wunsch des Nutzers, weicht von der Referenz ab)

* In der Tonspur gibt es 9 Trommelschläge im Achtel-Abstand (~137 BPM). Gemessen mit `beats.py song 8.9 11.2`.
* Deshalb 9 Clips mit je einem **Schnitt auf jedem Schlag**: Schnittbild = floor(t × 30) → 274, 280, 287, 294, 300, 307, 313, 320, 327.
* **Alle gleicher Übergang:** Jeder Clip zoomt mit derselben Geschwindigkeitskurve hinein (5 % → 2,2 % → 4,5 % pro Bild). Der Zoom läuft über die Schnitte durch.
* Auf jedem Schlag ein kurzer **Lichtimpuls**: Belichtung ×1,12 im Schlagbild, ×1,04 im nächsten Bild.
* **Clean:** keine Streifen, kein Abdunkeln, kein Echo; alle Clips mit derselben Farbstimmung.

---

## 6. Looks

* **CC-Filter** (`edit-toolkit/look.py`, nachgebaut nach einem vom Nutzer geschickten Avatar-Edit):
  * Tonwerte: Schwarzpunkt 0,018, Weißpunkt 0,975, Gamma 1,06, S-Kurve 40 %
  * Farbe: Sättigung ×1,3 (weniger bei schon satten Farben), Schatten kühl / Lichter warm
  * Schärfe und Glow: Klarheit 0,22, Detail 0,30, Glow 0,12
  * Danach eine Vignette von 22 %.
* **Teal-High-Key** (`teal_look.py`): luftiges Weiß, dunkle und neutrale Töne werden weich türkis, Haut, Rot und Pink bleiben erhalten.
* **Pink-Selektiv** (ffmpeg `colorhold`) für Clip 12, der danach weich auf S/W ausbleicht; **Rot-Selektiv** für den Clip mit roten Haaren.

---

## 7. Technik und Qualität

* **Bildschirmaufnahmen** sind 60-fps-Container mit doppelten Bildern. Duplikate entfernen (mittlere Differenz < 0,18), echte Bildzeiten über `showinfo` nutzen. Tempo je Quelle:
  * 60 fps → 1,0
  * 50 fps → 1,2 (im Intro 0,6)
  * 30 fps → 1,0
  * 25 fps → 25/30
  * 24 fps → 24/30
* **Zuschnitt:** Videobereich der iPhone-Aufnahme `crop=2096:1180:230:0` (nach Drehung). Danach je Szene ein quadratischer Ausschnitt ohne Untertitel, Logos und Leisten (`scenes.py`). Jede Szene über ihre ganze Länge prüfen.
* **Ausgabe:** 1080×1080, 30 fps, x264 slow CRF 15, tune film, BT.709, AAC 256k. Der Ton ist die Tonspur der Referenz.
* **Vorverarbeitung:** Rauschfilter `hqdn3d=2.2:1.8:3:3` vor dem Hochskalieren, Skalierung mit Lanczos.


---

# Referenz 4: Konzert-Edit (@mitanori), umgesetzt in `projects/felix-konzert`

576×576, 30 fps, 17,4 s. Bildnummern = t × 30. Edit bis Bild 469, danach schwarz (Musik läuft bis 17,4 s).

* **Aufbau:** 10 Szenen (Schnitte 0, 22, 60, 75, 97, 119, 141, 177, 190, 214). Ab Bild 235 kommen **dieselben Clips mit denselben Momenten** noch einmal (alle Schnitte +235).
* **Übergang „Unschärfe-Blende“**, an jedem Schnitt einzeln gemessen (Tabelle `TR` im Renderer):
  * raus: 3 Bilder (σ 1 → 2–4 → 4–9 bei 576 px), dazu leicht dunkler (×0,9 → ×0,6)
  * rein: 5–6 Bilder (σ 8–24 → 5–12 → 3–6 → 2–3 → 1–2), dazu wieder heller werdend
* **Messmethode:** Unschärfe über die bandbegrenzte Schärfe schätzen (Bild auf 144 px verkleinern, Energie Bild minus Blur σ 1,5), **ohne Ausrichtung**. Vergleich mit einem 6 Bilder entfernten Bild überschätzt σ wegen Zoom und Bewegung. Volle Laplace-Schärfe unterschätzt σ wegen Kompressions-Blöcken. Sehr starke Unschärfe (σ > 15) nach Augenmaß ergänzen.
* **Dunkle Takt-Blitze:** einzelne Bilder ×0,31 mit leichter Unschärfe (σ 3) auf jeder Achtelnote, in Szene B (31, 39, 47, 54) und G (147, 154, 162, 169), jeweils +235.
* **Schiebe-Übergang** (Bild 140): Die linke Hälfte zeigt das neue Bild (dunkel, waagerecht verwischt), die rechte Hälfte das alte Bild (unscharf). Danach 141–142 waagerechte Wischunschärfe (0,10 und 0,03 × Breite).
* **Kamera:** weiche Zoom-Kurven je Szene aus der Referenz (`ref_camera.json`), Richtung wechselt pro Szene.
* **Look** `rose_look.py`: tiefe Schwarztöne, rosa Lichter (a +8..+12), kühl-magenta Schatten, leicht weich.

# Referenz 3: „home.“-Edit (@dohwxn), vorbereitet in `projects/home-edit`

768×576 (4:3), 30 fps, Edit bis Bild 779.

* **Schnitte:** 13 harte Schnitte ohne Übergangseffekte bei 0, 52, 103, 155, 227, 286, 322, 352, 407, 462, 521, 556, 597, 670.
* **Ruckel-Look:** neues Bild nur auf dem globalen Raster floor(k × 3,54 + 1,75), also 8,47 Bilder/s. Schnitte liegen außerhalb des Rasters.
* **Lichtblitz** 546–549: Doppelbelichtung mit einem hellen, bläulichen Geist, 12 % nach oben versetzt.
* **Ende** ab 670: der letzte Clip als quadratisches Foto (70 % der Bildhöhe) mittig auf dunklem Grund mit weichem Schatten. Ab 780 schwarz.
* **Schriftzug** „home.“: hellila (232, 206, 238), mittig, Playfair Display Italic mit zusätzlicher Neigung. **Nur auf ausdrücklichen Wunsch einsetzen** (Regel 1).
* **Look** `home_look.py`: warm, weich, leicht verblasst.
