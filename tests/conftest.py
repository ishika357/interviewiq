import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import create_app  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    return create_app({"DATABASE": str(tmp_path / "test.db"), "TESTING": True, "LLM_PROVIDER": "none"})


class Client:
    """Test client wrapper that handles the CSRF token like a browser would."""

    def __init__(self, app):
        self.c = app.test_client()
        self.c.get("/api/health")
        self._tok()

    def _tok(self):
        with self.c.session_transaction() as s:
            s["csrf"] = "tok"

    def register(self, name="Asha", email="asha@example.com", pw="password123"):
        r = self.c.post("/register", data={"name": name, "email": email, "password": pw, "csrf_token": "tok"})
        self._tok()
        return r

    def post(self, url, **kw):
        kw.setdefault("headers", {})["X-CSRF-Token"] = "tok"
        return self.c.post(url, **kw)

    def get(self, url, **kw):
        return self.c.get(url, **kw)


@pytest.fixture()
def client(app):
    c = Client(app)
    c.register()
    return c
