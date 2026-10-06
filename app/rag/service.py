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

    def query(self, question: str, top_k: int = 3) -> QueryResult:
        matches = search_chunks(self._chunks, question, top_k)
        if not matches:
            return QueryResult(
                answer="No relevant information found in indexed documents.",
                sources=[],
            )

        bullets = [f"- {item.title} ({item.path})" for item in matches]
        answer = "Possible relevant sources:\n" + "\n".join(bullets)
        return QueryResult(answer=answer, sources=matches)
