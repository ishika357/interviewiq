"""Optional LLM client.

Supports the Anthropic Messages API and any OpenAI-compatible chat API through plain `requests`.
If no key is configured, `is_available()` is False and every caller falls back to a transparent,
non-LLM implementation. We never fabricate LLM output.
"""
from __future__ import annotations

import json
import logging
import re

import requests
from flask import current_app, has_app_context

log = logging.getLogger("interviewiq.llm")

DEFAULT_MODELS = {"anthropic": "claude-sonnet-4-5", "openai": "gpt-4o-mini"}


def provider() -> str:
    if not has_app_context():  # e.g. unit tests of agents outside Flask
        return ""
    cfg = current_app.config
    p = cfg.get("LLM_PROVIDER", "")
    if p == "none":
        return ""
    if p == "anthropic" and cfg.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if p == "openai" and cfg.get("OPENAI_API_KEY"):
        return "openai"
    if not p:
        if cfg.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        if cfg.get("OPENAI_API_KEY"):
            return "openai"
    return ""


def is_available() -> bool:
    return bool(provider())


def complete(system: str, user: str, max_tokens: int = 1200, temperature: float = 0.2) -> str | None:
    """Return model text, or None on any failure (callers must handle None)."""
    cfg = current_app.config
    prov = provider()
    if not prov:
        return None
    model = cfg.get("LLM_MODEL") or DEFAULT_MODELS[prov]
    try:
        if prov == "anthropic":
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": cfg["ANTHROPIC_API_KEY"],
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
                timeout=cfg["LLM_TIMEOUT"],
            )
            r.raise_for_status()
            return "".join(b.get("text", "") for b in r.json().get("content", []))
        r = requests.post(
            cfg["OPENAI_BASE_URL"].rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {cfg['OPENAI_API_KEY']}"},
            json={
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=cfg["LLM_TIMEOUT"],
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as exc:  # network, auth, rate limit, malformed body
        log.warning("LLM call failed: %s", exc)
        return None


def extract_json(text: str | None) -> dict | None:
    """Pull the first JSON object out of a model reply (handles ```json fences)."""
    if not text:
        return None
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except ValueError:
        return None


def complete_json(system: str, user: str, **kw) -> dict | None:
    return extract_json(complete(system, user, **kw))
