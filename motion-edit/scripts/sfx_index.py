"""Index a sound-effects library by role, so edits can ask for "a whoosh" instead of a file name.

  python sfx_index.py build  FOLDER [FOLDER ...] [--index PATH]   -> scan & classify (adds to the index)
  python sfx_index.py stats  [--index PATH]                         -> how many sounds per role
  python sfx_index.py pick   ROLE [--n 5] [--index PATH]            -> best matches for a role
  python sfx_index.py audition ROLE OUT.mp3 [--n 10] [--index PATH] -> the top N back to back, to listen
  python sfx_index.py ban    FILE_SUBSTRING [--index PATH]          -> never pick this sound again

Roles: whoosh, pop, click, impact, riser, ding, negative, glitch, typing, camera, notify.
The index lives at ~/.ametab-video/sfx_index.json by default (it stays on this computer,
the sounds are never copied or uploaded). Classification = file/folder name keywords
+ a quick audio analysis (length, attack, brightness, noisiness, rising energy).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np

DEFAULT_INDEX = os.path.join(os.path.expanduser("~"), ".ametab-video", "sfx_index.json")
EXT = (".wav", ".mp3", ".m4a", ".aif", ".aiff", ".ogg", ".flac")
SR = 16000

KEYWORDS = {
    "whoosh": ["whoosh", "swoosh", "swish", "whip", "woosh", "swipe", "transition", "pass by", "passby", "fly"],
    "pop": ["pop", "bubble", "blip", "pluck", "plop", "boop", "tick"],
    "click": ["click", "button", "switch", "tap", "toggle", "press", "key press", "mouse", "telephonebutton"],
    "impact": ["impact", "hit", "boom", "punch", "slam", "thud", "kick", "drum", "percussion", "stomp", "bass drop", "drop", "sword"],
    "riser": ["riser", "rise", "rising", "build", "sweep up", "upsweep", "charge", "power up", "powerup", "tension", "slide whistle"],
    "ding": ["ding", "chime", "bell", "positive", "success", "correct", "sparkle", "shine", "magic", "musical"],
    "negative": ["negative", "error", "wrong", "fail", "buzzer", "denied", "alarm"],
    "glitch": ["glitch", "digital", "data", "static", "scifi", "sci-fi", "computer", "robot", "distort", "tv", "television"],
    "typing": ["typing", "keyboard", "typewriter", "keys"],
    "camera": ["camera", "shutter", "photo", "snapshot"],
    "notify": ["notification", "notify", "alert", "message", "ringtone", "inquiry", "beep"],
}
# what each role should sound like: (min_s, max_s, attack 'fast'|'slow'|None, noisy True|False|None, rising)
SHAPE = {
    "whoosh": (0.25, 2.0, "slow", True, None),
    "pop": (0.04, 0.45, "fast", False, None),
    "click": (0.02, 0.3, "fast", None, None),
    "impact": (0.15, 3.0, "fast", None, False),
    "riser": (0.8, 6.0, "slow", None, True),
    "ding": (0.2, 3.0, "fast", False, False),
    "negative": (0.1, 2.0, None, None, None),
    "glitch": (0.1, 1.5, None, True, None),
    "typing": (0.5, 5.0, None, None, None),
    "camera": (0.1, 0.8, "fast", None, None),
    "notify": (0.1, 2.5, None, False, None),
}


def features(path):
    try:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-t", "8", "-ac", "1", "-ar", str(SR),
                              "-f", "f32le", "-"], capture_output=True, timeout=30).stdout
    except Exception:
        return None
    y = np.frombuffer(raw, np.float32)
    if len(y) < SR * 0.02:
        return None
    hop = SR // 100
    n = len(y) // hop
    env = np.sqrt((y[: n * hop].reshape(n, hop) ** 2).mean(axis=1)) + 1e-6
    db = 20 * np.log10(env)
    peak = db.max()
    alive = np.where(db > peak - 30)[0]
    dur = (alive[-1] - alive[0] + 1) / 100 if len(alive) else len(y) / SR
    attack = (int(np.argmax(db)) - (alive[0] if len(alive) else 0)) / 100
    spec = np.abs(np.fft.rfft(y[: min(len(y), SR * 2)] * np.hanning(min(len(y), SR * 2))))
    freqs = np.fft.rfftfreq(min(len(y), SR * 2), 1 / SR)
    centroid = float((spec * freqs).sum() / (spec.sum() + 1e-9))
    flat = float(np.exp(np.log(spec + 1e-9).mean()) / (spec.mean() + 1e-9))  # 0 tonal .. 1 noise
    half = len(env) // 2
    rising = bool(half > 5 and env[half:].mean() > env[:half].mean() * 1.6 and attack > dur * 0.5)
    return {"dur": round(float(dur), 3), "attack": round(float(attack), 3), "centroid": round(centroid),
            "flat": round(flat, 3), "rising": rising, "peak_db": round(float(peak), 1)}


def role_scores(name, f):
    # "WhipWhooshMulti_S011FO.972" -> "whip whoosh multi s011fo 972"; match keywords at word starts only
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
    text = re.sub(r"[_\-.()#]+", " ", text).lower()
    out = {}
    for role, words in KEYWORDS.items():
        kw = sum(1 for w in words if re.search(r"\b" + re.escape(w), text))
        lo, hi, attack, noisy, rising = SHAPE[role]
        fit = 0.0
        if f:
            fit += 1.0 if lo <= f["dur"] <= hi else -1.0
            if attack == "fast":
                fit += 0.5 if f["attack"] < 0.05 else -0.5
            if attack == "slow":
                fit += 0.5 if f["attack"] > 0.12 else -0.5
            if noisy is True:
                fit += 0.5 if f["flat"] > 0.25 else -0.3
            if noisy is False:
                fit += 0.5 if f["flat"] < 0.2 else -0.3
            if rising is True:
                fit += 1.0 if f["rising"] else -1.0
            if rising is False and f["rising"]:
                fit -= 0.5
        out[role] = round(2.0 * min(kw, 2) + fit, 2)
    return out


def load(index):
    if os.path.exists(index):
        return json.load(open(index, encoding="utf-8"))
    return {"sounds": [], "banned": []}


def save(data, index):
    os.makedirs(os.path.dirname(index), exist_ok=True)
    json.dump(data, open(index, "w", encoding="utf-8"), ensure_ascii=False)


def build(folders, index):
    data = load(index)
    known = {s["path"] for s in data["sounds"]}
    files = []
    for folder in folders:
        for root, _, names in os.walk(folder):
            for nm in names:
                if nm.lower().endswith(EXT):
                    p = os.path.abspath(os.path.join(root, nm))
                    if p not in known:
                        files.append(p)
    print(f"analysing {len(files)} new sounds...")

    def one(p):
        f = features(p)
        # the parent folder name ("Percussion", "Button"...) is as telling as the file name
        sc = role_scores(os.path.basename(os.path.dirname(p)) + " " + os.path.basename(p), f)
        best = max(sc, key=sc.get)
        return {"path": p, "name": os.path.basename(p), "f": f, "scores": sc,
                "role": best if sc[best] >= 3.5 else None}

    with ThreadPoolExecutor(max_workers=8) as ex:
        for k, item in enumerate(ex.map(one, files)):
            data["sounds"].append(item)
            if (k + 1) % 500 == 0:
                print(f"  {k + 1}/{len(files)}")
    save(data, index)
    stats(index)


def stats(index):
    data = load(index)
    counts = {}
    for s in data["sounds"]:
        counts[s["role"] or "(unsorted)"] = counts.get(s["role"] or "(unsorted)", 0) + 1
    print(f"{len(data['sounds'])} sounds in {index}")
    for r, c in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {r:10s} {c}")


def ranked(role, index):
    data = load(index)
    banned = data.get("banned", [])
    ok = [s for s in data["sounds"] if s["f"] and not any(b in s["path"] for b in banned)]
    # a name/folder match is far more reliable than the audio shape alone: it qualifies the sound,
    # the full score (name + shape) only orders them. Shape-only matches are a fallback for rare roles.
    def named(s):
        return role_scores(os.path.basename(os.path.dirname(s["path"])) + " " + s["name"], None)[role] >= 2
    pool = [s for s in ok if named(s)]
    if len(pool) < 5:
        pool = [s for s in ok if s["scores"].get(role, -9) >= 1.5]
    # strongest fit first; among equals prefer cleaner (louder peak, sensible length)
    pool.sort(key=lambda s: (-s["scores"][role], -s["f"]["peak_db"]))
    return pool


def pick(role, n=1, seed="", index=DEFAULT_INDEX):
    """Deterministic but varied choice: the same seed gives the same sound, different seeds rotate
    through the top matches."""
    pool = ranked(role, index)[: max(8, n)]
    if not pool:
        return []
    h = int(hashlib.md5(f"{role}:{seed}".encode()).hexdigest(), 16)
    start = h % len(pool)
    return [pool[(start + i) % len(pool)]["path"] for i in range(min(n, len(pool)))]


def audition(role, out, n, index):
    paths = [s["path"] for s in ranked(role, index)[:n]]
    if not paths:
        print("nothing for", role)
        return
    args, labels = [], []
    for i, p in enumerate(paths):
        args += ["-i", p]
        labels.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,apad=pad_dur=0.6[a{i}];")
    graph = "".join(labels) + "".join(f"[a{i}]" for i in range(len(paths))) + f"concat=n={len(paths)}:v=0:a=1[o]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", graph, "-map", "[o]", out], check=True)
    for i, p in enumerate(paths):
        print(f"{i + 1:2d}. {os.path.basename(p)}")
    print(f"-> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "stats", "pick", "audition", "ban"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--index", default=DEFAULT_INDEX)
    ap.add_argument("--n", type=int, default=5)
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.args, a.index)
    elif a.cmd == "stats":
        stats(a.index)
    elif a.cmd == "pick":
        for p in pick(a.args[0], a.n, "", a.index):
            print(p)
    elif a.cmd == "audition":
        audition(a.args[0], a.args[1], a.n, a.index)
    elif a.cmd == "ban":
        d = load(a.index)
        d.setdefault("banned", []).append(a.args[0])
        save(d, a.index)
        print("banned:", a.args[0])
