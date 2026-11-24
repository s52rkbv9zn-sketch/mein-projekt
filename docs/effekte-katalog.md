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


## Referenz 4 mit Hyunjin (`projects/hyunjin-konzert`)

* Derselbe Renderer wie Felix v3, nur Szenen, sichere Bereiche und Material getauscht. Doppelte Bilder werden relativ gefiltert (`dedupe.unique_indices`).
* Szenen-Wahl nach Handlung im Vorbild:
  * A Blick in die Kamera (Bühne)
  * B verspielt mit Takt-Blitzen (Herz-Hände)
  * C singt (Konzert)
  * D/E ruhig und hell (Fotoshooting, Brille)
  * F altes Spiegel-Selfie
  * G Geste mit Takt-Blitzen („Psst“)
  * H kurz und süß (Kusshand)
  * I Konzert (Gesicht sichtbar, nicht nach oben geneigt)
  * J Kapuze
* **Bewegte Sticker** (z. B. Glitzer-Emoji am Kopf in H5a ab 1,55 s) lassen sich nicht sauber wegrechnen. Lieber einen Zeitraum ohne Sticker wählen. Gefunden über die Zahl gelber, gesättigter Pixel je Bild.
* **v3 (Feedback: „noch flüssiger, Clip 7 wackelig, Clip 8 raus“):**
  * Gleichmäßige Zeitlupe mit `slowmo.resample()`. Ursache war ein ungleichmäßiger Bildtakt der Quellen.
  * Wechsel-Unruhe je Szene im Mittel 0,26 → 0,13 (Vorbild 0,12). Clip 3 0,81 → 0,09, Clip 7 0,64 → 0,26.
  * Clip 7 jetzt ein ruhiger Bühnen-Moment statt der schnellen „Psst“-Geste.
  * Clip 8 jetzt das Vlog mit schwarzer Weste statt der Kusshand.
  * Clip 1 und 10 auf den jeweils ruhigsten Moment gelegt. Gesichtsführung weicher (σ 0,18 s).
  * Ruckel-Check: Vorbild 7, Edit 0 ungleichmäßige Stellen.

## Referenz 4, Version 2 (Feedback des Nutzers: „Zeitlupe, Felix mittig, Übergänge zu hart“)

* **Zeitlupe:** Felix-Szenen aus 60-fps-Quellen mit halber Geschwindigkeit, silver (41 fps) mit 0,7. Bildänderung innerhalb der Szenen: v1 8,9, v2 5,4, Vorbild 3,9.
* **Mittig:** YuNet-Gesichtserkennung (100 % Treffer), Spur geglättet (Gauß 0,12 s). Ausschnittgröße = Gesichtshöhe ÷ (Vorbild-Anteil × 0,78), so begrenzt, dass das Gesicht im sicheren Bereich immer exakt mittig sitzen kann.
* **Unschärfe am Schnitt** (σ bei 576 px): rein 14–20 → 9–13 → 6–7 → 4 → 2,5 → 1,5; raus 1,5 → 3,5 → 6. Am Bild abgeglichen (Vorbild-Bild neben schärferem Nachbarbild, das unterschiedlich stark weichgezeichnet wurde). Automatische Schätzungen lagen daneben: Ausrichtung überschätzt, Bandenergie und Spektrum unterschätzen (Logo-Einblendungen bleiben scharf).
* **Farbangleichung je Szene** an die Vorbild-Szene (Lab, Stärke L 0,45, a/b 0,6, Streuungsverhältnis begrenzt auf 0,75–1,35).
* **Härte-Maß:** mittlere größte Bildänderung am Schnitt (64×64-Bilder): Vorbild 54,7, v1 67,0, v2 53,0.
* **Schiebe-Übergang:** Die neue Hälfte stark abgedunkelt (×0,45) und gestreift, wie im Vorbild.

---

# Referenz 5: „Anzug“-Edit (Fashion-Event, schwarzer Anzug), umgesetzt in `projects/felix-anzug`

576×768 (3:4 Hochformat), 30 fps, 14 s, Song ca. 99 BPM (Achtel = 9 Bilder). Ausgabe bei uns 1080×1440.

* **Aufbau:**
  * Intro 0–103: EIN Clip, Zeitlupe, ruhige Kamera (Zoom ±0,5 %).
  * Hauptteil 104–251: 6 Szenen (Schnitte 104, 124, 140, 178, 196, 215).
  * **252–399 = exakt dieselben Bilder wie 104–251** (Pixel-Abweichung nur Kompression).
  * Ab 400 schwarz.
* **Seitlicher Wisch** (Intro raus, 101–106, und S6 → S1, 250–253), waagerechte Bewegungsunschärfe als Anteil der Breite, Bild läuft seitlich herum:
  * raus: 0,024 (Versatz +1,4 %) → 0,20 (+9,8 %) → 0,85 (+14 %)
  * rein: ≥1,4 (ganz verwischt) → 0,71 (Versatz −15 %) → 0,135 → 0,03
  * Das neue Bild wächst dabei von 0,76 auf 1,0 (Zoom hinein, abbremsend).
* **Weißblitz** (Bild 115): Schwarz-Weiß und stark aufgehellte Kurve `20 + 235·(1−e^(−4y))/(1−e^(−4))`. Dunkles bleibt mittelgrau, Helles wird weiß.
* **Unschärfe-Blitz** (123–127):
  * 123 altes Bild σ 60 (bei 576 px) ×1,13
  * dann das neue Bild σ 14 → 7 → 3 → 1, das von 1,25× herauszoomt
* **Geteiltes Bild** (140/141):
  * 140: oben (bis 49,5 %) das alte Bild weiter hineingezoomt mit Zoom-Unschärfe, unten das neue Bild in S/W, 1,7× mit Zoom-Unschärfe
  * 141: oben (bis 55 %) das neue Bild in S/W 1,35× hell, unten S/W senkrecht verwischt und dunkler
  * 142–145: Farbe mit abklingender Zoom-Unschärfe, Helligkeit 1,14 → 1,0
* **Farbe ↔ Schwarz-Weiß im Takt** innerhalb derselben Szene: S/W 153–163, Farbe 164, S/W 171–179; S6: S/W 226–236, Farbe 237, S/W 245–251.
  * An jedem Wechsel ein **Zoom-Stoß**: 2 Bilder davor zunehmend, 2–3 Bilder danach abklingend.
  * Zoom-Unschärfe um das Gesicht, log-Umfang etwa 0,2–0,3. Die angepassten Werte waren ~0,5, das war am Bild zu stark.
  * Danach zoomt es wieder heraus. Zurück in Farbe kommt ein Sprung hinein (S6: +42 % über 237–239).
  * S/W = Luma mit Kontrast ×1,05.
* **Negativ-Kästchen** (je 1 Bild): Rechteck mit umgekehrter Helligkeit (Graustufen-Negativ).
  * 165: x 0,170–0,339, y 0,293–0,670
  * 241: Augenbalken x 0,3125–0,672, y 0,255–0,339
* **Senkrechter Wisch** (176–183), senkrechte Unschärfe als Anteil der Höhe:
  * 176: 0,15
  * 177: 1,5 (ganz verwischt)
  * 178/179: neues Bild S/W 1,1/0,8, sehr hell (×1,45/×1,2)
  * 180: Farbe 0,35 ×1,13
  * 181: 0,22
  * 182: 0,10 + σ 2
* **Heller Wisch** (196/197):
  * 196: neues Bild schräg verwischt (Winkel 24°, Länge 1,6 × Breite) ×1,1 + 18 % weiß
  * 197: S/W, verwischt, 55 % weiß
  * 198: fast scharf
* **Weißer Schiebe-Balken** (214/215):
  * 214: linke Hälfte altes Bild, rechte Hälfte Balken
  * 215: linke Hälfte Balken, rechte Hälfte neues Bild σ 40
  * Balken = senkrechter Verlauf, oben 254, ab 37 % abfallend auf 156 unten
  * Danach langes Scharfwerden σ 24 → 19 → 15 → 12 → 8,5 → 8 → 5,5 → 3 → 1,5 (216–224)
* **Kamera:** Zoom je Bild aus `ref_camera.json`:
  * vor Schnitten und Farbwechseln beschleunigt hinein
  * danach abbremsend heraus
* **Mess-Werkzeug:** Bild-Anpassung (Skalierung, Versatz, Unschärfe-Art, Helligkeit) gegen ein scharfes Nachbarbild, `edit-toolkit/analyse/bild_anpassung.py`. Bei Zoom-Unschärfe überschätzt die Anpassung, deshalb am Bild nachregeln.
* **Felix-Umsetzung:**
  * Die Quellen sind enger gefilmt als das Vorbild (Gesicht 300–500 px bei 1180 px Höhe). Deshalb größter Ausschnitt (volle Höhe), Gesicht darf ±0,08 von der Vorbild-Höhe abweichen.
  * Zoom-Umfang höchstens 1,32, bezogen auf die scharfen Bilder.
  * Farben blass wie im Vorbild: Lab-Angleichung a/b 0,75, Streuung bis 0,5, Sättigung je Szene 0,72–0,85.

---

# Referenz 6: „Drachen“-Edit (Animationsfilm, 16:9), umgesetzt in `projects/felix-drachen`

1024×576, 30 fps, 33,6 s.

* **Länge:** Edit bis Bild 887 (29,6 s), danach TikTok-Abspann. Den lassen wir weg.
* **Ausgabe:** 1920×1080.
* **Ton:** Die Vorbild-Musik ist sehr leise (−25,5 LUFS) und läuft bis 29,5 s, danach kommt der laute TikTok-Ton. Wir nehmen die Musik bis 29,6 s, normalisieren auf −14 LUFS und blenden 0,6 s aus.
* **Aufbau:** 27 Szenen. Schnitte bei 0, 22, 45, 66, 118, 146, 172, 215, 247, 269, 322, 353, 375, 430, 481, 537, 565, 589, 649, 670, 692, 750, 775, 797, 821, 840, 868.
  * Szene 27 ist dieselbe Einstellung wie Szene 1 (Klammer). Bei uns ist das derselbe Felix-Clip (Konzert, blau).
* **Musik:** ruhig, kaum Schläge (`beats.py` findet nur schwache Einsätze). Die Schnitte folgen der Melodie, deshalb übernehmen wir die Schnittbilder 1:1.
* **Übergänge** (Bildnummern; Stärken per `calibrate.py` gemessen):
  * Zoom-Stoß + Aufhellen 18–21: Zoom 1,12 → 1,06, Helligkeit ×1,35 → ×1,15
  * waagerechter Wisch: 143–155, 169–171, 319–321, 586–594, 646–648, 667–669, 840–844
  * senkrechter Wisch: 115–117, 212–214, 322–324 (322 + Glitch-Streifen), 478–485, 818–820
  * Zoom-Unschärfe: 353–357, 427–434, 534–548, 562–564, 649–654
  * weiches Scharfwerden: 66–70, 118–122, 215–219, 244–251 (247 dunkler ×0,6), 325–326, 670–674, 689–696, 747–754, 772–779, 797–801, 821–826, 865–872 (867 mit 30 % Weißschleier)
  * **Ring-Bokeh**: 66–69, 269–273, 350–352, 431–433, 478–480, 649–651 (größere Ringe), 794–796, 837–839, 869–871.
    * Helle Detail-Spitzen werden zu einzelnen dünnen Ringen mit leichtem Rot/Blau-Saum. Radius ~12 px bei 1024, Linie ~2,5 px.
    * Die Ringe bilden Ketten entlang heller Kanten.
    * Umsetzung: Spitzen mit Mindestabstand 0,75·Radius, höchstens 30 + 110·Stärke Ringe.
    * Das Gesicht wird geschont, sonst wirken die Augen „doppelt“. Erster Versuch per Faltung mit Ring-Kern gab Doppel-Konturen statt Ringen.
  * **Strecken** 371–374: Das Bild wird ab x0 waagerecht 5–10× gestreckt, ab 373 um x0 gespiegelt, so entstehen V-Formen. Bei Felix x0 auf den Kopf legen, sonst wird nur grauer Hintergrund gestreckt.
  * **Wölbung** 375–379: Die Mitte wird nach unten gebogen (0,30 → 0,03 der Höhe) und senkrecht gestreckt (3 → 1).
  * **Sanduhr** 567–570: Breite je Zeile m(y) = m0 + m1·|2y−1|, von 0,20/1,2 bis 0,97/0,05. Außen schwarz, senkrecht verwischt.
* **Kamera:** Zoom und Drehung je Bild aus `ref_camera.json`.
  * gedämpft: Zoom ×0,55, Drehung ×0,3
  * je Szene Zoom höchstens 1,40, Drehung höchstens ±3°
  * Bewegungsunschärfe passend zur Geschwindigkeit
* **Unschärfe messen statt schätzen (`projects/felix-drachen/calibrate.py`):**
  * Für jedes Übergangsbild das Schärfe-Verhältnis wie im Vorbild einstellen: Detail-Energie relativ zu den ruhigen Bildern der Szene.
  * Gemessen ohne Ränder, TikTok-Zeichen und Schrift. Die scharfen Einblendungen täuschen sonst Schärfe vor: unmaskiert 0,60, maskiert 0,03.
  * **Lehre:** Unschärfe nach Augenmaß in kleinen Rastern war etwa 10× zu stark (v1: hb 0,10–0,45; gemessen meist 0,01–0,05).
  * Bei sehr weichen Vorbild-Bildern reicht eine Wisch-Unschärfe allein nicht, weil Kanten in Wischrichtung erhalten bleiben. Dann Wisch auf 0,12 begrenzen und den Rest per Gauß ausgleichen.
* **Farben:** sanfter CC-Filter plus Lab-Angleichung an die Vorbild-Szene, getrennt nach Mittelwert und Streuung:
  * Mittelwert (Helligkeit, Farbstich): L 0,90, a/b 0,95
  * Streuung (Kontrast, Sättigung): L 0,70, a/b 0,80, Verhältnis begrenzt auf 0,4–1,5
  * v1 hatte 0,65/0,82 für beides. Dadurch waren dunkle Szenen zu hell und helle zu dunkel, und der Kontrast war doppelt so hoch wie im Vorbild. Die Schnitte waren zu hart: größte Bildänderung 69,7 statt 55,1.
  * Das Vorbild ist weich, kontrastarm und blaustichig (L-Streuung 9–23).
* **Helligkeit Bild für Bild wie im Vorbild** (`match_lum`). Die Szenen-Angleichung allein reichte nicht: Im Vorbild wird z. B. Szene 7 zum Ende hin dunkler, die Kamera fliegt in Wolken, und der Schnitt in die dunkle Szene 8 ist dadurch weich.
  * Lab-Helligkeit je Vorbild-Bild messen (ohne TikTok-Zeichen), innerhalb der Szene leicht glätten (σ 1 Bild).
  * Eigenes Bild zu 80 % angleichen, höchstens ±30. Dunkler: Richtung Schwarz skalieren. Heller: Richtung Weiß, so bleiben Schwarz und Weiß sauber.
  * **Härte am Schnitt** (größte Bildänderung, 64×36): Vorbild 56,5; v2 ohne Bild-Angleichung 71,3.

---

# Referenz 7a: rotes Bühnen-Edit (Cowboyhut), mit Hyunjin umgesetzt in `projects/vorbild7` (EDIT=hyunjin)

576×576, 30 fps, Song ca. 136 BPM.

* **Länge:** Edit bis 567, danach schwarz bis 601 (die Musik läuft weiter), dann TikTok-Abspann (weggelassen).
* **Ausgabe:** 1080×1080.
* **Aufbau:**
  * Intro 0–143: EIN Clip. Einblendung aus Schwarz über ~30 Bilder, zwei Lichtblitze (49, 59).
  * Weißblitz 144.
  * Hauptteil 145–355 mit 13 Szenen. Schnitte: 145, 170, 184, 209, 221, 231, 237, 249, 275, 287, 315, 328, 336.
  * **356–567 = 144–355 noch einmal.**
* **Übergänge:**
  * Einzelbild-Weißblitze: 144, 230, 335 (hellgrau), 356
  * dunkle Unschärfe-Dips: 183–185, 209, 221, 249, 275, 328
  * waagerechter Wisch 169–171
  * Scharfwerden nach dem Blitz: 145–152
  * Lichtblitze in der Szene: 187, 192–193
  * Schwarz-Weiß-Szene 231–236
  * **rote Wellen-Verzerrung** 237–238: jede Zeile im Zickzack verschoben, Dreieckswelle, Amplitude 0,07–0,10 der Breite, Periode 0,07 der Höhe
* **Kamera:** durchgehender Zoom hinein (~1,1–1,4 % pro Bild), vor dem Schnitt schneller (bis +3,7 %).
* **Tempo:** normal, keine Zeitlupe. Bewegung im Vorbild 6–10, Intro mit Lichtgeflacker.
* **Gesichter:** halbnah, Gesicht bei y ≈ 0,30, Größe ≈ 0,15–0,24.
* **Hyunjin-Szenen** (v3):
  * Intro: Konzert-Fancam, ein Clip
  * 1: Bühne
  * 2: grüne Weste
  * 3: Brille
  * 4: Konzert mit Mikro
  * 5: Bühne ruhig
  * 6: Fotoshooting in S/W
  * 7: Konzert
  * 8: Kapuze mit Händen
  * 9: Vlog
  * 10: Bühne mit Handschuh
  * 11: Herz-Hände
  * 12: graue Kapuzenjacke
  * 13: Spiegel-Selfie
  * **Selfie-Nahaufnahmen** (z. B. Kappe H4a) passen nicht in halbnahe Szenen: Der Ausschnitt kann nicht weiter werden als die Quelle, dann sind die Augen abgeschnitten. Lieber Bühnen- oder Halbtotal-Aufnahmen nehmen.
  * Messwerte: Unschärfe-Verlauf 0,97, Helligkeit 0,98, Härte am Schnitt 80 (Vorbild 75).

## Vorbild 7 – Übergänge v2 (Feedback „noch nicht so flüssig wie im Beispiel“)

**Ursachen**, durch den direkten Vergleich jedes Schnitts gefunden (Vorbild oben, Edit unten, Bilder c−3 … c+4):

1. **Starke Unschärfe war zu schwach.** Die alte Messung (nur feinste Detail-Stufe) hielt das Kompressionsrauschen des Vorbilds für Schärfe.
2. **Kasten-Wischunschärfe** (hb/vb) erzeugt sichtbare Doppelbilder. Im Vorbild sind die Wische weich.
3. **Einzelbild-Abdunklungen und -Aufhellungen wurden weggeglättet**, weil die Helligkeitskurve geglättet wurde.
4. **Spezial-Übergänge fehlten:**
   * geteilte Einblendung (7b, 151–159)
   * Geisterbild-Echo (7a, 145–148 u. a.)
   * Lichtstreifen (7a, 183)
   * flüssige Wellen (7a, 250–252)
5. **Farbsprünge:** Das Vorbild ist durchgehend rot, unsere Bühnen-Clips waren lila.

**Lösung (`projects/vorbild7/trans.py` + `trans_frame` im Renderer):**

* **Jedes Übergangsbild einzeln vermessen** (Schnitt −3 … +5 und alle Effekt-Bilder):
  * Detail-Energie in 4 Frequenzbändern (DoG 0,7–11,2 px bei 288 px), getrennt waagerecht/senkrecht, relativ zur ruhigen Szene.
  * Das eigene Bild vorher auf den Ziel-Kontrast bringen.
  * Verhältnisse unter 3 % zählen nicht (Rauschboden), grobe Bänder zählen mehr.
  * Ergebnis: weiche Gauß-Unschärfe **σx/σy** (Gittersuche).
* **Helligkeit, Kontrast und Farbigkeit je Bild exakt** wie das Vorbild-Bild (Lab: Mittel L, Streuung L, mittlere Chroma, relativ zur Szene). Die Glättung der Helligkeitskurve überspringt Übergangsbilder.
* Bei sehr dunklen Ausblend-Bildern misst das Verfahren unsicher (Rest > 2) → Werte von Hand am Bild setzen (`TRANS_OVERRIDE`).
* **Geteilte Einblendung:** Das Bild wird in der Mitte auseinandergeschoben, der Spalt grau gefüllt. Höhe 0,345 → 0,194 → 0,139 → 0,102 → 0,073 → 0,054 → 0,036 → 0,012 → 0,005, Grau 152 → 30 (gemessen über flache Zeilen).
* **Echo:** um das Gesicht vergrößerte Kopie (1,1–1,28×), 10–45 % deckend.
* **Lichtstreifen:** dünne helle Linie mit zwei Lichtpunkten auf Augenhöhe.
* **Wellen:** senkrechte Verschiebung je Spalte, Sinus mit Oberwelle, Amplitude 1,5–3,5 % der Höhe.
* **Zickzack:** Ausschlag nur ~5 % der Breite. Mit 10 % war die Figur nicht mehr zu erkennen.
* **Hyunjin-Look:** Farbtöne zu 50 % Richtung Rot gezogen (nur farbige Pixel), wie das durchgehend rote Vorbild.

**Messwerte Felix:**

| | Vorbild | vorher | jetzt |
|---|---|---|---|
| Härte am Schnitt | 43,4 | 51,3 | 42,6 |
| Abweichung des Bildänderungs-Verlaufs | – | 10,9 | 8,2 |
| Schärfe-Verlauf (Korrelation mit Vorbild) | – | 0,84 | 0,93 |

**Messwerte Hyunjin (v5):**
* Abweichung des Bildänderungs-Verlaufs an den Schnitten: 6,8 → 4,5.
* Herz-Hände-Szene ruhiger (Bildänderung 27 → 11–16 je Bild).
* Verbleibende „ungleichmäßige Stellen“ liegen in Übergangs-Abdunklungen oder in ruhigen Vlog-Momenten (24-fps-Quelle), nicht in echten Rucklern.

# Referenz 7b: Michael-Jackson-Intro, mit Felix umgesetzt in `projects/vorbild7` (EDIT=felix)

576×576, 30 fps.

* **Länge:** Edit bis 479, Weiß → Schwarz bis 509, dann TikTok-Abspann.
* **Intro 0–150 (Michael Jackson, Schwarz-Weiß):** Wunsch des Nutzers: unverändert lassen. Es wird aus dem Vorbild übernommen.
  * TikTok-Logo und Name oben links (0–125 × 0–102 px) weggerechnet (`cv2.inpaint`).
  * Ebenso die rot/türkis blinkenden Punkte in der Bildmitte (Erkennung: Farbe im S/W-Bild).
  * Danach auf 1080 hochskaliert (Lanczos + leicht nachgeschärft).
* **Farbteil:** 6 Szenen, Schnitte bei 151, 173, 191, 234, 252, 271. **316–479 = 151–314 noch einmal.**
* **Übergänge:**
  * dunkle Wisch-Übergänge (waagerecht): 171–176, 191–195, 232–238, 250–253, 270–274
  * Einstieg aus dem Intro 151–157: grau, entsättigt, verwischt, dann scharf werdend
* **Zoom-Pulse auf den Schlägen** (204, 216, 225, 282, 293, 304):
  * Die Kamera zoomt im Wechsel heraus und hinein, mit bis zu 10 % pro Bild am Schlag.
  * Dazu ein Lichtblitz (+25 Helligkeit) und kurze Wisch-Unschärfe.
  * Ohne Zeitsprung im Clip.
  * Umsetzung: Kamerakurve des Vorbilds mit Dämpfung 0,9.
* **Ende:** 480 weiß, blendet bis 507 ins Schwarze (Grauwerte wie im Vorbild).
* **Tempo:** normal (Bewegung im Vorbild 6,7–8,6).
* **Felix-Szenen:**
  * C1: lacht, rote Haare
  * C2: Anzug, Hand am Mund (wie MJ mit Handschuh)
  * C3: Ziegelwand, lacht
  * C4: Bühne, Drehung
  * C5: Fotoshooting
  * C6: Bühne, Arm hoch
  * Messwerte: Unschärfe 0,91, Helligkeit 0,94, Härte 53 (Vorbild 46), Ruckeln 9 (Vorbild 10). Das Intro weicht im Mittel 2,4 Graustufen ab (nur die entfernten Zeichen).

---

# Referenz 8: „Spam my phone if … is your bias“ (Trend-Video), mit Hyunjin in `projects/vorbild7` (EDIT=spam)

576×576, 30 fps.

* **Länge:** Edit bis Bild 537 (17,93 s), danach TikTok-Abspann. Die Musik klingt bei 17,76 s aus, der Abspann-Ton beginnt bei 17,94 s.
* **Aufbau:** 11 Szenen, **harte Schnitte** bei 55, 82, 104, 155, 219, 271, 320, 366, 429, 457.
* **Keine eigenen Effekte:** keine Zooms, keine Unschärfe, normales Tempo. Die Zoom-Werte in einzelnen Szenen (Selfies) kommen aus den Original-Clips.
* **Text** „Spam my phone if Bangchan is your bias“ (weiß, schwarze Kontur, Mitte unten) auf Wunsch weggelassen. Falls später gewünscht: „Spam my phone if Hyunjin is your bias“ im TikTok-Stil (Regel 1).
* **Umsetzung:**
  * Gesichtsgrößen je Szene wie im Vorbild, Nahaufnahmen etwas weiter (Qualität).
  * Natürliche Farben (`PLAIN`): nur sanfter CC-Filter, keine Angleichung an die Farben einer anderen Person.
* **Szenen:**
  * 1: grüne Weste
  * 2: Spiegel-Selfie
  * 3: grüne Weste mit Kamera
  * 4: Selfie mit Kappe
  * 5: Vlog
  * 6: Bühne mit Handschuh
  * 7: Herz-Hände
  * 8: Fotoshooting
  * 9: Bühne ruhig
  * 10: Brille
  * 11: Kapuze mit Händen
* **Achtung, Szenen-Grenzen der Quellen:**
  * Wenn eine Szene über eine Schnittstelle im Original-Clip hinausläuft, entsteht ein Doppelbild (Zwischenbild-Berechnung über den Schnitt).
  * Auch Überblendungen im Original selbst gibt es: H3b ab 8,37 s.
  * Deshalb Start + Länge × Tempo immer innerhalb der Szene halten, notfalls Tempo 0,92–0,98.

## Referenz 7b mit Felix im Intro (Wunsch: „Anfang gleich lassen, aber mit Felix“)

* **Intro 0–150 nachgebaut:** EIN Felix-Clip (Anzug mit Brille, `suit` ab 0,95 s) in Schwarz-Weiß.
* **Läuft und friert ein wie im Vorbild:**
  * Bewegung in 1–19, 39–54, 73–90, 109–118, 130–140
  * am Ende langsam anlaufend 145–150
  * dazwischen Standbild
* **Lade-Punkte** (rot 254,44,85 / türkis 37,244,238, Radius 0,014 × Breite, Mitte, tauschen alle 18 Bilder die Seite) während der Standbilder.
* **Schwarzer Balken oben:** 144–150 wächst von 0,2 % auf 12,5 % der Höhe.
* **S/W-Tonkurve:** Gesicht → L 48, Lichter → 64–68 (grau wie die Wand im Vorbild), Schatten fast schwarz.
  * Lehre: Histogramm-Angleichung an das Vorbild machte große helle Flächen flach grau (Straße hinter Felix).
* **Szene C2** jetzt Bärenmütze, weil der Anzug schon im Intro ist.

# Referenz 9: „Beggin'“-Lyric-Edit (ausgestanzter Text, Flackern), mit allen 8 Mitgliedern in `projects/beggin`

1024×576, 30 fps. Wunsch des Nutzers: **Text und Effekte bleiben, nur der Hintergrund wird getauscht** (Mitglieder in kurzen Abständen).

* **Länge:** Inhalt bis Bild 665 (22,2 s). Der Song endet bei 22,20 s, ab 22,22 s kommt der TikTok-Abspann-Ton.
* **Effekt „Verwaschen“:**
  * Das ganze Bild wechselt im Takt zwischen „normal“ und „verwaschen“.
  * Verwaschen heißt W(x) = A·x + B mit A ≈ (0,50; 0,53; 0,51) und B ≈ (118; 114; 116) je Kanal RGB, also 50 % fast-Weiß.
  * Die Wörter zeigen immer den **umgekehrten** Zustand („ausgestanzt“).
* **62 Wechsel** (10, 13, 19, … 650), im Achtel- oder Viertel-Takt (Song ≈ 129 BPM).
  * Lange Strecken: 217–253 normal (Titel „beggin'“) und 436–481 verwaschen („BABY“).
* **Text-Animation:**
  * Wörter blinken 1–2 Bilder.
  * Wörter werden getippt (BA → BABY, DAR → DARLING).
  * „hand“ und „girl“ stehen senkrecht.
  * Die Textebene gleitet langsam: ~0,1–0,2 px pro Bild bei 1024 Breite, oben und unten verschieden, dazu ein leichter Zoom.
* **Abblende:** 653–663 Helligkeit 0,93 → 0,26, danach fast schwarz.
* **Text-Masken** (`text_mask.py`, komplett: `make_masks.sh`, ~8 min):
  * Je Bildpaar gibt es drei Beziehungen: gleich, wird normal, wird verwaschen.
  * Der Zustand jedes Punktes wird vorwärts und rückwärts verfolgt. Text = Zustand ≠ Zustand des ganzen Bildes.
  * **Vorher die Bilder in „ruhende Text-Koordinaten“ umrechnen** (Bewegung aus `text_drift.py`, gespeichert in `text_drift.npz`).
    * Sonst friert die Maske zwischen zwei Wechseln ein und springt dann.
    * Buchstaben werden dabei auf einer Seite bis 7 px dünner, und das „i“ in „beggin'“ fehlte ganz.
  * Danach in dieser Reihenfolge:
    * aufräumen: Rand, TikTok-Logos, dieselbe Form muss in ±3 Bildern wiederkehren, kleine Teile nur in Wortgruppen
    * vervollständigen: Mehrheit aus ±12 Bildern
    * glätten: Schließen 3, Median 5
    * zurück in Bildkoordinaten (weiche Kanten)
  * Median 3 (statt 5) und Glättung der Beziehungen σ 0,5, sonst verschwinden dünne Striche kleiner Wörter.
  * Grenze: Kleine Wörter („of girl fact“, kleines „beggin'“) bleiben etwas rau. Dort ist der Hintergrund des Vorbilds fast weiß oder sehr unruhig.
* **Hintergrund** (`render.py`):
  * 26 Szenen der 8 Mitglieder.
  * Schnitt nur auf einem Flacker-Wechsel, alle 0,4–1,5 s. Das Bild springt dort ohnehin.
  * Zeitlupe 0,5× (`slowmo.resample`).
  * **Gesicht mittig:**
    * Der Ausschnitt ist so schmal, dass das Gesicht in jedem Bild der Szene mittig stehen kann.
    * Höchstens 2,1× vergrößern. Die Hochformat-Quellen von Bang Chan sind nur 1180 px breit.
  * Leichter Zoom 1,00 → 1,04 je Szene.
  * Farbe: CC-Filter, dann teilweise Lab-Angleichung an die Nahaufnahme des Vorbilds. Verwaschene Bilder werden dafür zurückgerechnet. Stärke: L 45 %, a/b 35 %.
  * Danach Verwaschen und Ausstanzen mit den Vorbild-Masken, Abblende, Ton bis 22,19 s.
* **Achtung, Schnitte und Blitze in den Quellen:** Die Vlogs haben Jump-Cuts, die Fotoshootings Kamerablitze. Das gab Doppelbilder und Flackern:
  * Changbin 3a: Schnitt bei 0,55 s
  * Han 7b: Schnitt bei 10,53 s
  * Changbin 3c: Blitze bei 6,35 / 6,75 / 7,29 s
  * Hyunjin Wappen: schnelle Bewegung ab 11,02 s
  * `render.py` warnt jetzt automatisch („ACHTUNG … Schnitt/Blitz in der Quelle“), wenn die Bildänderung in einer Szene über 15 liegt. Normale Bewegung liegt bei 1–9.
* **Ausschnitte (sicherer Bereich, volle Koordinaten 2556×1180):**
  * Han (RACHA-Logo oben rechts, Untertitel): x < 2010, y < 980
  * Felix Fell-Jacke (Untertitel, 2 Zeilen): y < 925
  * Seungmin weißes Studio (Text oben links): y ≥ 130
  * Lee Know und I.N (TALKER-Logo): x < 2060
  * Hyunjin Wappen-Fotoshooting (heller Rahmen, „Paper Tale“-Zeichen oben links bis x 460): x ≥ 470, y ≥ 90
