import json
from pathlib import Path

import pytest

from app.rag.evaluate import load_queries, ranking_metrics, run_evaluation


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluation" / "corpus"
DATASET = ROOT / "evaluation" / "queries.json"


def test_metrics_exact_values() -> None:
    metrics = ranking_metrics(["x", "a", "b"], ["a", "b", "c"], 3)
    assert metrics == pytest.approx({
        "recall_at_k": 2 / 3,
        "precision_at_k": 2 / 3,
        "mrr_at_k": 1 / 2,
        "map_at_k": (1 / 2 + 2 / 3) / 3,
    })


def test_metrics_truncation_missing_results_and_ap_denominator() -> None:
    assert ranking_metrics(["a"], ["a"], 3) == pytest.approx({
        "recall_at_k": 1, "precision_at_k": 1 / 3,
        "mrr_at_k": 1, "map_at_k": 1,
    })
    assert ranking_metrics(["a", "b", "c"], ["a", "b", "c"], 2) == pytest.approx({
        "recall_at_k": 2 / 3, "precision_at_k": 1,
        "mrr_at_k": 1, "map_at_k": 1,
    })
    assert set(ranking_metrics([], ["a"], 3).values()) == {0.0}
    assert ranking_metrics(["x", "a"], ["a"], 1)["mrr_at_k"] == 0


def test_metrics_reject_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="answerable"):
        ranking_metrics([], [], 3)
    with pytest.raises(ValueError, match="unique"):
        ranking_metrics(["a", "a"], ["a"], 3)
    with pytest.raises(ValueError, match="positive"):
        ranking_metrics([], ["a"], 0)


def test_benchmark_report_shape_and_measured_short_term_gain() -> None:
    report = run_evaluation(CORPUS, DATASET, repeats=2)
    assert report["split"] == "dev"
    assert len(report["corpus_sha256"]) == len(report["dataset_sha256"]) == 64
    for retriever in report["retrievers"].values():
        overall = retriever["overall"]
        assert overall["query_count"] == 16
        assert overall["answerable_count"] == 12
        assert overall["unanswerable_count"] == 4
        assert overall["latency_ms"]["p95"] > 0
        assert retriever["index_ms"] > 0
        assert set(retriever["by_language"]) == {"ru", "en"}
        assert retriever["by_group"]["no_answer"]["ranking"] is None
        # Near misses must remain visible, rather than being counted as correct answers.
        assert overall["no_answer"]["false_positive_rate"] >= 0.5
        assert all(row["id"].startswith("dev-") for row in retriever["queries"])
    baseline = report["retrievers"]["overlap"]["by_group"]["short_terms"]["ranking"]
    bm25 = report["retrievers"]["bm25"]["by_group"]["short_terms"]["ranking"]
    assert bm25["recall_at_k"] > baseline["recall_at_k"]
    assert report["retrievers"]["bm25"]["by_group"]["cross_language"]["ranking"]["recall_at_k"] == 0
    json.dumps(report, allow_nan=False)


def test_repeat_runs_have_identical_rankings_and_fingerprints() -> None:
    first = run_evaluation(CORPUS, DATASET, repeats=1)
    second = run_evaluation(CORPUS, DATASET, repeats=1)
    assert first["corpus_sha256"] == second["corpus_sha256"]
    assert first["dataset_sha256"] == second["dataset_sha256"]
    for name in first["retrievers"]:
        left = first["retrievers"][name]
        right = second["retrievers"][name]
        assert left["overall"]["ranking"] == right["overall"]["ranking"]
        assert [row["retrieved_paths"] for row in left["queries"]] == [
            row["retrieved_paths"] for row in right["queries"]
        ]


def test_test_split_is_explicit_and_disjoint() -> None:
    paths = {path.name for path in CORPUS.glob("*.md")}
    queries = load_queries(DATASET, paths)
    dev_families = {query.family for query in queries if query.split == "dev"}
    test_families = {query.family for query in queries if query.split == "test"}
    assert dev_families.isdisjoint(test_families)
    report = run_evaluation(CORPUS, DATASET, split="test", repeats=1)
    for retriever in report["retrievers"].values():
        assert all(row["id"].startswith("test-") for row in retriever["queries"])


@pytest.mark.parametrize("mutation", [
    "unknown_path", "duplicate_path", "duplicate_id", "duplicate_question",
    "family_leak", "bad_language", "bad_split", "empty_question", "short_question",
    "missing_field",
])
def test_dataset_validation(tmp_path: Path, mutation: str) -> None:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    first, second = payload["queries"][:2]
    if mutation == "unknown_path":
        first["relevant_paths"] = ["missing.md"]
    elif mutation == "duplicate_path":
        first["relevant_paths"] *= 2
    elif mutation == "duplicate_id":
        second["id"] = first["id"]
    elif mutation == "duplicate_question":
        second["question"] = first["question"]
    elif mutation == "family_leak":
        second["split"] = "test"
    elif mutation == "bad_language":
        first["language"] = "de"
    elif mutation == "bad_split":
        first["split"] = "train"
    elif mutation == "empty_question":
        first["question"] = " "
    elif mutation == "short_question":
        first["question"] = "IO"
    else:
        del first["family"]
    dataset = tmp_path / "queries.json"
    dataset.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_queries(dataset, {path.name for path in CORPUS.glob("*.md")})


@pytest.mark.parametrize("options", [
    {"k": 0}, {"k": 11}, {"repeats": 0}, {"split": "all"},
    {"bm25_k1": 0}, {"bm25_b": 2}, {"candidate_multiplier": 0},
])
def test_invalid_evaluation_options(options: dict) -> None:
    with pytest.raises(ValueError):
        run_evaluation(CORPUS, DATASET, **options)


def test_empty_corpus_fails_explicitly(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="corpus"):
        run_evaluation(tmp_path, DATASET)
