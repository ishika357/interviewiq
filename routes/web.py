"""Server-rendered pages: landing, auth, dashboard, setup, interview room, results, history, profile."""
from __future__ import annotations

import json
import re

from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db
from services import analytics, coding, orchestrator, report as report_pdf
from services.knowledge import DIFFICULTIES, ROLES, TOPIC_LABELS, load_coding_problems
from .auth_utils import clear_failures, current_user, login_required, record_failure, too_many_attempts

bp = Blueprint("web", __name__)
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


@bp.app_template_filter("score_class")
def score_class(v):
    if v is None:
        return "muted"
    return "good" if v >= 75 else "ok" if v >= 50 else "bad"


@bp.app_template_filter("pretty_dt")
def pretty_dt(v):
    return (v or "")[:16].replace("T", " ")


@bp.app_template_filter("tojson_safe")
def tojson_safe(v):
    return json.dumps(v).replace("<", "\\u003c")


# ---------- public ----------
@bp.route("/")
def landing():
    return render_template("landing.html", user=current_user())


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:60]
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        if not name or not EMAIL.match(email):
            flash("Enter your name and a valid email.", "error")
        elif len(pw) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            db = get_db()
            if db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                flash("An account with this email already exists.", "error")
            else:
                cur = db.execute("INSERT INTO users (name,email,password_hash) VALUES (?,?,?)", (name, email, generate_password_hash(pw)))
                db.commit()
                session.clear()
                session["uid"] = cur.lastrowid
                return redirect(url_for("web.dashboard"))
    return render_template("auth.html", mode="register")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        key = f"{request.remote_addr}|{email}"
        if too_many_attempts(key):
            flash("Too many failed attempts. Try again in a few minutes.", "error")
            return render_template("auth.html", mode="login"), 429
        row = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row and check_password_hash(row["password_hash"], request.form.get("password", "")):
            clear_failures(key)
            session.clear()
            session["uid"] = row["id"]
            return redirect(url_for("web.dashboard"))
        record_failure(key)
        flash("Incorrect email or password.", "error")
    return render_template("auth.html", mode="login")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("web.landing"))


# ---------- app pages ----------
@bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    return render_template("dashboard.html", user=user, d=analytics.dashboard(get_db(), user["id"]), active="dashboard")


@bp.route("/interview/new")
@login_required
def interview_new():
    from services import speech
    return render_template("setup.html", user=current_user(), roles=ROLES, difficulties=list(DIFFICULTIES), active="start",
                           whisper_ok=speech.whisper_available())


@bp.route("/interview/<int:iid>")
@login_required
def interview_room(iid):
    user = current_user()
    interview = orchestrator.get_interview(get_db(), iid, user["id"]) or abort(404)
    if interview["status"] == "completed":
        return redirect(url_for("web.results", iid=iid))
    from services import speech
    return render_template("room.html", interview=interview, whisper_ok=speech.whisper_available(), user=user)


@bp.route("/interview/<int:iid>/results")
@login_required
def results(iid):
    user = current_user()
    db = get_db()
    interview = orchestrator.get_interview(db, iid, user["id"]) or abort(404)
    if interview["status"] != "completed":
        return redirect(url_for("web.interview_room", iid=iid))
    turns = orchestrator.load_turns(db, iid)
    return render_template("results.html", interview=interview, turns=turns, report=interview["report"] or {}, user=user,
                           labels=TOPIC_LABELS, active="history")


@bp.route("/interview/<int:iid>/report.pdf")
@login_required
def report_download(iid):
    user = current_user()
    db = get_db()
    interview = orchestrator.get_interview(db, iid, user["id"]) or abort(404)
    if interview["status"] != "completed":
        abort(404)
    pdf = report_pdf.build_pdf(interview, orchestrator.load_turns(db, iid), user["name"])
    return Response(pdf, mimetype="application/pdf", headers={"Content-Disposition": f'attachment; filename="interviewiq-report-{iid}.pdf"'})


@bp.route("/history")
@login_required
def history():
    user = current_user()
    rows = get_db().execute("SELECT * FROM interviews WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    return render_template("history.html", user=user, rows=rows, active="history")


@bp.route("/performance")
@login_required
def performance():
    user = current_user()
    return render_template("performance.html", user=user, p=analytics.performance(get_db(), user["id"]), active="performance")


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:60]
        role = request.form.get("target_role", "").strip()[:60]
        if name:
            db.execute("UPDATE users SET name=?, target_role=? WHERE id=?", (name, role, user["id"]))
            db.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("web.profile"))
        flash("Name cannot be empty.", "error")
    stats = analytics.dashboard(db, user["id"])
    return render_template("profile.html", user=user, stats=stats, active="profile")


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = current_user()
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "password":
            if not check_password_hash(user["password_hash"], request.form.get("current", "")):
                flash("Current password is incorrect.", "error")
            elif len(request.form.get("new", "")) < 8:
                flash("New password must be at least 8 characters.", "error")
            else:
                db.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(request.form["new"]), user["id"]))
                db.commit()
                flash("Password changed.", "success")
        elif action == "delete":
            if request.form.get("confirm") == "DELETE":
                db.execute("DELETE FROM users WHERE id=?", (user["id"],))
                db.commit()
                session.clear()
                return redirect(url_for("web.landing"))
            flash("Type DELETE to confirm.", "error")
        return redirect(url_for("web.settings"))
    from services import llm, rag, sandbox, speech
    kb = rag.get_kb(current_app.config)
    sysinfo = {"llm": llm.provider() or "not configured (rule-based mode)", "whisper": "installed" if speech.whisper_available() else "not installed (typed answers only)",
               "embeddings": kb.embedder.name, "vector_index": kb.index_name, "kb_chunks": len(kb.chunks),
               "sandbox": current_app.config["SANDBOX_MODE"], "network_isolation": sandbox.isolation_report()["network_namespace"]}
    return render_template("settings.html", user=user, sysinfo=sysinfo, active="settings")


@bp.route("/coding")
@login_required
def coding_list():
    user = current_user()
    solved = {r["problem_id"] for r in get_db().execute("SELECT problem_id FROM coding_submissions WHERE user_id=? AND passed=total", (user["id"],))}
    return render_template("coding_list.html", user=user, problems=load_coding_problems(), solved=solved, active="coding")


@bp.route("/coding/<pid>")
@login_required
def coding_problem(pid):
    p = coding.get_problem(pid) or abort(404)
    user = current_user()
    last = get_db().execute("SELECT code FROM coding_submissions WHERE user_id=? AND problem_id=? ORDER BY id DESC LIMIT 1", (user["id"], pid)).fetchone()
    return render_template("coding.html", user=user, problem=coding.public_problem(p), last_code=last["code"] if last else None, active="coding")
