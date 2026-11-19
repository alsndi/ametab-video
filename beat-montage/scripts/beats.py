"""Find the beats in a song (numpy only, no librosa).

Usage: python beats.py MUSIC OUT.json [--start 0] [--length 60]

OUT.json: {"bpm", "beats": [t...], "downbeats": [t...], "energy": [[t, 0..1]...], "drop": t|null}
- beats: tempo grid snapped to the nearest onset peak
- downbeats: every 4th beat, phase picked where the low end hits hardest
- energy: loudness every 0.5 s (to cut faster where the song is busier)
- drop: biggest sudden rise in energy (good place for the strongest shot)
"""
import argparse
import json
import subprocess

import numpy as np

SR = 22050
HOP = 512


def load(path, start, length):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start)]
    if length:
        cmd += ["-t", str(length)]
    cmd += ["-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype=np.float32)


def stft_mag(y, n=2048):
    win = np.hanning(n).astype(np.float32)
    frames = 1 + (len(y) - n) // HOP
    idx = np.arange(n)[None, :] + HOP * np.arange(frames)[:, None]
    return np.abs(np.fft.rfft(y[idx] * win, axis=1))


def onset_envelope(mag, log=True):
    m = np.log1p(10 * mag) if log else mag
    flux = np.maximum(0, np.diff(m, axis=0)).sum(axis=1)
    flux = np.concatenate([[0], flux])
    flux -= np.convolve(flux, np.ones(16) / 16, mode="same")  # remove slow trend
    flux = np.maximum(flux, 0)
    return flux / (flux.max() + 1e-9)


def tempo_period(env, fps):
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    lags = np.arange(len(ac))
    bpm = 60 * fps / np.maximum(lags, 1)
    ok = (bpm >= 70) & (bpm <= 180)
    weight = np.exp(-0.5 * (np.log2(np.maximum(bpm, 1) / 115)) ** 2)  # mild preference for ~115 bpm
    score = np.where(ok, ac * weight, 0)
    return int(np.argmax(score))


def track(env, period):
    best_phase = max(range(period), key=lambda p: env[p::period].sum())
    beats, t = [], best_phase
    w = max(1, period // 8)
    while t < len(env):
        lo, hi = max(0, t - w), min(len(env), t + w + 1)
        snapped = lo + int(np.argmax(env[lo:hi]))
        beats.append(snapped)
        t = snapped + period
    return beats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("music")
    ap.add_argument("out")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--length", type=float, default=0.0)
    a = ap.parse_args()

    y = load(a.music, a.start, a.length)
    n = 2048
    mag = stft_mag(y, n)
    fps = SR / HOP
    env = onset_envelope(mag)
    low_bins = max(2, int(150 / (SR / 2) * mag.shape[1]))
    low_env = onset_envelope(mag[:, :low_bins], log=False)  # kick drum band, linear so loud kicks win
    period = tempo_period(env, fps)
    # lock the grid on kicks/snares rather than hi-hats: phase and snapping use a low-weighted envelope
    beat_frames = track(0.4 * env + 0.6 * low_env, period)
    offset = (n / 2) / SR  # frame index -> window center
    beats = [round(f / fps + offset, 3) for f in beat_frames]

    low = mag[:, :low_bins].sum(axis=1)
    phase = max(range(4), key=lambda p: sum(low[f] for f in beat_frames[p::4]))
    downbeats = beats[phase::4]

    rms = np.sqrt(np.convolve(y ** 2, np.ones(SR // 2) / (SR // 2), mode="same"))[:: SR // 2]
    rms = rms / (rms.max() + 1e-9)
    energy = [[round(i * 0.5, 2), round(float(v), 3)] for i, v in enumerate(rms)]
    jumps = np.diff(np.convolve(rms, np.ones(4) / 4, mode="same"))
    drop = round(float(np.argmax(jumps) * 0.5), 2) if len(jumps) and jumps.max() > 0.08 else None

    data = {"bpm": round(60 * fps / period, 1), "start": a.start, "beats": beats,
            "downbeats": downbeats, "energy": energy, "drop": drop}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    print(f"bpm {data['bpm']}, {len(beats)} beats, drop at {drop}s -> {a.out}")


if __name__ == "__main__":
    main()
