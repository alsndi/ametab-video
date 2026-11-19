"""Pick the best still frames from a video for a cover or thumbnail.

Usage: python candidates.py VIDEO OUT_DIR [--count 12] [--every 0.5] [--min-gap 1.5]

Scores every sampled frame by sharpness (no motion blur), exposure and contrast,
keeps the best ones that are at least --min-gap seconds apart, writes them as
OUT_DIR/cand_XX.png (full resolution) and OUT_DIR/sheet.jpg (numbered contact
sheet) and OUT_DIR/candidates.json (time + score for each).
Look at sheet.jpg and choose by expression: mouth mid-word, eyes open, clear gesture.
"""
import argparse
import json
import os
import subprocess

import cv2
import numpy as np


def sample(video, every):
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, int(round(fps * every)))
    i = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                yield i / fps, frame
        i += 1
    cap.release()


def score(frame):
    small = cv2.resize(frame, (360, int(360 * frame.shape[0] / frame.shape[1])))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    sharp = cv2.Laplacian(gray, cv2.CV_64F).var()
    mean = gray.mean()
    exposure = 1.0 - min(1.0, abs(mean - 120) / 120)   # best around mid-grey
    contrast = min(1.0, gray.std() / 60)
    # skin-tone share in the upper 2/3 (YCrCb box) - favors frames with a face over screen recordings
    top = cv2.cvtColor(small[: small.shape[0] * 2 // 3], cv2.COLOR_BGR2YCrCb)
    skin = cv2.inRange(top, (40, 135, 85), (240, 175, 130)).mean() / 255
    face = 0.15 + min(1.0, skin * 10)
    return float(np.log1p(sharp) * (0.5 + exposure) * (0.5 + contrast) * face)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--count", type=int, default=12)
    ap.add_argument("--every", type=float, default=0.5)
    ap.add_argument("--min-gap", type=float, default=1.5)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    scored = [(score(f), t, f) for t, f in sample(a.video, a.every)]
    scored.sort(key=lambda x: -x[0])
    picked = []
    for s, t, f in scored:
        if all(abs(t - p[1]) >= a.min_gap for p in picked):
            picked.append((s, t, f))
        if len(picked) == a.count:
            break
    picked.sort(key=lambda x: x[1])

    info, thumbs = [], []
    for k, (s, t, f) in enumerate(picked):
        path = os.path.join(a.out, f"cand_{k:02d}.png")
        cv2.imwrite(path, f)
        info.append({"index": k, "time": round(t, 2), "score": round(s, 2), "file": os.path.basename(path)})
        th = cv2.resize(f, (216, int(216 * f.shape[0] / f.shape[1])))
        cv2.rectangle(th, (0, 0), (64, 40), (0, 0, 0), -1)
        cv2.putText(th, str(k), (8, 32), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (10, 214, 255), 3)
        thumbs.append(th)
    with open(os.path.join(a.out, "candidates.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=1)

    cols = 6
    h, w = thumbs[0].shape[:2]
    rows = (len(thumbs) + cols - 1) // cols
    sheet = np.zeros((rows * h, cols * w, 3), np.uint8)
    for k, th in enumerate(thumbs):
        r, c = divmod(k, cols)
        sheet[r * h:r * h + th.shape[0], c * w:c * w + th.shape[1]] = th
    cv2.imwrite(os.path.join(a.out, "sheet.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"{len(picked)} candidates -> {a.out}/sheet.jpg")


if __name__ == "__main__":
    main()
