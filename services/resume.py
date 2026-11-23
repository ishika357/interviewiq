"""Resume Agent: validate PDF, extract text, and pull out structured facts.

Everything returned is copied from the resume text. Skills come from matching a fixed vocabulary
against the text, so nothing is invented. Heuristic extraction is imperfect; the UI shows the
parsed result so the candidate can see what the interviewer knows.
"""
from __future__ import annotations

import io
import re

SKILL_VOCAB = {
    "python": "python", "flask": "flask", "django": "django", "fastapi": "fastapi", "sql": "sql", "mysql": "sql",
    "postgresql": "sql", "sqlite": "sql", "mongodb": "mongodb", "machine learning": "machine learning",
    "deep learning": "deep learning", "nlp": "nlp", "natural language processing": "nlp", "computer vision": "deep learning",
    "tensorflow": "deep learning", "pytorch": "deep learning", "keras": "deep learning", "scikit-learn": "machine learning",
    "sklearn": "machine learning", "pandas": "data analysis", "numpy": "data analysis", "power bi": "data analysis",
    "tableau": "data analysis", "excel": "data analysis", "statistics": "statistics", "data analysis": "data analysis",
    "data visualization": "data analysis", "llm": "llm", "large language model": "llm", "generative ai": "generative ai",
    "rag": "rag", "langchain": "llm", "openai": "llm", "prompt engineering": "llm", "transformers": "deep learning",
    "java": "oop", "c++": "data structures", "javascript": "javascript", "react": "javascript", "node.js": "javascript",
    "html": "web", "css": "web", "rest api": "rest", "rest": "rest", "api": "api", "git": "git", "github": "git",
    "docker": "devops", "kubernetes": "devops", "aws": "cloud", "azure": "cloud", "gcp": "cloud", "linux": "linux",
    "selenium": "automation", "pytest": "testing", "junit": "testing", "postman": "testing", "jira": "testing",
    "data structures": "data structures", "algorithms": "algorithms", "oop": "oop", "opencv": "deep learning",
    "whisper": "llm", "faiss": "rag", "chromadb": "rag", "xgboost": "machine learning",
}
SECTION_HEADS = {
    "education": r"education|academic",
    "skills": r"skills|technical skills|technologies|tech stack",
    "projects": r"projects?|academic projects|personal projects",
    "experience": r"experience|work experience|internships?|employment",
    "achievements": r"achievements?|certifications?|awards|accomplishments",
}
DEGREE = re.compile(r"\b(b\.?\s?tech|m\.?\s?tech|b\.?\s?e\b|b\.?\s?sc|m\.?\s?sc|bca|mca|mba|bachelor|master|ph\.?d|diploma|university|college|institute|school of)\b", re.I)


def validate_pdf(data: bytes, max_bytes: int) -> str | None:
    """Return an error message, or None if the file looks like an acceptable PDF."""
    if not data:
        return "The resume file is empty."
    if len(data) > max_bytes:
        return f"Resume is too large (max {max_bytes // (1024 * 1024)} MB)."
    if not data.startswith(b"%PDF-"):
        return "Only real PDF files are accepted."
    return None


def extract_text(data: bytes, max_pages: int = 6) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise ValueError("The PDF is password protected.")
    return "\n".join((p.extract_text() or "") for p in reader.pages[:max_pages])


def _sections(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {k: [] for k in SECTION_HEADS}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        head = re.sub(r"[^a-zA-Z ]", "", line).strip().lower()
        matched = None
        if len(head) <= 32:
            for name, pat in SECTION_HEADS.items():
                if re.fullmatch(pat, head):
                    matched = name
                    break
        if matched:
            current = matched
            continue
        if current:
            out[current].append(line)
    return out


def find_skills(text: str) -> list[str]:
    low = " " + re.sub(r"\s+", " ", text.lower()) + " "
    found = []
    for term in sorted(SKILL_VOCAB, key=len, reverse=True):
        pat = r"(?<![a-z0-9+#.])" + re.escape(term) + r"(?![a-z0-9+#])"
        if re.search(pat, low) and term not in found:
            found.append(term)
    return found


def parse(text: str) -> dict:
    secs = _sections(text)
    skills = find_skills(text)
    education = [l for l in secs["education"] if DEGREE.search(l)][:3] or [l for l in text.splitlines() if DEGREE.search(l)][:3]

    projects: list[dict] = []
    cur = None
    for line in secs["projects"]:
        is_bullet = bool(re.match(r"^[•\-\*●▪>]\s*", line))
        if not is_bullet and len(line) <= 90:
            if cur:
                projects.append(cur)
            cur = {"name": re.split(r"\s[\-–|:]\s", line)[0].strip(), "details": []}
            if re.search(r"\s[\-–|:]\s", line):
                cur["details"].append(re.split(r"\s[\-–|:]\s", line, maxsplit=1)[1].strip())
        elif cur is not None:
            cur["details"].append(re.sub(r"^[•\-\*●▪>]\s*", "", line))
    if cur:
        projects.append(cur)
    for p in projects:
        p["text"] = " ".join([p["name"]] + p["details"])[:400]
        p["skills"] = find_skills(p["text"])
    projects = [p for p in projects if len(p["name"]) > 2][:5]

    experience = [l for l in secs["experience"] if len(l) > 5][:6]
    achievements = [re.sub(r"^[•\-\*●▪>]\s*", "", l) for l in secs["achievements"]][:5]
    return {
        "skills": skills,
        "education": education,
        "projects": projects,
        "experience": experience,
        "achievements": achievements,
        "text_chars": len(text),
    }


def analyze_pdf(data: bytes) -> dict:
    text = extract_text(data)
    if len(text.strip()) < 40:
        raise ValueError("No readable text found. The PDF may be a scanned image.")
    return parse(text)
