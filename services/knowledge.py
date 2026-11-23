"""Question bank loader and role -> topic mapping."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

ROLES = [
    "AI Engineer", "Python Developer", "Data Analyst", "Software Developer",
    "Machine Learning Engineer", "QA Engineer", "Other",
]
DIFFICULTIES = {"Beginner": (1, 2, 1), "Intermediate": (1, 3, 2), "Advanced": (2, 3, 3)}  # (min, max, start)

TOPIC_LABELS = {
    "python": "Python", "sql": "SQL", "ml": "Machine Learning", "dl": "Deep Learning",
    "dsa": "Data Structures & Algorithms", "genai": "Generative AI & RAG", "stats": "Data Analysis & Statistics",
    "swe": "Software Engineering", "qa": "QA & Testing", "hr": "HR & Communication",
}

ROLE_TOPICS = {
    "AI Engineer": ["python", "genai", "ml", "dl", "dsa"],
    "Python Developer": ["python", "dsa", "sql", "swe"],
    "Data Analyst": ["sql", "stats", "python", "ml"],
    "Software Developer": ["dsa", "swe", "python", "sql"],
    "Machine Learning Engineer": ["ml", "dl", "python", "genai", "stats"],
    "QA Engineer": ["qa", "swe", "python", "sql"],
}

# Keywords used to guess topics for a custom role (no invented content: we only pick from the bank).
CUSTOM_KEYWORDS = {
    "python": ["python", "backend", "django", "flask", "automation", "scripting"],
    "sql": ["sql", "database", "dba", "data engineer", "bi ", "business intelligence", "analyst"],
    "ml": ["machine learning", "ml", "data scien", "ai"],
    "dl": ["deep learning", "vision", "nlp", "neural"],
    "dsa": ["developer", "engineer", "programmer", "software"],
    "genai": ["llm", "generative", "genai", "prompt", "ai"],
    "stats": ["data", "analyst", "analytics", "scien", "research"],
    "swe": ["developer", "engineer", "software", "web", "devops", "full stack", "fullstack"],
    "qa": ["qa", "test", "quality", "sdet"],
}


@lru_cache(maxsize=1)
def load_questions() -> list[dict]:
    items = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    for q in items:
        q.setdefault("skills", [])
    return items


@lru_cache(maxsize=1)
def questions_by_id() -> dict[str, dict]:
    return {q["id"]: q for q in load_questions()}


@lru_cache(maxsize=1)
def load_coding_problems() -> list[dict]:
    return json.loads((DATA / "coding_problems.json").read_text(encoding="utf-8"))


def topics_for_role(role: str, custom_text: str = "") -> list[str]:
    if role in ROLE_TOPICS:
        return ROLE_TOPICS[role]
    text = (custom_text or role).lower()
    scored = []
    for topic, words in CUSTOM_KEYWORDS.items():
        hits = sum(1 for w in words if w in text)
        if hits:
            scored.append((hits, topic))
    scored.sort(reverse=True)
    topics = [t for _, t in scored[:4]]
    return topics or ["python", "dsa", "swe"]


def concept_label(group: str) -> str:
    """First alternative of a concept group, used as its human label."""
    return group.split("|")[0].strip()
