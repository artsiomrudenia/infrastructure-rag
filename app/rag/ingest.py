from pathlib import Path

from app.rag.models import Document


def read_markdown_documents(
    base_dir: Path,
    include_folders: list[str] | None = None,
    exclude_folders: list[str] | None = None,
) -> list[Document]:
    include_prefixes = _normalize_prefixes(include_folders)
    exclude_prefixes = _normalize_prefixes(exclude_folders)

    documents: list[Document] = []
    for file_path in sorted(base_dir.rglob("*.md")):
        relative_path = str(file_path.relative_to(base_dir)).replace("\\", "/")
        if _should_skip(relative_path, include_prefixes, exclude_prefixes):
            continue

        text = file_path.read_text(encoding="utf-8")
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        title = _extract_title(lines, file_path.stem)
        tags = _extract_tags(lines)

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


def _normalize_prefixes(folders: list[str] | None) -> list[str]:
    if not folders:
        return []
    normalized: list[str] = []
    for folder in folders:
        candidate = folder.strip().replace("\\", "/").strip("/").lower()
        if candidate:
            normalized.append(candidate)
    return normalized


def _should_skip(
    relative_path: str,
    include_prefixes: list[str],
    exclude_prefixes: list[str],
) -> bool:
    normalized = relative_path.lower()

    if include_prefixes and not any(
        normalized == prefix or normalized.startswith(f"{prefix}/")
        for prefix in include_prefixes
    ):
        return True

    if any(
        normalized == prefix or normalized.startswith(f"{prefix}/")
        for prefix in exclude_prefixes
    ):
        return True

    return False
