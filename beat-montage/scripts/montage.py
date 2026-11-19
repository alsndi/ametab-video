"""Cut a folder of clips to the beat of a song -> one 9:16 video.

Usage: python montage.py plan.json      (paths in the plan are relative to the plan's folder)

plan.json
{
  "music": "song.mp3", "music_start": 32.0, "duration": 15,
  "beats": "beats.json",            # from beats.py run with --start <music_start>
  "scan": "clips.json",             # from scan_clips.py
  "beats_per_shot": 2,              # shot length in beats
  "fast_after_drop": 1,             # beats per shot after the drop (0 = no change)
  "shots": [{"file": "a.mov", "in": 3.2}, ...],   # optional: fixed order / start points;
                                                  # missing shots are filled automatically
  "exclude": ["bad.mov"],
  "punch": true,                    # flash + small zoom kick on downbeat cuts
  "push": 1.06,                     # slow push-in over every shot (1 = off)
  "text": [{"start": 0, "end": 2.2, "title": "قهوة", "highlight": "الصبح"}],
  "fade_out": 1.0, "out": "montage.mp4"
}
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "talk-reel", "scripts"))
import render  # noqa: E402

FPS = 30
W, H = 1080, 1920


def cut_points(beats, duration, per, fast, drop, downbeats=()):
    """Cut every `per` beats (every `fast` beats after the drop), counted from a downbeat
    so the cuts - and the punch - land on the strong beats."""
    bt = [b for b in beats if 0.15 < b < duration - 0.15]
    if not bt:
        return [0.0, duration]
    first_down = next((i for i, b in enumerate(bt) if any(abs(b - d) < 0.02 for d in downbeats)), 0)
    pts, i = [0.0], first_down % per
    while i < len(bt):
        if bt[i] - pts[-1] >= 0.25:
            pts.append(bt[i])
        i += fast if (fast and drop is not None and bt[i] >= drop) else per
    if duration - pts[-1] < 0.25:
        pts.pop()
    pts.append(duration)
    return pts


def best_window(samples, length, used, dur):
    """Start time of the best-scoring window of `length` s not overlapping `used`."""
    best, best_t = -1, None
    t_max = dur - length - 0.15
    for t, _ in samples:
        if t < 0.2 or t > t_max:
            continue
        if any(t < u1 and t + length > u0 for u0, u1 in used):
            continue
        vals = [v for tt, v in samples if t <= tt <= t + length]
        sc = sum(vals) / max(1, len(vals))
        if sc > best:
            best, best_t = sc, t
    return best_t


def title_ass(texts, brand, path):
    base = render.ass_color(brand["text_color"])
    hi = render.ass_color(brand.get("fill_color", brand["palette"][0]))
    out = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "",
           "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
           "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
           "Alignment, MarginL, MarginR, MarginV, Encoding",
           f"Style: T,{brand['font']},150,{base},{base},&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,10,4,5,60,60,0,-1",
           "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for t in texts:
        text = f"{t['title']} {{\\c{hi}}}{t.get('highlight', '')}" if t.get("highlight") else t["title"]
        y = t.get("y", 820)
        out.append(f"Dialogue: 0,{render.ass_time(t['start'])},{render.ass_time(t['end'])},T,,0,0,0,,"
                   f"{{\\pos(540,{y})\\fad(80,150)\\fscx70\\fscy70\\t(0,160,\\fscx106\\fscy106)"
                   f"\\t(160,260,\\fscx100\\fscy100)}}{text}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def main():
    plan_path = os.path.abspath(sys.argv[1])
    work = os.path.dirname(plan_path)
    p = lambda r: r if os.path.isabs(r) else os.path.join(work, r)  # noqa: E731
    plan = json.load(open(plan_path, encoding="utf-8"))
    beats = json.load(open(p(plan["beats"]), encoding="utf-8"))
    scan = json.load(open(p(plan["scan"]), encoding="utf-8"))
    duration = float(plan["duration"])
    clips = [c for c in scan["clips"] if c["file"] not in plan.get("exclude", [])]
    clips.sort(key=lambda c: -c["mean"])
    by_name = {c["file"]: c for c in clips}

    pts = cut_points(beats["beats"], duration, plan.get("beats_per_shot", 2),
                     plan.get("fast_after_drop", 0), beats.get("drop"), beats.get("downbeats", []))
    downs = beats.get("downbeats", [])
    fixed = plan.get("shots", [])
    used = {c["file"]: [] for c in clips}
    shots, rr = [], 0
    for k in range(len(pts) - 1):
        length = pts[k + 1] - pts[k]
        if k < len(fixed):
            f, t_in = fixed[k]["file"], float(fixed[k]["in"])
        else:
            f, t_in = None, None
            for tries in range(len(clips)):
                c = clips[(rr + tries) % len(clips)]
                t = best_window(c["samples"], length, used[c["file"]], c["duration"])
                if t is not None:
                    f, t_in = c["file"], t
                    rr = (rr + tries + 1) % len(clips)
                    break
            if f is None:
                sys.exit(f"Not enough footage for shot {k} ({length:.2f}s); add clips or shorten the duration")
        used.setdefault(f, []).append((t_in - 0.5, t_in + length + 0.5))
        shots.append({"file": f, "in": round(t_in, 2), "len": round(length, 3),
                      "downbeat": k == 0 or any(abs(pts[k] - d) < 0.02 for d in downs)})

    inputs = sorted(set(s["file"] for s in shots))
    idx = {f: i for i, f in enumerate(inputs)}
    folder = scan["folder"]
    push = float(plan.get("push", 1.06))
    g, labels = [], []
    for i, s in enumerate(shots):
        n = max(1, round(s["len"] * FPS))
        chain = (f"[{idx[s['file']]}:v]trim=start={s['in']:.3f}:duration={s['len']:.3f},setpts=PTS-STARTPTS,"
                 f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1")
        z0 = 1.10 if (plan.get("punch", True) and s["downbeat"] and i > 0) else 1.0
        if push != 1.0 or z0 != 1.0:
            # kick in from z0 over 5 frames, then slow push to `push`
            z = f"if(lt(on,5),{z0}-({z0}-1)*on/5,1+({push}-1)*(on-5)/{max(1, n - 5)})"
            chain += f",zoompan=z='{z}':d=1:x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':s={W}x{H}:fps={FPS}"
        if plan.get("punch", True) and s["downbeat"] and i > 0:
            chain += ",eq=brightness='0.35*max(0,1-t/0.12)':eval=frame"
        g.append(chain + f",trim=end_frame={n},setpts=PTS-STARTPTS[v{i}];")
        labels.append(f"[v{i}]")
    g.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0,format=yuv420p[vc];")

    vout = "[vc]"
    if plan.get("text"):
        brand = json.load(open(os.path.join(HERE, "..", "..", "talk-reel", "brand.json"), encoding="utf-8"))
        out_name = os.path.basename(p(plan.get("out", "montage.mp4")))
        title_ass(plan["text"], brand, os.path.join(work, out_name + ".ass"))
        g.append(f"[vc]ass={out_name}.ass[vt];")
        vout = "[vt]"
    fade = float(plan.get("fade_out", 1.0))
    mi = len(inputs)
    g.append(f"[{mi}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,afade=t=in:d=0.05,"
             f"afade=t=out:st={duration - fade:.3f}:d={fade},loudnorm=I=-14:TP=-1.5[ao]")

    graph_name = "montage.graph.txt"
    with open(os.path.join(work, graph_name), "w", encoding="utf-8") as f:
        f.write("\n".join(g))
    with open(os.path.join(work, "montage.shots.json"), "w", encoding="utf-8") as f:
        json.dump({"cuts": pts, "shots": shots}, f, ensure_ascii=False, indent=1)

    args = []
    for f in inputs:
        args += ["-i", os.path.join(folder, f)]
    args += ["-ss", str(plan.get("music_start", 0)), "-i", p(plan["music"]),
             "-filter_complex", "__GRAPH__", "-map", vout, "-map", "[ao]", "-t", str(duration),
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", p(plan.get("out", "montage.mp4"))]
    if render.run_ffmpeg(args, graph_name, work) != 0:
        sys.exit("ffmpeg failed")
    print(f"done: {len(shots)} shots on {len(pts) - 1} cuts, bpm {beats['bpm']} -> {plan.get('out', 'montage.mp4')}")


if __name__ == "__main__":
    main()
