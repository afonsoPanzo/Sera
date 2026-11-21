import os
import sys
from pathlib import Path

import pytest

os.environ["MOCK_MODE"] = "1"
os.environ.pop("OPENAI_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def fresh_store(tmp_path, monkeypatch):
    from app import documents
    from app.store import store

    monkeypatch.setattr(documents, "UPLOAD_DIR", tmp_path / "uploads")
    store.__init__()
    store.seed_demo()
    yield store


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)
