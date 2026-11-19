"""Transcribe a video to word-level timestamps.

Usage: python transcribe.py INPUT_VIDEO OUT_JSON [--model small] [--lang ar]

Output JSON: {"duration": float, "words": [{"w": str, "s": float, "e": float}, ...]}
Uses faster-whisper if installed, otherwise openai-whisper.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile


def extract_audio(video, wav):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000", wav],
        check=True,
    )


def duration_of(video):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def with_faster_whisper(wav, model_name, lang):
    from faster_whisper import WhisperModel

    import numpy as np

    # Decode with ffmpeg ourselves: faster-whisper's PyAV decoder breaks with some av versions.
    pcm = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", wav, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, check=True,
    ).stdout
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

    def run(device, compute_type):
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
        segments, _ = model.transcribe(audio, language=lang, word_timestamps=True, vad_filter=False)
        words = []
        for seg in segments:
            for w in seg.words or []:
                words.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)})
        return words

    try:
        return run("auto", "auto")
    except RuntimeError as err:  # GPU found but CUDA libraries missing
        print(f"GPU failed ({err}); using CPU", file=sys.stderr)
        return run("cpu", "int8")


def with_openai_whisper(wav, model_name, lang):
    import whisper

    model = whisper.load_model(model_name)
    result = model.transcribe(wav, language=lang, word_timestamps=True)
    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            words.append({"w": w["word"].strip(), "s": round(w["start"], 3), "e": round(w["end"], 3)})
    return words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--model", default="small")
    ap.add_argument("--lang", default="ar")
    a = ap.parse_args()

    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "audio.wav")
        extract_audio(a.video, wav)
        try:
            words = with_faster_whisper(wav, a.model, a.lang)
        except ImportError:
            try:
                words = with_openai_whisper(wav, a.model, a.lang)
            except ImportError:
                sys.exit("No Whisper installed. Run: pip install faster-whisper  (or: pip install openai-whisper)")

    words = [w for w in words if w["w"]]
    data = {"duration": duration_of(a.video), "words": words}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"{len(words)} words -> {a.out}")


if __name__ == "__main__":
    main()
