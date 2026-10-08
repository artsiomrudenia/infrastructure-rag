from pathlib import Path

from app.rag.models import RetrievalItem
from app.rag.service import RAGService


def test_deduplicate_by_path_keeps_best_ordered_unique_items() -> None:
    service = RAGService.from_docs_directory(Path("sample_docs"))

    items = [
        RetrievalItem(
            path="a.md",
            title="A",
            snippet="chunk-1",
            score=5.0,
        ),
        RetrievalItem(
            path="a.md",
            title="A",
            snippet="chunk-2",
            score=4.0,
        ),
        RetrievalItem(
            path="b.md",
            title="B",
            snippet="chunk-1",
            score=3.0,
        ),
        RetrievalItem(
            path="c.md",
            title="C",
            snippet="chunk-1",
            score=2.0,
        ),
    ]

    unique = service._deduplicate_by_path(items, limit=3)

    assert [item.path for item in unique] == ["a.md", "b.md", "c.md"]
