# Retrieval benchmark

## Scope and labels

This is a small, deliberately synthetic regression benchmark, not evidence of
production quality. Its eight English runbooks were written for this repository;
no private vault content or external operational documents are included.
Similar documents distinguish restart vs memory failures, registry authentication
vs name resolution, and full disks vs slow IO.

[queries.json](queries.json) contains 32 manually annotated questions:
16 dev and 16 held-out test (each 12 answerable and four unanswerable).
Both splits contain RU and EN questions, identifiers, short terms, paraphrases,
RU-to-EN questions without shared identifiers, and multi-relevant questions.
`relevant_paths` is the complete set of documents that address the requested task;
an empty list means no document supplies the answer. Sharing vocabulary alone
is not relevance. No-answer cases include both unrelated questions and plausible
near misses (for example, registry retention vs registry authentication).

Labels are document-level, not chunk-level. Retrieval uses the same service,
700-character chunks, 120-character overlap, candidate pool, and path deduplication
as the API. A document contributes at most one hit. Dev and test share the corpus,
but query families (including their translations/paraphrases) are disjoint.
The loader validates IDs, duplicate questions, paths, languages, and family leakage.
Review labels when extending the corpus; unjudged new documents can change relevance.

## Run and select configurations

From the project root, with the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m app.rag.evaluate --split dev --k 3 --output dev-results.json

# Optional dev experiments: change one factor at a time; save each report
.\.venv\Scripts\python.exe -m app.rag.evaluate --split dev --k 3 `
    --bm25-k1 1.2 --bm25-b 0.5 --candidate-multiplier 10 --output dev-alternative.json

# Freeze the chosen settings BEFORE running test; pass the same values here
.\.venv\Scripts\python.exe -m app.rag.evaluate --split test --k 3 `
    --bm25-k1 1.5 --bm25-b 0.75 --candidate-multiplier 5 --output test-results.json
```

The default split is dev; there is intentionally no combined dev/test tuning mode.
Choose a primary metric and K before experiments (for example Recall@3), then check
MRR, MAP, precision, latency, and per-group regressions rather than just the average.
Use dev only for selecting parameters or tokenization. Run test after freezing;
do not tune against its failures. Add a new held-out set if repeatedly iterating.
The initial configuration uses conventional BM25 defaults, not a claimed tuned optimum.
To use a selected configuration in the API, set `RAG_RETRIEVER=bm25`,
`RAG_BM25_K1`, `RAG_BM25_B`, and `RAG_CANDIDATE_MULTIPLIER` to the same values
before startup. Invalid active settings raise an error instead of silently falling back.

Both retrievers run for every command. Reports contain corpus/dataset SHA-256
fingerprints, all chosen settings, index-build time, overall/group/language aggregates,
and per-query ranked paths and metrics. Keep reports together with the source revision
and Python/machine details when comparing runs. Rankings are deterministic for the
same inputs/configuration; wall-clock timings are not.

## Metric definitions

Ranking metrics are macro averages over **answerable queries only**:

- Recall@K: relevant returned documents / all relevant documents.
- Precision@K: relevant returned documents / K, even when fewer results were returned.
- MRR@K: reciprocal rank of the first relevant document within K, or zero.
- MAP@K: mean AP@K, where AP@K sums precision at each relevant rank and divides
  by `min(number of relevant documents, K)`. Other AP conventions differ; use this
  definition when comparing reports.

For **unanswerable queries**, reports separately show false-positive rate (any
returned source) and correct-abstention rate (no sources). These are retrieval
abstention diagnostics, not generated-answer accuracy. Missing categories use
JSON `null`, not a misleading zero. `queries` exposes individual misses and false
positives for inspection; `by_group` and `by_language` expose improvements/regressions.

Each query gets one untimed warmup, then `--repeats` timed retrievals (default five).
Latency includes tokenization, ranking, snippets, and deduplication, but excludes
HTTP, indexing, and response assembly. Reported p50/p95 are nearest-rank percentiles
of per-query mean latencies, not production request-level tail latencies.
`index_ms` separately includes reading documents, chunking, and building statistics.
On eight documents, timing numbers are illustrative only.

## What BM25 changes

BM25 uses positive Robertson IDF (`log(1 + (N-df+0.5)/(df+0.5))`), term-frequency
saturation (`k1`), and chunk-length normalization (`b`). Each chunk's searchable
field combines title, path, tags, and text once, without the baseline's metadata
bonuses. Distinct query terms contribute once. Equal scores retain corpus/chunk order.
The inverted index is built once on startup/reindex, not on every question.

Its Unicode tokenizer preserves short tokens, hyphenated names and underscore
identifiers, including `IO`, `IP`, `node-a`, and `ERR_AUTH_42`; it uses the existing
English stop-word list. The baseline intentionally retains its original three-character
minimum and scoring. Thus the comparison measures the BM25 **retrieval configuration**,
including tokenizer changes, not solely the BM25 formula. Neither algorithm stems,
translates, or provides semantic retrieval; pure RU-to-EN misses are expected.

Positive overlap is the only result-admission rule today. Near-miss false positives
are expected and must remain visible. BM25 scores are not probabilities; returning
top-K does not mean relevant information exists. Future semantic search will need
its own measured no-answer policy; RRF scores will not be confidence either.
No vector database, embeddings, RRF, or generation is added in this iteration.
