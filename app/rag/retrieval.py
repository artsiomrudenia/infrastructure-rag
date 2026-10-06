import re
from collections import Counter

from app.rag.models import Chunk, RetrievalItem


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
    "what",
    "why",
}


def search_chunks(chunks: list[Chunk], question: str, top_k: int) -> list[RetrievalItem]:
    query_tokens = _tokenize(question)
    query_counts = Counter(query_tokens)
    results: list[RetrievalItem] = []

    for chunk in chunks:
        score = _score_chunk(chunk, query_counts)
        if score <= 0:
            continue
        results.append(
            RetrievalItem(
                path=chunk.path,
                title=chunk.title,
                snippet=_snippet(chunk.text),
                score=score,
            )
        )

    results.sort(key=lambda item: item.score, reverse=True)
    return results[:top_k]


def _tokenize(text: str) -> list[str]:
    raw_tokens = re.findall(r"[a-zA-Zа-яА-Я0-9_-]+", text.lower())
    return [
        token
        for token in raw_tokens
        if len(token) >= 3 and token not in STOP_WORDS
    ]


def _score_chunk(chunk: Chunk, query_counts: Counter[str]) -> float:
    chunk_tokens = _tokenize(chunk.text)
    chunk_counts = Counter(chunk_tokens)

    score = 0.0
    for token, query_count in query_counts.items():
        if token in chunk_counts:
            score += min(chunk_counts[token], query_count)

    tags_bonus = sum(1 for token in query_counts if token in chunk.tags)
    return score + (tags_bonus * 0.25)


def _snippet(text: str, limit: int = 220) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."
