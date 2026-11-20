"""Text behind you / orbiting around you / rising and fading / cycling colours.

Usage: python depth.py depth.json [--still SECONDS]

depth.json (paths relative to its folder; times are seconds in the SOURCE video)
{
  "source": "../video.mp4",
  "start": 0.0, "end": 4.0,                      # the part that gets the effect (keep it short: 2-8 s)
  "items": [
    {"mode": "behind", "text": "حركة قوية", "start": 0.0, "end": 2.2, "y": 520, "size": 260,
     "colors": ["#FFD60A", "#ff3b4a", "#22d3ee"]},
    {"mode": "orbit",  "text": "بطارية أطول", "start": 2.2, "end": 4.0, "cx": 540, "cy": 600,
     "rx": 430, "ry": 110, "count": 5, "speed": 0.35, "size": 84},
    {"mode": "rise",   "text": "١٠٠٪", "start": 2.5, "end": 4.0, "y": 1350, "size": 150, "front": true}
  ],
  "out": "depth.mp4"
}
Layers: video -> "back" text -> you (cut out with matte.py) -> "front" text.
behind/rise draw on the back layer unless "front": true. orbit splits itself: the half going behind
your head is on the back layer, the half passing in front on the front layer.
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


def probe_size(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip()
    w, h = out.split(",")[:2]
    return int(w), int(h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--still", type=float, help="preview one frame (source seconds) as PNG")
    a = ap.parse_args()
    plan_path = os.path.abspath(a.plan)
    work = os.path.dirname(plan_path)
    p = lambda r: r if os.path.isabs(r) else os.path.join(work, r)  # noqa: E731
    plan = json.load(open(plan_path, encoding="utf-8"))
    src = p(plan["source"])
    s, e = float(plan["start"]), float(plan["end"])
    dur = e - s
    out = p(plan.get("out", "depth.mp4"))
    base = os.path.splitext(out)[0]

    mask = base + "_mask.mp4"
    if not os.path.exists(mask) or os.path.getmtime(mask) < os.path.getmtime(plan_path):
        subprocess.run([sys.executable, os.path.join(HERE, "matte.py"), src, mask, "--start", str(s), "--end", str(e)],
                       check=True)

    proj = os.path.join(work, "motion")
    ensure_project(proj)
    items = []
    for it in plan["items"]:
        it = dict(it)
        it["start"] = round(it["start"] - s, 3)
        it["end"] = round(it["end"] - s, 3)
        items.append(it)
    layers = {}
    for layer in ("back", "front"):
        props = {"duration": round(dur, 3), "layer": layer, "items": items}
        pf = os.path.join(proj, "public", f"_depth_{layer}.json")
        json.dump(props, open(pf, "w", encoding="utf-8"), ensure_ascii=False)
        if a.still is not None:
            png = f"{base}_{layer}.png"
            subprocess.run([NPX, "remotion", "still", "src/index.ts", "DepthText", png, f"--props={pf}",
                            f"--frame={int((a.still - s) * 30)}", "--log=error"], cwd=proj, check=True)
            layers[layer] = png
        else:
            mov = f"{base}_{layer}.mov"
            subprocess.run([NPX, "remotion", "render", "src/index.ts", "DepthText", mov, f"--props={pf}",
                            "--codec=prores", "--prores-profile=4444", "--pixel-format=yuva444p10le",
                            "--image-format=png", "--log=error"], cwd=proj, check=True)
            layers[layer] = mov

    if a.still is not None:
        t = a.still - s
        still = f"{base}_still_{a.still:.1f}.png"
        vw, vh = probe_size(src)
        g = (f"[1:v]format=gray[m];[0:v]split[v0][v1];[v1][m]alphamerge[person];"
             f"[2:v]scale={vw}:{vh}[bk];[3:v]scale={vw}:{vh}[fr];"
             f"[v0][bk]overlay[b1];[b1][person]overlay[b2];[b2][fr]overlay,scale=540:-1")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a.still), "-i", src, "-ss", str(t), "-i", mask,
                        "-i", layers["back"], "-i", layers["front"], "-filter_complex", g, "-frames:v", "1", still],
                       check=True)
        print(f"still -> {still}")
        return

    # text layers are drawn on a 1080x1920 canvas; scale them to the source size (e.g. 720x1280)
    vw, vh = probe_size(src)
    g = (f"[0:v]split[base][src];"
         f"[src]trim=start={s}:duration={dur},setpts=PTS-STARTPTS[seg];"
         f"[1:v]format=gray[m];[seg][m]alphamerge,setpts=PTS+{s}/TB[person];"
         f"[2:v]format=yuva444p,scale={vw}:{vh},setpts=PTS+{s}/TB[back];"
         f"[3:v]format=yuva444p,scale={vw}:{vh},setpts=PTS+{s}/TB[front];"
         f"[base][back]overlay=eof_action=pass:enable='between(t,{s},{e})'[b1];"
         f"[b1][person]overlay=eof_action=pass:enable='between(t,{s},{e})'[b2];"
         f"[b2][front]overlay=eof_action=pass:enable='between(t,{s},{e})',format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-i", mask, "-i", layers["back"], "-i", layers["front"],
                    "-filter_complex", g, "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18",
                    "-preset", "medium", "-c:a", "copy", "-movflags", "+faststart", out], check=True)
    print(f"done -> {out}  (effect {s:.1f}-{e:.1f}s; layers kept: {os.path.basename(layers['back'])}, "
          f"{os.path.basename(layers['front'])})")


if __name__ == "__main__":
    main()
