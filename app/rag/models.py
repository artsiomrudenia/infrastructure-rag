from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    path: str
    title: str
    tags: list[str]
    text: str


@dataclass(frozen=True)
class Chunk:
    path: str
    title: str
    tags: list[str]
    chunk_id: int
    text: str
    section: str | None = None


@dataclass(frozen=True)
class RetrievalItem:
    path: str
    title: str
    snippet: str
    score: float


@dataclass(frozen=True)
class QueryResult:
    summary: str
    evidence: list[str]
    recommended_actions: list[str]
    sources: list[RetrievalItem]


@dataclass(frozen=True)
class ContextSource:
    source_id: str
    path: str
    title: str
    section: str | None
    chunk_id: int
    score: float


@dataclass(frozen=True)
class ContextResult:
    context: str
    sources: list[ContextSource]
    truncated: bool
