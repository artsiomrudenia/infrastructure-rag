from app.rag.models import Chunk, Document


def split_documents_into_chunks(
    documents: list[Document], chunk_size: int = 700, overlap: int = 120
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in documents:
        text = document.text
        if not text.strip():
            continue

        start = 0
        chunk_id = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            body = text[start:end].strip()
            if body:
                chunks.append(
                    Chunk(
                        path=document.path,
                        title=document.title,
                        tags=document.tags,
                        chunk_id=chunk_id,
                        text=body,
                    )
                )
                chunk_id += 1

            if end >= len(text):
                break
            start = max(0, end - overlap)

    return chunks
