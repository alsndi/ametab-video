"""Full reel edit from one plan file: captions, punch-in zooms, flash transitions,
motion-graphic clips, numbered step markers, hearts and sound effects -> one ffmpeg pass.

Usage:  python edit.py edit.json
All relative paths inside edit.json are resolved against the folder that holds edit.json.
See ../SKILL.md for the plan format.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "talk-reel", "scripts"))
import render  # noqa: E402  (shared caption builder from talk-reel)

DEFAULT_BRAND = os.path.join(HERE, "..", "..", "talk-reel", "brand.json")
FPS = "30000/1001"
HEART = "m 60 30 b 60 0 0 0 0 36 b 0 72 60 96 60 120 b 60 96 120 72 120 36 b 120 0 60 0 60 30"


# ---------- small helpers ----------
def color(hex_color):
    return render.ass_color(hex_color) + "&"


def circle(r):
    k = 0.5523 * r
    return (f"m {r} 0 b {r + k} 0 {2 * r} {r - k} {2 * r} {r} b {2 * r} {r + k} {r + k} {2 * r} {r} {2 * r} "
            f"b {r - k} {2 * r} 0 {r + k} 0 {r} b 0 {r - k} {r - k} 0 {r} 0")


def rrect(w, h, r=22):
    return (f"m {r} 0 l {w - r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h - r} b {w} {h} {w} {h} {w - r} {h} "
            f"l {r} {h} b 0 {h} 0 {h} 0 {h - r} l 0 {r} b 0 0 0 0 {r} 0")


def pulses(dur_ms, start=300, period=520, big=104):
    tags, t, up = [], start, True
    while t + period <= dur_ms:
        s = big if up else 100
        tags.append(f"\\t({t},{t + period},\\fscx{s}\\fscy{s})")
        t += period
        up = not up
    return "".join(tags)


def dlg(layer, t0, t1, text, style="FX"):
    return f"Dialogue: {layer},{render.ass_time(t0)},{render.ass_time(t1)},{style},,0,0,0,,{text}"


def to_sec(ass_t):
    h, m, s = ass_t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


# ---------- overlays ----------
def marker_lines(m, mc):
    t0, t1 = m["start"], m["end"]
    dur = int((t1 - t0) * 1000)
    if "ring" in m:
        cx, cy, r = m["ring"]
        path = circle(r)
        bx, by = cx + int(r * 0.75), cy - int(r * 0.75)
    else:
        cx, cy, w, h = m["box"]
        path = rrect(w, h)
        bx, by = cx - w // 2 + 4, cy - h // 2 - 4
    intro = "\\fscx70\\fscy70\\t(0,180,\\fscx106\\fscy106)\\t(180,300,\\fscx100\\fscy100)"
    pop = "\\fscx0\\fscy0\\t(60,260,\\fscx115\\fscy115)\\t(260,360,\\fscx100\\fscy100)"
    out = [
        dlg(1, t0, t1, f"{{\\an5\\pos({cx},{cy})\\fad(120,150)\\1a&HFF&\\3c{mc}\\3a&H70&"
                       f"\\bord22\\blur14\\shad0{intro}{pulses(dur)}\\p1}}{path}"),
        dlg(2, t0, t1, f"{{\\an5\\pos({cx},{cy})\\fad(120,150)\\1a&HFF&\\3c{mc}"
                       f"\\bord8\\shad0{intro}{pulses(dur)}\\p1}}{path}"),
    ]
    if m.get("n") is not None:
        out.append(dlg(3, t0, t1, f"{{\\an5\\pos({bx},{by})\\fad(120,150)\\1c{mc}\\3c&H101010&\\bord4\\shad2"
                                  f"{pop}\\p1}}{circle(36)}"))
        out.append(dlg(4, t0, t1, f"{{\\an5\\pos({bx},{by + 2})\\fad(120,150)\\fnArial\\b1\\fs50\\1c&H101010&"
                                  f"\\bord0\\shad0{pop}}}{m['n']}"))
    if m.get("tap"):
        tt, tx, ty = m["tap"]
        out.append(dlg(5, tt, tt + 0.45, f"{{\\an5\\pos({tx},{ty})\\1a&HFF&\\3c&HFFFFFF&\\bord7\\shad0"
                                         f"\\fscx25\\fscy25\\t(0,450,\\fscx220\\fscy220\\3a&HFF&)\\p1}}{circle(40)}"))
        out.append(dlg(5, tt, tt + 0.30, f"{{\\an5\\pos({tx},{ty})\\1c&HFFFFFF&\\1a&H60&\\bord0\\shad0"
                                         f"\\t(0,300,\\fscx60\\fscy60\\1a&HFF&)\\p1}}{circle(28)}"))
    return out


def heart_lines(h):
    c = color(h.get("color", "#FF4D9D"))
    return [dlg(3, h["start"], h["end"],
                f"{{\\an5\\pos({h.get('x', 540)},{h.get('y', 1150)})\\fad(0,200)\\1c{c}\\3c&HFFFFFF&\\bord6\\shad3"
                f"\\fscx0\\fscy0\\t(0,160,\\fscx130\\fscy130)\\t(160,300,\\fscx100\\fscy100)"
                f"\\t(600,800,\\fscx112\\fscy112)\\t(800,1000,\\fscx100\\fscy100)\\p1}}{HEART}")]


def build_subs(plan, words, brand, total):
    ass = render.build_ass(words, brand, total).rstrip("\n").split("\n")
    i = ass.index("[Events]") - 1
    word_style = next(l for l in ass if l.startswith("Style: Word,"))
    low = word_style.split(",")
    low[0] = "Style: WordLow"
    low[-2] = str(plan.get("screen_margin_v", 200))
    fx = "Style: FX,Arial,40,&H00FFFFFF,&H00FFFFFF,&H00101010,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1"
    ass[i:i] = [",".join(low), fx]
    ranges = plan.get("screen_ranges", [])
    lines = []
    for l in ass:
        if l.startswith("Dialogue:") and any(a <= to_sec(l.split(",")[1]) < b for a, b in ranges):
            l = l.replace(",Word,", ",WordLow,", 1)
        lines.append(l)
    mc = color(plan.get("marker_color", "#FFD60A"))
    for m in plan.get("markers", []):
        lines += marker_lines(m, mc)
    for h in plan.get("hearts", []):
        lines += heart_lines(h)
    return "\n".join(lines) + "\n"


# ---------- timeline ----------
def full_segments(plan, duration):
    """Sort the plan's segments and fill any gaps with plain (zoom 1.0) footage."""
    segs = sorted(plan.get("segments", []), key=lambda s: s["start"])
    out, t = [], 0.0
    for s in segs:
        if s["start"] < t - 0.001:
            sys.exit(f"Segments overlap at {s['start']}s")
        if s["start"] > t + 0.001:
            out.append({"start": t, "end": s["start"]})
        out.append(s)
        t = s["end"]
    if t < duration - 0.001:
        out.append({"start": t, "end": duration})
    return out


def video_graph(segments, clip_inputs, W, H, ass_name):
    g, labels = [], []
    for i, s in enumerate(segments):
        a, b = s["start"], s["end"]
        kind = s.get("type", "cut")
        z = float(s.get("zoom", 1.0))
        base = f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS"
        if kind == "clip":
            idx = clip_inputs[s["file"]]
            off = float(s.get("clip_start", 0))
            g.append(f"[{idx}:v]trim=start={off:.3f}:end={off + b - a:.3f},setpts=PTS-STARTPTS,fps={FPS},"
                     f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[v{i}];")
        elif kind == "trans":
            n = round((b - a) * 30)
            step = (z - 1.0) / max(n - 1, 1)
            g.append(f"{base},zoompan=z='max(1,{z}-{step:.4f}*on)':d=1:x='iw/2-iw/zoom/2':"
                     f"y='ih/2-ih/zoom/2':s={W}x{H}:fps={FPS},"
                     f"eq=brightness='{s.get('flash', 0.45)}*max(0,1-t/0.2)':eval=frame,setsar=1[v{i}];")
        elif z != 1.0:
            w = int(W * z) // 2 * 2
            h = int(H * z) // 2 * 2
            ay = float(s.get("anchor_y", 0.3))  # 0 = keep top, 0.5 = center
            g.append(f"{base},scale={w}:{h},crop={W}:{H}:{(w - W) // 2}:{int((h - H) * ay)},setsar=1[v{i}];")
        else:
            g.append(f"{base},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[v{i}];")
        labels.append(f"[v{i}]")
    g.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0,fps={FPS}[vc];")
    g.append(f"[vc]ass={ass_name}[vo];")
    return g


def audio_graph(sfx, first_sfx_input, lufs):
    g = [f"[0:a]aresample=48000,loudnorm=I={lufs}:TP=-2:LRA=11[voice];"]
    mix = ["[voice]"]
    for k, s in enumerate(sfx):
        ms = int(s["at"] * 1000)
        g.append(f"[{first_sfx_input + k}:a]aresample=48000,volume={s.get('vol', 0.5)},adelay={ms}|{ms}[s{k}];")
        mix.append(f"[s{k}]")
    g.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first,alimiter=limit=0.93[ao]")
    return g


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    plan_path = os.path.abspath(sys.argv[1])
    work = os.path.dirname(plan_path)
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    p = lambda rel: rel if os.path.isabs(rel) else os.path.join(work, rel)  # noqa: E731

    with open(p(plan["words"]), encoding="utf-8") as f:
        data = json.load(f)
    words = data["words"]
    for i, w in plan.get("word_fixes", {}).items():
        words[int(i)]["w"] = w
    for i in plan.get("line_breaks", []):
        words[i]["brk"] = True
    words = [w for w in words if render.clean(w["w"])]

    with open(p(plan["brand"]) if plan.get("brand") else DEFAULT_BRAND, encoding="utf-8") as f:
        brand = json.load(f)
    W, H = brand["width"], brand["height"]

    out = p(plan.get("out", "reel.mp4"))
    ass_name = os.path.basename(out) + ".ass"
    with open(os.path.join(work, ass_name), "w", encoding="utf-8") as f:
        f.write(build_subs(plan, words, brand, data["duration"]))

    segments = full_segments(plan, data["duration"])
    clips = []
    for s in segments:
        if s.get("type") == "clip" and s["file"] not in clips:
            clips.append(s["file"])
    clip_inputs = {c: 1 + k for k, c in enumerate(clips)}

    sfx = list(plan.get("sfx", []))
    auto = plan.get("marker_sfx")
    if auto:
        for m in plan.get("markers", []):
            if auto.get("appear"):
                sfx.append({"file": auto["appear"], "at": m["start"], "vol": auto.get("appear_vol", 0.55)})
            if auto.get("tap") and m.get("tap"):
                sfx.append({"file": auto["tap"], "at": m["tap"][0], "vol": auto.get("tap_vol", 0.8)})
    sfx_dir = p(plan.get("sfx_dir", "sfx"))
    for s in sfx:
        if not os.path.exists(os.path.join(sfx_dir, s["file"])):
            sys.exit(f"Missing sound: {os.path.join(sfx_dir, s['file'])}")

    graph = video_graph(segments, clip_inputs, W, H, ass_name) + \
        audio_graph(sfx, 1 + len(clips), plan.get("loudness", -15))
    graph_name = os.path.basename(out) + ".graph.txt"
    with open(os.path.join(work, graph_name), "w", encoding="utf-8") as f:
        f.write("\n".join(graph))

    args = ["-i", p(plan["source"])]
    for c in clips:
        args += ["-i", p(c)]
    for s in sfx:
        args += ["-i", os.path.join(sfx_dir, s["file"])]
    args += ["-filter_complex", "__GRAPH__", "-map", "[vo]", "-map", "[ao]",
             "-c:v", "libx264", "-preset", "medium", "-crf", str(plan.get("crf", 18)), "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
    if render.run_ffmpeg(args, graph_name, work) != 0:
        sys.exit("ffmpeg failed")
    print(f"done: {out}  ({len(segments)} segments, {len(plan.get('markers', []))} markers, {len(sfx)} sounds)")


if __name__ == "__main__":
    main()
