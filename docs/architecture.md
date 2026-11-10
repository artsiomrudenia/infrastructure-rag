# Architecture

```mermaid
flowchart TB
    User[Engineer] --> Api[FastAPI Service]
    Api --> Retriever[Retrieval Layer]
    Retriever --> Baseline[Token-overlap baseline]
    Retriever --> BM25[Optional BM25]
    Retriever --> Semantic[Optional local E5 / exact cosine]
    Retriever --> Hybrid[Optional BM25 + E5 / chunk RRF]
    Baseline --> Store[In-memory chunks / Markdown docs]
    BM25 --> Store
    Semantic --> Store
    Hybrid --> Store
    Eval[Offline RU/EN benchmark] --> Retriever
    CI[GitHub Actions] --> Image[Docker Image]
    Image --> Registry[Container Registry]
    Registry --> Helm[Helm Release]
    Helm --> K8s[Kubernetes]
```

`RAG_RETRIEVER=overlap` preserves the original default; `bm25` opts into
precomputed term statistics. `semantic` opts into local CPU E5 embeddings and
exact cosine ranking, using separately installed optional dependencies and weights.
`hybrid` combines BM25 and semantic chunk ranks with equal-weight RRF (c=60).
Each branch retrieves `top_k * candidate_multiplier` chunks; fusion joins by position
in the shared chunk list, caps the fused pool to that depth, then deduplicates by
document path. Equal fused scores use corpus/chunk order; raw branch scores are
not summed. All four modes use the same chunking and source deduplication.
`/query` assembles summaries/actions from retrieved documents; it does not call an LLM.
The [evaluation benchmark](../evaluation/README.md) measures ranking and no-answer
behavior independently of HTTP. Embeddings are rebuilt in memory at startup/reindex;
there is no vector database or ANN. Hybrid rebuilds both branch indexes before
replacing the existing state and reuses the encoder on reindex. Its source scores
are RRF values, not cosine/confidence; an empty lexical branch does not veto semantic
candidates. Neither semantic nor hybrid implements no-answer abstention.
Generation remains a future stage.
The existing Docker/Helm/raw-manifest deployment remains lexical-only.
