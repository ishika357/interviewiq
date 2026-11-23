"""Learning Agent: turns real interview results into a 7-day study plan.

Everything is derived from the candidate's evaluated answers: weak topics (average < 65), the specific
concepts they missed, and the knowledge-base sections that cover those concepts. Nothing is generic filler.
"""
from __future__ import annotations

from .knowledge import TOPIC_LABELS, load_coding_problems

WEAK_BELOW = 65.0
STRONG_ABOVE = 80.0


def topic_stats(turns: list[dict]) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for t in turns:
        if t.get("overall") is None:
            continue
        s = stats.setdefault(t["topic"], {"scores": [], "missing": {}, "questions": []})
        s["scores"].append(t["overall"])
        ev = t.get("eval") or {}
        for m in (ev.get("rubric") or {}).get("missing", []):
            s["missing"][m] = s["missing"].get(m, 0) + 1
        s["questions"].append({"question": t["question"], "score": t["overall"], "missing": list((ev.get("rubric") or {}).get("missing", []))})
    for s in stats.values():
        s["avg"] = round(sum(s["scores"]) / len(s["scores"]), 1)
    return stats


def build_roadmap(turns: list[dict], previous_topic_avgs: dict[str, float], kb, role: str = "") -> dict:
    stats = topic_stats(turns)
    if not stats:
        return {"summary": "No evaluated answers yet.", "weak_topics": [], "days": []}
    ranked = sorted(stats.items(), key=lambda kv: kv[1]["avg"])
    weak = [(t, s) for t, s in ranked if s["avg"] < WEAK_BELOW and t != "hr"]
    hr = stats.get("hr")
    weak_info = []
    for t, s in weak:
        prev = previous_topic_avgs.get(t)
        weak_info.append({
            "topic": t, "label": TOPIC_LABELS.get(t, t), "score": s["avg"],
            "trend": round(s["avg"] - prev, 1) if prev is not None else None,
            "missing": [m for m, _ in sorted(s["missing"].items(), key=lambda x: -x[1])][:6],
        })

    blocks = []
    for info in weak_info[:3]:
        s = stats[info["topic"]]
        tasks, resources, seen = [], [], set()
        for q in sorted(s["questions"], key=lambda q: q["score"])[:2]:
            hits = kb.search(q["question"], k=1)  # the KB section that actually answers the weak question
            focus = ", ".join(q["missing"][:4])
            if hits and hits[0]["section"] not in seen:
                h = hits[0]
                seen.add(h["section"])
                tasks.append(f"Read '{h['section']}' ({h['source']})" + (f" and write notes on: {focus}." if focus else " and summarise it in your own words."))
                resources.append({"source": h["source"], "section": h["section"]})
            elif focus:
                tasks.append(f"Review your course notes on: {focus}.")
        weakest_q = sorted(s["questions"], key=lambda q: q["score"])[0]["question"]
        tasks.append(f"Re-answer aloud, with an example: \"{weakest_q}\"")
        blocks.append({"days": 2 if len(blocks) < 2 else 1, "title": f"{info['label']} fundamentals", "tasks": tasks, "resources": resources})

    coding_topics = {t for t, _ in weak} & {"python", "dsa"}
    if coding_topics or role in ("Python Developer", "Software Developer"):
        probs = [p for p in load_coding_problems() if role in p["roles"] or "Other" in p["roles"]][:3]
        blocks.append({"days": 1, "title": "Coding practice", "resources": [],
                       "tasks": [f"Solve '{p['title']}' in the Coding Practice section and compare your complexity with {p['time']}." for p in probs]})
    if hr and hr["avg"] < WEAK_BELOW:
        blocks.append({"days": 1, "title": "Communication practice", "resources": [{"source": "HR and Behavioural Interview Knowledge", "section": "The STAR method"}],
                       "tasks": ["Write two STAR stories (problem, your actions, measurable result).", "Record yourself answering 'Tell me about yourself' in under 90 seconds."]})
    if not blocks:
        low_t, low_s = ranked[0]
        blocks.append({"days": 3, "title": f"Stretch: {TOPIC_LABELS.get(low_t, low_t)}", "resources": [],
                       "tasks": ["Your scores are strong. Retake the interview at the next difficulty level.",
                                 f"Lowest topic was {TOPIC_LABELS.get(low_t, low_t)} ({low_s['avg']:.0f}/100): review its missing concepts and add real examples to your answers."]})

    days, cursor = [], 1
    for b in blocks:
        if cursor > 6:
            break
        end = min(6, cursor + b["days"] - 1)
        label = f"Day {cursor}" if end == cursor else f"Day {cursor}-{end}"
        days.append({"day": label, "title": b["title"], "tasks": b["tasks"], "resources": b["resources"]})
        cursor = end + 1
    days.append({"day": "Day 7", "title": "Retake assessment", "resources": [],
                 "tasks": [f"Take a new {role or 'practice'} interview at the same difficulty.", "Compare each topic score with this interview to measure improvement."]})

    strong = [TOPIC_LABELS.get(t, t) for t, s in ranked if s["avg"] >= STRONG_ABOVE]
    summary = (f"Focus areas: {', '.join(w['label'] for w in weak_info)}. " if weak_info else "No topic fell below the weak threshold. ") + \
              (f"Strong areas: {', '.join(strong)}." if strong else "")
    return {"summary": summary.strip(), "weak_topics": weak_info, "days": days,
            "basis": f"Weak = topic average below {WEAK_BELOW:.0f}/100; concepts come from your evaluated answers."}
