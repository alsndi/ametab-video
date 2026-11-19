"""Cut the person out of a video: writes a black/white alpha (mask) video for a time range.

Usage: python matte.py VIDEO OUT_MASK.mp4 [--start 0] [--end 4] [--downsample 0.25]

Uses Robust Video Matting (rvm_mobilenetv3_fp32.onnx, GPL-3.0, ~15 MB) with onnxruntime on the CPU.
The model is NOT part of the plugin: it lives in ~/.ametab-video/models. If it is missing the script
stops and says so - ask the user before downloading it from
https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx
"""
import argparse
import os
import subprocess
import sys
import time

import numpy as np

MODEL = os.path.join(os.path.expanduser("~"), ".ametab-video", "models", "rvm_mobilenetv3_fp32.onnx")


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout.strip().split(",")
    num, den = out[2].split("/")
    return int(out[0]), int(out[1]), float(num) / float(den), out[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--downsample", type=float, default=0.25, help="0.25 for 1080p, 0.4 for 720p")
    a = ap.parse_args()
    if not os.path.exists(MODEL):
        sys.exit(f"Model missing: {MODEL}\nAsk the user, then download rvm_mobilenetv3_fp32.onnx (see this file's docstring).")
    import onnxruntime as ort

    w, h, fps, fps_str = probe(a.video)
    sess = ort.InferenceSession(MODEL, providers=["CPUExecutionProvider"])
    rec = [np.zeros([1, 1, 1, 1], np.float32)] * 4
    ds = np.array([a.downsample], np.float32)

    cmd = ["ffmpeg", "-v", "error", "-ss", str(a.start)]
    if a.end:
        cmd += ["-t", str(a.end - a.start)]
    cmd += ["-i", a.video, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    reader = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    writer = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}",
                               "-r", fps_str, "-i", "-", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
                               a.out], stdin=subprocess.PIPE)
    size = w * h * 3
    n, t0 = 0, time.time()
    while True:
        buf = reader.stdout.read(size)
        if len(buf) < size:
            break
        src = np.frombuffer(buf, np.uint8).reshape(h, w, 3).astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        fgr, pha, *rec = sess.run(None, {"src": src, "r1i": rec[0], "r2i": rec[1], "r3i": rec[2], "r4i": rec[3],
                                         "downsample_ratio": ds})
        writer.stdin.write((np.clip(pha[0, 0], 0, 1) * 255).astype(np.uint8).tobytes())
        n += 1
    writer.stdin.close()
    writer.wait()
    reader.wait()
    print(f"mask: {n} frames ({n / fps:.2f}s) in {time.time() - t0:.1f}s -> {a.out}")


if __name__ == "__main__":
    main()
