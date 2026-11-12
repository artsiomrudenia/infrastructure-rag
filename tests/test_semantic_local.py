"""Opt-in real-model acceptance checks; never download weights during tests."""

import json
import os
from pathlib import Path

import pytest


MODEL_DIR = os.getenv("RAG_TEST_SEMANTIC_MODEL_DIR")
pytestmark = pytest.mark.skipif(
    not MODEL_DIR, reason="Set RAG_TEST_SEMANTIC_MODEL_DIR for real local E5 checks",
)


@pytest.mark.parametrize("retriever", ["semantic", "hybrid"])
def test_local_e5_dev_and_http(monkeypatch: pytest.MonkeyPatch, retriever: str) -> None:
    from fastapi.testclient import TestClient

    from app import main
    from app.rag.evaluate import load_queries
    from app.rag.ingest import read_markdown_documents
    from app.rag.semantic import SemanticInputTooLong
    from app.rag.service import RAGService

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    root = Path(__file__).resolve().parents[1]
    corpus = root / "evaluation" / "corpus"
    assert MODEL_DIR is not None
    service = RAGService(corpus, retriever=retriever, semantic_model_dir=Path(MODEL_DIR))
    queries = load_queries(
        root / "evaluation" / "queries.json",
        {document.path for document in read_markdown_documents(corpus)},
    )
    cross_language = [
        query for query in queries if query.split == "dev" and query.group == "cross_language"
    ]
    assert cross_language
    assert any(
        set(query.relevant_paths) & {item.path for item in service.retrieve(query.question, 3)}
        for query in cross_language
    )
    question = cross_language[0].question
    expected = service.retrieve(question, 3)
    service.reindex()
    assert [item.path for item in service.retrieve(question, 3)] == [
        item.path for item in expected
    ]
    assert service.retrieve("quantum entanglement photon polarization", 3)

    with pytest.raises(SemanticInputTooLong):
        service.retrieve("memory " * 600, 3)

    monkeypatch.setattr(main, "_rag", service)
    client = TestClient(main.app)
    assert client.get("/healthz").json() == {"status": "ok"}
    response = client.post("/query", json={"question": question, "top_k": 3})
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"summary", "evidence", "recommended_actions", "sources"}
    assert payload["sources"][0]["path"] in cross_language[0].relevant_paths
    assert client.post("/reindex").status_code == 200
    assert client.post("/query", json={"question": "memory " * 600}).status_code == 422

    monkeypatch.setattr(main, "_docs_dir", corpus)
    monkeypatch.setattr(main, "_include_folders", [])
    monkeypatch.setattr(main, "_exclude_folders", [])
    monkeypatch.setattr(main, "_semantic_model_dir", MODEL_DIR)
    assert client.post("/ui/config", json={"retriever": "overlap"}).status_code == 200
    configured = client.post("/ui/config", json={"retriever": retriever})
    assert configured.status_code == 200
    assert configured.json()["retriever"] == retriever
    assert configured.json()["model_configured"] is True
    response = client.post("/query", json={"question": question, "top_k": 3})
    assert response.status_code == 200
    assert response.json()["sources"][0]["path"] in cross_language[0].relevant_paths
    assert json.loads(response.headers["X-RAG-Runtime"])["retriever"] == retriever
