"""Put an image / screenshot / video BEHIND the speaker (green-screen look without a green screen).

Usage: python behind.py behind.json [--still SECONDS]

behind.json (paths relative to its folder; times in the source video)
{
  "source": "../video.mp4",
  "segments": [
    {"start": 2.0, "end": 6.5, "bg": "profile.png"},                          # image
    {"start": 9.0, "end": 14.0, "bg": "screen.mp4", "bg_start": 3.0},          # video (from 3 s in)
    {"start": 20.0, "end": 24.0, "bg": "site.png", "fit": "contain", "pan": true}
  ],
  "dim": 0.15,          # darken the new background a little so the person pops (0 = off)
  "blur": 0,            # blur the background (px) - 0 keeps it sharp so it can be read
  "glow": true,         # soft light edge around the person so the cut-out sits naturally
  "out": "behind.mp4"
}
fit: "cover" (fill, crop edges - default) or "contain" (whole image visible on a blurred copy of itself;
     align "top" (default, shows above the head) | "center" | "bottom").
pan: slow Ken Burns zoom on images. Outside the segments the original video plays.
The person is cut out with depth-text/scripts/matte.py (Robust Video Matting, on this computer).
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MATTE = os.path.join(HERE, "..", "..", "depth-text", "scripts", "matte.py")
IMG = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    st = d["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    return st["width"], st["height"], st["r_frame_rate"], float(d["format"]["duration"])


def bg_chain(idx, seg, W, H, fps, dim, blur):
    d = seg["end"] - seg["start"]
    fit = seg.get("fit", "cover")
    n = max(1, round(d * float(eval(fps))))
    if fit == "contain":
        c = (f"[{idx}:v]split[bga{idx}][bgb{idx}];"
             f"[bga{idx}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30[bgx{idx}];"
             f"[bgb{idx}]scale={W}:{H}:force_original_aspect_ratio=decrease[bgf{idx}];"
             f"[bgx{idx}][bgf{idx}]overlay=(W-w)/2:{ {'top': '(H-h)*0.06', 'center': '(H-h)/2', 'bottom': '(H-h)*0.94'}[seg.get('align', 'top')] }")
    else:
        c = f"[{idx}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if seg.get("pan") and seg["bg"].lower().endswith(IMG):
        c += (f",scale={W * 2}:{H * 2},zoompan=z='1+0.08*on/{n}':d={n}:x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'"
              f":s={W}x{H}:fps={fps}")
    c += f",fps={fps},trim=duration={d:.3f},setpts=PTS-STARTPTS+{seg['start']}/TB"
    if blur:
        c += f",boxblur={blur}"
    if dim:
        c += f",eq=brightness={-dim}"
    return c + f",format=yuv420p[bg{idx}];"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--still", type=float)
    a = ap.parse_args()
    plan_path = os.path.abspath(a.plan)
    work = os.path.dirname(plan_path)
    p = lambda r: r if os.path.isabs(r) else os.path.join(work, r)  # noqa: E731
    plan = json.load(open(plan_path, encoding="utf-8"))
    src = p(plan["source"])
    W, H, fps, total = probe(src)
    segs = sorted(plan["segments"], key=lambda s: s["start"])
    out = p(plan.get("out", "behind.mp4"))
    base = os.path.splitext(out)[0]

    # one mask for the whole video (simplest to keep in sync); reused if the plan did not change
    mask = base + "_mask.mp4"
    if not os.path.exists(mask):
        subprocess.run([sys.executable, MATTE, src, mask], check=True)

    args = ["-i", src, "-i", mask]
    for s in segs:
        bg = p(s["bg"])
        if bg.lower().endswith(IMG):
            args += ["-loop", "1", "-t", f"{s['end'] - s['start'] + 1:.3f}", "-i", bg]
        else:
            args += ["-ss", str(s.get("bg_start", 0)), "-stream_loop", "-1", "-i", bg]
    g = "[0:v]split[base][src];[1:v]format=gray,scale=%d:%d[m];" % (W, H)
    if plan.get("glow", True):
        # soft light rim: dilate+blur the mask, use it as a faint white halo under the person
        g += "[m]split[m1][m2];[m2]gblur=sigma=6,lutyuv=y='val*0.35'[halo];"
        g += "[src][m1]alphamerge[person];"
    else:
        g += "[src][m]alphamerge[person];"
    cur = "base"
    for k, s in enumerate(segs):
        idx = 2 + k
        g += bg_chain(idx, s, W, H, fps, plan.get("dim", 0.15), plan.get("blur", 0))
        g += (f"[{cur}][bg{idx}]overlay=eof_action=pass:enable='between(t,{s['start']},{s['end']})'[c{k}];")
        cur = f"c{k}"
    when = "+".join(f"between(t,{s['start']},{s['end']})" for s in segs)
    if plan.get("glow", True):
        g += (f"color=white:s={W}x{H}:r={fps}[white];[white][halo]alphamerge[rim];"
              f"[{cur}][rim]overlay=shortest=1:enable='{when}'[cr];")
        cur = "cr"
    g += f"[{cur}][person]overlay=enable='{when}',format=yuv420p[v]"

    if a.still is not None:
        still = f"{base}_still_{a.still:.1f}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", g, "-map", "[v]",
                        "-ss", str(a.still), "-frames:v", "1", "-update", "1", still], check=True)
        print(f"still -> {still}")
        return
    subprocess.run(["ffmpeg", "-v", "error", "-stats", "-y", *args, "-filter_complex", g, "-map", "[v]",
                    "-map", "0:a?", "-t", f"{total:.3f}", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                    "-c:a", "copy", "-movflags", "+faststart", out], check=True)
    print(f"done -> {out}  ({len(segs)} background segment(s))")


if __name__ == "__main__":
    main()
