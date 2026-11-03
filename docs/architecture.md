# Architecture

```mermaid
flowchart TB
    User[Engineer] --> Api[FastAPI Service]
    Api --> Retriever[Retrieval Layer]
    Retriever --> Baseline[Token-overlap baseline]
    Retriever --> BM25[Optional BM25]
    Baseline --> Store[In-memory chunks / Markdown docs]
    BM25 --> Store
    Eval[Offline RU/EN benchmark] --> Retriever
    CI[GitHub Actions] --> Image[Docker Image]
    Image --> Registry[Container Registry]
    Registry --> Helm[Helm Release]
    Helm --> K8s[Kubernetes]
```

`RAG_RETRIEVER=overlap` preserves the original default; `bm25` opts into
precomputed term statistics. Both use the same chunking and source deduplication.
`/query` assembles summaries/actions from retrieved documents; it does not call an LLM.
The [evaluation benchmark](../evaluation/README.md) measures ranking and no-answer
behavior independently of HTTP. Embeddings, RRF, vector databases, and generation
are future stages, not parts of the current service.
