from __future__ import annotations

import time
from functools import wraps

from flask import g, jsonify, redirect, request, session, url_for

from db import get_db, row_to_dict


def current_user() -> dict | None:
    uid = session.get("uid")
    if not uid:
        return None
    if "user" not in g:
        g.user = row_to_dict(get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
        if g.user is None:
            session.clear()
    return g.user


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if not current_user():
            if request.path.startswith("/api/"):
                return jsonify(error="Please log in."), 401
            return redirect(url_for("web.login"))
        return view(*a, **kw)
    return wrapped


# Minimal in-memory brute-force protection (use Redis or Flask-Limiter in production).
_FAILS: dict[str, list[float]] = {}


def too_many_attempts(key: str, limit: int = 6, window: int = 600) -> bool:
    now = time.time()
    _FAILS[key] = [t for t in _FAILS.get(key, []) if now - t < window]
    return len(_FAILS[key]) >= limit


def record_failure(key: str) -> None:
    _FAILS.setdefault(key, []).append(time.time())


def clear_failures(key: str) -> None:
    _FAILS.pop(key, None)
