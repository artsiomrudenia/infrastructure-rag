import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.rag.service import RAGService
from app.rag.semantic import SemanticInputTooLong


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
_semantic_model_dir = os.getenv("RAG_SEMANTIC_MODEL_DIR", "").strip()

_rag = RAGService.from_docs_directory(
    _docs_dir,
    include_folders=_include_folders,
    exclude_folders=_exclude_folders,
    retriever=os.getenv("RAG_RETRIEVER", "overlap"),
    bm25_k1=float(os.getenv("RAG_BM25_K1", "1.5")),
    bm25_b=float(os.getenv("RAG_BM25_B", "0.75")),
    candidate_multiplier=int(os.getenv("RAG_CANDIDATE_MULTIPLIER", "5")),
    semantic_model_dir=Path(_semantic_model_dir).expanduser() if _semantic_model_dir else None,
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
    try:
        result = _rag.query(payload.question, payload.top_k)
    except SemanticInputTooLong as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
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
