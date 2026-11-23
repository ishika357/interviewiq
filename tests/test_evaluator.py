import pytest

from services import evaluator, speech
from services.knowledge import questions_by_id
from services.rag import get_kb


@pytest.fixture(scope="module")
def kb():
    return get_kb({})


def score(kb, qid, answer, duration=None):
    q = questions_by_id()[qid]
    turn = {"question": q["q"], "reference": q["ref"], "concepts": q["c"], "difficulty": q["d"], "topic": q["topic"],
            "reference_source": "bank", "answer_source": "text"}
    return evaluator.heuristic_evaluate(turn, answer, speech.analyze(answer, duration), kb)


GOOD = ("Lists are mutable ordered sequences so you can modify them, while tuples are immutable. Tuples are hashable so they can be "
        "dictionary keys and they use less memory. For example I use a tuple for coordinates.")


def test_score_ordering(kb):
    good = score(kb, "py1", GOOD)["scores"]["overall"]
    ok = score(kb, "py1", "A list can be changed but a tuple cannot be changed. Tuples are faster.")["scores"]["overall"]
    vague = score(kb, "py1", "Both are data structures used to store items.")["scores"]["overall"]
    off = score(kb, "py1", "I enjoy playing cricket on weekends with my friends.")["scores"]["overall"]
    assert good > ok > vague > off


def test_idk_and_empty_score_zero(kb):
    assert score(kb, "py1", "I don't know")["scores"]["overall"] == 0
    assert score(kb, "py1", "")["scores"]["overall"] == 0


def test_wrong_topic_is_not_rewarded(kb):
    assert score(kb, "py1", "A hash table uses a hash function and chaining to handle collisions.")["scores"]["technical"] < 20


def test_evidence_is_quoted_from_answer(kb):
    ev = score(kb, "py1", GOOD)
    assert ev["evidence"]
    for e in ev["evidence"]:
        assert e["quote"] in GOOD


def test_scores_in_range_and_schema(kb):
    ev = score(kb, "ml2", "Overfitting is when a model memorizes noise in training data. Use regularization and dropout.")
    assert set(ev["scores"]) == {"overall", "technical", "relevance", "quality", "communication"}
    assert all(0 <= v <= 100 for v in ev["scores"].values())
    assert ev["rubric"]["missing"] is not None and ev["improved_answer"]


def test_filler_words_reduce_communication(kb):
    clean = score(kb, "py1", GOOD, 30)["scores"]["communication"]
    um = score(kb, "py1", "Um so basically lists are like mutable and um tuples are you know immutable and basically yeah " * 2, 30)["scores"]["communication"]
    assert um < clean


def test_speech_metrics():
    m = speech.analyze("um I think um the model is basically good basically good", 6.0)
    assert m["filler_counts"].get("um") == 2 and m["wpm"] == 110
