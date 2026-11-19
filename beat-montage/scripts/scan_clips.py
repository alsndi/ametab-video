"""Score every moment of every clip in a folder so the montage can use the best parts.

Usage: python scan_clips.py CLIPS_DIR OUT.json [--rate 4]

For each clip (mp4/mov/m4v/mkv/webm), samples RATE frames per second at low resolution
and scores each sample: sharp (not blurry) + some motion (alive, not shaky) + not too dark.
OUT.json: {"clips": [{"file", "duration", "width", "height", "samples": [[t, score]...], "mean"}]}
Also writes OUT_DIR/clips_sheet.jpg: one row per clip (6 frames), to see what each clip is.
"""
import argparse
import json
import os
import subprocess

import cv2
import numpy as np

EXT = (".mp4", ".mov", ".m4v", ".mkv", ".webm")
W, H = 96, 170


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:stream_side_data=rotation:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    st = d["streams"][0]
    w, h = st["width"], st["height"]
    rot = 0
    for sd in st.get("side_data_list", []):
        rot = int(sd.get("rotation", 0) or 0)
    if abs(rot) in (90, 270):
        w, h = h, w
    return float(d["format"]["duration"]), w, h


def frames(path, rate):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf",
                          f"fps={rate},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("out")
    ap.add_argument("--rate", type=float, default=4)
    a = ap.parse_args()

    files = sorted(f for f in os.listdir(a.folder) if f.lower().endswith(EXT))
    clips, rows = [], []
    for name in files:
        path = os.path.join(a.folder, name)
        dur, w, h = probe(path)
        fr = frames(path, a.rate).astype(np.float32)
        sharp = np.array([cv2.Laplacian(f, cv2.CV_32F).var() for f in fr])
        motion = np.concatenate([[0], np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))])
        bright = fr.mean(axis=(1, 2))
        s = np.log1p(sharp) / (np.log1p(sharp).max() + 1e-6)
        m = np.clip(motion / 12, 0, 1)
        m = np.where(motion > 30, 0.3, m)  # very large change = shake or a cut inside the clip
        b = np.clip((bright - 25) / 60, 0, 1)
        score = (0.55 * s + 0.35 * m + 0.10) * b
        samples = [[round(i / a.rate, 2), round(float(v), 3)] for i, v in enumerate(score)]
        clips.append({"file": name, "duration": round(dur, 2), "width": w, "height": h,
                      "samples": samples, "mean": round(float(score.mean()), 3)})
        picks = np.linspace(0, len(fr) - 1, 6).astype(int)
        row = np.hstack([cv2.cvtColor(fr[k].astype(np.uint8), cv2.COLOR_GRAY2BGR) for k in picks])
        cv2.putText(row, name[:18], (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (10, 214, 255), 1)
        rows.append(row)
        print(f"{name}: {dur:.1f}s {w}x{h} mean {score.mean():.2f}")

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"folder": os.path.abspath(a.folder), "clips": clips}, f, indent=1)
    if rows:
        cv2.imwrite(os.path.join(os.path.dirname(os.path.abspath(a.out)), "clips_sheet.jpg"),
                    cv2.resize(np.vstack(rows), None, fx=1.5, fy=1.5))


if __name__ == "__main__":
    main()
