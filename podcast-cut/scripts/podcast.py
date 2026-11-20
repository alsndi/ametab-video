"""Multi-camera podcast / interview editor.

  python podcast.py sync     plan.json   -> finds each camera's offset from its audio (writes offsets.json)
  python podcast.py speakers plan.json   -> who talks when + the camera cut list (writes cuts.json)
  python podcast.py transcript plan.json -> word timings of the whole session on the main audio (words.json)
                                           and prints it as timed paragraphs (to pick reel moments)
  python podcast.py render   plan.json   -> renders plan["format"]: "16x9" full episode or "9x16" reel

plan.json (paths relative to its folder)
{
  "cams": [
    {"file": "camA.mp4", "speaker": "A", "crop_x": 0.5},   # crop_x: person's center 0..1, used for 9:16
    {"file": "camB.mp4", "speaker": "B", "crop_x": 0.45},
    {"file": "wide.mp4", "wide": true}
  ],
  "mics": [{"file": "micA.wav", "speaker": "A"}, {"file": "micB.wav", "speaker": "B"}],  # optional
  "main_audio": "mix.wav",          # program sound; or {"cam": 0} to use a camera's audio
  "min_shot": 2.0, "max_shot": 9.0,  # max_shot: cut to the wide (or the listener) after this long
  "range": [120.0, 175.5],           # optional: part of the session (reference = first camera's clock)
  "format": "9x16",
  "hook": {"title": "أكبر", "highlight": "غلطة", "seconds": 3},   # 9x16 only
  "words": "words.json",             # from `transcript`; 9x16 captions are cut from it
  "out": "reel1.mp4"
}
"""
import json
import os
import subprocess
import sys

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "talk-reel", "scripts"))
import render  # noqa: E402

ENV_RATE = 100  # envelope samples per second for syncing
VAD_RATE = 10   # loudness samples per second for speaker detection


def pcm(path, rate, start=0.0, dur=None):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start)]
    if dur:
        cmd += ["-t", str(dur)]
    cmd += ["-i", path, "-vn", "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)


def duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 path], capture_output=True, text=True, check=True).stdout)


def envelope(path, seconds):
    y = pcm(path, 8000, 0, seconds)
    hop = 8000 // ENV_RATE
    rms = np.sqrt(np.add.reduceat(y[: len(y) // hop * hop] ** 2, np.arange(0, len(y) // hop * hop, hop)) / hop)
    e = np.diff(np.log(rms + 1e-4), prepend=0)
    e = np.maximum(e, 0)
    return (e - e.mean()) / (e.std() + 1e-9)


def load(plan_path):
    plan = json.load(open(plan_path, encoding="utf-8"))
    work = os.path.dirname(os.path.abspath(plan_path))
    return plan, work, (lambda r: r if os.path.isabs(r) else os.path.join(work, r))


def cmd_sync(plan_path):
    plan, work, p = load(plan_path)
    sources = [c["file"] for c in plan["cams"]] + [m["file"] for m in plan.get("mics", [])]
    if isinstance(plan.get("main_audio"), str):
        sources.append(plan["main_audio"])
    seconds = plan.get("sync_seconds", 180)
    ref = envelope(p(sources[0]), seconds)
    offsets = {sources[0]: 0.0}
    for s in sources[1:]:
        e = envelope(p(s), seconds)
        corr = signal.correlate(e, ref, mode="full", method="fft")
        lags = signal.correlation_lags(len(e), len(ref), mode="full")
        k = int(np.argmax(corr))
        conf = float(corr[k] / (np.sort(corr)[-50:].mean() + 1e-9))
        offsets[s] = round(lags[k] / ENV_RATE, 3)  # source time = reference time + offset
        print(f"{s}: offset {offsets[s]:+.3f}s (peak/near-peaks {conf:.2f}{'  LOW - check' if conf < 1.3 else ''})")
    json.dump(offsets, open(os.path.join(work, "offsets.json"), "w", encoding="utf-8"), indent=1)


def offsets_of(work):
    path = os.path.join(work, "offsets.json")
    if not os.path.exists(path):
        sys.exit("Run `sync` first")
    return json.load(open(path, encoding="utf-8"))


def loudness_db(path, off, start, dur):
    """dB loudness at VAD_RATE on the reference clock (start..start+dur)."""
    src_start = start + off
    pad = max(0.0, -src_start)
    y = pcm(path, 16000, max(0.0, src_start), dur - pad)
    hop = 16000 // VAD_RATE
    n = len(y) // hop
    rms = np.sqrt((y[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    db = 20 * np.log10(rms + 1e-6)
    db = np.concatenate([np.full(int(pad * VAD_RATE), -120.0), db])
    out = np.full(int(dur * VAD_RATE), -120.0)
    out[: min(len(out), len(db))] = db[: len(out)]
    return out


def cmd_speakers(plan_path):
    plan, work, p = load(plan_path)
    offs = offsets_of(work)
    ref_dur = duration(p(plan["cams"][0]["file"]))
    start, end = plan.get("range", [0.0, ref_dur])
    dur = end - start
    sources = plan.get("mics") or [c for c in plan["cams"] if c.get("speaker")]
    names = [s["speaker"] for s in sources]
    db = np.vstack([loudness_db(p(s["file"]), offs[s["file"]], start, dur) for s in sources])
    db -= np.percentile(db, 20, axis=1, keepdims=True)          # each source relative to its own floor
    db = signal.medfilt(db, kernel_size=[1, 5])
    top = db.argmax(axis=0)
    srt = np.sort(db, axis=0)
    margin = srt[-1] - (srt[-2] if len(sources) > 1 else 0)
    active = srt[-1] > 8
    label = np.where(active & (margin > 3), top, np.where(active, -2, -1))  # -2 overlap, -1 silence

    cams = plan["cams"]
    cam_of = {c["speaker"]: i for i, c in enumerate(cams) if c.get("speaker")}
    wide = next((i for i, c in enumerate(cams) if c.get("wide")), None)
    min_shot = plan.get("min_shot", 2.0)
    max_shot = plan.get("max_shot", 9.0)

    want = []
    cur = cam_of.get(names[int(top[0])], 0)
    for v in label:
        if v >= 0:
            cur = cam_of.get(names[v], cur)
        elif v == -2 and wide is not None:
            cur = wide
        want.append(cur)
    # runs, then merge short ones into the previous shot
    runs = []
    for i, c in enumerate(want):
        if runs and runs[-1][2] == c:
            runs[-1][1] = i + 1
        else:
            runs.append([i, i + 1, c])
    merged = []
    for r in runs:
        if merged and (r[1] - r[0]) / VAD_RATE < min_shot:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    # break very long shots with the wide (or the other camera) so it does not get static
    cuts = []
    for a, b, c in merged:
        t, end_t = a / VAD_RATE, b / VAD_RATE
        while end_t - t > max_shot + min_shot:
            cuts.append([round(start + t, 2), round(start + t + max_shot, 2), c])
            alt = wide if wide is not None and wide != c else (c + 1) % len(cams)
            cuts.append([round(start + t + max_shot, 2), round(start + t + max_shot + min_shot, 2), alt])
            t += max_shot + min_shot
        cuts.append([round(start + t, 2), round(start + end_t, 2), c])
    talk = {n: round(float((label == k).sum()) / VAD_RATE, 1) for k, n in enumerate(names)}
    json.dump({"range": [start, end], "cuts": cuts, "talk_seconds": talk},
              open(os.path.join(work, "cuts.json"), "w", encoding="utf-8"), indent=1)
    print(f"{len(cuts)} shots over {dur:.1f}s; talk time {talk}")


def main_audio(plan, p, offs):
    m = plan.get("main_audio", {"cam": 0})
    if isinstance(m, dict):
        f = plan["cams"][m.get("cam", 0)]["file"]
    else:
        f = m
    return p(f), offs.get(f, 0.0)


def cmd_transcript(plan_path):
    plan, work, p = load(plan_path)
    offs = offsets_of(work)
    audio, off = main_audio(plan, p, offs)
    sys.path.insert(0, os.path.join(HERE, "..", "..", "talk-reel", "scripts"))
    out = os.path.join(work, "words.json")
    subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "talk-reel", "scripts", "transcribe.py"),
                    audio, out, "--model", plan.get("model", "medium"), "--lang", plan.get("lang", "ar")], check=True)
    data = json.load(open(out, encoding="utf-8"))
    for w in data["words"]:  # move to the reference clock
        w["s"] = round(w["s"] - off, 3)
        w["e"] = round(w["e"] - off, 3)
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    para, t0 = [], None
    for i, w in enumerate(data["words"]):
        if t0 is None:
            t0 = w["s"]
        para.append(w["w"])
        nxt = data["words"][i + 1]["s"] if i + 1 < len(data["words"]) else None
        if nxt is None or nxt - w["e"] > 0.8 or len(para) > 40:
            print(f"[{t0:7.1f} - {w['e']:7.1f}] {' '.join(para)}")
            para, t0 = [], None


def cmd_render(plan_path):
    plan, work, p = load(plan_path)
    offs = offsets_of(work)
    cuts_path = os.path.join(work, "cuts.json")
    if not os.path.exists(cuts_path):
        sys.exit("Run `speakers` first")
    cutdata = json.load(open(cuts_path, encoding="utf-8"))
    start, end = plan.get("range", cutdata["range"])
    cuts = [[max(a, start), min(b, end), c] for a, b, c in cutdata["cuts"] if b > start and a < end]
    vertical = plan.get("format", "16x9") == "9x16"
    W, H = (1080, 1920) if vertical else (1920, 1080)
    cams = plan["cams"]
    out = p(plan.get("out", "podcast.mp4"))
    g, labels = [], []
    for i, (a, b, c) in enumerate(cuts):
        cam = cams[c]
        s = a + offs[cam["file"]]
        if vertical:
            cx = float(cam.get("crop_x", 0.5))
            fit = (f"scale=-2:{H},crop={W}:{H}:'max(0,min(iw-{W},iw*{cx}-{W}/2))':0")
        else:
            fit = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
        g.append(f"[{c}:v]trim=start={s:.3f}:duration={b - a:.3f},setpts=PTS-STARTPTS,fps=30,{fit},setsar=1[v{i}];")
        labels.append(f"[v{i}]")
    g.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0,format=yuv420p[vc];")
    vout = "[vc]"
    if vertical:
        brand = json.load(open(os.path.join(HERE, "..", "..", "talk-reel", "brand.json"), encoding="utf-8"))
        lines = []
        if plan.get("words"):
            words = [dict(w, s=w["s"] - start, e=w["e"] - start)
                     for w in json.load(open(p(plan["words"]), encoding="utf-8"))["words"]
                     if w["s"] >= start and w["e"] <= end]
            for i, w in plan.get("word_fixes", {}).items():
                words[int(i)]["w"] = w
            lines = render.build_ass(words, brand, end - start).rstrip("\n").split("\n")
        else:
            lines = render.build_ass([{"w": " ", "s": 0, "e": 0.01}], brand, 0.02).rstrip("\n").split("\n")
        hook = plan.get("hook")
        if hook:
            hi = render.ass_color(brand.get("fill_color", "#FFD60A"))
            i = lines.index("[Events]") - 1
            lines[i:i] = [f"Style: Hook,{brand['font']},120,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,"
                          f"100,100,0,0,1,9,4,8,60,60,230,-1"]
            lines.append(f"Dialogue: 5,0:00:00.00,{render.ass_time(hook.get('seconds', 3))},Hook,,0,0,0,,"
                         f"{{\\fad(0,200)\\fscx70\\fscy70\\t(0,180,\\fscx105\\fscy105)\\t(180,280,\\fscx100\\fscy100)}}"
                         f"{hook['title']} {{\\c{hi}}}{hook.get('highlight', '')}")
        ass_name = os.path.basename(out) + ".ass"
        open(os.path.join(work, ass_name), "w", encoding="utf-8").write("\n".join(lines) + "\n")
        g.append(f"[vc]{render.ass_filter(ass_name)}[vt];")
        vout = "[vt]"
    audio, aoff = main_audio(plan, p, offs)
    ai = len(cams)
    g.append(f"[{ai}:a]atrim=start={start + aoff:.3f}:duration={end - start:.3f},asetpts=PTS-STARTPTS,"
             f"aresample=48000,afade=t=in:d=0.05,afade=t=out:st={max(0, end - start - 0.3):.3f}:d=0.3,"
             f"loudnorm=I={-14 if vertical else -16}:TP=-1.5:LRA=11[ao]")
    graph_name = os.path.basename(out) + ".graph.txt"
    open(os.path.join(work, graph_name), "w", encoding="utf-8").write("\n".join(g))
    args = []
    for cam in cams:
        args += ["-i", p(cam["file"])]
    args += ["-i", audio, "-filter_complex", "__GRAPH__", "-map", vout, "-map", "[ao]",
             "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
    if render.run_ffmpeg(args, graph_name, work) != 0:
        sys.exit("ffmpeg failed")
    print(f"done: {len(cuts)} shots, {end - start:.1f}s, {W}x{H} -> {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    {"sync": cmd_sync, "speakers": cmd_speakers, "transcript": cmd_transcript,
     "render": cmd_render}.get(sys.argv[1], lambda _: sys.exit(__doc__))(sys.argv[2])
