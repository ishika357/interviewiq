"""Central configuration. Secrets come from environment variables (.env), never from code."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _secret_key() -> str:
    """Use SECRET_KEY if set, otherwise create and persist a random one (dev convenience)."""
    key = os.getenv("SECRET_KEY")
    if key:
        return key
    instance = BASE_DIR / "instance"
    instance.mkdir(exist_ok=True)
    path = instance / "secret_key"
    if not path.exists():
        path.write_text(secrets.token_hex(32))
    return path.read_text().strip()


class Config:
    BASE_DIR = BASE_DIR
    INSTANCE_DIR = BASE_DIR / "instance"
    DATA_DIR = BASE_DIR / "data"
    DATABASE = os.getenv("DATABASE_PATH", str(BASE_DIR / "instance" / "interviewiq.db"))
    UPLOAD_DIR = BASE_DIR / "instance" / "uploads"
    SECRET_KEY = _secret_key()
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # hard upper bound for any request body

    # Upload limits
    MAX_AUDIO_BYTES = 15 * 1024 * 1024
    MAX_RESUME_BYTES = 5 * 1024 * 1024

    # LLM (optional). provider: anthropic | openai | none (auto-detected from keys)
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").lower()
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "")
    LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "40"))

    # Speech
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

    # Embeddings: "auto" tries sentence-transformers then TF-IDF
    EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "auto").lower()
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # Code sandbox: "subprocess" (default) or "docker"
    SANDBOX_MODE = os.getenv("SANDBOX_MODE", "subprocess").lower()
    SANDBOX_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "10"))
    SANDBOX_MEMORY_MB = int(os.getenv("SANDBOX_MEMORY_MB", "256"))

    TESTING = False
