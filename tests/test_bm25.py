import math
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.rag.bm25 import BM25Index, tokenize_bm25
from app.rag.models import Chunk
from app.rag.retrieval import search_chunks
from app.rag.service import RAGService


def chunk(text: str, path: str = "runbook.md", chunk_id: int = 0) -> Chunk:
    return Chunk(path=path, title="", tags=[], chunk_id=chunk_id, text=text)


def test_tokenizer_keeps_short_terms_identifiers_and_cyrillic() -> None:
    assert tokenize_bm25("How to IO IP df -i ERR_AUTH_42 node-a Ёж") == [
        "io", "ip", "df", "i", "err_auth_42", "node-a", "ёж",
    ]


def test_single_chunk_score_matches_bm25_formula() -> None:
    index = BM25Index([chunk("fault fault")], k1=1.5, b=0.75)
    result = index.search("fault fault", 1)[0]
    # Field includes the path token as well as two body tokens.
    expected = math.log(1 + 0.5 / 1.5) * (2 * 2.5 / (2 + 1.5))
    assert result.score == pytest.approx(expected)


def test_bm25_length_normalization_and_rare_terms() -> None:
    chunks = [
        chunk("fault " + "noise " * 100, "long.md"),
        chunk("fault", "short.md"),
        chunk("rare", "rare.md"),
    ]
    results = BM25Index(chunks).search("fault", 3)
    assert [item.path for item in results] == ["short.md", "long.md"]
    unnormalized = BM25Index(chunks, b=0).search("fault", 3)
    assert unnormalized[0].score == pytest.approx(unnormalized[1].score)
    ranked = BM25Index([
        chunk("common rare", "a.md"),
        chunk("common common", "b.md"),
        chunk("common common", "c.md"),
    ], b=0).search("common rare", 3)
    assert ranked[0].path == "a.md"


def test_short_terms_improve_over_unchanged_baseline() -> None:
    chunks = [chunk("IO IP ERR_AUTH_42 node-a")]
    assert search_chunks(chunks, "IO", 3) == []
    assert BM25Index(chunks).search("IO", 3)[0].path == "runbook.md"
    assert BM25Index(chunks).search("err_auth_42", 3)
    assert BM25Index(chunks).search("node-a", 3)


def test_empty_unknown_and_stopword_queries() -> None:
    assert BM25Index([]).search("fault", 3) == []
    index = BM25Index([chunk("fault")])
    for question in ("", "the and how", "unknown", "!!!"):
        assert index.search(question, 3) == []
    assert BM25Index([chunk("", path="")]).search("fault", 3) == []


def test_ties_keep_corpus_order_and_limit() -> None:
    index = BM25Index([chunk("fault", "a.md"), chunk("fault", "b.md")])
    assert [item.path for item in index.search("fault", 1)] == ["a.md"]


@pytest.mark.parametrize("k1,b", [
    (0, 0.75), (-1, 0.75), (float("inf"), 0.75),
    (float("nan"), 0.75), (1.5, -0.1), (1.5, 1.1), (1.5, float("nan")),
])
def test_invalid_bm25_parameters(k1: float, b: float) -> None:
    with pytest.raises(ValueError):
        BM25Index([], k1=k1, b=b)


def test_invalid_retrieval_options(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown retriever"):
        RAGService(tmp_path, retriever="unknown")
    with pytest.raises(ValueError, match="candidate_multiplier"):
        RAGService(tmp_path, candidate_multiplier=0)
    with pytest.raises(ValueError, match="top_k"):
        RAGService(tmp_path).retrieve("fault", 0)
    with pytest.raises(ValueError, match="top_k"):
        BM25Index([]).search("fault", 0)


def test_bm25_reindex_rebuilds_index_and_deduplicates(tmp_path: Path) -> None:
    first = tmp_path / "first.md"
    first.write_text("# First\n" + "IO failure\n" * 200, encoding="utf-8")
    (tmp_path / "second.md").write_text("# Second\nIO issue", encoding="utf-8")
    service = RAGService.from_docs_directory(tmp_path, retriever="bm25")
    assert len(service.retrieve("IO", 2)) == 2
    assert len({item.path for item in service.retrieve("IO", 2)}) == 2
    first.write_text("# First\nhealthy", encoding="utf-8")
    (tmp_path / "second.md").write_text("# Second\nhealthy", encoding="utf-8")
    service.reindex()
    assert service.query("IO").sources == []
    assert service.document_count == 2
    assert service.chunk_count == 2


def test_failed_reindex_preserves_existing_index(tmp_path: Path) -> None:
    document = tmp_path / "io.md"
    document.write_text("# IO\nIO latency", encoding="utf-8")
    service = RAGService(tmp_path, retriever="bm25")
    before = service.retrieve("IO")
    document.write_bytes(b"\xff")
    with pytest.raises(UnicodeDecodeError):
        service.reindex()
    assert service.retrieve("IO") == before
    assert service.document_count == service.chunk_count == 1


@pytest.mark.parametrize("override,expected_error", [
    ({}, None),
    ({"RAG_RETRIEVER": "invalid"}, "Unknown retriever"),
    ({"RAG_BM25_K1": "0"}, "BM25 k1"),
    ({"RAG_BM25_B": "1.1"}, "BM25 b"),
    ({"RAG_CANDIDATE_MULTIPLIER": "0"}, "candidate_multiplier"),
])
def test_startup_reads_retriever_configuration(
    tmp_path: Path, override: dict[str, str], expected_error: str | None,
) -> None:
    env = {
        **os.environ,
        "RAG_DOCS_DIR": str(tmp_path),
        "RAG_INCLUDE_FOLDERS": "",
        "RAG_EXCLUDE_FOLDERS": "",
        "RAG_RETRIEVER": "bm25",
        "RAG_BM25_K1": "1.2",
        "RAG_BM25_B": "0.5",
        "RAG_CANDIDATE_MULTIPLIER": "10",
        **override,
    }
    result = subprocess.run(
        [sys.executable, "-c",
         "from app.main import _rag; "
         "assert _rag.retriever == 'bm25'; "
         "assert _rag.bm25_k1 == 1.2; "
         "assert _rag.bm25_b == 0.5; "
         "assert _rag.candidate_multiplier == 10"],
        cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, timeout=30,
    )
    if expected_error is None:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0
        assert expected_error in result.stderr


def test_default_service_preserves_overlap_ranking() -> None:
    service = RAGService(Path("sample_docs"))
    question = "error rate after deployment"
    expected = service._deduplicate_by_path(
        search_chunks(service._chunks, question, 15), 3
    )
    assert service.retrieve(question) == expected


def test_bm25_api_keeps_contract(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from app import main

    (tmp_path / "io.md").write_text(
        "# IO latency\n## Checks\n1. Measure IO wait.\n", encoding="utf-8"
    )
    monkeypatch.setattr(main, "_rag", RAGService(tmp_path, retriever="bm25"))
    client = TestClient(main.app)
    response = client.post("/query", json={"question": "IO latency", "top_k": 2})
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"summary", "evidence", "recommended_actions", "sources"}
    assert set(payload["sources"][0]) == {"path", "title", "snippet", "score"}
    assert payload["sources"][0]["path"] == "io.md"
    assert payload["recommended_actions"] == ["Measure IO wait."]
    assert client.post("/reindex").json() == {
        "indexed_documents": 1, "indexed_chunks": 1,
    }
    assert client.post("/query", json={"question": "unicorn"}).json()["sources"] == []
