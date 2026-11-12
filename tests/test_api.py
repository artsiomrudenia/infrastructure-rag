import json
import os
from pathlib import Path

import pytest
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


def test_web_workspace() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Infrastructure RAG" in response.text
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_ui_config() -> None:
    response = client.get("/ui/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["retriever"] in {"overlap", "bm25", "semantic", "hybrid"}
    assert payload["generation"] is False


def test_info() -> None:
    response = client.get("/info")
    assert response.status_code == 200
    payload = response.json()
    assert payload["project"] == "infrastructure-rag"


@pytest.fixture
def runtime(monkeypatch):
    import app.main as main
    from app.rag.service import RAGService

    monkeypatch.setattr(main, "_rag", RAGService(PROJECT_ROOT / "sample_docs"))
    monkeypatch.setattr(main, "_semantic_model_dir", "")
    return main


def test_runtime_switch_and_query_attribution(runtime) -> None:
    settings = {"retriever": "bm25", "bm25_k1": 1.2, "bm25_b": 0.5, "candidate_multiplier": 8}
    response = client.post("/ui/config", json=settings)
    assert response.status_code == 200
    assert all(response.json()[key] == value for key, value in settings.items())
    response = client.post("/query", json={"question": "CrashLoopBackOff", "top_k": 1})
    assert response.status_code == 200
    assert json.loads(response.headers["X-RAG-Runtime"])["retriever"] == "bm25"
    assert set(response.json()) == {"summary", "evidence", "recommended_actions", "sources"}
    assert client.post("/reindex").status_code == 200
    assert client.post("/ui/config", json={"retriever": "overlap"}).status_code == 200
    assert client.get("/ui/config").json()["retriever"] == "overlap"


@pytest.mark.parametrize("settings", [
    {"retriever": "unknown"},
    {"retriever": "bm25", "bm25_k1": 0},
    {"retriever": "bm25", "bm25_k1": 11},
    {"retriever": "bm25", "bm25_b": -0.1},
    {"retriever": "bm25", "bm25_b": 1.1},
    {"retriever": "overlap", "candidate_multiplier": 0},
    {"retriever": "overlap", "candidate_multiplier": 51},
    {"retriever": "semantic"},
    {"retriever": "hybrid"},
])
def test_runtime_rejects_invalid_settings(runtime, settings) -> None:
    original = runtime._rag
    assert client.post("/ui/config", json=settings).status_code == 422
    assert runtime._rag is original


def test_runtime_build_failure_keeps_index(runtime, monkeypatch) -> None:
    original = runtime._rag
    before = client.post("/query", json={"question": "CrashLoopBackOff"}).json()

    def fail_build(*args, **kwargs):
        raise RuntimeError("Index build failed")

    monkeypatch.setattr(runtime.RAGService, "from_docs_directory", fail_build)
    assert client.post("/ui/config", json={"retriever": "bm25"}).status_code == 503
    assert runtime._rag is original
    assert client.post("/query", json={"question": "CrashLoopBackOff"}).json() == before
