from pathlib import Path

from app.rag.models import Document


def read_markdown_documents(base_dir: Path) -> list[Document]:
    documents: list[Document] = []
    for file_path in sorted(base_dir.rglob("*.md")):
        text = file_path.read_text(encoding="utf-8")
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        title = _extract_title(lines, file_path.stem)
        tags = _extract_tags(lines)
        relative_path = str(file_path.relative_to(base_dir)).replace("\\", "/")

        documents.append(
            Document(path=relative_path, title=title, tags=tags, text=text)
        )

    return documents


def _extract_title(lines: list[str], fallback: str) -> str:
    for line in lines:
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return fallback


def _extract_tags(lines: list[str]) -> list[str]:
    for line in lines:
        if line.startswith("#") and " " in line:
            tokens = [token for token in line.split() if token.startswith("#")]
            return [token.removeprefix("#").lower() for token in tokens]
    return []
