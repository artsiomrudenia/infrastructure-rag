from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from app.rag.models import Chunk, RetrievalItem
from app.rag.retrieval import _snippet

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray


class Encoder(Protocol):
    def encode(self, texts: list[str]) -> NDArray[np.float32]: ...


class SemanticInputTooLong(ValueError):
    pass


class E5Encoder:
    def __init__(self, model_dir: Path) -> None:
        if not model_dir.is_dir():
            raise ValueError(f"Local semantic model directory does not exist: {model_dir}")
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                "Semantic retrieval requires requirements-semantic.txt"
            ) from error

        torch.set_num_threads(4)
        self._model = SentenceTransformer(
            str(model_dir.resolve()), device="cpu",
            local_files_only=True, trust_remote_code=False,
        )

    def encode(self, texts: list[str]) -> NDArray[np.float32]:
        # Reject oversized input rather than silently losing a runbook's tail.
        for start in range(0, len(texts), 32):
            batch = texts[start:start + 32]
            token_ids = self._model.tokenizer(
                batch, truncation=False, add_special_tokens=True,
            )["input_ids"]
            if any(len(ids) > self._model.max_seq_length for ids in token_ids):
                raise SemanticInputTooLong(
                    f"Semantic input exceeds {self._model.max_seq_length} tokens "
                    "(including E5 prefix and special tokens)"
                )
        return self._model.encode(
            texts, batch_size=32, convert_to_numpy=True,
            normalize_embeddings=True, show_progress_bar=False,
        )


class SemanticIndex:
    def __init__(self, chunks: list[Chunk], encoder: Encoder) -> None:
        import numpy as np

        self._chunks = tuple(chunks)
        self._encoder = encoder
        if not chunks:
            self._vectors = np.empty((0, 0), dtype=np.float32)
            return
        passages = [f"passage: {chunk.title}\n{chunk.text}" for chunk in chunks]
        self._vectors = self._normalize(encoder.encode(passages), len(chunks))

    @staticmethod
    def _normalize(vectors: NDArray[np.float32], rows: int) -> NDArray[np.float32]:
        import numpy as np

        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] != rows or matrix.shape[1] == 0:
            raise ValueError("Encoder must return a nonempty-dimensional (N, D) matrix")
        if not np.isfinite(matrix).all():
            raise ValueError("Encoder returned nonfinite vectors")
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        if not np.isfinite(norms).all() or np.any(norms == 0):
            raise ValueError("Encoder returned zero or invalid vector norms")
        return matrix / norms

    def rank_chunks(self, question: str, top_k: int) -> list[tuple[int, float]]:
        import numpy as np

        if top_k < 1:
            raise ValueError("top_k must be positive")
        if not self._chunks:
            return []
        query = self._normalize(self._encoder.encode([f"query: {question}"]), 1)
        if query.shape[1] != self._vectors.shape[1]:
            raise ValueError("Query and passage embedding dimensions differ")
        scores = np.clip(self._vectors @ query[0], -1.0, 1.0)
        ranked = np.argsort(-scores, kind="stable")[:top_k]
        return [(int(index), float(scores[index])) for index in ranked]

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
