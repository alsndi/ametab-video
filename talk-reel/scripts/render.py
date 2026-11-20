"""Cut silences, build colorful word captions and render a 9:16 reel in one ffmpeg pass.

Usage:
  python render.py INPUT_VIDEO WORDS_JSON OUT_VIDEO [--brand brand.json]
                   [--gap 0.35] [--pad 0.08] [--drop-fillers] [--no-cut] [--crf 18]

WORDS_JSON comes from transcribe.py (you may hand-edit the words to fix spelling;
keep "s"/"e" times). Writes OUT_VIDEO plus OUT_VIDEO.ass and OUT_VIDEO.plan.json next to it.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BRAND = os.path.join(HERE, "..", "brand.json")

FILLERS = {"اه", "آه", "ااه", "ام", "امم", "اممم", "ممم", "مم", "هممم", "um", "uh", "uhm", "eh"}


def clean(word):
    return re.sub(r"[\{\}\\]", "", word).strip()


def bare(word):
    return re.sub(r"[^\w]", "", word, flags=re.UNICODE).lower()


def ass_color(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def ass_time(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_segments(words, duration, gap, pad):
    segs = []
    for w in words:
        s = max(0.0, w["s"] - pad)
        e = min(duration, w["e"] + pad)
        if segs and s - segs[-1][1] < gap:
            segs[-1][1] = max(segs[-1][1], e)
        else:
            segs.append([s, e])
    return segs


def remap(words, segs):
    """Move word times onto the cut timeline."""
    out, offset, i = [], 0.0, 0
    offsets = []
    for s, e in segs:
        offsets.append(offset)
        offset += e - s
    for w in words:
        while i < len(segs) - 1 and w["s"] >= segs[i][1]:
            i += 1
        s0, e0 = segs[i]
        ns = offsets[i] + min(max(w["s"], s0), e0) - s0
        ne = offsets[i] + min(max(w["e"], s0), e0) - s0
        out.append({"w": w["w"], "s": ns, "e": max(ne, ns + 0.05)})
    return out, offset


def chunk_words(words, max_words, max_secs):
    chunks, cur = [], []
    for w in words:
        if cur and (
            w.get("brk")  # hand-set in words.json: start a new caption line at this word
            or len(cur) >= max_words
            or w["e"] - cur[0]["s"] > max_secs
            or w["s"] - cur[-1]["e"] > 0.45
            or re.search(r"[.!?؟،,]$", cur[-1]["w"])
        ):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def build_ass(words, brand, total):
    W, H = brand["width"], brand["height"]
    base = ass_color(brand["text_color"])
    outline = ass_color(brand["outline_color"])
    if brand.get("outline_alpha"):  # e.g. "70" = semi-transparent outline, used as a soft glow
        outline = "&H" + brand["outline_alpha"] + outline[4:]
    bold = -1 if brand.get("bold", True) else 0
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {W}",
        f"PlayResY: {H}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Word,{brand['font']},{brand['font_size']},{base},{base},{outline},"
        f"{ass_color(brand['shadow_color']) if brand.get('shadow_color') else '&H80000000'},"
        # Encoding -1 = libass auto base direction; with 1 (LTR) Arabic word order breaks
        # as soon as one word gets its own override tags.
        f"{bold},0,0,0,100,100,0,0,1,{brand['outline']},{brand['shadow']},2,60,60,{brand['margin_v']},-1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    palette = [ass_color(c) for c in brand["palette"]]
    scale = brand.get("highlight_scale", 115)
    # "word": only the current word is colored (palette cycles per chunk).
    # "fill": every word already said stays colored (fill_color) until the chunk ends.
    # "soft": thin white text, words not said yet are faded, the spoken word switches to an elegant
    #         accent font (e.g. Amiri italic) in a soft colour - no thick outline.
    mode = brand.get("highlight_mode", "word")
    fill = mode == "fill"
    soft = mode == "soft"
    if fill or soft:
        palette = [ass_color(brand.get("fill_color", brand["palette"][0]))]
    acc_font = brand.get("accent_font", brand["font"])
    unsaid = brand.get("unsaid_alpha", "&H90&")
    chunks = chunk_words(words, brand["max_words"], brand["max_chunk_seconds"])
    for ci, chunk in enumerate(chunks):
        color = palette[ci % len(palette)]
        next_start = chunks[ci + 1][0]["s"] if ci + 1 < len(chunks) else total
        chunk_end = min(chunk[-1]["e"] + 0.25, next_start)
        for k, w in enumerate(chunk):
            start = chunk[0]["s"] if k == 0 else w["s"]
            end = chunk[k + 1]["s"] if k + 1 < len(chunk) else chunk_end
            if end <= start:
                continue
            parts = []
            for j, other in enumerate(chunk):
                text = clean(other["w"])
                if soft:
                    if j == k:
                        parts.append(f"{{\\fn{acc_font}\\b1\\i1\\c{color}\\fscx{scale}\\fscy{scale}}}{text}"
                                     f"{{\\fn{brand['font']}\\b0\\i0\\c{base}\\fscx100\\fscy100}}")
                    elif j > k:
                        parts.append(f"{{\\1a{unsaid}}}{text}{{\\1a&H00&}}")
                    else:
                        parts.append(text)
                    continue
                if j == k:
                    parts.append(
                        f"{{\\c{color}\\fscx{scale}\\fscy{scale}}}{text}{{\\c{base}\\fscx100\\fscy100}}"
                    )
                elif fill and j < k:
                    parts.append(f"{{\\c{color}}}{text}{{\\c{base}}}")
                else:
                    parts.append(text)
            intro = "{\\fad(70,0)}" if k == 0 else ""
            if soft:
                intro = "{" + (f"\\blur{brand.get('glow_blur', 6)}") + ("\\fad(90,0)" if k == 0 else "") + "}"
            lines.append(
                f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Word,,0,0,0,,{intro}{' '.join(parts)}"
            )
    return "\n".join(lines) + "\n"


def run_ffmpeg(args, graph_path, cwd):
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats"] + args
    new = cmd[:]
    i = new.index("__GRAPH__")
    new[i - 1:i + 1] = ["-/filter_complex", graph_path]
    r = subprocess.run(new, cwd=cwd)
    if r.returncode != 0:
        old = cmd[:]
        old[i - 1:i + 1] = ["-filter_complex_script", graph_path]
        r = subprocess.run(old, cwd=cwd)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("words")
    ap.add_argument("out")
    ap.add_argument("--brand", default=DEFAULT_BRAND)
    ap.add_argument("--gap", type=float, default=0.35, help="pauses longer than this are cut (seconds)")
    ap.add_argument("--pad", type=float, default=0.08, help="breathing room kept around each word")
    ap.add_argument("--drop-fillers", action="store_true")
    ap.add_argument("--no-cut", action="store_true")
    ap.add_argument("--crf", type=int, default=18)
    a = ap.parse_args()

    with open(a.brand, encoding="utf-8") as f:
        brand = json.load(f)
    with open(a.words, encoding="utf-8") as f:
        data = json.load(f)

    words = [w for w in data["words"] if clean(w["w"])]
    if a.drop_fillers:
        words = [w for w in words if bare(w["w"]) not in FILLERS]
    if not words:
        sys.exit("No words to render.")
    duration = data["duration"]

    segs = [[0.0, duration]] if a.no_cut else build_segments(words, duration, a.gap, a.pad)
    new_words, total = remap(words, segs)

    out = os.path.abspath(a.out)
    work = os.path.dirname(out)
    base_name = os.path.basename(out)
    ass_name = base_name + ".ass"
    with open(os.path.join(work, ass_name), "w", encoding="utf-8") as f:
        f.write(build_ass(new_words, brand, total))
    with open(os.path.join(work, base_name + ".plan.json"), "w", encoding="utf-8") as f:
        json.dump(
            {"original": duration, "final": round(total, 3), "cut": round(duration - total, 3),
             "segments": [[round(s, 3), round(e, 3)] for s, e in segs]},
            f, indent=1,
        )

    W, H = brand["width"], brand["height"]
    g = []
    for i, (s, e) in enumerate(segs):
        g.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}];")
        g.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}];")
    g.append("".join(f"[v{i}][a{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[vc][ac];")
    g.append(
        f"[vc]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
        f"ass={ass_name}[vo];"
    )
    g.append("[ac]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[ao]")
    graph_name = base_name + ".graph.txt"
    with open(os.path.join(work, graph_name), "w", encoding="utf-8") as f:
        f.write("\n".join(g))

    code = run_ffmpeg(
        ["-i", os.path.abspath(a.video), "-filter_complex", "__GRAPH__",
         "-map", "[vo]", "-map", "[ao]",
         "-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf), "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", base_name],
        graph_name, work,
    )
    if code != 0:
        sys.exit("ffmpeg failed")
    print(f"done: {out}  ({duration:.1f}s -> {total:.1f}s, {len(segs)} segments)")


if __name__ == "__main__":
    main()
