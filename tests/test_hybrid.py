import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.rag.hybrid import HybridIndex, reciprocal_rank_fusion
from app.rag.models import Chunk
from app.rag.service import RAGService


def test_rrf_exact_scores_missing_branch_and_corpus_order_ties() -> None:
    ranked = reciprocal_rank_fusion([0, 1, 2], [1, 2, 0], 3)
    assert [index for index, _ in ranked] == [1, 0, 2]
    assert [score for _, score in ranked] == pytest.approx([
        1 / 62 + 1 / 61, 1 / 61 + 1 / 63, 1 / 63 + 1 / 62,
    ])
    assert reciprocal_rank_fusion([2, 1], [1, 2], 2) == [
        (1, 1 / 61 + 1 / 62), (2, 1 / 61 + 1 / 62),
    ]
    assert reciprocal_rank_fusion([], [5, 2], 1) == [(5, 1 / 61)]
    assert reciprocal_rank_fusion([5], [], 3) == [(5, 1 / 61)]
    assert reciprocal_rank_fusion([], [], 3) == []


def test_rrf_validates_limit_and_duplicate_chunk_indices() -> None:
    with pytest.raises(ValueError, match="top_k"):
        reciprocal_rank_fusion([], [], 0)
    for first, second in [([1, 1], []), ([], [1, 1])]:
        with pytest.raises(ValueError, match="unique"):
            reciprocal_rank_fusion(first, second, 3)


@pytest.fixture
def encoder():
    np = pytest.importorskip("numpy")

    class FakeEncoder:
        def encode(self, texts):
            return np.array([
                [1, 0] if "memory" in text else [0, 1] for text in texts
            ], dtype=np.float32)

    return FakeEncoder()


def test_hybrid_fuses_chunk_identity_not_path_text_or_raw_score(
    encoder, monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks = [
        Chunk("same.md", "Runbook", [], 0, "identical text"),
        Chunk("same.md", "Runbook", [], 1, "identical text"),
        Chunk("other.md", "Runbook", [], 0, "other text"),
    ]
    index = HybridIndex(chunks, encoder)
    calls = []

    def lexical(question, top_k):
        calls.append(("bm25", question, top_k))
        return [(0, 100000), (2, 1)]

    def semantic(question, top_k):
        calls.append(("semantic", question, top_k))
        return [(1, 0.99), (2, -0.5)]

    monkeypatch.setattr(index._bm25, "rank_chunks", lexical)
    monkeypatch.setattr(index._semantic, "rank_chunks", semantic)
    results = index.search("question", 3)
    assert calls == [("bm25", "question", 3), ("semantic", "question", 3)]
    assert [item.path for item in results] == ["other.md", "same.md", "same.md"]
    assert [item.score for item in results] == pytest.approx([2 / 62, 1 / 61, 1 / 61])
    assert results[0].snippet == "other text"


def test_hybrid_real_branches_empty_lexical_and_empty_corpus(encoder) -> None:
    chunks = [
        Chunk("a.md", "Memory", [], 0, "memory"),
        Chunk("b.md", "Disk", [], 0, "disk"),
    ]
    index = HybridIndex(chunks, encoder)
    # No lexical overlap: semantic ranks still contribute, with no abstention.
    matches = index.search("unknown", 2)
    assert [item.path for item in matches] == ["b.md", "a.md"]
    assert [item.score for item in matches] == pytest.approx([1 / 61, 1 / 62])
    assert index.search("memory", 1)[0].path == "a.md"
    assert index.search("memory", 1)[0].score == pytest.approx(2 / 61)
    assert HybridIndex([], encoder).search("question", 3) == []
    with pytest.raises(ValueError, match="top_k"):
        index.search("question", 0)


def test_hybrid_startup_reads_env_without_changing_http_contract(
    tmp_path: Path, encoder,
) -> None:
    env = {
        **os.environ,
        "RAG_RETRIEVER": "hybrid",
        "RAG_SEMANTIC_MODEL_DIR": str(tmp_path),
        "RAG_DOCS_DIR": str(tmp_path),
        "RAG_INCLUDE_FOLDERS": "",
        "RAG_EXCLUDE_FOLDERS": "",
        "RAG_BM25_K1": "1.2",
        "RAG_BM25_B": "0.5",
        "RAG_CANDIDATE_MULTIPLIER": "2",
    }
    code = (
        "import numpy as np; import app.rag.service as service; "
        "from types import SimpleNamespace; "
        "service.E5Encoder = lambda path: SimpleNamespace("
        "encode=lambda texts: np.ones((len(texts), 2))); "
        "from app.main import _rag, info; "
        "assert _rag.retriever == 'hybrid'; "
        "assert _rag.candidate_multiplier == 2; "
        "assert _rag._hybrid._bm25.k1 == 1.2; "
        "assert _rag._hybrid._bm25.b == 0.5; "
        "assert 'retriever' not in info()"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_service_expands_both_branches_before_document_dedup(
    tmp_path: Path, encoder, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.rag.service.E5Encoder", lambda path: encoder)
    (tmp_path / "a.md").write_text("# Memory\n" + "memory\n" * 200, encoding="utf-8")
    (tmp_path / "b.md").write_text("# Memory\nmemory", encoding="utf-8")
    service = RAGService(
        tmp_path, retriever="hybrid", semantic_model_dir=tmp_path,
        candidate_multiplier=3,
    )
    index = service._hybrid
    assert index is not None
    calls = []
    lexical_rank = index._bm25.rank_chunks
    semantic_rank = index._semantic.rank_chunks

    def lexical(question, top_k):
        calls.append(("bm25", top_k))
        return lexical_rank(question, top_k)

    def semantic(question, top_k):
        calls.append(("semantic", top_k))
        return semantic_rank(question, top_k)

    monkeypatch.setattr(index._bm25, "rank_chunks", lexical)
    monkeypatch.setattr(index._semantic, "rank_chunks", semantic)
    results = service.retrieve("memory", 2)
    assert calls == [("bm25", 6), ("semantic", 6)]
    assert len(results) == 2
    assert {item.path for item in results} == {"a.md", "b.md"}
