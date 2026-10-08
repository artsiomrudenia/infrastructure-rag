import os
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


def _read_env_list(name: str) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _resolve_docs_dir() -> Path:
    raw = os.getenv("RAG_DOCS_DIR", "").strip()
    if not raw:
        return Path(__file__).resolve().parents[1] / "sample_docs"
    return Path(raw).expanduser().resolve()


_docs_dir = _resolve_docs_dir()
_include_folders = _read_env_list("RAG_INCLUDE_FOLDERS")
_exclude_folders = _read_env_list("RAG_EXCLUDE_FOLDERS")

_rag = RAGService.from_docs_directory(
    _docs_dir,
    include_folders=_include_folders,
    exclude_folders=_exclude_folders,
)


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
        "docs_dir": str(_docs_dir),
        "include_folders": _include_folders,
        "exclude_folders": _exclude_folders,
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
