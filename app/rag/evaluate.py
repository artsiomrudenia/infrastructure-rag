"""Offline document-level evaluation of the same retrievers used by /query."""

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
from time import perf_counter

from app.rag.ingest import read_markdown_documents
from app.rag.hybrid import RRF_C
from app.rag.service import RAGService


@dataclass(frozen=True)
class EvaluationQuery:
    id: str
    split: str
    family: str
    language: str
    group: str
    question: str
    relevant_paths: list[str]


@dataclass(frozen=True)
class EvaluatedQuery:
    id: str
    language: str
    group: str
    relevant_paths: list[str]
    retrieved_paths: list[str]
    metrics: dict[str, float]
    latency_ms: float


def ranking_metrics(
    retrieved: list[str], relevant: list[str], k: int
) -> dict[str, float]:
    if k < 1:
        raise ValueError("k must be positive")
    if not relevant:
        raise ValueError("Ranking metrics require an answerable query")
    if len(retrieved) != len(set(retrieved)):
        raise ValueError("Retrieved paths must be unique")
    relevant_set = set(relevant)
    hits = 0
    first_reciprocal_rank = 0.0
    precision_sum = 0.0
    for rank, path in enumerate(retrieved[:k], start=1):
        if path in relevant_set:
            hits += 1
            precision_sum += hits / rank
            if first_reciprocal_rank == 0:
                first_reciprocal_rank = 1 / rank
    return {
        "recall_at_k": hits / len(relevant_set),
        "precision_at_k": hits / k,
        "mrr_at_k": first_reciprocal_rank,
        "map_at_k": precision_sum / min(len(relevant_set), k),
    }


def load_queries(path: Path, corpus_paths: set[str]) -> list[EvaluationQuery]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("Evaluation dataset must have version 1")
    rows = payload.get("queries")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Evaluation dataset must contain queries")
    queries: list[EvaluationQuery] = []
    seen_ids: set[str] = set()
    seen_questions: set[str] = set()
    family_splits: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each query must be an object")
        for field in ("id", "split", "family", "language", "group", "question"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"Query field {field} must be a nonempty string")
        if len(row["question"]) < 3:
            raise ValueError(f"Question must meet the API's three-character minimum: {row['id']}")
        paths = row.get("relevant_paths")
        if (
            not isinstance(paths, list)
            or any(not isinstance(item, str) or item not in corpus_paths for item in paths)
            or len(paths) != len(set(paths))
        ):
            raise ValueError(f"Invalid relevance paths for {row['id']}")
        if row["split"] not in {"dev", "test"} or row["language"] not in {"ru", "en"}:
            raise ValueError(f"Invalid split or language for {row['id']}")
        question_key = " ".join(row["question"].casefold().split())
        if row["id"] in seen_ids or question_key in seen_questions:
            raise ValueError(f"Duplicate query: {row['id']}")
        previous_split = family_splits.setdefault(row["family"], row["split"])
        if previous_split != row["split"]:
            raise ValueError(f"Query family leaks across splits: {row['family']}")
        seen_ids.add(row["id"])
        seen_questions.add(question_key)
        queries.append(EvaluationQuery(
            id=row["id"], split=row["split"], family=row["family"],
            language=row["language"], group=row["group"],
            question=row["question"], relevant_paths=paths,
        ))
    if {query.split for query in queries} != {"dev", "test"}:
        raise ValueError("Dataset must contain both dev and test queries")
    return queries


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * percentile) - 1)]


def summarize(rows: list[EvaluatedQuery]) -> dict:
    answerable = [row for row in rows if row.relevant_paths]
    unanswerable = [row for row in rows if not row.relevant_paths]
    latencies = [row.latency_ms for row in rows]
    return {
        "query_count": len(rows),
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "ranking": {
            metric: mean(row.metrics[metric] for row in answerable)
            for metric in ("recall_at_k", "precision_at_k", "mrr_at_k", "map_at_k")
        } if answerable else None,
        "no_answer": {
            "false_positive_rate": mean(bool(row.retrieved_paths) for row in unanswerable),
            "correct_abstention_rate": mean(not row.retrieved_paths for row in unanswerable),
        } if unanswerable else None,
        "latency_ms": {
            "mean": mean(latencies),
            "p50": _percentile(latencies, 0.5),
            "p95": _percentile(latencies, 0.95),
        },
    }


def run_evaluation(
    corpus: Path, dataset: Path, split: str = "dev", k: int = 3,
    repeats: int = 5, bm25_k1: float = 1.5, bm25_b: float = 0.75,
    candidate_multiplier: int = 5,
    semantic_model_dir: Path | None = None,
) -> dict:
    if split not in {"dev", "test"}:
        raise ValueError("split must be dev or test")
    if not 1 <= k <= 10 or repeats < 1:
        raise ValueError("k must be between 1 and 10; repeats must be positive")
    documents = read_markdown_documents(corpus)
    if not documents:
        raise ValueError("Evaluation corpus must contain Markdown documents")
    queries = load_queries(dataset, {document.path for document in documents})
    selected = [query for query in queries if query.split == split]
    corpus_content = [(document.path, document.text) for document in documents]
    report: dict = {
        "schema_version": 1,
        "split": split,
        "k": k,
        "repeats": repeats,
        "corpus_sha256": hashlib.sha256(
            json.dumps(corpus_content, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "config": {
            "bm25_k1": bm25_k1, "bm25_b": bm25_b,
            "candidate_multiplier": candidate_multiplier,
            "chunk_size": 700, "chunk_overlap": 120,
            "semantic_model_dir": str(semantic_model_dir.resolve()) if semantic_model_dir else None,
            "semantic_query_prefix": "query: " if semantic_model_dir else None,
            "semantic_passage_prefix": "passage: " if semantic_model_dir else None,
            "semantic_device": "cpu" if semantic_model_dir else None,
            "semantic_threads": 4 if semantic_model_dir else None,
            "hybrid_rrf_c": RRF_C if semantic_model_dir else None,
            "hybrid_weights": [1, 1] if semantic_model_dir else None,
            "hybrid_fusion_unit": "chunk" if semantic_model_dir else None,
            "hybrid_branch_depth": k * candidate_multiplier if semantic_model_dir else None,
        },
        "retrievers": {},
    }
    names = (
        ("overlap", "bm25", "semantic", "hybrid")
        if semantic_model_dir else ("overlap", "bm25")
    )
    for name in names:
        start = perf_counter()
        service = RAGService(
            corpus, retriever=name, bm25_k1=bm25_k1, bm25_b=bm25_b,
            candidate_multiplier=candidate_multiplier,
            semantic_model_dir=semantic_model_dir,
        )
        index_ms = (perf_counter() - start) * 1000
        rows: list[EvaluatedQuery] = []
        for query in selected:
            matches = service.retrieve(query.question, k)
            samples: list[float] = []
            for _ in range(repeats):
                start = perf_counter()
                matches = service.retrieve(query.question, k)
                samples.append((perf_counter() - start) * 1000)
            paths = [match.path for match in matches]
            rows.append(EvaluatedQuery(
                id=query.id, language=query.language, group=query.group,
                relevant_paths=query.relevant_paths, retrieved_paths=paths,
                metrics=ranking_metrics(paths, query.relevant_paths, k)
                if query.relevant_paths else {},
                latency_ms=mean(samples),
            ))
        report["retrievers"][name] = {
            "index_ms": index_ms,
            "overall": summarize(rows),
            "by_language": {
                language: summarize([row for row in rows if row.language == language])
                for language in sorted({row.language for row in rows})
            },
            "by_group": {
                group: summarize([row for row in rows if row.group == group])
                for group in sorted({row.group for row in rows})
            },
            "queries": [asdict(row) for row in rows],
        }
    return report


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=root / "evaluation" / "corpus")
    parser.add_argument("--dataset", type=Path, default=root / "evaluation" / "queries.json")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--bm25-k1", type=float, default=1.5)
    parser.add_argument("--bm25-b", type=float, default=0.75)
    parser.add_argument("--candidate-multiplier", type=int, default=5)
    parser.add_argument("--semantic-model-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_evaluation(
        args.corpus, args.dataset, args.split, args.k, args.repeats,
        args.bm25_k1, args.bm25_b, args.candidate_multiplier,
        args.semantic_model_dir,
    )
    serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
