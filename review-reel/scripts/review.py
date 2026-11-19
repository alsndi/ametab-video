"""Product / review reel: voiceover on top of b-roll clips, with captions, labels and a ducked music bed.

  python review.py phrases WORDS.json          -> numbered phrases with start times (to plan the shots)
  python review.py render  review.json         -> renders the reel

review.json (paths relative to its folder)
{
  "voice": "vo.m4a", "words": "words.json",
  "scan": "clips.json",                       # from beat-montage/scripts/scan_clips.py (clips folder inside)
  "shots": [                                   # one per phrase/idea, start = time in the voiceover
    {"start": 0.0, "file": "unbox.mov", "in": 1.2},
    {"start": 2.6, "file": "detail.mov"},      # no "in" -> best moment of that clip
    {"start": 5.1}                             # no "file" -> best unused moment of any clip
  ],
  "word_fixes": {"3": "آيفون"}, "line_breaks": [7, 15],
  "labels": [{"start": 6.0, "end": 8.5, "text": "السعر 129 ريال"}],
  "music": "bed.mp3", "music_start": 0, "music_vol": 0.22,
  "sfx_dir": "sfx", "sfx": [{"file": "09_Pop.wav", "at": 6.0, "vol": 0.5}],
  "push": 1.06, "tail": 0.6, "out": "review.mp4"
}
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "talk-reel", "scripts"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "beat-montage", "scripts"))
import render  # noqa: E402
from montage import best_window  # noqa: E402

FPS = 30
W, H = 1080, 1920
BRAND = os.path.join(HERE, "..", "..", "talk-reel", "brand.json")


def phrases(words, gap=0.35, max_words=9):
    out, cur = [], []
    for i, w in enumerate(words):
        if cur and (w["s"] - words[i - 1]["e"] > gap or len(cur) >= max_words
                    or re.search(r"[.!?؟،,]$", words[i - 1]["w"])):
            out.append(cur)
            cur = []
        cur.append(i)
    if cur:
        out.append(cur)
    return out


def label_lines(labels, brand):
    fill = render.ass_color(brand.get("fill_color", "#FFD60A"))
    lines = [f"Style: Label,{brand['font']},74,&H00101010,&H00101010,{fill},{fill},-1,0,0,0,100,100,0,0,3,18,0,8,60,60,260,-1"]
    ev = []
    for lb in labels:
        ev.append(f"Dialogue: 6,{render.ass_time(lb['start'])},{render.ass_time(lb['end'])},Label,,0,0,0,,"
                  f"{{\\fad(100,150)\\fscx60\\fscy60\\t(0,160,\\fscx108\\fscy108)\\t(160,260,\\fscx100\\fscy100)}}"
                  f"{lb['text']}")
    return lines, ev


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("phrases", "render"):
        sys.exit(__doc__)
    if sys.argv[1] == "phrases":
        words = json.load(open(sys.argv[2], encoding="utf-8"))["words"]
        for k, ph in enumerate(phrases(words)):
            print(f"{k:2d}  {words[ph[0]]['s']:6.2f}-{words[ph[-1]]['e']:6.2f}  [{ph[0]}..{ph[-1]}]  "
                  + " ".join(words[i]["w"] for i in ph))
        return

    plan_path = os.path.abspath(sys.argv[2])
    work = os.path.dirname(plan_path)
    p = lambda r: r if os.path.isabs(r) else os.path.join(work, r)  # noqa: E731
    plan = json.load(open(plan_path, encoding="utf-8"))
    data = json.load(open(p(plan["words"]), encoding="utf-8"))
    scan = json.load(open(p(plan["scan"]), encoding="utf-8"))
    clips = {c["file"]: c for c in scan["clips"]}
    words = data["words"]
    for i, w in plan.get("word_fixes", {}).items():
        words[int(i)]["w"] = w
    for i in plan.get("line_breaks", []):
        words[i]["brk"] = True
    words = [w for w in words if render.clean(w["w"])]
    total = min(data["duration"], words[-1]["e"] + float(plan.get("tail", 0.6)))

    # --- shots ---
    shots = sorted(plan["shots"], key=lambda s: s["start"])
    shots[0]["start"] = 0.0
    used = {f: [] for f in clips}
    order = sorted(clips, key=lambda f: -clips[f]["mean"])
    rr = 0
    for k, s in enumerate(shots):
        end = shots[k + 1]["start"] if k + 1 < len(shots) else total
        s["len"] = round(end - s["start"], 3)
        if s.get("file") and s.get("in") is not None:
            pass
        elif s.get("file"):
            c = clips[s["file"]]
            s["in"] = best_window(c["samples"], s["len"], used[s["file"]], c["duration"])
            if s["in"] is None:
                s["in"] = 0.0
        else:
            for tries in range(len(order)):
                c = clips[order[(rr + tries) % len(order)]]
                t = best_window(c["samples"], s["len"], used[c["file"]], c["duration"])
                if t is not None:
                    s["file"], s["in"] = c["file"], t
                    rr = (rr + tries + 1) % len(order)
                    break
            if not s.get("file"):
                sys.exit(f"No clip long enough for shot at {s['start']}s ({s['len']}s)")
        if clips[s["file"]]["duration"] < s["in"] + s["len"]:
            print(f"warning: {s['file']} is shorter than shot at {s['start']}s; it will freeze on the last frame")
        used[s["file"]].append((s["in"] - 0.5, s["in"] + s["len"] + 0.5))

    # --- subtitles ---
    brand = json.load(open(p(plan["brand"]) if plan.get("brand") else BRAND, encoding="utf-8"))
    ass = render.build_ass(words, brand, total).rstrip("\n").split("\n")
    if plan.get("labels"):
        style, ev = label_lines(plan["labels"], brand)
        i = ass.index("[Events]") - 1
        ass[i:i] = style
        ass += ev
    out = p(plan.get("out", "review.mp4"))
    ass_name = os.path.basename(out) + ".ass"
    with open(os.path.join(work, ass_name), "w", encoding="utf-8") as f:
        f.write("\n".join(ass) + "\n")

    # --- graph ---
    files = sorted(set(s["file"] for s in shots))
    idx = {f: i for i, f in enumerate(files)}
    push = float(plan.get("push", 1.06))
    g, labels = [], []
    for i, s in enumerate(shots):
        n = max(1, round(s["len"] * FPS))
        chain = (f"[{idx[s['file']]}:v]trim=start={s['in']:.3f},setpts=PTS-STARTPTS,fps={FPS},"
                 f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                 f"tpad=stop_mode=clone:stop_duration={s['len']:.3f}")
        if push != 1.0:
            chain += (f",zoompan=z='1+({push}-1)*on/{n}':d=1:x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':"
                      f"s={W}x{H}:fps={FPS}")
        g.append(chain + f",trim=end_frame={n},setpts=PTS-STARTPTS[v{i}];")
        labels.append(f"[v{i}]")
    g.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0,format=yuv420p,ass={ass_name}[vo];")

    vi = len(files)
    g.append(f"[{vi}:a]atrim=duration={total:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
             f"loudnorm=I=-15:TP=-2:LRA=11,asplit=2[voice][key];")
    mix = ["[voice]"]
    nxt = vi + 1
    if plan.get("music"):
        g.append(f"[{nxt}:a]aresample=48000,atrim=duration={total:.3f},asetpts=PTS-STARTPTS,"
                 f"volume={plan.get('music_vol', 0.22)},afade=t=out:st={max(0, total - 1.2):.3f}:d=1.2[bed];")
        g.append("[bed][key]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=350[ducked];")
        mix.append("[ducked]")
        nxt += 1
    else:
        g.append("[key]anullsink;")
    sfx = plan.get("sfx", [])
    sfx_dir = p(plan.get("sfx_dir", "sfx"))
    for k, s in enumerate(sfx):
        ms = int(s["at"] * 1000)
        g.append(f"[{nxt + k}:a]aresample=48000,volume={s.get('vol', 0.5)},adelay={ms}|{ms}[s{k}];")
        mix.append(f"[s{k}]")
    g.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first,alimiter=limit=0.93[ao]")

    graph_name = os.path.basename(out) + ".graph.txt"
    with open(os.path.join(work, graph_name), "w", encoding="utf-8") as f:
        f.write("\n".join(g))
    with open(os.path.join(work, os.path.basename(out) + ".shots.json"), "w", encoding="utf-8") as f:
        json.dump(shots, f, ensure_ascii=False, indent=1)

    args = []
    for f in files:
        args += ["-i", os.path.join(scan["folder"], f)]
    args += ["-i", p(plan["voice"])]
    if plan.get("music"):
        args += ["-ss", str(plan.get("music_start", 0)), "-i", p(plan["music"])]
    for s in sfx:
        args += ["-i", os.path.join(sfx_dir, s["file"])]
    args += ["-filter_complex", "__GRAPH__", "-map", "[vo]", "-map", "[ao]", "-t", f"{total:.3f}",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
    if render.run_ffmpeg(args, graph_name, work) != 0:
        sys.exit("ffmpeg failed")
    print(f"done: {len(shots)} shots, {total:.1f}s -> {out}")


if __name__ == "__main__":
    main()
