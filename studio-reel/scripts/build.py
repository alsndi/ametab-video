"""Ametab studio-style reel: dark rounded cards with one accent colour, boxed captions,
split screen / picture-in-picture, checklists, numbered lists, scores, REC frame, progress bar.

Usage: python build.py studio.json [--still SECONDS]

studio.json (paths relative to its folder)
{
  "source": "../video.mp4", "words": "words.json",
  "word_fixes": {"3": "آيفون"}, "line_breaks": [12],
  "accent": "green",            # red | green | cyan | blue | orange | yellow | purple | "#22c55e"
  "face_y": 0.30,               # face centre in the source (0 top .. 1 bottom)
  "keywords": ["مخترق", "الكاميرا"],   # get the accent pill inside captions
  "rec": 2.0, "progress": true,
  "beats": [
    {"at_word": 0,  "layout": "full", "zoom": 1.08},
    {"at_word": 6,  "layout": "split", "card": {"type": "list", "n": 1, "total": 7, "title": "التلفون يحمى", "emoji": "🌡️"}},
    {"at_word": 30, "layout": "pip",   "card": {"type": "checklist", "title": "شتسوي؟", "items": ["...", "..."], "at_words": [31, 36]}},
    {"start": 40.0, "layout": "full"}
  ],
  "auto_sfx": true,             # whoosh on layout change, pop on a new card, ding on each checklist tick
  "sfx": [{"role": "impact", "at": 0.0, "vol": 0.5}],
  "music": "bed.mp3", "music_vol": 0.08,
  "out": "studio.mp4"
}
A beat starts at "at_word" (that word's start) or "start" (seconds) and lasts until the next beat.
Card images ("image", "logo") are file paths; they are copied into the Remotion project.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "..", "motion-edit", "remotion")
sys.path.insert(0, os.path.join(HERE, "..", "..", "motion-edit", "scripts"))
import sfx_index  # noqa: E402

NPX = "npx.cmd" if os.name == "nt" else "npx"
NPM = "npm.cmd" if os.name == "nt" else "npm"
THEMES = {"red": "#ff3b4a", "green": "#22c55e", "cyan": "#22d3ee", "blue": "#3b82f6",
          "orange": "#f97316", "yellow": "#FFD60A", "purple": "#a855f7"}


def ensure_project(work):
    if not os.path.exists(os.path.join(work, "package.json")):
        shutil.copytree(TEMPLATE, work, dirs_exist_ok=True)
    else:
        shutil.copytree(os.path.join(TEMPLATE, "src"), os.path.join(work, "src"), dirs_exist_ok=True)
    if not os.path.exists(os.path.join(work, "node_modules", "remotion")):
        print("npm install (first time only)...")
        subprocess.run([NPM, "install", "--no-fund", "--no-audit"], cwd=work, check=True)
    os.makedirs(os.path.join(work, "public"), exist_ok=True)
    fonts_src = os.path.join(HERE, "..", "..", "fonts")
    if os.path.isdir(fonts_src):
        shutil.copytree(fonts_src, os.path.join(work, "public", "fonts"), dirs_exist_ok=True)


def link_or_copy(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def duration_of(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                capture_output=True, text=True, check=True).stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--still", type=float)
    a = ap.parse_args()
    plan_path = os.path.abspath(a.plan)
    work = os.path.dirname(plan_path)
    p = lambda r: r if os.path.isabs(r) else os.path.join(work, r)  # noqa: E731
    plan = json.load(open(plan_path, encoding="utf-8"))
    proj = os.path.join(work, "motion")
    ensure_project(proj)
    pub = os.path.join(proj, "public")

    src = p(plan["source"])
    total = duration_of(src)
    link_or_copy(src, os.path.join(pub, "source.mp4"))
    if a.still is None:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "2", "-ar", "48000",
                        os.path.join(pub, "voice.wav")], check=True)

    words = []
    if plan.get("words"):
        words = json.load(open(p(plan["words"]), encoding="utf-8"))["words"]
        for i, w in plan.get("word_fixes", {}).items():
            words[int(i)]["w"] = w
        for i in plan.get("line_breaks", []):
            words[i]["brk"] = True

    def t_of(item):
        if "at_word" in item:
            return 0.0 if item["at_word"] == 0 else words[item["at_word"]]["s"]
        return float(item.get("start", 0.0))

    raw = sorted(plan["beats"], key=t_of)
    beats, img_n = [], 0
    for k, b in enumerate(raw):
        start = t_of(b)
        end = t_of(raw[k + 1]) if k + 1 < len(raw) else total
        beat = {"start": round(start, 3), "end": round(end, 3), "layout": b.get("layout", "full")}
        if b.get("zoom"):
            beat["zoom"] = b["zoom"]
        if b.get("card"):
            card = dict(b["card"])
            for key in ("image",):
                if card.get(key):
                    name = f"img_{img_n:02d}{os.path.splitext(card[key])[1]}"
                    shutil.copyfile(p(card[key]), os.path.join(pub, name))
                    card[key] = name
                    img_n += 1
            for side in ("home", "away"):
                if card.get(side, {}).get("logo"):
                    name = f"img_{img_n:02d}{os.path.splitext(card[side]['logo'])[1]}"
                    shutil.copyfile(p(card[side]["logo"]), os.path.join(pub, name))
                    card[side] = {**card[side], "logo": name}
                    img_n += 1
            if card.get("at_words"):
                card["at"] = [round(words[i]["s"] - start, 3) for i in card.pop("at_words")]
            beat["card"] = card
        beats.append(beat)

    # ---- sounds ----
    sfx = [dict(s) for s in plan.get("sfx", [])]
    if plan.get("auto_sfx", True):
        prev = None
        for b in beats:
            if prev is not None and (b["layout"] != prev["layout"] or bool(b.get("card")) != bool(prev.get("card"))):
                sfx.append({"role": "whoosh", "at": max(0.0, b["start"] - 0.12), "vol": 0.45})
            if b.get("card"):
                sfx.append({"role": "pop", "at": b["start"] + 0.05, "vol": 0.5})
                if b["card"]["type"] == "checklist":
                    n = len(b["card"]["items"])
                    ats = b["card"].get("at") or [(10 + i * ((b["end"] - b["start"]) * 30 - 15) / n) / 30 for i in range(n)]
                    for t in ats:
                        sfx.append({"role": "ding", "at": b["start"] + t, "vol": 0.3})
            prev = b
    out_sfx = []
    if sfx:
        index_path = plan.get("sfx_index", sfx_index.DEFAULT_INDEX)
        lib = {x["path"]: x for x in sfx_index.load(index_path)["sounds"]} if os.path.exists(index_path) else {}
        for k, s in enumerate(sfx):
            if s.get("role"):
                if not lib:
                    print("no sound index - skipping role sounds (run motion-edit/scripts/sfx_index.py build <folder>)")
                    continue
                seed = "" if s["role"] in ("click", "pop", "ding") else f"{s['at']:.2f}"
                picked = sfx_index.pick(s["role"], 1, seed, index_path)
                if not picked:
                    continue
                path = picked[0]
                gain = 10 ** (max(-18, min(18, -8 - lib[path]["f"]["peak_db"])) / 20)
            else:
                path = p(os.path.join(plan.get("sfx_dir", "sfx"), s["file"]))
                gain = 1.0
            name = f"sfx_{k:02d}{os.path.splitext(path)[1]}"
            shutil.copyfile(path, os.path.join(pub, name))
            out_sfx.append({"src": name, "at": round(s["at"], 3), "vol": round(min(1.0, s.get("vol", 0.5) * gain), 4)})

    accent = plan.get("accent", "red")
    props = {
        "duration": round(total, 3), "video": "source.mp4", "audio": "voice.wav",
        "faceY": plan.get("face_y", 0.35), "accent": THEMES.get(accent, accent),
        "words": [{k: w[k] for k in ("w", "s", "e", "brk") if k in w} for w in words],
        "keywords": plan.get("keywords", []), "beats": beats,
        "progress": plan.get("progress", True), "rec": plan.get("rec", 0), "sfx": out_sfx,
    }
    if plan.get("music"):
        ext = os.path.splitext(plan["music"])[1]
        shutil.copyfile(p(plan["music"]), os.path.join(pub, "music" + ext))
        props["music"] = "music" + ext
        props["musicVol"] = plan.get("music_vol", 0.08)
    props_file = os.path.join(pub, "_studio.json")
    json.dump(props, open(props_file, "w", encoding="utf-8"), ensure_ascii=False)

    out = p(plan.get("out", "studio.mp4"))
    if a.still is not None:
        still = os.path.splitext(out)[0] + f"_still_{a.still:.1f}.png"
        subprocess.run([NPX, "remotion", "still", "src/index.ts", "Studio", still, f"--props={props_file}",
                        f"--frame={int(a.still * 30)}", "--log=error"], cwd=proj, check=True)
        print(f"still -> {still}")
        return
    raw_out = os.path.splitext(out)[0] + "_raw.mp4"
    subprocess.run([NPX, "remotion", "render", "src/index.ts", "Studio", raw_out, f"--props={props_file}",
                    "--codec=h264", "--crf=18", "--log=error", "--concurrency=50%"], cwd=proj, check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw_out, "-c:v", "copy", "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out],
                   check=True)
    os.remove(raw_out)
    with open(os.path.splitext(out)[0] + ".beats.json", "w", encoding="utf-8") as f:
        json.dump({"beats": beats, "sfx": out_sfx}, f, ensure_ascii=False, indent=1)
    print(f"done: {len(beats)} beats, {len(out_sfx)} sounds, {total:.1f}s -> {out}")


if __name__ == "__main__":
    main()
