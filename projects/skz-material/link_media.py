#!/usr/bin/env python3
"""Ordnet hochgeladene Stray-Kids-Aufnahmen (gleiche Dateinamen moeglich) ueber md5 zu und
verlinkt sie nach media/ unter den Namen aus manifest.json.

Aufruf:  python3 link_media.py [ordner ...]      (Standard: /root/.claude/uploads)
"""
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.join(HERE, "media")
MAN = json.load(open(os.path.join(HERE, "manifest.json")))["files"]


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    roots = sys.argv[1:] or ["/root/.claude/uploads"]
    by_md5 = {}
    for root in roots:
        for dp, _, fn in os.walk(root):
            for f in fn:
                if f.lower().endswith((".mov", ".mp4", ".m4v")):
                    p = os.path.join(dp, f)
                    by_md5.setdefault(md5(p), p)
    os.makedirs(MEDIA, exist_ok=True)
    missing = []
    for name, info in MAN.items():
        src = by_md5.get(info["md5"])
        if src is None:
            missing.append(f"{name} ({info['member']})")
            continue
        dst = os.path.join(MEDIA, name)
        if os.path.lexists(dst):
            os.remove(dst)
        os.symlink(os.path.abspath(src), dst)
        print(f"{name:20s} {info['member']:10s} <- {os.path.basename(src)}")
    if missing:
        print("FEHLT (bitte hochladen):", ", ".join(missing))
        sys.exit(1)


if __name__ == "__main__":
    main()
