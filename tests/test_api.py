import io
import json

from reportlab.pdfgen import canvas


def start(client, n="5", role="AI Engineer", level="Intermediate"):
    r = client.post("/api/interviews", data={"role": role, "difficulty": level, "num_questions": n})
    assert r.status_code == 201, r.json
    return r.json["id"]


def state(client, iid):
    return client.get(f"/api/interviews/{iid}/state").json


def answer(client, iid, idx, text="Lists are mutable and tuples are immutable, hashable, for example coordinates.", sid="s", source="text"):
    return client.post(f"/api/interviews/{iid}/answer", json={"idx": idx, "text": text, "source": source, "submission_id": sid})


def test_pages_require_login(app):
    c = app.test_client()
    for url in ("/dashboard", "/history", "/performance", "/interview/new", "/coding"):
        assert c.get(url).status_code == 302
    assert c.get("/api/analytics").status_code == 401


def test_csrf_enforced(client):
    r = client.c.post("/api/interviews", data={"role": "AI Engineer"})
    assert r.status_code == 400


def test_full_interview_journey(client):
    iid = start(client)
    for i in range(5):
        st = state(client, iid)
        assert st["current"]["idx"] == i and st["answered"] == i
        assert answer(client, iid, i, sid=f"s{i}").status_code == 200
    assert state(client, iid)["done"]
    fin = client.post(f"/api/interviews/{iid}/finish")
    assert fin.status_code == 200
    page = client.get(f"/interview/{iid}/results")
    assert page.status_code == 200 and b"Question-wise feedback" in page.data
    assert client.get(f"/interview/{iid}/report.pdf").data[:4] == b"%PDF"
    dash = client.get("/api/dashboard").json
    assert dash["total"] == 1 and dash["average"] is not None


def test_answer_submission_is_idempotent(client):
    iid = start(client)
    r1 = answer(client, iid, 0, sid="a")
    r2 = answer(client, iid, 0, text="a different retry body", sid="a")  # retry / double click
    assert r1.json["duplicate"] is False and r2.json["duplicate"] is True
    assert r2.json["next"]["idx"] == 1
    st = state(client, iid)
    assert st["answered"] == 1  # still exactly one saved answer, no skipped question
    # stale retry of an old question after progressing
    assert answer(client, iid, 1, sid="b").status_code == 200
    stale = answer(client, iid, 0, sid="a")
    assert stale.json["duplicate"] is True and state(client, iid)["answered"] == 2


def test_cannot_skip_ahead_or_finish_early(client):
    iid = start(client)
    assert answer(client, iid, 3).status_code in (404, 409)
    assert client.post(f"/api/interviews/{iid}/finish").status_code == 409


def test_empty_answer_rejected_and_skip_scores_zero(client):
    iid = start(client)
    assert answer(client, iid, 0, text="  ").status_code == 400
    assert answer(client, iid, 0, text="", source="skipped").status_code == 200


def test_user_data_isolated(app, client):
    iid = start(client)
    from tests.conftest import Client
    other = Client(app)
    other.register("Eve", "eve@example.com")
    assert other.get(f"/interview/{iid}/results").status_code == 404
    assert other.get(f"/api/interviews/{iid}/state").status_code == 404
    assert answer(other, iid, 0).status_code == 404


def test_validation_errors(client):
    assert client.post("/api/interviews", data={"role": "Wizard", "difficulty": "Beginner", "num_questions": "5"}).status_code == 400
    assert client.post("/api/interviews", data={"role": "AI Engineer", "difficulty": "Easy", "num_questions": "5"}).status_code == 400
    assert client.post("/api/interviews", data={"role": "AI Engineer", "difficulty": "Beginner", "num_questions": "7"}).status_code == 400
    bad = client.post("/api/interviews", data={"role": "AI Engineer", "difficulty": "Beginner", "num_questions": "5",
                                               "resume": (io.BytesIO(b"MZ not a pdf"), "evil.pdf")}, content_type="multipart/form-data")
    assert bad.status_code == 400


def test_resume_upload_personalises(client):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i, ln in enumerate(["SKILLS", "Python, Flask, SQL", "PROJECTS", "Stock Predictor - LSTM model in Python"]):
        c.drawString(50, 800 - 18 * i, ln)
    c.save()
    r = client.post("/api/interviews", data={"role": "Python Developer", "difficulty": "Intermediate", "num_questions": "10",
                                             "resume": (io.BytesIO(buf.getvalue()), "cv.pdf")}, content_type="multipart/form-data")
    assert r.status_code == 201 and "python" in r.json["resume"]["skills"]


def test_audio_upload_validation(client):
    iid = start(client)
    r = client.post(f"/api/interviews/{iid}/transcribe", data={"idx": "0", "audio": (io.BytesIO(b"hello not audio" * 50), "a.webm")},
                    content_type="multipart/form-data")
    assert r.status_code == 400 and "Unsupported" in r.json["error"]


def test_copilot_grounded_and_refuses_unknown(client):
    iid = start(client)
    for i in range(5):
        answer(client, iid, i, sid=f"s{i}")
    client.post(f"/api/interviews/{iid}/finish")
    r = client.post(f"/api/interviews/{iid}/copilot", json={"message": "explain the vanishing gradient problem"}).json
    assert r["sources"] and "gradient" in r["answer"].lower()
    r = client.post(f"/api/interviews/{iid}/copilot", json={"message": "explain quantum chromodynamics lattice"}).json
    assert not r["sources"] and "knowledge base" in r["answer"]


def test_coding_flow(client):
    good = "def two_sum(nums, target):\n    seen = {}\n    for i, x in enumerate(nums):\n        if target - x in seen:\n            return [seen[target - x], i]\n        seen[x] = i\n"
    r = client.post("/api/coding/c1/submit", json={"code": good}).json
    assert r["passed"] == r["total"] == 5
    assert r["results"][-1]["hidden"] and "expected" not in r["results"][-1]  # hidden tests are not leaked
    assert r["feedback"]["complexity"]["time"] == "O(n)"
    run = client.post("/api/coding/c1/run", json={"code": "def two_sum(a, b):\n    return []"}).json
    assert run["total"] == 2 and run["passed"] == 0


def test_dashboard_has_no_fake_data(client):
    d = client.get("/api/dashboard").json
    assert d["total"] == 0 and d["average"] is None and d["best"] is None and d["trend"] == []
