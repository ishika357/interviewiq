"""Speech Agent: ffmpeg conversion, Whisper transcription (if installed), and speech analytics.

Speech analytics describe *how the answer was delivered* (pace, fillers, pauses, repetition).
They deliberately make no claims about emotion, honesty, personality or confidence.
"""
from __future__ import annotations

import logging
import re
import subprocess
import tempfile
import threading
from pathlib import Path

from .textutil import tokenize

log = logging.getLogger("interviewiq.speech")

FILLERS_SINGLE = {"um", "uh", "umm", "uhh", "er", "erm", "ah", "hmm", "basically", "actually", "literally"}
FILLERS_MULTI = ["you know", "i mean", "kind of", "sort of", "like i said"]

_model = None
_model_kind = None
_model_lock = threading.Lock()


def whisper_available() -> bool:
    for name in ("faster_whisper", "whisper"):
        try:
            __import__(name)
            return True
        except Exception:
            continue
    return False


def _load_model(size: str):
    global _model, _model_kind
    with _model_lock:
        if _model is not None:
            return _model, _model_kind
        try:
            from faster_whisper import WhisperModel  # type: ignore

            _model, _model_kind = WhisperModel(size, device="cpu", compute_type="int8"), "faster"
        except Exception:
            import whisper  # type: ignore

            _model, _model_kind = whisper.load_model(size), "openai"
        return _model, _model_kind


def convert_to_wav(src: Path, dst: Path) -> None:
    """WebM/MP4/OGG -> 16 kHz mono WAV, the format Whisper expects."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ar", "16000", "-ac", "1", str(dst)]
    res = subprocess.run(cmd, capture_output=True, timeout=90)
    if res.returncode != 0:
        raise RuntimeError("ffmpeg could not decode the audio: " + res.stderr.decode(errors="ignore")[:200])


def transcribe_file(audio_bytes: bytes, suffix: str, model_size: str = "base") -> dict:
    """Return {ok, text, segments, duration, error}. Never raises."""
    if not whisper_available():
        return {"ok": False, "error": "Whisper is not installed on the server. Type your answer instead.", "text": "", "segments": []}
    try:
        with tempfile.TemporaryDirectory(prefix="iiq_audio_") as tmp:
            src, wav = Path(tmp) / f"in{suffix}", Path(tmp) / "out.wav"
            src.write_bytes(audio_bytes)
            convert_to_wav(src, wav)
            model, kind = _load_model(model_size)
            segments = []
            if kind == "faster":
                seg_iter, info = model.transcribe(str(wav), vad_filter=True)
                for s in seg_iter:
                    segments.append({"start": s.start, "end": s.end, "text": s.text.strip()})
                duration = info.duration
            else:
                result = model.transcribe(str(wav), fp16=False)
                segments = [{"start": s["start"], "end": s["end"], "text": s["text"].strip()} for s in result.get("segments", [])]
                duration = segments[-1]["end"] if segments else 0.0
            text = " ".join(s["text"] for s in segments).strip()
            return {"ok": True, "text": text, "segments": segments, "duration": duration, "error": None}
    except Exception as exc:
        log.exception("Transcription failed")
        return {"ok": False, "error": f"Transcription failed: {exc}", "text": "", "segments": []}


def analyze(text: str, duration_sec: float | None, segments: list[dict] | None = None) -> dict:
    """Compute delivery metrics. `duration_sec` is None for typed answers."""
    words = tokenize(text)
    n = len(words)
    low = " ".join(words)
    fillers: dict[str, int] = {}
    for w in words:
        if w in FILLERS_SINGLE:
            fillers[w] = fillers.get(w, 0) + 1
    for phrase in FILLERS_MULTI:
        c = len(re.findall(r"\b" + re.escape(phrase) + r"\b", low))
        if c:
            fillers[phrase] = c
    filler_total = sum(fillers.values())

    # repeated phrases: any 3-word phrase (not made of stop words only) used 2+ times
    from .textutil import STOP
    grams: dict[str, int] = {}
    for i in range(n - 2):
        g = words[i : i + 3]
        if sum(1 for w in g if w not in STOP) >= 2:
            grams[" ".join(g)] = grams.get(" ".join(g), 0) + 1
    repeated = sorted(((g, c) for g, c in grams.items() if c >= 2), key=lambda x: -x[1])[:3]
    immediate = sum(1 for a, b in zip(words, words[1:]) if a == b and a not in STOP)  # "the the", "model model"

    out = {
        "word_count": n,
        "filler_counts": fillers,
        "filler_total": filler_total,
        "filler_per_100": round(100 * filler_total / n, 1) if n else 0.0,
        "repeated_phrases": [{"phrase": g, "count": c} for g, c in repeated],
        "immediate_repeats": immediate,
        "duration_sec": round(duration_sec, 1) if duration_sec else None,
        "wpm": None,
        "pauses": None,
        "long_pauses": None,
        "source": "audio" if duration_sec else "text",
    }
    if duration_sec and duration_sec >= 3 and n:
        out["wpm"] = round(n / (duration_sec / 60.0))
    if segments and len(segments) > 1:
        gaps = [b["start"] - a["end"] for a, b in zip(segments, segments[1:])]
        out["pauses"] = sum(1 for g in gaps if g >= 0.7)
        out["long_pauses"] = sum(1 for g in gaps if g >= 2.0)
    out["feedback"] = _feedback(out)
    return out


def _feedback(m: dict) -> list[str]:
    tips = []
    if m["word_count"] < 15:
        tips.append("Your answer was very short. Aim for 4-6 sentences: definition, how it works, and a quick example.")
    if m["wpm"]:
        if m["wpm"] < 100:
            tips.append(f"Your pace was about {m['wpm']} words per minute, which is on the slower side. A pace of 110-160 usually sounds natural.")
        elif m["wpm"] > 175:
            tips.append(f"Your pace was about {m['wpm']} words per minute, which is fast. Slow down slightly so key points land.")
        else:
            tips.append(f"Your pace of about {m['wpm']} words per minute is comfortable to follow.")
    if m["filler_per_100"] >= 4:
        top = ", ".join(f"'{k}' x{v}" for k, v in sorted(m["filler_counts"].items(), key=lambda x: -x[1])[:3])
        tips.append(f"Filler words were frequent ({top}). Try pausing silently instead.")
    elif m["filler_total"] == 0 and m["word_count"] >= 20:
        tips.append("No filler words detected, which keeps the answer crisp.")
    if m["repeated_phrases"]:
        tips.append(f"You repeated the phrase '{m['repeated_phrases'][0]['phrase']}'. Vary your wording or merge the points.")
    if m["long_pauses"]:
        tips.append(f"There were {m['long_pauses']} long pause(s) over 2 seconds. Outline your answer in your head before you begin.")
    if m["source"] == "text":
        tips.append("This was a typed answer, so pace and pause metrics are not available.")
    return tips


def communication_score(m: dict) -> tuple[float, list[str]]:
    """Heuristic 0-100 delivery score from measurable signals only."""
    notes = []
    score = 100.0
    n = m["word_count"]
    if n < 15:
        score -= 45
        notes.append("very short answer")
    elif n < 30:
        score -= 20
        notes.append("short answer")
    score -= min(30, m["filler_per_100"] * 4)
    if m["filler_per_100"] >= 4:
        notes.append("frequent filler words")
    score -= min(15, 5 * len(m["repeated_phrases"]) + 3 * m["immediate_repeats"])
    if m["wpm"]:
        if m["wpm"] < 90 or m["wpm"] > 185:
            score -= 12
            notes.append("pace outside 90-185 wpm")
    if m["long_pauses"]:
        score -= min(12, 4 * m["long_pauses"])
        notes.append("long pauses")
    return max(0.0, min(100.0, score)), notes
