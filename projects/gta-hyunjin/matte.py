#!/usr/bin/env python3
"""Personen praezise freistellen (Haare einzeln) mit RobustVideoMatting (ResNet50, ONNX, onnxruntime).

Modell: https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_resnet50_fp32.onnx
Fuer ein Standbild wird dasselbe Bild mehrmals durchgeschickt, damit sich der innere Zustand einschwingt.

    python3 matte.py MODELL.onnx FOTO_ORDNER AUSGABE_ORDNER [A,B,...]
Ausgabe: K_alpha.png (0..255), K_fgr.png (vom Hintergrund bereinigte Vordergrundfarbe)
"""
import os, sys
import numpy as np
import cv2
import onnxruntime as ort


def matte(sess, img, iters=6, internal=640):
    h, w = img.shape[:2]
    src = (cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
    ratio = np.array([min(1.0, internal / max(h, w))], np.float32)
    rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4
    for _ in range(iters):
        fgr, pha, *rec = sess.run(None, {"src": src, "r1i": rec[0], "r2i": rec[1], "r3i": rec[2], "r4i": rec[3],
                                         "downsample_ratio": ratio})
    a = pha[0, 0]
    f = cv2.cvtColor((fgr[0].transpose(1, 2, 0) * 255).clip(0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
    return a, f


def main():
    model, src, out = sys.argv[1:4]
    keys = sys.argv[4].split(",") if len(sys.argv) > 4 else list("ABCDE")
    os.makedirs(out, exist_ok=True)
    so = ort.SessionOptions()
    so.intra_op_num_threads = os.cpu_count() or 4
    sess = ort.InferenceSession(model, so, providers=["CPUExecutionProvider"])
    for k in keys:
        img = cv2.imread(os.path.join(src, f"{k}.jpg"))
        a, f = matte(sess, img)
        cv2.imwrite(os.path.join(out, f"{k}_alpha.png"), (a * 255).clip(0, 255).astype(np.uint8))
        cv2.imwrite(os.path.join(out, f"{k}_fgr.png"), f)
        print(k, img.shape, "Anteil Person %.2f" % (a > 0.5).mean(), flush=True)


if __name__ == "__main__":
    main()
