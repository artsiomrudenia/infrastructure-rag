from pathlib import Path

from app.rag.chunking import split_documents_into_chunks
from app.rag.ingest import read_markdown_documents
from app.rag.models import QueryResult
from app.rag.retrieval import search_chunks


class RAGService:
    def __init__(self, docs_dir: Path) -> None:
        self.docs_dir = docs_dir
        self._documents = read_markdown_documents(docs_dir)
        self._chunks = split_documents_into_chunks(self._documents)

    @property
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @classmethod
    def from_docs_directory(cls, docs_dir: Path) -> "RAGService":
        return cls(docs_dir)

    def reindex(self) -> None:
        self._documents = read_markdown_documents(self.docs_dir)
        self._chunks = split_documents_into_chunks(self._documents)

    def query(self, question: str, top_k: int = 3) -> QueryResult:
        matches = search_chunks(self._chunks, question, top_k)
        if not matches:
            return QueryResult(
                summary="No relevant information found in indexed documents.",
                evidence=[],
                recommended_actions=[
                    "Try a more specific infrastructure question.",
                    "Add relevant runbook content to indexed documents.",
                ],
                sources=[],
            )

        summary = self._build_summary(matches)
        evidence = [
            f"{item.title} ({item.path}) [score={item.score:.2f}]"
            for item in matches
        ]
        recommended_actions = self._recommended_actions(matches)
        return QueryResult(
            summary=summary,
            evidence=evidence,
            recommended_actions=recommended_actions,
            sources=matches,
        )

    def _build_summary(self, matches: list) -> str:
        top = matches[0]
        return (
            f"Most relevant runbook: {top.title}. "
            f"Found {len(matches)} supporting source(s)."
        )

    def _recommended_actions(self, matches: list) -> list[str]:
        primary = matches[0].title.lower()
        if "crashloopbackoff" in primary:
            return [
                "Inspect pod events with kubectl describe.",
                "Check previous container logs for crash reason.",
                "Validate ConfigMap/Secret values and rollback if needed.",
            ]
        if "pipeline" in primary or "gitlab" in primary:
            return [
                "Inspect failing GitLab job logs.",
                "Validate registry credentials and image tags.",
                "Re-run pipeline after fixing deploy variables.",
            ]
        if "prometheus" in primary or "error rate" in primary:
            return [
                "Compare error-rate metrics before/after deployment.",
                "Check service logs for 5xx spikes.",
                "Rollback release if regression is confirmed.",
            ]
        return [
            "Open top evidence runbook and follow listed checks.",
            "Validate recent deployment/config changes.",
            "Escalate with collected evidence if issue persists.",
        ]
