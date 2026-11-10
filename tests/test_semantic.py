import os
from pathlib import Path
import subprocess
import sys

import pytest

np = pytest.importorskip("numpy")

from app.rag.models import Chunk
from app.rag.semantic import E5Encoder, SemanticIndex, SemanticInputTooLong
from app.rag.service import RAGService


class FakeEncoder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.fail = False

    def encode(self, texts: list[str]):
        self.calls.append(texts)
        if self.fail:
            raise RuntimeError("Embedding failure")
        return np.array([
            [1.0, 0.0] if "memory" in text else [0.0, 1.0]
            for text in texts
        ], dtype=np.float32)


def make_chunk(text: str, path: str = "doc.md", index: int = 0) -> Chunk:
    return Chunk(path=path, title="Runbook", tags=[], chunk_id=index, text=text)


def test_e5_prefixes_index_once_cosine_and_stable_ties() -> None:
    encoder = FakeEncoder()
    index = SemanticIndex([
        make_chunk("memory", "memory.md"),
        make_chunk("disk", "a.md"),
        make_chunk("disk", "b.md"),
    ], encoder)
    assert encoder.calls == [[
        "passage: Runbook\nmemory",
        "passage: Runbook\ndisk",
        "passage: Runbook\ndisk",
    ]]
    matches = index.search("disk", 3)
    assert [item.path for item in matches] == ["a.md", "b.md", "memory.md"]
    assert [item.score for item in matches] == pytest.approx([1, 1, 0])
    assert encoder.calls[-1] == ["query: disk"]
    index.search("memory", 1)
    assert len(encoder.calls) == 3


def test_normalization_and_negative_scores_are_ranks_not_abstention() -> None:
    class Encoder:
        def encode(self, texts):
            if texts[0].startswith("passage:"):
                return np.array([[3, 0], [-4, 0]])
            return np.array([[2, 0]])

    index = SemanticIndex([make_chunk("a"), make_chunk("b")], Encoder())
    assert [match.score for match in index.search("unknown", 10)] == [1, -1]


def test_empty_index_does_not_encode() -> None:
    encoder = FakeEncoder()
    assert SemanticIndex([], encoder).search("question", 3) == []
    assert encoder.calls == []
    with pytest.raises(ValueError, match="top_k"):
        SemanticIndex([], encoder).search("question", 0)


@pytest.mark.parametrize("vectors", [
    np.array([1, 0]),
    np.array([[1, 0], [1, 0]]),
    np.empty((1, 0)),
    np.array([[0, 0]]),
    np.array([[np.nan, 0]]),
    np.array([[np.inf, 0]]),
])
def test_invalid_vectors_are_explicit_errors(vectors) -> None:
    class Encoder:
        def encode(self, texts):
            return vectors

    with pytest.raises(ValueError):
        SemanticIndex([make_chunk("text")], Encoder())


def test_query_dimension_mismatch() -> None:
    class Encoder:
        def encode(self, texts):
            return np.ones((len(texts), 2 if texts[0].startswith("passage:") else 3))

    with pytest.raises(ValueError, match="dimensions"):
        SemanticIndex([make_chunk("text")], Encoder()).search("query", 3)


@pytest.mark.parametrize("retriever", ["semantic", "hybrid"])
def test_model_path_required_and_missing_directory(tmp_path: Path, retriever: str) -> None:
    with pytest.raises(ValueError, match="semantic_model_dir"):
        RAGService(tmp_path, retriever=retriever)
    with pytest.raises(ValueError, match="does not exist"):
        E5Encoder(tmp_path / "missing")


def test_model_loader_is_cpu_local_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    calls = []

    def load(path, **kwargs):
        calls.append((path, kwargs))
        return object()

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        set_num_threads=lambda count: calls.append(count),
    ))
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(
        SentenceTransformer=load,
    ))
    E5Encoder(tmp_path)
    assert calls == [
        4,
        (str(tmp_path.resolve()), {
            "device": "cpu", "local_files_only": True, "trust_remote_code": False,
        }),
    ]


def test_missing_optional_dependencies_fail_explicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    original_import = builtins.__import__

    def import_without_torch(name, *args, **kwargs):
        if name == "torch":
            raise ImportError("No torch installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_torch)
    with pytest.raises(RuntimeError, match="requirements-semantic.txt"):
        E5Encoder(tmp_path)


@pytest.mark.parametrize("retriever", ["semantic", "hybrid"])
def test_service_reindex_reuses_encoder_and_preserves_index_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    retriever: str,
) -> None:
    encoder = FakeEncoder()
    loaders = []

    def load(path):
        loaders.append(path)
        return encoder

    monkeypatch.setattr("app.rag.service.E5Encoder", load)
    doc = tmp_path / "memory.md"
    doc.write_text("# Runbook\n" + "memory\n" * 200, encoding="utf-8")
    service = RAGService(tmp_path, retriever=retriever, semantic_model_dir=tmp_path)
    assert len(service.retrieve("memory", 3)) == 1
    assert len(loaders) == 1
    before = service.retrieve("memory")
    encoder.fail = True
    doc.write_text("# Runbook\ndisk", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Embedding failure"):
        service.reindex()
    encoder.fail = False
    assert service.retrieve("memory") == before
    service.reindex()
    assert len(loaders) == 1
    assert service.chunk_count == 1
    expected_score = 0 if retriever == "semantic" else 2 / 61
    assert service.retrieve("memory")[0].score == pytest.approx(expected_score)
    assert "disk" in service.retrieve("memory")[0].snippet
    doc.unlink()
    service.reindex()
    assert service.retrieve("memory") == []


def test_token_limit_rejects_input_before_model_encode() -> None:
    class Model:
        max_seq_length = 4

        def tokenizer(self, texts, **kwargs):
            assert kwargs == {"truncation": False, "add_special_tokens": True}
            return {"input_ids": [[1] * len(text.split()) for text in texts]}

        def encode(self, texts, **kwargs):
            return np.ones((len(texts), 2))

    encoder = E5Encoder.__new__(E5Encoder)
    encoder._model = Model()
    assert encoder.encode(["query: small"]).shape == (1, 2)
    with pytest.raises(SemanticInputTooLong, match="4 tokens"):
        encoder.encode(["query: this input is too long"])


@pytest.mark.parametrize("retriever", ["semantic", "hybrid"])
def test_semantic_api_contract_and_token_limit_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    retriever: str,
) -> None:
    from fastapi.testclient import TestClient
    from app import main

    monkeypatch.setattr("app.rag.service.E5Encoder", lambda path: FakeEncoder())
    (tmp_path / "memory.md").write_text("# Memory\nmemory", encoding="utf-8")
    service = RAGService(tmp_path, retriever=retriever, semantic_model_dir=tmp_path)
    monkeypatch.setattr(main, "_rag", service)
    client = TestClient(main.app)
    response = client.post("/query", json={"question": "memory", "top_k": 3})
    assert response.status_code == 200
    assert set(response.json()) == {"summary", "evidence", "recommended_actions", "sources"}
    assert set(response.json()["sources"][0]) == {"path", "title", "snippet", "score"}
    assert client.post("/reindex").status_code == 200

    def fail(question, top_k):
        raise SemanticInputTooLong("Input too long")

    monkeypatch.setattr(service, "query", fail)
    response = client.post("/query", json={"question": "memory"})
    assert response.status_code == 422
    assert response.json()["detail"] == "Input too long"


def test_evaluation_opt_in_four_retrievers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.rag.evaluate import run_evaluation

    monkeypatch.setattr("app.rag.service.E5Encoder", lambda path: FakeEncoder())
    root = Path(__file__).resolve().parents[1]
    report = run_evaluation(
        root / "evaluation" / "corpus", root / "evaluation" / "queries.json",
        repeats=1, semantic_model_dir=tmp_path,
    )
    assert set(report["retrievers"]) == {"overlap", "bm25", "semantic", "hybrid"}
    assert report["config"]["semantic_query_prefix"] == "query: "
    assert report["config"]["semantic_model_dir"] == str(tmp_path.resolve())
    assert report["retrievers"]["semantic"]["overall"]["no_answer"]["false_positive_rate"] == 1
    assert report["retrievers"]["hybrid"]["overall"]["no_answer"]["false_positive_rate"] == 1
    assert report["config"]["hybrid_rrf_c"] == 60
    assert report["config"]["hybrid_weights"] == [1, 1]
    assert report["config"]["hybrid_fusion_unit"] == "chunk"
    assert report["config"]["hybrid_branch_depth"] == 15
    assert all(
        len(row["retrieved_paths"]) == len(set(row["retrieved_paths"]))
        for mode in ("semantic", "hybrid")
        for row in report["retrievers"][mode]["queries"]
    )


def test_lexical_imports_do_not_load_ml_packages() -> None:
    env = {**os.environ, "RAG_RETRIEVER": "overlap"}
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; from app.rag.service import RAGService; "
         "from pathlib import Path; RAGService(Path('sample_docs')); "
         "assert not any(n in sys.modules for n in "
         "('torch', 'numpy', 'sentence_transformers'))"],
        cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
