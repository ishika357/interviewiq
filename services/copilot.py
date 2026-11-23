"""Interview Copilot: post-interview assistant grounded in the user's results and the knowledge base.

Without an LLM it answers with rule-based templates built from stored evaluation data and verbatim KB
passages. With an LLM it receives only: the user's own results and retrieved KB chunks, and is told to
cite chunks as [S#] and to say when the context does not contain the answer.
"""
from __future__ import annotations

import random
import re

from . import llm
from .knowledge import TOPIC_LABELS, load_questions

NO_KB = "I couldn't find that in the knowledge base, so I won't guess. Try rephrasing with a specific technical term."


def _weakest(turns: list[dict], k: int = 3) -> list[dict]:
    done = [t for t in turns if t.get("overall") is not None]
    return sorted(done, key=lambda t: t["overall"])[:k]


def _question_ref(message: str, turns: list[dict]) -> dict | None:
    m = re.search(r"(?:question|q)\s*#?\s*(\d+)", message.lower())
    if m:
        i = int(m.group(1)) - 1
        return next((t for t in turns if t["idx"] == i and t.get("overall") is not None), None)
    return None


def _intent(msg: str) -> str:
    m = msg.lower()
    if re.search(r"lose|lost|marks|why.*(score|low|bad)|what went wrong|weak", m):
        return "why"
    if re.search(r"better answer|improve.*answer|model answer|how should i have|ideal answer", m):
        return "better"
    if re.search(r"another question|ask me|quiz me|practice question|more questions", m):
        return "another"
    if re.search(r"study next|what should i (study|learn)|roadmap|study plan|next steps|learn next", m):
        return "study"
    if re.search(r"explain|what is|what are|how does|difference between|define|meaning of", m):
        return "explain"
    return "general"


def _fmt_turn(t: dict) -> str:
    ev = t.get("eval") or {}
    miss = (ev.get("rubric") or {}).get("missing", [])
    return (f"Q{t['idx'] + 1} ({TOPIC_LABELS.get(t['topic'], t['topic'])}, {t['overall']:.0f}/100): {t['question']}\n"
            f"   Feedback: {ev.get('feedback', '')}" + (f"\n   Missing: {', '.join(miss[:5])}." if miss else ""))


def answer(message: str, interview: dict, turns: list[dict], report: dict, kb) -> dict:
    intent = _intent(message)
    target = _question_ref(message, turns)
    hits = kb.search(message, k=3)
    sources = [{"source": h["source"], "section": h["section"], "score": h["score"]} for h in hits]

    if intent == "another":
        weak = _weakest(turns, 1)
        topic = weak[0]["topic"] if weak else interview.get("role", "")
        asked = {t.get("qid") for t in turns}
        pool = [q for q in load_questions() if q["topic"] == topic and q["id"] not in asked] or \
               [q for q in load_questions() if q["id"] not in asked and q["topic"] != "hr"]
        if not pool:
            return {"answer": "You've already seen every question I have on this topic.", "sources": [], "mode": "rule-based"}
        q = random.choice(pool)
        return {"answer": f"Here is another {TOPIC_LABELS.get(q['topic'], q['topic'])} question, picked because it was one of your weaker areas:\n\n\"{q['q']}\"\n\n"
                          "Answer it aloud, then ask me to explain the concept if you get stuck.",
                "sources": [], "mode": "rule-based"}

    if intent == "study":
        rm = report.get("roadmap") or {}
        if not rm.get("days"):
            return {"answer": "There isn't a roadmap yet because no answers have been evaluated.", "sources": [], "mode": "rule-based"}
        lines = [rm.get("summary", "")] + [f"{d['day']}: {d['title']}" for d in rm["days"]]
        return {"answer": "Here is your study order based on this interview:\n" + "\n".join(lines), "sources": [], "mode": "rule-based"}

    if intent == "why":
        pool = [target] if target else _weakest(turns, 3)
        if not pool:
            return {"answer": "No evaluated answers are available yet.", "sources": [], "mode": "rule-based"}
        # retrieve KB material about the weakest question (not about the chat message itself)
        hits = kb.search(pool[0]["question"], k=2)
        sources = [{"source": h["source"], "section": h["section"], "score": h["score"]} for h in hits]
        return _maybe_llm(message, interview, "These answers cost you the most marks:\n\n" + "\n\n".join(_fmt_turn(t) for t in pool), pool, hits, sources)

    if intent == "better":
        t = target or (_weakest(turns, 1) or [None])[0]
        if not t:
            return {"answer": "No evaluated answers are available yet.", "sources": [], "mode": "rule-based"}
        ev = t.get("eval") or {}
        text = (f"For Q{t['idx'] + 1} (\"{t['question']}\"), here is a stronger answer ({ev.get('improved_answer_source', 'reference')}):\n\n"
                f"{ev.get('improved_answer', '')}\n\nYour answer was missing: {', '.join((ev.get('rubric') or {}).get('missing', [])[:5]) or 'nothing major'}.")
        return {"answer": text, "sources": [], "mode": "rule-based"}

    # explain / general: grounded in KB
    if not hits:
        return {"answer": NO_KB, "sources": [], "mode": "rule-based"}
    base = "From the knowledge base:\n\n" + "\n\n".join(f"{h['text']} [{h['source']} / {h['section']}]" for h in hits[:2])
    return _maybe_llm(message, interview, base, _weakest(turns, 2), hits, sources)


def _maybe_llm(message: str, interview: dict, rule_text: str, focus: list[dict], hits: list[dict], sources: list[dict]) -> dict:
    if not llm.is_available():
        return {"answer": rule_text, "sources": sources, "mode": "rule-based"}
    ctx = "\n".join(_fmt_turn(t) for t in focus) or "(no answers)"
    kb_ctx = "\n".join(f"[S{i + 1}] ({h['source']} / {h['section']}) {h['text']}" for i, h in enumerate(hits)) or "(no knowledge-base passages found)"
    system = ("You are an interview coach. Use ONLY the candidate results and knowledge-base passages provided. "
              "Cite knowledge-base facts as [S#]. If the context does not contain the answer, say so instead of guessing. Max 180 words.")
    user = f"Role: {interview['role']} ({interview['difficulty']})\n\nCandidate results:\n{ctx}\n\nKnowledge base:\n{kb_ctx}\n\n<question>\n{message[:500]}\n</question>"
    text = llm.complete(system, user, max_tokens=500, temperature=0.3)
    if not text:
        return {"answer": rule_text, "sources": sources, "mode": "rule-based"}
    return {"answer": text.strip(), "sources": sources, "mode": "llm"}
