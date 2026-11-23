import io

from reportlab.pdfgen import canvas

from services import interviewer, resume
from services.rag import get_kb


def make_pdf(lines):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for ln in lines:
        c.drawString(50, y, ln)
        y -= 18
    c.save()
    return buf.getvalue()


RESUME = ["Asha Rao", "EDUCATION", "B.Tech in Computer Science (AI), Example Institute of Technology", "SKILLS",
          "Python, Flask, SQL, Machine Learning, Git", "PROJECTS", "AI Interview Analyzer - Flask app using Whisper for speech",
          "- Built audio pipeline with FFmpeg", "ACHIEVEMENTS", "- Winner of college hackathon"]


def test_resume_extraction_is_grounded():
    d = resume.analyze_pdf(make_pdf(RESUME))
    assert {"python", "flask", "sql", "machine learning", "git"} <= set(d["skills"])
    assert "docker" not in d["skills"] and "tensorflow" not in d["skills"]  # never invent skills
    assert d["projects"] and "Interview Analyzer" in d["projects"][0]["name"]
    assert any("B.Tech" in e for e in d["education"])


def test_pdf_validation():
    assert resume.validate_pdf(b"not a pdf", 1000)
    assert resume.validate_pdf(b"%PDF-1.4" + b"0" * 2000, 1000)  # too large
    assert resume.validate_pdf(make_pdf(RESUME), 10**6) is None


def test_rag_retrieves_relevant_source():
    kb = get_kb({})
    hits = kb.search("what is the vanishing gradient problem", k=3)
    assert hits and hits[0]["section"].lower().startswith("vanishing")
    assert hits[0]["source"] and hits[0]["score"] > 0
    assert kb.search("zzzz qqqq xxxx", k=3) == []


def _iv(n=10, level="Intermediate", resume_data=None):
    return {"id": 7, "role": "AI Engineer", "difficulty": level, "num_questions": n, "resume": resume_data}


def _turn(i, q, overall, answer="x"):
    return {"idx": i, "qid": q["qid"], "kind": q["kind"], "topic": q["topic"], "difficulty": q["difficulty"], "question": q["question"],
            "overall": overall, "answer_text": answer}


def test_no_repeated_questions_and_adaptivity():
    iv, turns = _iv(15), []
    for i in range(15):
        q = interviewer.next_question(iv, turns)
        assert q is not None
        turns.append(_turn(i, q, 30.0 if i % 3 == 0 else 80.0))
    qs = [t["question"] for t in turns]
    assert len(set(qs)) == len(qs)
    assert any(t["kind"] in ("probe", "followup") for t in turns)


def test_weak_answer_triggers_easier_probe_same_topic():
    iv = _iv(10, "Advanced")
    first = interviewer.next_question(iv, [])
    t0 = _turn(0, first, 90)
    second = interviewer.next_question(iv, [t0])
    t1 = _turn(1, second, 20)
    third = interviewer.next_question(iv, [t0, t1])
    assert third["kind"] == "probe" and third["topic"] == second["topic"]
    assert third["difficulty"] <= second["difficulty"]


def test_difficulty_stays_in_configured_window():
    iv, turns = _iv(15, "Beginner"), []
    for i in range(15):
        q = interviewer.next_question(iv, turns)
        assert q["difficulty"] <= 2
        turns.append(_turn(i, q, 95.0))


def test_resume_questions_use_resume_content():
    d = resume.analyze_pdf(make_pdf(RESUME))
    iv, turns = _iv(10, resume_data=d), []
    kinds = []
    for i in range(6):
        q = interviewer.next_question(iv, turns)
        kinds.append(q["kind"])
        turns.append(_turn(i, q, 60.0))
    assert "resume" in kinds
