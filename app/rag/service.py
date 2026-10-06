from pathlib import Path
import re

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
