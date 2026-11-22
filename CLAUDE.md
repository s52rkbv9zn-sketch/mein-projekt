# Projekt: K-Pop-Fan-Edits (Video-Star-Stil)

Der Nutzer macht Fan-Edits (z. B. Felix / Stray Kids) und schickt Bildschirmaufnahmen der Clips,
Beispiel-Edits als Vorlage („Referenz“) und Wünsche. Claude baut die Edits hier in der Cloud mit
ffmpeg + Python (numpy, scipy, opencv-python-headless) und schickt die MP4 im Chat.
**Immer auf Deutsch antworten, einfach und ohne Fachchinesisch erklären.**

Wichtige Dateien:
* `docs/effekte-katalog.md`: alle Übergänge und Effekte der Referenz mit genauen Werten. **Vor jedem Edit lesen.**
* `edit-toolkit/`: CC-Filter (`look.py`), Teal-Look, Analyse-Werkzeuge (`analyse/`)
* `projects/felix-sorinyx/`: fertiges Projekt (Renderer v15, Szenenliste, gemessene Kamerakurve)
* `projects/felix-anzug/`: Felix-Edit nach Referenz 5 (Hochformat 3:4, Farbe/Schwarz-Weiß im Takt, Wische, Negativ-Kästchen; Hauptteil wiederholt sich)
* `projects/hyunjin-konzert/`: Hyunjin-Edit nach Referenz 4 (Konzert), abgeleitet aus `felix-konzert` (Szenen aus `skz-material`, Kennungen H2a–H6b)

## Regeln des Nutzers (gelernt, bitte einhalten)

1. **Keine eigene Schrift / kein Text im Video.** Aus den Quellen alles wegschneiden, was nicht zur Person gehört: Untertitel, Übersetzungen, YouTube-Leisten, Sender-Logos, Wasserzeichen. Schrift auf der Person selbst (Kleidung) ist erlaubt. **Ausnahme:** Der Nutzer nennt den Text ausdrücklich (z. B. TikTok-Trend „STAYs, you have one job… / Like for Felix / Comment your bias“). Dann TikTok-Stil: TikTok Sans SemiBold (`edit-toolkit/TikTokSans-600.ttf`), weiß mit schwarzer Kontur. **Solche Trend-Videos schlicht halten** (Wunsch des Nutzers): keine Effekte (kein Zoom, keine Blitze, kein Pop-in, keine Zeitlupe), keine schnelle Folge aller Mitglieder, harte Schnitte auf dem Takt, Text steht ruhig, etwa 12 s. Vorlage: `projects/onejob/render_plain.py`.
2. **Intro = ein einziger Clip.** Die Effekte gehören in den Clip: Stotter-Sprünge im selben Clip, S/W-Flackern, Zoom-Stöße, Farbe weich ausblenden. Mehrere verschiedene Clips im Intro sind nicht gewollt.
3. **Übergänge 1:1 wie in der Referenz.** Nicht schätzen, sondern Bild für Bild messen und vergleichen (siehe Ablauf). Gewünscht: „flüssig, clean, smooth“.
4. **Schnitte exakt auf den Beat.** Schläge aus der Tonspur messen (`beats.py`). Schnittbild = floor(t × 30). In reinen Trommel-Passagen: jeder Schlag ein Schnitt, alle mit **demselben** sauberen Übergang hintereinander.
5. **Flüssigkeit kommt von der Kamerabewegung.** Jeder Clip zoomt durchgehend (2–5 % pro Bild), vor dem Schnitt schneller werdend. Keine Richtungs-Ruckler, keine gespiegelten Bildränder, kein hartes Stehenbleiben.
6. **Qualität ist wichtig.** CC-Filter verwenden, Zoom maximal ~1,4×, doppelte Bilder der Bildschirmaufnahmen entfernen, Export in hoher Qualität (siehe Katalog, Abschnitt 7).
7. **Keine Clips selbst von YouTube oder TikTok laden.** Der Nutzer liefert sie. Erlaubnis des Nutzers ändert daran nichts.
8. **Zeitlupe wie im Vorbild.** Bewegt sich die Person im Vorbild langsam, Felix ebenfalls verlangsamen: bevorzugt 60-fps-Quellen in halber Geschwindigkeit (echte Einzelbilder, keine erfundenen Zwischenbilder). Bewegung messen (`vergleich.py`, Median-Bildänderung) und mit dem Vorbild vergleichen.
9. **Die Person immer mittig.** Ausschnitt per Gesichtserkennung (`edit-toolkit/face_track.py`) führen: Gesicht waagerecht in der Mitte, Höhe und Größe wie im Vorbild. Ausschnitt nur im „sicheren Bereich“ ohne Einblendungen. Kleine Einblendungen am Rand notfalls wegrechnen (`cv2.inpaint`).
10. **Weiche Übergänge.** Unschärfe am Schnitt eher stärker als gedacht (am Bild abgleichen, nicht nur schätzen). Farben jeder Szene an die passende Vorbild-Szene angleichen (Lab-Mittelwert/Streuung), damit die Farbsprünge am Schnitt klein bleiben. Maß: größte Bildänderung am Schnitt ≈ Vorbild.
11. Wenn der Nutzer auf eine Stelle zeigt (Screenshot oder Sekunde), genau diese Stelle ändern und den Rest so lassen. Bei Unklarheit (welche Szene?) Szenen in der Antwort benennen.

## Ablauf, der sich bewährt hat

1. **Medien:** Uploads liegen unter `/root/.claude/uploads/<session>/`. Für das Felix-Projekt ordnet `projects/felix-sorinyx/link_media.py` sie automatisch zu (über md5), für die anderen Mitglieder `projects/skz-material/link_media.py` (Liste mit Szenen: `projects/skz-material/manifest.json`).
   * **Wer ist drauf?** Personen nie am Gesicht bestimmen. Bei neuen Clips ein Übersichtsbild mit nummerierten Szenen (1a, 1b …) schicken und den Nutzer sagen lassen, wer drauf ist. Das dann in `manifest.json` eintragen.
   * Upload-Grenze des Nutzers: 30 MB, also etwa 12 s Bildschirmaufnahme pro Datei.
2. **Referenz zerlegen:**
   * Alle Bilder mit Zeitstempel ausgeben: `ffmpeg -i ref.mp4 -vf drawtext=...%{pts} -fps_mode passthrough f_%04d.png`
   * Raster zu je 10 Bildern pro Zeile ansehen, Schnitte und Effekte notieren.
   * Bildnummer im Edit = round(pts × 30); TikTok-Exporte beginnen oft bei 0,161 s.
3. **Messen:**
   * `analyse/kamera_profil.py`: Zoom, Drehung und Verschiebung pro Bild
   * `analyse/beats.py`: Schläge
   * bei Bedarf Helligkeit und Schärfe pro Bild
   * Feine Effekte (Shake, Wellen, Ränder) nur in Vergrößerungen von Bildausschnitten erkennbar, z. B. 6× horizontal am Bildrand.
4. **Bauen:** Renderer kopieren und anpassen (Pipeline siehe `projects/felix-sorinyx/render.py`):
   * pro Bild: Quelle holen, Kamera (Zoom/Drehung) mit Bewegungsunschärfe
   * dann Übergangseffekte
   * dann CC-Filter, dann Vignette
   * Ausgabe per Pipe an ffmpeg
5. **Prüfen vor dem Abschicken:**
   * `analyse/vergleich.py ref edit out/ <Schnittbilder>`: Streifen oben Referenz / unten Edit, plus Ruckel-Messung
   * Streifen ansehen und Schnitte gegen die Schläge prüfen
   * erst dann schicken
6. **Zwischenmeldungen:** Lange Renderläufe (3–5 min) im Hintergrund laufen lassen und dem Nutzer kurz sagen, was gerade passiert.

## Technische Fallstricke

* **Zeitachse:** ffmpeg füllt beim Dekodieren nach rawvideo ab t=0 auf. Deshalb mit `fps=30:start_time=0` dekodieren, dann ist Index = Bildnummer. Mit der Datei-Bildnummer (+5) gerechnet, liegt alles 5 Bilder daneben.
* **Bildschirmaufnahmen:**
  * iPhone-Aufnahmen sind 1180×2556, um 90° gedreht und 60 fps mit doppelten Bildern.
  * Videobereich bei Querformat-Quellen: `crop=2096:1180:230:0`.
  * Viele Aufnahmen haben denselben Dateinamen, deshalb über md5 oder Länge zuordnen.
* **ECC-Messung:** In verschwommenen Übergangsbildern ist sie unzuverlässig (cc < 0,8). Die Bewegung der Person verfälscht Drehung und Zoom; mit Hintergrund-Maske gegenprüfen.
* **Ränder:** `warpAffine` mit `BORDER_REFLECT_101` zeigt gespiegelte Ränder, sobald der Zoom unter die nötige Abdeckung fällt. Die Abdeckung bei Drehung θ beträgt cos θ + sin θ.
* **Ruckel-Check:** Ein Edit ist gut, wenn die Zahl der „ungleichmäßigen Stellen“ ≈ Referenz ist (Referenz-Edit: 5).
