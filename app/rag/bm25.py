import math
import re
from collections import Counter

from app.rag.models import Chunk, RetrievalItem
from app.rag.retrieval import STOP_WORDS, _snippet


def tokenize_bm25(text: str) -> list[str]:
    # Keep short terms (IP, IO) and identifiers such as ERR_42 and node-a.
    return [
        token
        for token in re.findall(r"[^\W_]+(?:[_-][^\W_]+)*", text.lower())
        if token not in STOP_WORDS
    ]


class BM25Index:
    def __init__(
        self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75
    ) -> None:
        if not math.isfinite(k1) or k1 <= 0:
            raise ValueError("BM25 k1 must be finite and positive")
        if not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError("BM25 b must be between 0 and 1")
        self.k1 = k1
        self.b = b
        self._chunks = tuple(chunks)
        self._lengths: list[int] = []
        self._postings: dict[str, list[tuple[int, int]]] = {}
        for index, chunk in enumerate(chunks):
            counts = Counter(tokenize_bm25(
                f"{chunk.title}\n{chunk.path}\n{' '.join(chunk.tags)}\n{chunk.text}"
            ))
            self._lengths.append(sum(counts.values()))
            for token, count in counts.items():
                self._postings.setdefault(token, []).append((index, count))
        self._average_length = (
            sum(self._lengths) / len(chunks) if chunks else 0.0
        )

    def rank_chunks(self, question: str, top_k: int) -> list[tuple[int, float]]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        scores: dict[int, float] = {}
        count = len(self._chunks)
        for token in sorted(set(tokenize_bm25(question))):
            postings = self._postings.get(token, [])
            if not postings:
                continue
            idf = math.log1p((count - len(postings) + 0.5) / (len(postings) + 0.5))
            for index, frequency in postings:
                normalization = self.k1 * (
                    1 - self.b + self.b * self._lengths[index] / self._average_length
                )
                scores[index] = scores.get(index, 0.0) + (
                    idf * frequency * (self.k1 + 1) / (frequency + normalization)
                )
        ranked = sorted(scores, key=lambda index: (-scores[index], index))
        return [(index, scores[index]) for index in ranked[:top_k]]

    def search(self, question: str, top_k: int) -> list[RetrievalItem]:
        return [
            RetrievalItem(
                path=self._chunks[index].path,
                title=self._chunks[index].title,
                snippet=_snippet(self._chunks[index].text),
                score=score,
            )
            for index, score in self.rank_chunks(question, top_k)
        ]
