"""Several versions of one reel for Instagram Trial Reels (shown to non-followers first) or A/B tests.

Usage: python trial.py trial.json

trial.json (paths relative to its folder)
{
  "source": "../video.mp4", "words": "words.json", "word_fixes": {"15": "مفعّليها"},
  "cut": true,                     # remove long pauses (talk-reel logic)
  "hook_seconds": 2.6,             # how long the written hook stays on top
  "variants": [
    {"name": "A-question", "start_word": 0,  "style": "fill",
     "hook": {"title": "ليش بطاريتك", "highlight": "تخلص بسرعة؟"},
     "caption": "first line of the post caption for this version"},
    {"name": "B-result",   "start_word": 3,  "style": "soft",
     "hook": {"title": "بطارية تطوّل", "highlight": "يوم كامل"}},
    {"name": "C-secret",   "start_word": 11, "style": "word",
     "hook": {"title": "إعداد", "highlight": "مخفي"}}
  ],
  "out_dir": "trials"
}
style: fill (Tajawal, words turn yellow) | soft (thin + Amiri accent) | word (colourful current word)
start_word: the version starts at that word (skip a slow opening; test a different first sentence).
Writes trials/<name>.mp4 for each version and trials/TRIALS.md (what each one tests + its caption).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TALK = os.path.join(HERE, "..", "..", "talk-reel")
sys.path.insert(0, os.path.join(TALK, "scripts"))
import render  # noqa: E402

STYLES = {
    "fill": os.path.join(TALK, "brand.json"),
    "soft": os.path.join(TALK, "brand_soft.json"),
}


def brand_for(style):
    if style == "word":
        b = json.load(open(STYLES["fill"], encoding="utf-8"))
        b.update(highlight_mode="word", palette=["#FFD60A", "#00F5D4", "#FF4D9D", "#9B7BFF"], highlight_scale=115)
        return b
    return json.load(open(STYLES[style], encoding="utf-8"))


def hook_lines(hook, seconds, brand, style):
    hi = render.ass_color(brand.get("fill_color", brand["palette"][0]))
    if style == "soft":
        font, size, extra = brand["font"], 110, f"\\blur4\\fn{brand['font']}"
        text = f"{hook['title']} {{\\fn{brand.get('accent_font', brand['font'])}\\i1\\b1\\c{hi}\\fscx210\\fscy210}}{hook.get('highlight', '')}"
        style_line = (f"Style: Hook,{font},{size},&H00FFFFFF,&H00FFFFFF,&H70000000,&H80000000,0,0,0,0,100,100,0,0,1,6,2,8,60,60,250,-1")
    else:
        font, size, extra = brand["font"], 120, ""
        text = f"{hook['title']} {{\\c{hi}}}{hook.get('highlight', '')}"
        style_line = (f"Style: Hook,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,9,4,8,60,60,250,-1")
    ev = (f"Dialogue: 5,0:00:00.00,{render.ass_time(seconds)},Hook,,0,0,0,,"
          f"{{{extra}\\fad(0,250)\\fscx70\\fscy70\\t(0,180,\\fscx105\\fscy105)\\t(180,280,\\fscx100\\fscy100)}}{text}")
    return style_line, ev


def main():
    plan_path = os.path.abspath(sys.argv[1])
    work = os.path.dirname(plan_path)
    p = lambda r: r if os.path.isabs(r) else os.path.join(work, r)  # noqa: E731
    plan = json.load(open(plan_path, encoding="utf-8"))
    src = p(plan["source"])
    data = json.load(open(p(plan["words"]), encoding="utf-8"))
    words_all = data["words"]
    for i, w in plan.get("word_fixes", {}).items():
        words_all[int(i)]["w"] = w
    out_dir = p(plan.get("out_dir", "trials"))
    os.makedirs(out_dir, exist_ok=True)
    report = ["# Trial reels", "", "| النسخة | تبدأ من | الهوك | ستايل الكابشن | المدة | وش تختبر |", "|---|---|---|---|---|---|"]
    captions = []

    for v in plan["variants"]:
        style = v.get("style", "fill")
        brand = brand_for(style)
        sw = v.get("start_word", 0)
        t0 = max(0.0, words_all[sw]["s"] - 0.08) if sw else 0.0
        words = [dict(w, s=w["s"] - t0, e=w["e"] - t0) for w in words_all[sw:] if render.clean(w["w"])]
        dur = data["duration"] - t0
        segs = render.build_segments(words, dur, plan.get("gap", 0.35), plan.get("pad", 0.08)) if plan.get("cut", True) \
            else [[0.0, dur]]
        new_words, total = render.remap(words, segs)

        ass = render.build_ass(new_words, brand, total).rstrip("\n").split("\n")
        if v.get("hook"):
            style_line, ev = hook_lines(v["hook"], plan.get("hook_seconds", 2.6), brand, style)
            i = ass.index("[Events]") - 1
            ass[i:i] = [style_line]
            ass.append(ev)
        name = v["name"]
        ass_name = f"{name}.ass"
        open(os.path.join(out_dir, ass_name), "w", encoding="utf-8").write("\n".join(ass) + "\n")

        W, H = brand["width"], brand["height"]
        g = []
        for k, (a, b) in enumerate(segs):
            g.append(f"[0:v]trim=start={a + t0:.3f}:end={b + t0:.3f},setpts=PTS-STARTPTS[v{k}];")
            g.append(f"[0:a]atrim=start={a + t0:.3f}:end={b + t0:.3f},asetpts=PTS-STARTPTS[a{k}];")
        g.append("".join(f"[v{k}][a{k}]" for k in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[vc][ac];")
        g.append(f"[vc]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,ass={ass_name}[vo];")
        g.append("[ac]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[ao]")
        graph = f"{name}.graph.txt"
        open(os.path.join(out_dir, graph), "w", encoding="utf-8").write("\n".join(g))
        code = render.run_ffmpeg(["-i", src, "-filter_complex", "__GRAPH__", "-map", "[vo]", "-map", "[ao]",
                                  "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                                  "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", f"{name}.mp4"],
                                 graph, out_dir)
        if code:
            sys.exit(f"ffmpeg failed for {name}")
        first = " ".join(w["w"] for w in words[:6])
        hook_txt = f"{v['hook']['title']} {v['hook'].get('highlight', '')}" if v.get("hook") else "—"
        report.append(f"| `{name}` | «{first}…» | {hook_txt} | {style} | {total:.1f}s | {v.get('tests', '')} |")
        if v.get("caption"):
            captions.append(f"**{name}**\n\n```\n{v['caption']}\n```\n")
        print(f"{name}: {total:.1f}s ({len(segs)} cuts) -> {os.path.join(out_dir, name + '.mp4')}")

    report += ["", "## الكابشن لكل نسخة", ""] + captions + [
        "", "## شلون تختبرها", "",
        "1. انشر كل نسخة كـ **Trial Reel** (إنستقرام يعرضها لغير المتابعين أول)، كل وحدة بيوم مختلف أو بفرق ساعات.",
        "2. بعد 24-48 ساعة قارن: نسبة المشاهدة لآخر الفيديو، والحفظ، والمشاركة — مو اللايكات بس.",
        "3. النسخة اللي تفوز انشرها لمتابعينك، واكتب وش الفرق اللي فاز (الهوك؟ أول جملة؟ الستايل؟)."]
    open(os.path.join(out_dir, "TRIALS.md"), "w", encoding="utf-8").write("\n".join(report) + "\n")
    print(f"report -> {os.path.join(out_dir, 'TRIALS.md')}")


if __name__ == "__main__":
    main()
