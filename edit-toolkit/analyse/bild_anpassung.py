#!/usr/bin/env python3
"""Bild-Anpassung: misst, wie ein Uebergangsbild aus einem scharfen Nachbarbild entsteht.

Sucht Skalierung, Versatz, Unschaerfe (Art waehlbar) und Helligkeit, mit denen das Quellbild
dem Zielbild am aehnlichsten wird (Graustufen, 192x256, Nelder-Mead).

    python3 bild_anpassung.py VIDEO "[(Ziel, Quelle, 'motion'|'gauss'|'zoom', Winkel_rad), ...]"

Arten: motion = Wisch-Unschaerfe (Laenge x Breite, Winkel 0 = waagerecht, pi/2 = senkrecht),
       gauss = Gauss (sigma in px bei 576 Breite), zoom = radiale Zoom-Unschaerfe (log-Umfang).
Hinweis: Zoom-Unschaerfe wird ueberschaetzt (Bewegung der Person), Werte am Bild nachregeln.
Bildnummern wie im Edit (fps=30, start_time=0).
"""
import subprocess
import numpy as np, cv2, sys
from scipy.optimize import minimize


def _load(path):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", "fps=30:start_time=0", "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True)
    w, h = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                                    "stream=width,height", "-of", "csv=p=0", path],
                                   capture_output=True, text=True).stdout.strip().split(",")[:2])
    return np.frombuffer(p.stdout, np.uint8).reshape(-1, h, w, 3)


a = None
SW,SH=192,256
def gray(f): return cv2.resize(cv2.cvtColor(a[f],cv2.COLOR_RGB2GRAY),(SW,SH),interpolation=cv2.INTER_AREA).astype(np.float32)
def warp(img,s,dx,dy,wrap=False):
    M=np.array([[s,0,(1-s)*SW/2+dx*SW],[0,s,(1-s)*SH/2+dy*SH]],np.float32)
    return cv2.warpAffine(img,M,(SW,SH),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP if wrap else cv2.BORDER_REFLECT)
def motion(img,L,ang):
    n=max(1,int(round(L*SW)))
    if n<=1: return img
    k=np.zeros((n*2+1,n*2+1),np.float32); c=n
    for t in np.linspace(-n/2,n/2,n*4):
        x=int(round(c+t*np.cos(ang))); y=int(round(c+t*np.sin(ang))); k[y,x]=1
    k/=k.sum()
    return cv2.filter2D(img,-1,k,borderType=cv2.BORDER_REFLECT)
def model(src,p,kind,ang=0.0,wrap=False):
    s,dx,dy,b,g,o=p
    im=warp(src,np.exp(s),dx,dy,wrap)
    if kind=="gauss": im=cv2.GaussianBlur(im,(0,0),max(0.3,b*SW/576*1.0)) if b>0.05 else im
    elif kind=="motion": im=motion(im,max(0,b),ang)
    elif kind=="zoom":
        z=max(0.0,b); n=max(1,int(z*60)+1); acc=np.zeros_like(im)
        for k in range(n):
            sc=np.exp(z*(k/(max(1,n-1))-0.5)) if n>1 else 1.0
            acc+=warp(im,sc,0,0)
        im=acc/n
    return im*g+o
def fit(t,src,kind,ang=0.0,p0=(0,0,0,0.1,1,0),wrap=False):
    T=gray(t); S=gray(src)
    f=lambda p: float(np.mean((model(S,p,kind,ang,wrap)-T)**2))
    best=None
    for b0 in ({"motion":[0.08,0.4],"zoom":[0.05,0.25]}.get(kind,[3,15])):
        for s0 in (-0.12,0.0,0.12):
            p=list(p0); p[3]=b0; p[0]=s0
            r=minimize(f,p,method="Nelder-Mead",options=dict(maxiter=600,xatol=1e-3,fatol=1e-2))
            if best is None or r.fun<best.fun: best=r
    s,dx,dy,b,g,o=best.x
    print(f"{t} from {src} {kind:6s} ang={np.degrees(ang):4.0f}: scale {np.exp(s):.3f} dx {dx:+.3f} dy {dy:+.3f} blur {b:6.3f} gain {g:.2f} off {o:+6.1f}  rmse {np.sqrt(best.fun):.1f}")
    return best.x
if __name__=="__main__":
    import ast
    a=_load(sys.argv[1])
    jobs=ast.literal_eval(sys.argv[2])
    for j in jobs: fit(*j)
