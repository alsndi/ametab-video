"""Look at a video before planning the edit.

  python frames.py cuts  VIDEO                 -> prints hard-cut times (scene changes)
  python frames.py sheet VIDEO OUT.jpg [STEP]  -> contact sheet, one frame every STEP s (default 0.5)
  python frames.py strip VIDEO START OUT.jpg [SECONDS] [FPS]
        -> 8 frames from START with a yellow grid and the time offset printed on each.
           Each frame is 270x480: multiply a grid position by 4 to get 1080x1920 coords.
           Use it to find where a button / row sits and how long it stays still.
"""
import os
import subprocess
import sys

FONT = "C\\:/Windows/Fonts/arial.ttf" if os.name == "nt" else "/System/Library/Fonts/Supplemental/Arial.ttf"


def ff(*args):
    return subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True)


def cuts(video, threshold=0.3):
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", video, "-an", "-vf",
         f"select='gt(scene,{threshold})',metadata=print:file=-", "-f", "null", "-"],
        capture_output=True, text=True)
    times = [line.split("pts_time:")[1] for line in r.stdout.splitlines() if "pts_time:" in line]
    print("cuts:", ", ".join(f"{float(t):.2f}" for t in times) or "none")


def sheet(video, out, step=0.5):
    r = ff("-i", video, "-vf", f"fps=1/{step},scale=135:240,tile=10x8", "-frames:v", "1", out)
    print(r.stderr or f"sheet -> {out} (row-major, {step}s per frame, 80 frames max)")


def strip(video, start, out, seconds=1.6, fps=5):
    vf = (f"fps={fps},scale=270:480,drawgrid=w=27:h=48:t=1:c=yellow@0.4,"
          f"drawtext=fontfile='{FONT}':text='+%{{pts\\:flt}}':x=5:y=440:fontsize=24:fontcolor=red:box=1,"
          f"tile=8x1")
    r = ff("-ss", str(start), "-t", str(seconds), "-i", video, "-vf", vf, "-frames:v", "1", out)
    if r.returncode:  # drawtext needs a font file; fall back to the grid only
        vf = f"fps={fps},scale=270:480,drawgrid=w=27:h=48:t=1:c=yellow@0.4,tile=8x1"
        r = ff("-ss", str(start), "-t", str(seconds), "-i", video, "-vf", vf, "-frames:v", "1", out)
    print(r.stderr or f"strip -> {out} (frame k = {start} + k/{fps} s; grid cell = 27x48 -> x4 for full res)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, video = sys.argv[1], sys.argv[2]
    if cmd == "cuts":
        cuts(video)
    elif cmd == "sheet":
        sheet(video, sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 0.5)
    elif cmd == "strip":
        strip(video, float(sys.argv[3]), sys.argv[4],
              float(sys.argv[5]) if len(sys.argv) > 5 else 1.6, int(sys.argv[6]) if len(sys.argv) > 6 else 5)
    else:
        sys.exit(__doc__)
