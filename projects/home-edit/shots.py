"""Szenenliste fuer das home.-Edit: ein Eintrag pro Schnitt (CUTS in render.py).

clip  = Datei in MEDIA_DIR
t     = Startzeit in der Quelle (Sekunden)
vf    = ffmpeg-Filter fuer Drehung/Ausschnitt (Ergebnis 4:3, beim letzten Eintrag quadratisch)
size  = Ausgabegroesse dieser Szene (Standard 1440x1080; Foto-Ende quadratisch)
look  = optionale Feinanpassung von home_look (sat, warm, haze, soften)

TESTSTAND: Felix-Clips, nur um die Technik zu pruefen. Wird durch die Stray-Kids-Szenen ersetzt.
"""
import os

MEDIA_DIR = os.environ.get("EDIT_MEDIA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "media"))

B = "crop=2096:1180:230:0"          # Videobereich der iPhone-Bildschirmaufnahmen (Querformat-Quellen)
SHOTS = [
    dict(clip="clip12.mov", t=2.0,  vf=B + ",crop=1440:1080:330:50"),
    dict(clip="clip6.mov",  t=5.5,  vf=B + ",crop=1200:900:500:150"),
    dict(clip="clip9.mov",  t=6.0,  vf=B + ",crop=1300:975:150:100"),
    dict(clip="clip9.mov",  t=1.0,  vf=B + ",crop=1200:900:300:100"),
    dict(clip="clip12.mov", t=0.1,  vf=B + ",crop=1573:1180:250:0"),
    dict(clip="clip10.mov", t=2.0,  vf=B + ",crop=1440:1080:300:50"),
    dict(clip="clip12.mov", t=8.4,  vf=B + ",crop=1300:975:250:100"),
    dict(clip="clip7.mov",  t=0.2,  vf=B + ",transpose=1,crop=1000:750:90:200"),
    dict(clip="clip7.mov",  t=7.7,  vf=B + ",crop=1400:1050:350:60"),
    dict(clip="clip8.mov",  t=0.2,  vf=B + ",crop=1300:975:450:0"),
    dict(clip="clip13.mov", t=0.2,  vf=B + ",crop=1400:1050:150:60"),
    dict(clip="clip13.mov", t=13.7, vf=B + ",crop=1240:930:300:120"),
    dict(clip="clip13.mov", t=10.2, vf=B + ",crop=1240:930:350:120"),
    dict(clip="clip2.mov",  t=0.2,  vf=B + ",crop=960:960:450:60", size=(1080, 1080)),
]
