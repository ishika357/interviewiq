"""Small NLP helpers shared by evaluator, RAG and speech analysis."""
from __future__ import annotations

import re

STOP = set(
    "a an the and or but if then else of to in on at by for with from as is are was were be been being it its this that these those "
    "i you he she we they me my your our their do does did done have has had will would can could should may might must not no so "
    "than too very just about into over under again also there here what which who whom how why when where all any each more most other "
    "some such only own same s t explain describe tell please define mean means give understand use used using".split()
)
_TOKEN = re.compile(r"[a-z0-9_+#]+(?:'[a-z]+)?")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


def stem(word: str) -> str:
    """Very light suffix stripper (enough to match plural/-ing/-ed forms)."""
    for suf in ("ization", "ations", "ation", "ingly", "ing", "edly", "ed", "ies", "es", "s", "ly"):
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)] + ("y" if suf == "ies" else "")
    return word


def analyzer(text: str) -> list[str]:
    """Stemmed unigrams + bigrams without stop words, used by TF-IDF."""
    toks = [stem(t) for t in tokenize(text) if t not in STOP and len(t) > 1]
    return toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def word_count(text: str) -> int:
    return len(tokenize(text))
