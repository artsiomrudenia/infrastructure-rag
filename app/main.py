import os
import json
from pathlib import Path
from threading import RLock
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
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
_web_dir = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=_web_dir), name="static")


@app.get("/", include_in_schema=False)
def workspace() -> FileResponse:
    return FileResponse(_web_dir / "index.html")


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


_runtime_lock = RLock()


class RuntimeRequest(BaseModel):
    retriever: Literal["overlap", "bm25", "semantic", "hybrid"]
    bm25_k1: float = Field(default=1.5, gt=0, le=10, allow_inf_nan=False)
    bm25_b: float = Field(default=0.75, ge=0, le=1, allow_inf_nan=False)
    candidate_multiplier: int = Field(default=5, ge=1, le=50)


def _runtime_config() -> dict:
    return {
        "retriever": _rag.retriever,
        "model": "intfloat/multilingual-e5-small" if _rag.retriever in {"semantic", "hybrid"} else None,
        "model_configured": bool(_semantic_model_dir),
        "bm25_k1": _rag.bm25_k1,
        "bm25_b": _rag.bm25_b,
        "candidate_multiplier": _rag.candidate_multiplier,
        "rrf_c": 60 if _rag.retriever == "hybrid" else None,
        "generation": False,
    }


@app.get("/ui/config")
def ui_config() -> dict:
    with _runtime_lock:
        return _runtime_config()


@app.post("/ui/config")
def configure_runtime(payload: RuntimeRequest) -> dict:
    global _rag
    with _runtime_lock:
        if payload.retriever in {"semantic", "hybrid"} and not _semantic_model_dir:
            raise HTTPException(status_code=422, detail="Set RAG_SEMANTIC_MODEL_DIR before starting the server to enable semantic/hybrid.")
        try:
            replacement = RAGService.from_docs_directory(
                _docs_dir,
                include_folders=_include_folders,
                exclude_folders=_exclude_folders,
                retriever=payload.retriever,
                bm25_k1=payload.bm25_k1,
                bm25_b=payload.bm25_b,
                candidate_multiplier=payload.candidate_multiplier,
                semantic_model_dir=Path(_semantic_model_dir).expanduser() if _semantic_model_dir else None,
            )
        except Exception as error:
            raise HTTPException(status_code=503, detail="Could not build the new index. Previous runtime and index are unchanged. Check local model assets and documents.") from error
        _rag = replacement
        return _runtime_config()


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/info")
def info() -> dict:
    with _runtime_lock:
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
def query(payload: QueryRequest, response: Response) -> QueryResponse:
    try:
        with _runtime_lock:
            result = _rag.query(payload.question, payload.top_k)
            response.headers["X-RAG-Runtime"] = json.dumps(_runtime_config())
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
    with _runtime_lock:
        _rag.reindex()
        return ReindexResponse(
            indexed_documents=_rag.document_count,
            indexed_chunks=_rag.chunk_count,
        )
