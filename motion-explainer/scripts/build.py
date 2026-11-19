"""Build a motion-graphics explainer (no filming) from a voiceover and a scene list.

Usage: python build.py explainer.json [--still SECONDS]

explainer.json (paths relative to its folder)
{
  "voice": "vo.m4a", "words": "words.json",       # optional; without them give every scene "start"/"end"
  "word_fixes": {"3": "آيفون"}, "line_breaks": [8],
  "music": "bed.mp3", "music_vol": 0.12,           # optional
  "scenes": [
    {"type": "title",   "at_word": 0,  "title": "حركة", "highlight": "قوية", "emoji": "⚡"},
    {"type": "phone",   "at_word": 6,  "image": "shot1.png", "caption": "الإعدادات", "taps": [{"x": 0.22, "y": 0.68, "at": 0.9}]},
    {"type": "number",  "at_word": 14, "value": "٥س", "label": "استخدام يومي", "emoji": "📱"},
    {"type": "bullets", "at_word": 20, "title": "الخطوات", "items": ["الإعدادات", "مدة الاستخدام", "قيود المحتوى"]},
    {"type": "compare", "at_word": 30, "left": {"label": "بعد", "value": "١٠س"}, "right": {"label": "قبل", "value": "٦س"}},
    {"type": "icon",    "at_word": 38, "emoji": "❤️", "text": "لايك وشارك"}
  ],
  "tail": 0.6, "out": "explainer.mp4"
}
A scene starts at its "at_word" (that word's start time) or "start" (seconds) and lasts until the next scene.
--still S: only render one frame at S seconds to OUT_still.png (fast layout check).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "..", "motion-edit", "remotion")
NPX = "npx.cmd" if os.name == "nt" else "npx"
NPM = "npm.cmd" if os.name == "nt" else "npm"


def ensure_project(work):
    if not os.path.exists(os.path.join(work, "package.json")):
        shutil.copytree(TEMPLATE, work, dirs_exist_ok=True)
    else:
        shutil.copytree(os.path.join(TEMPLATE, "src"), os.path.join(work, "src"), dirs_exist_ok=True)
    if not os.path.exists(os.path.join(work, "node_modules", "remotion")):
        print("npm install (first time only)...")
        subprocess.run([NPM, "install", "--no-fund", "--no-audit"], cwd=work, check=True)
    os.makedirs(os.path.join(work, "public"), exist_ok=True)


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

    props = {"scenes": []}
    words = []
    if plan.get("words"):
        words = json.load(open(p(plan["words"]), encoding="utf-8"))["words"]
        for i, w in plan.get("word_fixes", {}).items():
            words[int(i)]["w"] = w
        for i in plan.get("line_breaks", []):
            words[i]["brk"] = True
        props["words"] = [{k: w[k] for k in ("w", "s", "e", "brk") if k in w} for w in words]
    if plan.get("voice"):
        ext = os.path.splitext(plan["voice"])[1]
        shutil.copyfile(p(plan["voice"]), os.path.join(pub, "voice" + ext))
        props["voice"] = "voice" + ext
    if plan.get("music"):
        ext = os.path.splitext(plan["music"])[1]
        shutil.copyfile(p(plan["music"]), os.path.join(pub, "music" + ext))
        props["music"] = "music" + ext
        props["musicVol"] = plan.get("music_vol", 0.12)

    starts = []
    for s in plan["scenes"]:
        if "at_word" in s:
            starts.append(words[s["at_word"]]["s"] if s["at_word"] else 0.0)
        elif "start" in s:
            starts.append(float(s["start"]))
        else:
            sys.exit(f"scene {s} needs at_word or start")
    if words:
        total = words[-1]["e"] + float(plan.get("tail", 0.6))
    else:
        total = float(plan.get("duration") or plan["scenes"][-1].get("end", starts[-1] + 3))
    for k, s in enumerate(plan["scenes"]):
        sc = {kk: vv for kk, vv in s.items() if kk not in ("at_word",)}
        sc["start"] = round(starts[k], 3)
        sc["end"] = round(starts[k + 1] if k + 1 < len(starts) else total, 3)
        if sc["type"] == "phone":
            name = "img_%02d%s" % (k, os.path.splitext(sc["image"])[1])
            shutil.copyfile(p(sc["image"]), os.path.join(pub, name))
            sc["image"] = name
        props["scenes"].append(sc)
    props["duration"] = round(total, 3)
    props_file = os.path.join(pub, "_explainer.json")
    json.dump(props, open(props_file, "w", encoding="utf-8"), ensure_ascii=False)

    out = p(plan.get("out", "explainer.mp4"))
    if a.still is not None:
        still = os.path.splitext(out)[0] + f"_still_{a.still:.1f}.png"
        subprocess.run([NPX, "remotion", "still", "src/index.ts", "Explainer", still, f"--props={props_file}",
                        f"--frame={int(a.still * 30)}", "--log=error"], cwd=proj, check=True)
        print(f"still -> {still}")
        return
    raw = os.path.splitext(out)[0] + "_raw.mp4"
    subprocess.run([NPX, "remotion", "render", "src/index.ts", "Explainer", raw, f"--props={props_file}",
                    "--codec=h264", "--crf=17", "--log=error"], cwd=proj, check=True)
    # loudness for social: -14 LUFS, video stream copied as is
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-c:v", "copy", "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out],
                   check=True)
    os.remove(raw)
    print(f"done: {len(props['scenes'])} scenes, {total:.1f}s -> {out}")


if __name__ == "__main__":
    main()
