"""Render a reel cover (1080x1920) and three YouTube thumbnails (1280x720) from one frame.

Usage:
  python make_covers.py IMAGE OUT_DIR --title "حركة" --highlight "قوية"
         [--tag "جرّبها"] [--emoji "🔋"] [--face-x 0.5] [--face-y 0.3] [--work DIR]
         [--look studio --accent green --rec]

--face-x/--face-y: where the face center is in IMAGE (0..1), read off the frame.
--work: folder that holds (or will hold) a copy of the Remotion template; defaults to
        OUT_DIR/../motion. The template is copied and `npm install`ed the first time.
Writes OUT_DIR/cover_reel.png, thumb_side.png, thumb_bold.png, thumb_split.png
and OUT_DIR/cover_grid_check.png (the reel cover with the 1:1 and 3:4 grid crops drawn).
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
    else:  # refresh the source files so new templates are there
        shutil.copytree(os.path.join(TEMPLATE, "src"), os.path.join(work, "src"), dirs_exist_ok=True)
    if not os.path.exists(os.path.join(work, "node_modules", "remotion")):
        print("npm install (first time only)...")
        subprocess.run([NPM, "install", "--no-fund", "--no-audit"], cwd=work, check=True)
    os.makedirs(os.path.join(work, "public"), exist_ok=True)


def still(work, comp, props, out):
    props_file = os.path.join(work, "public", "_props.json")
    with open(props_file, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False)
    r = subprocess.run([NPX, "remotion", "still", "src/index.ts", comp, out, f"--props={props_file}", "--log=error"],
                       cwd=work)
    if r.returncode:
        sys.exit(f"remotion still failed for {comp}")


def grid_check(cover, out):
    # 1:1 crop (yellow) and 3:4 crop (cyan) as the profile grid shows them
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", cover, "-vf",
                    "drawbox=x=0:y=420:w=1080:h=1080:c=yellow:t=8,drawbox=x=0:y=240:w=1080:h=1440:c=cyan:t=6,scale=540:-1",
                    out], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--title", required=True)
    ap.add_argument("--highlight", required=True)
    ap.add_argument("--tag")
    ap.add_argument("--emoji")
    ap.add_argument("--face-x", type=float, default=0.5)
    ap.add_argument("--face-y", type=float, default=0.3)
    ap.add_argument("--work")
    ap.add_argument("--look", choices=["classic", "studio"], default="classic",
                    help="classic: yellow word + black stroke. studio: word on an accent box (Ametab studio style)")
    ap.add_argument("--accent", default="red", help="studio accent: red|green|cyan|blue|orange|yellow|purple|#hex")
    ap.add_argument("--rec", action="store_true", help="studio: green REC corners on the reel cover")
    a = ap.parse_args()

    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    work = os.path.abspath(a.work or os.path.join(out, "..", "motion"))
    ensure_project(work)
    shutil.copyfile(a.image, os.path.join(work, "public", "cover_src.png"))

    base = {"image": "cover_src.png", "title": a.title, "highlight": a.highlight,
            "faceX": a.face_x, "faceY": a.face_y}
    if a.tag:
        base["tag"] = a.tag
    if a.emoji:
        base["emoji"] = a.emoji
    themes = {"red": "#ff3b4a", "green": "#22c55e", "cyan": "#22d3ee", "blue": "#3b82f6",
              "orange": "#f97316", "yellow": "#FFD60A", "purple": "#a855f7"}
    base["look"] = a.look
    base["accent"] = themes.get(a.accent, a.accent)
    base["rec"] = a.rec

    still(work, "ReelCover", base, os.path.join(out, "cover_reel.png"))
    for layout in ("side", "bold", "split"):
        still(work, "YouTubeThumb", {**base, "layout": layout}, os.path.join(out, f"thumb_{layout}.png"))
    grid_check(os.path.join(out, "cover_reel.png"), os.path.join(out, "cover_grid_check.png"))
    print(f"done -> {out}: cover_reel.png, thumb_side.png, thumb_bold.png, thumb_split.png, cover_grid_check.png")


if __name__ == "__main__":
    main()
