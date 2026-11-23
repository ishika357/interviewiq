# InterviewIQ - AI Interview Intelligence Platform

Flask app that runs adaptive mock interviews (voice or text), evaluates answers with an explainable rubric,
grounds feedback in a RAG knowledge base, runs a sandboxed coding round, and builds a personalised 7-day roadmap.

## Quick start (Python 3.10+)
```bash
python -m venv venv && source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # Windows: copy .env.example .env
python app.py                                          # http://127.0.0.1:5000
```
Register an account and start an interview. It works immediately with no API key.

### Optional upgrades
| Feature | Install / configure | Without it |
|---|---|---|
| Voice transcription | `pip install openai-whisper` (or `faster-whisper`) and FFmpeg on PATH | Typed answers only (UI says so) |
| LLM evaluation, generated follow-ups, copilot phrasing | set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in `.env` | Rubric + semantic-similarity engine (labelled "no LLM key") |
| Better embeddings | `pip install sentence-transformers` | TF-IDF embeddings |
| FAISS index | `pip install faiss-cpu` | Exact NumPy cosine search (same results at this size) |
| Safer code sandbox | install Docker, set `SANDBOX_MODE=docker` | Hardened subprocess (see Security) |

## Run the tests
```bash
python -m pytest -q        # 34 tests: evaluator, sandbox, RAG, resume, adaptivity, API, security
```

## Project layout
```
app.py                  app factory, CSRF, security headers, error handlers
config.py  db.py        settings from env; SQLite schema + helpers
routes/web.py           pages (landing, auth, dashboard, setup, room, results, history, ...)
routes/api.py           JSON API (interviews, transcribe, answer, finish, copilot, coding, analytics)
services/orchestrator   interview lifecycle + idempotent submission (calls the agents below)
services/interviewer    Interviewer Agent: adaptive next-question logic
services/evaluator      Evaluation Agent: rubric scoring, evidence, optional LLM blend
services/speech         Speech Agent: ffmpeg + Whisper + pace/filler/pause analytics
services/resume         Resume Agent: PDF -> skills/projects/education (no invention)
services/roadmap        Learning Agent: 7-day plan from real weaknesses
services/coding + sandbox + sandbox_runner   Coding Agent and isolated execution
services/rag            chunking, embeddings, FAISS/NumPy index, hybrid retrieval with sources
services/copilot        post-interview assistant grounded in results + KB
data/                   questions.json (65 curated Q with reference answers + concept groups),
                        knowledge_base/*.md (RAG corpus), coding_problems.json
templates/ static/      premium dark UI (design tokens in static/css/app.css)
tests/                  pytest suite
docs/                   ARCHITECTURE.md, VIVA_NOTES.md
```

## Key behaviours
* **No fake data**: dashboard, analytics and reports are SQL over saved answers. Empty accounts show empty states.
* **Idempotent answers**: `submit_answer` checks "already saved?" first, then does a conditional `UPDATE ... WHERE answered_at IS NULL`.
  Retries, double clicks and refreshes return the stored result and never skip or duplicate a question.
* **Camera fix**: one `getUserMedia` stream is opened once and reused for the whole interview; only a new `MediaRecorder` is created per answer.
* **Honest processing screen**: lists real stages with measured milliseconds, never fake percentages.
* **Privacy**: audio is transcribed then discarded; resumes are not stored (only extracted text); camera is a local preview and is never recorded or analysed.
  DeepFace/emotion inference was intentionally removed (unreliable and not defensible).

## Security summary
CSRF tokens on every POST, password hashing (Werkzeug), per-user data access checks, login throttling, upload validation by magic bytes and size,
API keys only from environment, security headers. Candidate code never runs in the Flask process: separate process, `-I -S`, empty env,
temp cwd, CPU/memory/file-size/fd rlimits, import allow-list, removed `open/eval/exec`, per-test alarm, process-group kill, and a network
namespace (`unshare -rn`) where the OS allows. **A Python-level sandbox is not a perfect jail** - for any public deployment use `SANDBOX_MODE=docker`
(`--network none`, read-only FS, pids/memory limits). The Docker mode is implemented but was not exercised in development.

## Known limitations (be upfront in your viva)
* Heuristic evaluation depends on curated concept groups; answers phrased very differently may be under-scored. The LLM mode reduces this.
* Whisper, LLM and sentence-transformers paths are implemented but depend on packages/keys not available in the build environment; the
  LLM call path was tested only with parsing/fallback logic, not against a live API.
* In-memory login throttling resets on restart; use Redis/Flask-Limiter in production. SQLite is fine for a demo; move to PostgreSQL to scale.
* Browser behaviour was verified in headless Chromium with a fake camera/mic; test on your own browsers/devices (Chrome/Edge recommended).
