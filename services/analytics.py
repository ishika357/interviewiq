"""Analytics: every number comes from rows in the database. Nothing is hard-coded."""
from __future__ import annotations

from .knowledge import TOPIC_LABELS


def dashboard(db, user_id: int) -> dict:
    rows = db.execute(
        "SELECT id, role, difficulty, overall, technical, communication, created_at, completed_at, num_questions "
        "FROM interviews WHERE user_id=? AND status='completed' ORDER BY completed_at, id", (user_id,)).fetchall()
    scores = [r["overall"] for r in rows if r["overall"] is not None]
    active = db.execute("SELECT id FROM interviews WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    out = {"total": len(rows), "average": None, "best": None, "improvement_pct": None, "improvement_points": None,
           "trend": [{"id": r["id"], "label": (r["completed_at"] or "")[:10], "overall": r["overall"]} for r in rows],
           "recent": [dict(r) for r in reversed(rows[-5:])], "active_interview_id": active["id"] if active else None}
    if scores:
        out["average"] = round(sum(scores) / len(scores), 1)
        out["best"] = round(max(scores), 1)
    if len(scores) >= 2:
        k = min(3, len(scores) // 2)
        first, last = sum(scores[:k]) / k, sum(scores[-k:]) / k
        out["improvement_points"] = round(last - first, 1)
        out["improvement_pct"] = round((last - first) / first * 100, 1) if first > 0 else None
    return out


def performance(db, user_id: int) -> dict:
    interviews = db.execute(
        "SELECT id, role, completed_at, overall, technical, communication, relevance, quality FROM interviews "
        "WHERE user_id=? AND status='completed' ORDER BY completed_at, id", (user_id,)).fetchall()
    topics = db.execute(
        """SELECT t.topic, AVG(t.overall) AS avg, COUNT(*) AS n FROM turns t JOIN interviews i ON i.id=t.interview_id
           WHERE i.user_id=? AND i.status='completed' AND t.overall IS NOT NULL GROUP BY t.topic ORDER BY avg""", (user_id,)).fetchall()
    cells = db.execute(
        """SELECT t.topic, t.difficulty, AVG(t.overall) AS avg, COUNT(*) AS n FROM turns t JOIN interviews i ON i.id=t.interview_id
           WHERE i.user_id=? AND i.status='completed' AND t.overall IS NOT NULL GROUP BY t.topic, t.difficulty""", (user_id,)).fetchall()
    diff = db.execute(
        """SELECT t.difficulty, AVG(t.overall) AS avg, AVG(t.technical) AS tech, COUNT(*) AS n FROM turns t JOIN interviews i ON i.id=t.interview_id
           WHERE i.user_id=? AND i.status='completed' AND t.overall IS NOT NULL GROUP BY t.difficulty ORDER BY t.difficulty""", (user_id,)).fetchall()
    return {
        "interviews": [{"id": r["id"], "label": (r["completed_at"] or "")[:10], "role": r["role"], "overall": r["overall"],
                        "technical": r["technical"], "communication": r["communication"], "relevance": r["relevance"],
                        "quality": r["quality"]} for r in interviews],
        "topics": [{"topic": r["topic"], "label": TOPIC_LABELS.get(r["topic"], r["topic"]), "avg": round(r["avg"], 1), "n": r["n"]} for r in topics],
        "heatmap": [{"topic": r["topic"], "label": TOPIC_LABELS.get(r["topic"], r["topic"]), "difficulty": r["difficulty"],
                     "avg": round(r["avg"], 1), "n": r["n"]} for r in cells],
        "difficulty": [{"difficulty": r["difficulty"], "avg": round(r["avg"], 1), "technical": round(r["tech"], 1), "n": r["n"]} for r in diff],
    }
