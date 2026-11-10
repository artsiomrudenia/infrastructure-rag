from app.rag.bm25 import BM25Index
from app.rag.models import Chunk, RetrievalItem
from app.rag.retrieval import _snippet
from app.rag.semantic import Encoder, SemanticIndex


RRF_C = 60


def reciprocal_rank_fusion(
    first: list[int], second: list[int], top_k: int,
) -> list[tuple[int, float]]:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    scores: dict[int, float] = {}
    for ranking in (first, second):
        if len(set(ranking)) != len(ranking):
            raise ValueError("Each ranking must contain unique chunk indices")
        for rank, index in enumerate(ranking, start=1):
            scores[index] = scores.get(index, 0.0) + 1 / (RRF_C + rank)
    ranked = sorted(scores, key=lambda index: (-scores[index], index))
    return [(index, scores[index]) for index in ranked[:top_k]]


class HybridIndex:
    def __init__(
        self, chunks: list[Chunk], encoder: Encoder,
        k1: float = 1.5, b: float = 0.75,
    ) -> None:
        self._chunks = tuple(chunks)
        self._bm25 = BM25Index(chunks, k1=k1, b=b)
        self._semantic = SemanticIndex(chunks, encoder)

    def search(self, question: str, top_k: int) -> list[RetrievalItem]:
        # Both indexes use positions in the same chunk list, not document paths.
        lexical = [index for index, _ in self._bm25.rank_chunks(question, top_k)]
        semantic = [index for index, _ in self._semantic.rank_chunks(question, top_k)]
        return [
            RetrievalItem(
                path=self._chunks[index].path,
                title=self._chunks[index].title,
                snippet=_snippet(self._chunks[index].text),
                score=score,
            )
            for index, score in reciprocal_rank_fusion(lexical, semantic, top_k)
        ]
