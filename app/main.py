from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.rag.service import RAGService


class QueryRequest(BaseModel):
    question: str = Field(min_length=3)
    top_k: int = Field(default=3, ge=1, le=10)


class SourceItem(BaseModel):
    path: str
    title: str
    snippet: str
    score: float


class QueryResponse(BaseModel):
    summary: str
    evidence: list[str]
    recommended_actions: list[str]
    sources: list[SourceItem]


app = FastAPI(title="infrastructure-rag", version="0.2.0")

_docs_dir = Path(__file__).resolve().parents[1] / "sample_docs"
_rag = RAGService.from_docs_directory(_docs_dir)


class ReindexResponse(BaseModel):
    indexed_documents: int
    indexed_chunks: int


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/info")
def info() -> dict:
    return {
        "project": "infrastructure-rag",
        "description": "Retrieval-augmented assistant for infrastructure runbooks",
        "domain": "infrastructure",
        "indexed_documents": _rag.document_count,
        "indexed_chunks": _rag.chunk_count,
    }


@app.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    result = _rag.query(payload.question, payload.top_k)
    sources = [
        SourceItem(
            path=item.path,
            title=item.title,
            snippet=item.snippet,
            score=item.score,
        )
        for item in result.sources
    ]
    return QueryResponse(
        summary=result.summary,
        evidence=result.evidence,
        recommended_actions=result.recommended_actions,
        sources=sources,
    )


@app.post("/reindex", response_model=ReindexResponse)
def reindex() -> ReindexResponse:
    _rag.reindex()
    return ReindexResponse(
        indexed_documents=_rag.document_count,
        indexed_chunks=_rag.chunk_count,
    )
