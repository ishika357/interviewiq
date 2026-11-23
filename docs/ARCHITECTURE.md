# Architecture

```
Browser (HTML/CSS/JS, MediaRecorder, Chart.js)
   |  fetch + CSRF header
Flask routes (routes/web.py pages, routes/api.py JSON)         <- thin: validate, authorise, delegate
   |
services/orchestrator.py  --- owns lifecycle + SQLite writes
   |-- interviewer.py  (Interviewer Agent)   choose next question, adapt difficulty, probe / deepen
   |-- speech.py       (Speech Agent)        ffmpeg -> Whisper -> pace/filler/pause metrics
   |-- evaluator.py    (Evaluation Agent)    rubric + embeddings (+ LLM blend) -> JSON with evidence
   |-- roadmap.py      (Learning Agent)      weak topics + missed concepts -> 7-day plan
   |-- resume.py       (Resume Agent)        PDF -> skills/projects/education
   |-- coding.py -> sandbox.py -> sandbox_runner.py (Coding Agent) isolated execution
   |-- rag.py + copilot.py                   KB retrieval and the post-interview assistant
   '-- llm.py                                optional provider client; every caller has a non-LLM fallback
SQLite: users, interviews, turns (one row per question+answer), coding_submissions
```

## Interview lifecycle
1. `POST /api/interviews` validates role/difficulty/count/resume, stores the interview and creates turn 0 (always "Tell me about yourself").
2. Room loads `GET /state` (server is the source of truth, so refresh = resume).
3. Voice: `POST /transcribe` (Whisper) returns text the candidate can edit. Text is also accepted directly.
4. `POST /answer {idx, text, source, submission_id}` -> speech analytics -> evaluation -> conditional UPDATE -> choose and insert next turn.
5. After the last answer `POST /finish` aggregates scores, strengths/weaknesses and the roadmap into `report_json`.

## Adaptive logic
Target difficulty starts at the configured level and moves +1 after a score >= 75, -1 after < 45, clamped to the level's window
(Beginner 1-2, Intermediate 1-3, Advanced 2-3). A weak answer triggers a *probe* (easier, same topic); a strong one a *deeper* follow-up.
With an LLM, the follow-up is generated from the candidate's actual answer; otherwise it is chosen from the curated bank. No repeats; topics rotate.

## Scoring rubric (all 0-100)
overall = 0.45 technical + 0.20 relevance + 0.20 quality + 0.15 communication
* technical = 0.7 concept coverage (synonym groups) + 0.3 embedding similarity to the reference answer
* relevance = similarity to question+reference, gated by whether any concept matched
* quality = coverage, length vs. expected for difficulty, example present, structure
* communication = measurable delivery only (length, fillers, repeats, pace, long pauses)
LLM mode blends 70% LLM / 30% heuristic and verifies that quoted evidence really appears in the answer.

## RAG pipeline
load `data/knowledge_base/*.md` -> split by heading, then sentence-bounded chunks (<= 900 chars) -> embed (sentence-transformers or TF-IDF)
-> FAISS or NumPy cosine index -> hybrid rerank (title-match boost) -> top-k with score threshold -> sources returned to the user.
Below the threshold the copilot says it could not find the topic instead of guessing.

## API
| Method | Path | Purpose |
|---|---|---|
| POST | /api/interviews | create (multipart: role, custom_role, difficulty, num_questions, resume?) |
| POST | /api/resume/preview | parse a resume without creating an interview |
| GET | /api/interviews/<id>/state | progress + current question |
| POST | /api/interviews/<id>/transcribe | audio -> transcript |
| POST | /api/interviews/<id>/answer | idempotent answer submission |
| POST | /api/interviews/<id>/finish | build the report |
| POST | /api/interviews/<id>/copilot | ask the copilot |
| GET | /api/dashboard, /api/analytics | metrics from the database |
| POST | /api/coding/<pid>/run, /submit | run visible tests / run all tests + feedback |
All POSTs need the `X-CSRF-Token` header (see `static/js/app.js`).
