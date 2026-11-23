"""JSON API used by the browser. Thin handlers: business logic lives in services/."""
from __future__ import annotations

import json
import logging
import re

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from db import get_db
from services import analytics, coding, copilot, orchestrator, resume as resume_agent
from services.knowledge import DIFFICULTIES, ROLES
from services.rag import get_kb
from .auth_utils import current_user, login_required

log = logging.getLogger("interviewiq.api")
bp = Blueprint("api", __name__)


def err(msg: str, status: int = 400):
    return jsonify(error=msg), status


def _own(iid: int):
    return orchestrator.get_interview(get_db(), iid, current_user()["id"])


def _audio_suffix(data: bytes) -> str | None:
    """Identify the container from magic bytes instead of trusting the client's filename or MIME type."""
    if data[:4] == b"\x1aE\xdf\xa3":
        return ".webm"
    if data[4:8] == b"ftyp":
        return ".mp4"
    if data[:4] == b"OggS":
        return ".ogg"
    if data[:4] == b"RIFF":
        return ".wav"
    return None


@bp.get("/health")
def health():
    return jsonify(status="ok")


@bp.post("/interviews")
@login_required
def create_interview():
    f = request.form
    role = f.get("role", "")
    if role == "Other":
        role = re.sub(r"[^\w\s/&+.#-]", "", f.get("custom_role", "")).strip()[:60]
        if len(role) < 3:
            return err("Enter a custom role name (at least 3 characters).")
    elif role not in ROLES:
        return err("Choose a valid job role.")
    difficulty = f.get("difficulty", "")
    if difficulty not in DIFFICULTIES:
        return err("Choose a valid difficulty.")
    try:
        n = int(f.get("num_questions", "0"))
    except ValueError:
        n = 0
    if n not in (5, 10, 15):
        return err("Choose 5, 10 or 15 questions.")

    parsed, fname, warning = None, None, None
    file = request.files.get("resume")
    if file and file.filename:
        data = file.read(current_app.config["MAX_RESUME_BYTES"] + 1)
        problem = resume_agent.validate_pdf(data, current_app.config["MAX_RESUME_BYTES"])
        if problem:
            return err(problem)
        try:
            parsed = resume_agent.analyze_pdf(data)
            fname = secure_filename(file.filename)[:80]
        except Exception as exc:
            log.warning("Resume parsing failed: %s", exc)
            return err(f"We couldn't read that resume: {exc}")
        if not parsed["skills"] and not parsed["projects"]:
            warning = "We could not find skills or projects in the resume, so questions will not be personalised."
            parsed = None
    iid = orchestrator.create_interview(get_db(), current_user()["id"], role, difficulty, n, parsed, fname)
    return jsonify(id=iid, redirect=f"/interview/{iid}", resume=parsed, warning=warning), 201


@bp.post("/resume/preview")
@login_required
def resume_preview():
    """Lets the setup wizard show what was extracted before the interview starts. Nothing is stored."""
    file = request.files.get("resume")
    if not file or not file.filename:
        return err("No file uploaded.")
    data = file.read(current_app.config["MAX_RESUME_BYTES"] + 1)
    problem = resume_agent.validate_pdf(data, current_app.config["MAX_RESUME_BYTES"])
    if problem:
        return err(problem)
    try:
        return jsonify(resume_agent.analyze_pdf(data))
    except Exception as exc:
        return err(f"We couldn't read that resume: {exc}")


@bp.get("/interviews/<int:iid>/state")
@login_required
def interview_state(iid):
    iv = _own(iid)
    if not iv:
        return err("Interview not found.", 404)
    return jsonify(orchestrator.state(get_db(), iv))


@bp.post("/interviews/<int:iid>/transcribe")
@login_required
def transcribe(iid):
    iv = _own(iid)
    if not iv:
        return err("Interview not found.", 404)
    if iv["status"] != "active":
        return err("This interview is already completed.", 409)
    audio = request.files.get("audio")
    try:
        idx = int(request.form.get("idx", ""))
    except ValueError:
        return err("Missing question number.")
    if not audio:
        return err("No audio received.")
    data = audio.read(current_app.config["MAX_AUDIO_BYTES"] + 1)
    if not data or len(data) > current_app.config["MAX_AUDIO_BYTES"]:
        return err("Audio is empty or too large (max 15 MB).")
    suffix = _audio_suffix(data)
    if not suffix:
        return err("Unsupported audio format.")
    res = orchestrator.transcribe(get_db(), iv, idx, data, suffix, current_app.config["WHISPER_MODEL"])
    if not res["ok"]:
        return err(res["error"], res.get("status", 422))
    return jsonify(text=res["text"], duration=res["duration"], ms=res["ms"])


@bp.post("/interviews/<int:iid>/answer")
@login_required
def submit_answer(iid):
    iv = _own(iid)
    if not iv:
        return err("Interview not found.", 404)
    body = request.get_json(silent=True) or {}
    try:
        idx = int(body.get("idx"))
    except (TypeError, ValueError):
        return err("Missing question number.")
    dur = body.get("duration")
    try:
        dur = float(dur) if dur is not None else None
        if dur is not None and not (0 <= dur <= 900):
            dur = None
    except (TypeError, ValueError):
        dur = None
    res = orchestrator.submit_answer(get_db(), iv, idx, str(body.get("text", "")), str(body.get("source", "text")), dur,
                                     str(body.get("submission_id", ""))[:64], current_app.config)
    if "error" in res:
        return err(res["error"], res.get("status", 400))
    return jsonify(res)


@bp.post("/interviews/<int:iid>/finish")
@login_required
def finish(iid):
    iv = _own(iid)
    if not iv:
        return err("Interview not found.", 404)
    res = orchestrator.finish_interview(get_db(), iv, current_app.config)
    if "error" in res:
        return err(res["error"], res.get("status", 400))
    return jsonify(redirect=f"/interview/{iid}/results", stages=res["stages"], already=res["already"])


@bp.post("/interviews/<int:iid>/copilot")
@login_required
def copilot_chat(iid):
    iv = _own(iid)
    if not iv or iv["status"] != "completed":
        return err("Copilot is available after an interview is completed.", 404)
    msg = str((request.get_json(silent=True) or {}).get("message", "")).strip()[:500]
    if len(msg) < 3:
        return err("Ask a question (at least 3 characters).")
    turns = orchestrator.load_turns(get_db(), iid)
    return jsonify(copilot.answer(msg, iv, turns, iv["report"] or {}, get_kb(current_app.config)))


@bp.get("/analytics")
@login_required
def analytics_api():
    return jsonify(analytics.performance(get_db(), current_user()["id"]))


@bp.get("/dashboard")
@login_required
def dashboard_api():
    return jsonify(analytics.dashboard(get_db(), current_user()["id"]))


# ---------- coding ----------
def _code_body():
    body = request.get_json(silent=True) or {}
    code = str(body.get("code", ""))
    return code if code.strip() else None


@bp.post("/coding/<pid>/run")
@login_required
def coding_run(pid):
    p = coding.get_problem(pid)
    code = _code_body()
    if not p:
        return err("Problem not found.", 404)
    if not code:
        return err("Write some code first.")
    res = coding.run_submission(p, code, current_app.config, only_visible=True)
    res.pop("_raw", None)
    return jsonify(res)


@bp.post("/coding/<pid>/submit")
@login_required
def coding_submit(pid):
    p = coding.get_problem(pid)
    code = _code_body()
    if not p:
        return err("Problem not found.", 404)
    if not code:
        return err("Write some code first.")
    res = coding.run_submission(p, code, current_app.config)
    res.pop("_raw", None)
    feedback = coding.build_feedback(p, code, res, res["passed"], res["total"])
    db = get_db()
    db.execute("INSERT INTO coding_submissions (user_id, problem_id, code, passed, total, result_json, feedback_json) VALUES (?,?,?,?,?,?,?)",
               (current_user()["id"], pid, code[:20000], res["passed"], res["total"], json.dumps(res["results"]), json.dumps(feedback)))
    db.commit()
    return jsonify({**res, "feedback": feedback})
