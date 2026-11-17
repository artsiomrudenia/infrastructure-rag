import os
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ["RAG_DOCS_DIR"] = str(PROJECT_ROOT / "sample_docs")
os.environ["RAG_INCLUDE_FOLDERS"] = ""
os.environ["RAG_EXCLUDE_FOLDERS"] = ""

from app.main import app
from app.rag.service import RAGService

client = TestClient(app)


def test_context_endpoint_returns_bounded_source_references(
    tmp_path: Path, monkeypatch,
) -> None:
    import app.main as main

    (tmp_path / "storage.md").write_text(
        "# Storage runbook\n\n## Symptoms\n"
        + ("Storage latency rises while capacity is available.\n" * 12)
        + "\n## Checks\n"
        + ("Measure IO wait and compare queue depth with provisioned IOPS.\n" * 12),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "_rag", RAGService(tmp_path))

    response = client.post("/context", json={
        "question": "storage latency queue IOPS",
        "max_chunks": 4,
        "max_chars": 256,
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload["context"]
    assert payload["context_chars"] == len(payload["context"]) <= 256
    assert payload["max_chars"] == 256
    assert payload["truncated"] is True
    assert payload["sources"]
    for source in payload["sources"]:
        assert source["source_id"] in payload["context"]
        assert source["path"] == "storage.md"
        assert source["section"] in {"Symptoms", "Checks"}
        assert isinstance(source["chunk_id"], int)

    no_match = client.post("/context", json={
        "question": "quantum entanglement satellites",
    })
    assert no_match.status_code == 200
    assert no_match.json()["context"] == ""
    assert no_match.json()["sources"] == []


def test_context_endpoint_rejects_out_of_range_limits() -> None:
    for body in (
        {"question": "valid question", "max_chunks": 0},
        {"question": "valid question", "max_chars": 31},
        {"question": "valid question", "max_chars": 20001},
    ):
        assert client.post("/context", json=body).status_code == 422