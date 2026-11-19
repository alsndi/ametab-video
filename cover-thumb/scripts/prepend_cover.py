"""Put the cover image as the very first frames of a reel (so it can be picked as the cover
from inside the video, and shows while the reel loads).

Usage: python prepend_cover.py REEL.mp4 COVER.png OUT.mp4 [--seconds 0.1]
"""
import argparse
import subprocess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reel")
    ap.add_argument("cover")
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=0.1)
    a = ap.parse_args()

    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height,r_frame_rate", "-of", "csv=p=0", a.reel],
                           capture_output=True, text=True, check=True).stdout.strip().split(",")
    w, h, fps = probe[0], probe[1], probe[2]
    graph = (f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps},"
             f"trim=duration={a.seconds},format=yuv420p[cv];"
             f"anullsrc=r=48000:cl=stereo,atrim=duration={a.seconds}[ca];"
             f"[0:v]setsar=1,format=yuv420p[mv];[0:a]aresample=48000[ma];"
             f"[cv][ca][mv][ma]concat=n=2:v=1:a=1[v][a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.reel, "-loop", "1", "-i", a.cover,
                    "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", a.out], check=True)
    print(f"done -> {a.out}")


if __name__ == "__main__":
    main()
