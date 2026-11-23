"""RAG knowledge base: load -> chunk -> embed -> index -> retrieve (with source references).

Embedding backends:
  * sentence-transformers (if installed and EMBEDDING_BACKEND is auto/sbert)
  * TF-IDF with stemming (always available, no download needed)
Vector index: FAISS if installed, otherwise exact cosine search with NumPy (identical results for this corpus size).
"""
from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

import numpy as np

from .textutil import analyzer, sentences

log = logging.getLogger("interviewiq.rag")
KB_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge_base"
MAX_CHUNK_CHARS = 900


class Embedder:
    """Turns text into L2-normalised vectors. Backend is chosen once at fit time."""

    def __init__(self, corpus: list[str], backend: str = "auto", model_name: str = "all-MiniLM-L6-v2"):
        self.name = "tfidf"
        self._st = None
        self._tfidf = None
        if backend in ("auto", "sbert", "sentence-transformers"):
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                self._st = SentenceTransformer(model_name)
                self.name = f"sentence-transformers:{model_name}"
            except Exception as exc:
                if backend != "auto":
                    log.warning("sentence-transformers unavailable (%s); using TF-IDF", exc)
        if self._st is None:
            from sklearn.feature_extraction.text import TfidfVectorizer

            self._tfidf = TfidfVectorizer(analyzer=analyzer, sublinear_tf=True)
            self._tfidf.fit(corpus)

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._st is not None:
            v = np.asarray(self._st.encode(texts, normalize_embeddings=True), dtype="float32")
            return v
        m = self._tfidf.transform(texts).toarray().astype("float32")
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return m / norms


def load_chunks() -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(KB_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title_m = re.match(r"#\s+(.+)", text)
        title = title_m.group(1).strip() if title_m else path.stem
        for block in re.split(r"\n(?=## )", text):
            if not block.startswith("## "):
                continue
            head, _, body = block.partition("\n")
            section = head[3:].strip()
            body = body.strip()
            pieces, cur = [], ""
            for s in sentences(body):
                if len(cur) + len(s) > MAX_CHUNK_CHARS and cur:
                    pieces.append(cur.strip())
                    cur = ""
                cur += s + " "
            if cur.strip():
                pieces.append(cur.strip())
            for i, piece in enumerate(pieces):
                chunks.append({
                    "id": f"{path.stem}#{section}#{i}",
                    "text": piece,
                    "source": title,
                    "section": section,
                    "file": path.name,
                })
    return chunks


class KnowledgeBase:
    def __init__(self, backend: str = "auto", model_name: str = "all-MiniLM-L6-v2"):
        self.chunks = load_chunks()
        # the section title is repeated so a query that names the concept matches its heading strongly
        texts = [f"{c['section']}. {c['section']}. {c['text']}" for c in self.chunks]
        self.embedder = Embedder(texts, backend, model_name)
        self.matrix = self.embedder.encode(texts)
        self.index = None
        try:
            import faiss  # type: ignore

            self.index = faiss.IndexFlatIP(self.matrix.shape[1])
            self.index.add(self.matrix)
        except Exception:
            self.index = None
        self.index_name = "faiss" if self.index is not None else "numpy-cosine"

    def search(self, query: str, k: int = 3, min_score: float = 0.12) -> list[dict]:
        """Vector search + small title-match boost (hybrid ranking). Returns chunks with source references."""
        if not query.strip() or not self.chunks:
            return []
        q = self.embedder.encode([query])
        pool = min(len(self.chunks), k + 6)
        if self.index is not None:
            scores, ids = self.index.search(q, pool)
            pairs = list(zip(ids[0].tolist(), scores[0].tolist()))
        else:
            sims = (self.matrix @ q[0]).tolist()
            pairs = sorted(enumerate(sims), key=lambda p: p[1], reverse=True)[:pool]
        q_terms = {t for t in analyzer(query) if "_" not in t}
        ranked = []
        for i, score in pairs:
            if i < 0 or score < min_score:
                continue
            title_terms = {t for t in analyzer(self.chunks[i]["section"]) if "_" not in t}
            boost = 0.15 * len(q_terms & title_terms) / len(q_terms) if q_terms else 0.0
            ranked.append((i, score, score + boost))
        ranked.sort(key=lambda r: r[2], reverse=True)
        return [{**self.chunks[i], "score": round(float(raw), 3)} for i, raw, _ in ranked[:k]]

    def similarity(self, a: str, b: str) -> float:
        """Cosine similarity of two texts in this embedding space (0..1)."""
        va, vb = self.embedder.encode([a, b])
        return float(max(0.0, np.dot(va, vb)))


_kb: KnowledgeBase | None = None
_lock = threading.Lock()


def get_kb(config=None) -> KnowledgeBase:
    global _kb
    with _lock:
        if _kb is None:
            cfg = config or {}
            _kb = KnowledgeBase(cfg.get("EMBEDDING_BACKEND", "auto"), cfg.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
            log.info("KB ready: %d chunks, embeddings=%s, index=%s", len(_kb.chunks), _kb.embedder.name, _kb.index_name)
        return _kb
