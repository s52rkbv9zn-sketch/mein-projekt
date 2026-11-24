#!/usr/bin/env python3
"""Sucht die Medien dieses Projekts unter den hochgeladenen Dateien und verlinkt sie nach media/.

Die Bildschirmaufnahmen haben oft identische Dateinamen, deshalb wird ueber die Pruefsumme
(md5) zugeordnet, ersatzweise ueber die Laenge in Sekunden.

Aufruf:  python3 link_media.py [ordner ...]      (Standard: /root/.claude/uploads)
"""
import hashlib, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.join(HERE, "media")

# name -> (md5, Laenge in s)
EXPECTED = {
    "clip1.mov":  ("409c7e32667c54d8ef84b99a7d169c66", 1.763),
    "clip2.mov":  ("bead245b3152bd63a350e8cc240bed33", 2.330),
    "clip3.mov":  ("d6f5951cb14f6c7e94d0a5ed6663f150", 4.160),
    "clip4.mov":  ("c38fa6f6e5a5eb90e98afb0801be04b7", 9.712),
    "clip5.mov":  ("d86cd294621b25bcca0797c21612603e", 4.210),
    "clip6.mov":  ("3bb8dcf5f1432e26d871d56a2083668b", 11.710),
    "clip7.mov":  ("4a04ae447862bd254491cba27861c22f", 11.228),
    "clip8.mov":  ("8ad2607534c66122ef45e9ce3c857591", 8.893),
    "clip9.mov":  ("b0cf308d7c0618423502a83f6125f421", 12.102),
    "clip10.mov": ("1d722a52720aeaa5d46d08df993edfc4", 16.768),
    "clip11.mov": ("d6d8a9fd26809727ed13e1964133ed7f", 3.213),
    "clip12.mov": ("e00a6ae787771b33884f4eaecaf8de94", 15.065),
    "clip13.mov": ("85ab0d6276e64e62bed85288b5d7e24e", 14.820),
    "reference.mp4": ("695e27de52f9c37c77a90530af93a156", 21.330),
    "reference_konzert.mov": ("2c813e447b6ef0dce0e0e3c5b0511473", 17.430),   # Referenz 4 (Konzert-Edit)
    "reference_anzug.mov": ("84c32ee4b2afddace7730b76ec0f8a1b", 13.966),   # Referenz 5 (Anzug-Edit)
    "reference_drachen.mp4": ("ce202601a7154b74cbb949d1cac33688", 33.624),   # Referenz 6 (Drachen-Edit, 16:9)
    "reference_rot.mp4": ("a052f5a19e497b883cb6532127b720e6", 24.067),   # Referenz 7a (rotes Buehnen-Edit, Hyunjin)
    "reference_mj.mp4": ("88f4f2b7e3559fe158a3b097a057e7b8", 21.020),   # Referenz 7b (Michael-Jackson-Intro, Felix)
    "reference_spam.mp4": ("15a9ce3073b7f342a69cfbb75b482ddf", 21.967),   # Referenz 8 ("Spam my phone", Hyunjin)
    "reference_beggin.mp4": ("a88d074f648b84fb41262a5c9f3c04d4", 26.237),   # Referenz 9 (Beggin-Lyric-Edit, SKZ)
}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def main():
    roots = sys.argv[1:] or ["/root/.claude/uploads"]
    files = []
    for root in roots:
        for dp, _, fn in os.walk(root):
            files += [os.path.join(dp, f) for f in fn if f.lower().endswith((".mov", ".mp4", ".m4v"))]
    by_md5 = {}
    for p in files:
        by_md5.setdefault(md5(p), p)
    os.makedirs(MEDIA, exist_ok=True)
    missing = []
    for name, (h, dur) in EXPECTED.items():
        src = by_md5.get(h)
        how = "md5"
        if src is None:
            cands = [p for p in files if (d := duration(p)) is not None and abs(d - dur) < 0.03]
            src = cands[0] if len(cands) == 1 else None
            how = "Laenge"
        if src is None:
            missing.append(name)
            continue
        dst = os.path.join(MEDIA, name)
        if os.path.lexists(dst):
            os.remove(dst)
        os.symlink(os.path.abspath(src), dst)
        print(f"{name:14s} <- {os.path.basename(src)}  ({how})")
    if missing:
        print("FEHLT (bitte hochladen):", ", ".join(missing))
        sys.exit(1)


if __name__ == "__main__":
    main()
