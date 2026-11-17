import re

from app.rag.models import Chunk, Document


_SECTION_HEADING = re.compile(r"(?m)^ {0,3}#{2,6}[ \t]+(.+?)\s*$")


def split_documents_into_chunks(
    documents: list[Document], chunk_size: int = 700, overlap: int = 120
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in documents:
        text = document.text
        if not text.strip():
            continue

        headings = [
            (match.start(), match.group(1).rstrip("#").strip())
            for match in _SECTION_HEADING.finditer(text)
        ]
        start = 0
        chunk_id = 0
        heading_index = 0
        current_section: str | None = None
        while start < len(text):
            end = min(start + chunk_size, len(text))
            body = text[start:end].strip()
            while heading_index < len(headings) and headings[heading_index][0] <= start:
                current_section = headings[heading_index][1]
                heading_index += 1
            section = current_section
            if section is None:
                section = next(
                    (heading for position, heading in headings if start < position < end),
                    None,
                )
            if body:
                chunks.append(
                    Chunk(
                        path=document.path,
                        title=document.title,
                        tags=document.tags,
                        chunk_id=chunk_id,
                        text=body,
                        section=section,
                    )
                )
                chunk_id += 1

            if end >= len(text):
                break
            start = max(0, end - overlap)

    return chunks
