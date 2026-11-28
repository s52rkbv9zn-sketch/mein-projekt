"""Alle Woerter des Vorbilds (Referenz 9, "Beggin'"), vom Bild abgelesen.

(Text, Drehung, erstes Bild, letztes Bild[, Hinweise]). Hinweise (dict, nur wo noetig): "box" = Suchbereich
(x0, y0, x1, y1) in ruhenden Text-Koordinaten bei 1024x576, "size" = (min, max) Schriftgroesse in px pro em. Drehung 0 = waagerecht, -90 = im Uhrzeigersinn gedreht (von oben
nach unten zu lesen), None = beide Richtungen probieren. Die Bildbereiche sind grob (mit Rand); wann genau
welcher Buchstabe sichtbar ist (Eintippen, Blinken), misst fit_words.py aus den Masken.
Gleiches Wort an anderer Stelle oder spaeter neu = eigener Eintrag.
"""
WORDS = [
    ("i'm",      0,   0,  38),
    ("on",       0,   8,  38),
    ("knees",    0,  16,  38),
    ("my",       0,  16,  38),
    ("when",     0,  28,  38),
    ("BEGGIN",   0,  38,  60),
    ("cause",    0,  60,  90),
    ("i",        0,  68,  90),
    ("don't",    0,  68,  90),
    ("wanna",    0,  75,  90),
    ("lose",     0,  83,  90),
    ("YOU",      0,  90, 106),
    ("i",        0, 115, 143, {"box": (355, 165, 410, 250)}),      # kleines i zwischen "my" und "got"
    ("got",      0, 115, 143),
    ("my",       0, 119, 143),
    ("arms",     0, 119, 143),
    ("all",      0, 127, 143),
    ("spread",   0, 134, 143),
    ("I",        0, 143, 181),
    ("HOPE",     0, 150, 181),
    ("MY",       0, 157, 181),
    ("HEART",    0, 167, 181),
    ("FED",      0, 172, 181),
    ("matter",   0, 183, 256),
    ("fact",     0, 188, 256),
    ("of",       0, 194, 256),
    ("girl",  None, 194, 256),
    ("i'm",      0, 202, 256),
    ("beggin'",  0, 206, 256),
    ("BEGGIN",   0, 256, 293),
    ("BEGGIN",   0, 294, 316),
    ("YOU",      0, 315, 368),
    ("put",      0, 368, 421),
    ("your",     0, 374, 421),
    ("loving",   0, 382, 421),
    ("hand",   -90, 397, 421),
    ("out",      0, 404, 421),
    ("BABY",     0, 420, 481),
    ("beggin',", 0, 480, 594, {"size": (120, 260)}),
    ("you",      0, 532, 594),
    ("beggin'",  0, 538, 594, {"size": (30, 90)}),               # kleines "beggin'" oben
    ("PUT",      0, 593, 654),
    ("YOUR",     0, 599, 654),
    ("LOVING",   0, 607, 654),
    ("HAND",     0, 622, 654),
    ("OUT",      0, 637, 654),
    ("DARLING",  0, 652, 665),
]
