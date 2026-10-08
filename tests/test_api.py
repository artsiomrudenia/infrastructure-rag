import os
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ["RAG_DOCS_DIR"] = str(PROJECT_ROOT / "sample_docs")
os.environ["RAG_INCLUDE_FOLDERS"] = ""
os.environ["RAG_EXCLUDE_FOLDERS"] = ""

from app.main import app

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_info() -> None:
    response = client.get("/info")
    assert response.status_code == 200
    payload = response.json()
    assert payload["project"] == "infrastructure-rag"
