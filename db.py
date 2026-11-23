"""SQLite data layer (standard-library sqlite3, no ORM, easy to read for a beginner)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    target_role TEXT DEFAULT '',
    prefs_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS interviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    num_questions INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',          -- active | completed
    resume_json TEXT,
    resume_filename TEXT,
    engine TEXT DEFAULT 'heuristic',                 -- evaluation engine used: llm | heuristic
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    overall REAL, technical REAL, communication REAL, relevance REAL, quality REAL,
    report_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_interviews_user ON interviews(user_id, created_at);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    qid TEXT,
    kind TEXT NOT NULL DEFAULT 'base',               -- base | followup | probe | resume
    topic TEXT NOT NULL,
    difficulty INTEGER NOT NULL DEFAULT 2,
    question TEXT NOT NULL,
    reference TEXT,
    reference_source TEXT DEFAULT 'bank',
    concepts_json TEXT DEFAULT '[]',
    asked_at TEXT NOT NULL DEFAULT (datetime('now')),
    answer_text TEXT,
    answer_source TEXT,                              -- audio | text | skipped
    duration_sec REAL,
    speech_json TEXT,
    eval_json TEXT,
    overall REAL, technical REAL, relevance REAL, quality REAL, communication REAL,
    submission_id TEXT,
    answered_at TEXT,
    UNIQUE(interview_id, idx)
);

CREATE TABLE IF NOT EXISTS coding_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    problem_id TEXT NOT NULL,
    code TEXT NOT NULL,
    passed INTEGER NOT NULL,
    total INTEGER NOT NULL,
    result_json TEXT,
    feedback_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(path: str) -> None:
    conn = _connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def row_to_dict(row, json_fields=()) -> dict | None:
    """Convert a sqlite Row to a dict and decode JSON columns (name_json -> name)."""
    if row is None:
        return None
    d = dict(row)
    for key in list(d):
        if key.endswith("_json"):
            raw = d.pop(key)
            try:
                d[key[:-5]] = json.loads(raw) if raw else None
            except (TypeError, ValueError):
                d[key[:-5]] = None
    return d
