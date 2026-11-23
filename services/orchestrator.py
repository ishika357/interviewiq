"""Orchestrator: coordinates the specialised agents and owns interview lifecycle + persistence.

Agents (each independently testable, all can share one LLM through separate prompts):
  Resume Agent       services/resume.py       parse PDF -> skills/projects/education
  Interviewer Agent  services/interviewer.py  next question, adaptive follow-ups
  Speech Agent       services/speech.py       Whisper transcription + delivery metrics
  Evaluation Agent   services/evaluator.py    rubric scoring with evidence
  Learning Agent     services/roadmap.py      7-day plan from real weaknesses
  Coding Agent       services/coding.py       sandboxed code assessment
Routes call only this module; it holds the database logic.

Idempotency: a turn is "answered" exactly once. submit_answer checks the stored answer FIRST, and the
UPDATE is conditional (`WHERE answered_at IS NULL`), so retries, double clicks and concurrent requests
all return the saved result instead of corrupting progress.
"""
from __future__ import annotations

import json
import logging
import time

from db import row_to_dict
from . import evaluator, interviewer, roadmap, speech
from .knowledge import TOPIC_LABELS
from .rag import get_kb

log = logging.getLogger("interviewiq.orchestrator")
SCORE_COLS = ("overall", "technical", "relevance", "quality", "communication")


# ---------- reads ----------
def get_interview(db, interview_id: int, user_id: int) -> dict | None:
    """Access control lives here: an interview is only returned to its owner."""
    row = db.execute("SELECT * FROM interviews WHERE id=? AND user_id=?", (interview_id, user_id)).fetchone()
    return row_to_dict(row)


def load_turns(db, interview_id: int) -> list[dict]:
    rows = db.execute("SELECT * FROM turns WHERE interview_id=? ORDER BY idx", (interview_id,)).fetchall()
    return [row_to_dict(r) for r in rows]


def public_turn(t: dict | None) -> dict | None:
    if not t:
        return None
    return {"idx": t["idx"], "question": t["question"], "topic": t["topic"], "topic_label": TOPIC_LABELS.get(t["topic"], t["topic"]),
            "difficulty": t["difficulty"], "kind": t["kind"]}


def state(db, interview: dict) -> dict:
    turns = load_turns(db, interview["id"])
    answered = [t for t in turns if t["answered_at"]]
    current = next((t for t in turns if not t["answered_at"]), None)
    return {
        "interview_id": interview["id"], "status": interview["status"], "role": interview["role"],
        "difficulty": interview["difficulty"], "total": interview["num_questions"], "answered": len(answered),
        "current": public_turn(current), "done": current is None and len(answered) >= interview["num_questions"],
        "elapsed_seconds": _elapsed(db, interview["id"]),
    }


def _elapsed(db, interview_id: int) -> int:
    r = db.execute("SELECT CAST(strftime('%s','now') - strftime('%s', created_at) AS INTEGER) AS s FROM interviews WHERE id=?", (interview_id,)).fetchone()
    return int(r["s"] or 0)


# ---------- create ----------
def create_interview(db, user_id: int, role: str, difficulty: str, num_questions: int, resume: dict | None, resume_name: str | None) -> int:
    cur = db.execute(
        "INSERT INTO interviews (user_id, role, difficulty, num_questions, resume_json, resume_filename) VALUES (?,?,?,?,?,?)",
        (user_id, role, difficulty, num_questions, json.dumps(resume) if resume else None, resume_name))
    iid = cur.lastrowid
    interview = get_interview(db, iid, user_id)
    _insert_turn(db, interview, [])
    db.commit()
    return iid


def _insert_turn(db, interview: dict, turns: list[dict]) -> dict | None:
    nxt = interviewer.next_question(interview, turns)
    if nxt is None:
        return None
    db.execute(
        "INSERT OR IGNORE INTO turns (interview_id, idx, qid, kind, topic, difficulty, question, reference, reference_source, concepts_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (interview["id"], len(turns), nxt["qid"], nxt["kind"], nxt["topic"], nxt["difficulty"], nxt["question"],
         nxt["reference"], nxt["reference_source"], json.dumps(nxt["concepts"])))
    return nxt


# ---------- transcription (step before submit, so the candidate can review the text) ----------
def transcribe(db, interview: dict, idx: int, audio: bytes, suffix: str, whisper_model: str) -> dict:
    turn = db.execute("SELECT * FROM turns WHERE interview_id=? AND idx=?", (interview["id"], idx)).fetchone()
    if not turn:
        return {"ok": False, "error": "Unknown question.", "status": 404}
    if turn["answered_at"]:
        return {"ok": False, "error": "This question was already answered.", "status": 409}
    t0 = time.perf_counter()
    res = speech.transcribe_file(audio, suffix, whisper_model)
    ms = round((time.perf_counter() - t0) * 1000)
    if not res["ok"]:
        return {"ok": False, "error": res["error"], "status": 422, "ms": ms}
    if not res["text"].strip():
        return {"ok": False, "error": "No speech was detected. Check your microphone and try again, or type your answer.", "status": 422, "ms": ms}
    meta = {"duration": res.get("duration"), "segments": res["segments"]}
    db.execute("UPDATE turns SET speech_json=? WHERE id=? AND answered_at IS NULL", (json.dumps(meta), turn["id"]))
    db.commit()
    return {"ok": True, "text": res["text"], "duration": res.get("duration"), "ms": ms}


# ---------- submit (idempotent) ----------
def submit_answer(db, interview: dict, idx: int, text: str, source: str, client_duration: float | None, submission_id: str | None, config) -> dict:
    row = db.execute("SELECT * FROM turns WHERE interview_id=? AND idx=?", (interview["id"], idx)).fetchone()
    if row is None:
        return {"error": "Unknown question.", "status": 404}
    turn = row_to_dict(row)
    # 1) ALREADY SAVED? -> return the stored outcome (this check comes before any session/position checks)
    if turn["answered_at"]:
        return {"duplicate": True, **_after_submit(db, interview, turn)}
    first_open = db.execute("SELECT MIN(idx) AS m FROM turns WHERE interview_id=? AND answered_at IS NULL", (interview["id"],)).fetchone()["m"]
    if first_open is not None and idx != first_open:
        return {"error": "That question is not the current one.", "status": 409}

    source = source if source in ("audio", "text", "skipped") else "text"
    text = (text or "").strip()[:6000]
    if source == "skipped":
        text = ""
    if source != "skipped" and not text:
        return {"error": "Please record or type an answer, or choose Skip.", "status": 400}

    stages = []
    pre = turn.get("speech") or {}
    duration = pre.get("duration") if source == "audio" and pre.get("duration") else (client_duration if source == "audio" else None)
    stages.append({"name": "Audio transcription", "status": "done" if source == "audio" else "skipped",
                   "detail": "Whisper (completed before submit)" if source == "audio" else "typed or skipped answer"})

    t0 = time.perf_counter()
    metrics = speech.analyze(text, duration, pre.get("segments"))
    stages.append({"name": "Speech analysis", "status": "done", "ms": round((time.perf_counter() - t0) * 1000)})

    turn["answer_source"] = source
    t0 = time.perf_counter()
    kb = get_kb(config)
    ev = evaluator.evaluate(turn, text, metrics, kb)
    stages.append({"name": "Answer evaluation", "status": "done", "ms": round((time.perf_counter() - t0) * 1000),
                   "detail": f"engine: {ev['engine']} (technical correctness, relevance, feedback)"})

    s = ev["scores"]
    cur = db.execute(
        """UPDATE turns SET answer_text=?, answer_source=?, duration_sec=?, speech_json=?, eval_json=?,
           overall=?, technical=?, relevance=?, quality=?, communication=?, submission_id=?, answered_at=datetime('now')
           WHERE id=? AND answered_at IS NULL""",
        (text, source, duration, json.dumps(metrics), json.dumps(ev), s["overall"], s["technical"], s["relevance"],
         s["quality"], s["communication"], submission_id, turn["id"]))
    if cur.rowcount == 0:  # a concurrent request won the race
        db.rollback()
        fresh = row_to_dict(db.execute("SELECT * FROM turns WHERE id=?", (turn["id"],)).fetchone())
        return {"duplicate": True, **_after_submit(db, interview, fresh)}

    t0 = time.perf_counter()
    turns = load_turns(db, interview["id"])
    if len(turns) < interview["num_questions"]:
        _insert_turn(db, interview, turns)
    db.commit()
    stages.append({"name": "Next question selection", "status": "done", "ms": round((time.perf_counter() - t0) * 1000)})
    turn = row_to_dict(db.execute("SELECT * FROM turns WHERE id=?", (turn["id"],)).fetchone())
    return {"duplicate": False, "stages": stages, **_after_submit(db, interview, turn)}


def _after_submit(db, interview: dict, turn: dict) -> dict:
    st = state(db, interview)
    return {"saved": {"idx": turn["idx"], "source": turn["answer_source"]}, "next": st["current"], "done": st["done"],
            "answered": st["answered"], "total": st["total"]}


# ---------- finish ----------
def finish_interview(db, interview: dict, config) -> dict:
    if interview["status"] == "completed":
        return {"report": interview["report"], "already": True, "stages": []}
    turns = load_turns(db, interview["id"])
    done = [t for t in turns if t["answered_at"]]
    if len(done) < interview["num_questions"]:
        return {"error": "Answer every question (or skip) before finishing.", "status": 409}
    stages = []
    t0 = time.perf_counter()
    avg = {c: round(sum(t[c] for t in done) / len(done), 1) for c in SCORE_COLS}
    prev = previous_topic_averages(db, interview["user_id"], interview["id"])
    kb = get_kb(config)
    rm = roadmap.build_roadmap(done, prev, kb, interview["role"])
    stats = roadmap.topic_stats(done)
    topic_scores = {t: s["avg"] for t, s in stats.items()}
    strengths, weaknesses = [], []
    for t, s in sorted(stats.items(), key=lambda kv: -kv[1]["avg"]):
        label = TOPIC_LABELS.get(t, t)
        if s["avg"] >= roadmap.STRONG_ABOVE:
            strengths.append(f"{label}: strong ({s['avg']:.0f}/100)")
        elif s["avg"] < roadmap.WEAK_BELOW:
            miss = [m for m, _ in sorted(s["missing"].items(), key=lambda x: -x[1])][:3]
            weaknesses.append(f"{label}: needs work ({s['avg']:.0f}/100)" + (f"; commonly missed: {', '.join(miss)}" if miss else ""))
    sp = [t["speech"] for t in done if t.get("speech") and t["speech"].get("source") == "audio"]
    speech_summary = None
    if sp:
        wpms = [m["wpm"] for m in sp if m.get("wpm")]
        speech_summary = {"answers_spoken": len(sp), "avg_wpm": round(sum(wpms) / len(wpms)) if wpms else None,
                          "filler_per_100": round(sum(m["filler_per_100"] for m in sp) / len(sp), 1)}
    engines = {(t["eval"] or {}).get("engine", "heuristic") for t in done}
    engine = "llm" if "llm" in engines else "heuristic"
    recs = [w["label"] + ": " + ("review " + ", ".join(w["missing"][:3]) if w["missing"] else "practice more answers") for w in rm["weak_topics"]]
    if avg["communication"] < 70:
        recs.append("Communication: reduce filler words and give a concrete example in every answer.")
    if not recs:
        recs.append("Retake at a higher difficulty to keep growing.")
    report = {"averages": avg, "topic_scores": topic_scores, "strengths": strengths, "weaknesses": weaknesses,
              "recommendations": recs, "roadmap": rm, "speech_summary": speech_summary, "engine": engine,
              "skipped": sum(1 for t in done if t["answer_source"] == "skipped")}
    db.execute(
        """UPDATE interviews SET status='completed', completed_at=datetime('now'), overall=?, technical=?, communication=?, relevance=?,
           quality=?, engine=?, report_json=? WHERE id=? AND status='active'""",
        (avg["overall"], avg["technical"], avg["communication"], avg["relevance"], avg["quality"], engine, json.dumps(report), interview["id"]))
    db.commit()
    stages.append({"name": "Report preparation", "status": "done", "ms": round((time.perf_counter() - t0) * 1000)})
    return {"report": report, "already": False, "stages": stages}


def previous_topic_averages(db, user_id: int, exclude_id: int) -> dict[str, float]:
    rows = db.execute(
        """SELECT t.topic, AVG(t.overall) AS a FROM turns t JOIN interviews i ON i.id=t.interview_id
           WHERE i.user_id=? AND i.status='completed' AND i.id<>? AND t.overall IS NOT NULL GROUP BY t.topic""",
        (user_id, exclude_id)).fetchall()
    return {r["topic"]: round(r["a"], 1) for r in rows}
