from pathlib import Path
import re

from app.rag.bm25 import BM25Index
from app.rag.chunking import split_documents_into_chunks
from app.rag.ingest import read_markdown_documents
from app.rag.models import QueryResult, RetrievalItem
from app.rag.retrieval import search_chunks


class RAGService:
    def __init__(
        self,
        docs_dir: Path,
        include_folders: list[str] | None = None,
        exclude_folders: list[str] | None = None,
        retriever: str = "overlap",
        bm25_k1: float = 1.5,
        bm25_b: float = 0.75,
        candidate_multiplier: int = 5,
    ) -> None:
        if retriever not in {"overlap", "bm25"}:
            raise ValueError(f"Unknown retriever: {retriever}")
        if candidate_multiplier < 1:
            raise ValueError("candidate_multiplier must be positive")
        self.docs_dir = docs_dir
        self.retriever = retriever
        self.bm25_k1 = bm25_k1
        self.bm25_b = bm25_b
        self.candidate_multiplier = candidate_multiplier
        self.include_folders = include_folders or []
        self.exclude_folders = exclude_folders or []
        self.reindex()

    @property
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @classmethod
    def from_docs_directory(
        cls,
        docs_dir: Path,
        include_folders: list[str] | None = None,
        exclude_folders: list[str] | None = None,
        retriever: str = "overlap",
        bm25_k1: float = 1.5,
        bm25_b: float = 0.75,
        candidate_multiplier: int = 5,
    ) -> "RAGService":
        return cls(
            docs_dir, include_folders=include_folders,
            exclude_folders=exclude_folders, retriever=retriever,
            bm25_k1=bm25_k1, bm25_b=bm25_b,
            candidate_multiplier=candidate_multiplier,
        )

    def reindex(self) -> None:
        documents = read_markdown_documents(
            self.docs_dir,
            include_folders=self.include_folders,
            exclude_folders=self.exclude_folders,
        )
        chunks = split_documents_into_chunks(documents)
        bm25 = (
            BM25Index(chunks, k1=self.bm25_k1, b=self.bm25_b)
            if self.retriever == "bm25" else None
        )
        self._documents = documents
        self._chunks = chunks
        self._bm25 = bm25

    def retrieve(self, question: str, top_k: int = 3) -> list[RetrievalItem]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        candidate_limit = top_k * self.candidate_multiplier
        if self._bm25 is not None:
            raw_matches = self._bm25.search(question, candidate_limit)
        else:
            raw_matches = search_chunks(self._chunks, question, candidate_limit)
        return self._deduplicate_by_path(raw_matches, top_k)

    def query(self, question: str, top_k: int = 3) -> QueryResult:
        matches = self.retrieve(question, top_k)
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

    def _deduplicate_by_path(
        self, items: list[RetrievalItem], limit: int
    ) -> list[RetrievalItem]:
        unique_items: list[RetrievalItem] = []
        seen_paths: set[str] = set()

        for item in items:
            if item.path in seen_paths:
                continue
            seen_paths.add(item.path)
            unique_items.append(item)
            if len(unique_items) >= limit:
                break

        return unique_items

    def _build_summary(self, matches: list) -> str:
        top = matches[0]
        return (
            f"Most relevant runbook: {top.title}. "
            f"Found {len(matches)} supporting source(s)."
        )

    def _recommended_actions(self, matches: list) -> list[str]:
        top_path = matches[0].path
        document = next((doc for doc in self._documents if doc.path == top_path), None)
        if document is None:
            return self._default_actions()

        actions = self._extract_actions_from_text(document.text)
        if actions:
            return actions[:3]

        return self._default_actions()

    def _extract_actions_from_text(self, text: str) -> list[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        actions: list[str] = []

        in_checks_section = False
        for line in lines:
            lower_line = line.lower()

            if lower_line.startswith("## checks"):
                in_checks_section = True
                continue
            if in_checks_section and lower_line.startswith("## "):
                in_checks_section = False

            if in_checks_section:
                match = re.match(r"^\d+[\.)]\s+(.*)$", line)
                if match:
                    actions.append(self._normalize_action(match.group(1)))

            if lower_line.startswith("## typical fix"):
                continue

        # Add a typical fix sentence if present.
        typical_fix = self._extract_typical_fix(lines)
        if typical_fix:
            actions.append(self._normalize_action(typical_fix))

        unique_actions: list[str] = []
        seen: set[str] = set()
        for action in actions:
            key = action.lower()
            if key in seen:
                continue
            seen.add(key)
            unique_actions.append(action)

        return unique_actions

    def _extract_typical_fix(self, lines: list[str]) -> str | None:
        for index, line in enumerate(lines):
            if line.lower().startswith("## typical fix"):
                if index + 1 < len(lines):
                    return lines[index + 1]
        return None

    def _normalize_action(self, action: str) -> str:
        normalized = action.strip().rstrip(".")
        if not normalized:
            return ""
        return normalized[0].upper() + normalized[1:] + "."

    def _default_actions(self) -> list[str]:
        return [
            "Open top evidence runbook and follow listed checks.",
            "Validate recent deployment or configuration changes.",
            "Escalate with collected evidence if issue persists.",
        ]
