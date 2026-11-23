# Viva preparation notes

**One-line pitch:** an adaptive interview platform whose scores are explainable, whose feedback is grounded in a knowledge base, and whose code execution is isolated.

## Likely questions and strong answers
* **Why not just call an LLM for everything?** LLMs vary run to run and can hallucinate. The rubric (concept coverage + embeddings) is deterministic and explainable; the LLM is an optional layer, blended 70/30, with evidence verification.
* **What is RAG and where is it used?** Retrieve relevant KB chunks and give them to the generator so answers cite sources. Used in the copilot and in roadmap resource links. Pipeline: chunk -> embed -> index -> retrieve -> ground -> cite.
* **TF-IDF vs sentence embeddings?** TF-IDF matches words; SBERT matches meaning. The system auto-upgrades when sentence-transformers is installed.
* **How is the interview adaptive?** Score-driven difficulty inside a window, probe on weak answers, deeper on strong ones, LLM-generated follow-ups when available.
* **How do you prevent duplicate submissions?** Check stored answer first, then conditional UPDATE (`WHERE answered_at IS NULL`), plus a per-answer submission id and a disabled button. The DB `UNIQUE(interview_id, idx)` is the last guard.
* **Why remove DeepFace?** Facial emotion inference is unreliable and ethically questionable for hiring-style tools; the product only measures delivery (pace, fillers, pauses).
* **Is the sandbox secure?** Layered (process isolation, rlimits, import allow-list, no file access, timeouts, network namespace). Not a perfect jail; production should use Docker/gVisor/Firecracker.
* **How would you scale?** PostgreSQL, a job queue (Celery/RQ) for Whisper/LLM calls, Redis rate limiting, object storage, containerised sandbox workers.
* **Limitations?** Concept groups need curation; heuristic scoring can under-score unusual phrasing; small question bank (65); no proctoring.

## Demo script (5 minutes)
1. Register; start a 5-question AI Engineer interview with a resume. 2. Give one strong, one weak, one "I don't know" answer and show the probe follow-up.
3. Finish: show scores with evidence, concept chips, improved answers, roadmap with KB sources. 4. Ask the Copilot "why did I lose marks" and an unknown topic (it refuses to guess).
5. Coding: submit an O(n^2) Two Sum and show the complexity hint; run an infinite loop and show the timeout. 6. Performance page: heatmap and trends.
