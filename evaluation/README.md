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

Both lexical retrievers run for every command; semantic and hybrid are opt-in. Reports contain corpus/dataset SHA-256
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
The original lexical iteration added no embeddings, vector database, RRF or
generation. The opt-in semantic extension below adds embeddings only.

## Optional semantic comparison

After installing `requirements-semantic.txt` and downloading the pinned model as
described in the [README](../README.md#optional-local-semantic-retrieval):

```powershell
$modelDir = Join-Path $env:LOCALAPPDATA "infrastructure-rag\models\multilingual-e5-small-614241f"
.\.venv\Scripts\python.exe -m app.rag.evaluate --split dev --k 3 `
    --semantic-model-dir $modelDir --output semantic-dev-results.json
```

This runs overlap, BM25, semantic and hybrid RRF on the identical corpus/queries. Omitting
`--semantic-model-dir` retains the original two-retriever offline command with no
ML dependencies. API environment settings do not implicitly enable semantic in
the benchmark. Use test only after freezing choices; the first semantic acceptance
check is on dev: at least one pure RU-to-EN question must have a relevant top-3 hit.
Do not tune against the test split or modify labels to satisfy that check.

Semantic uses normalized E5 embeddings, `query: ` and `passage: ` prefixes, title
plus body, CPU/four threads, and exact dot-product ranking. Equal cosine scores
retain chunk order. Path/tag metadata is not embedded. Inputs exceeding the
model's token limit fail explicitly. The current character-based chunking is
unchanged and is not guaranteed to fit every tokenizer/input language.

`index_ms` for semantic includes model loading as well as reading, chunking and
document encoding; warmed per-query latency includes query encoding. Keep this
cold-start distinction when comparing lexical modes. Reports record the model
directory and prefixes; retain the downloaded revision and dependency versions
with reports. Optional unit tests use deterministic fake vectors and no network,
while actual cross-language quality must be verified with the real local model.

There is deliberately no semantic score threshold: any nonempty corpus returns
nearest candidates. Expect no-answer false positives, not automatic abstention.
Compare groups and individual query results, not just mean Recall. The subsequent
hybrid extension below adds RRF; no vector DB, reranking, new chunking, or generation
is included.

### First local semantic dev measurement (2026-11-10)

Pinned E5 revision: `614241f622f53c4eeff9890bdc4f31cfecc418b3`;
K=3, five repeats, unchanged corpus/labels/chunking, BM25 k1=1.5/b=0.75,
candidate multiplier=5. These are **dev**, not held-out test results:

| Metric | Overlap | BM25 | Semantic |
|---|---:|---:|---:|
| Recall@3 | 0.750 | 0.833 | 1.000 |
| Precision@3 | 0.278 | 0.306 | 0.361 |
| MRR@3 | 0.750 | 0.833 | 0.958 |
| MAP@3 | 0.736 | 0.833 | 0.958 |
| Pure RU-to-EN Recall@3 | 0 | 0 | 1 |
| No-answer false-positive rate | 0.5 | 0.5 | 1 |

Both pure RU-to-EN dev questions retrieved their relevant document. However,
`dev-restart-paraphrase` ranks its relevant document second under semantic (first
under the lexical methods), and all four no-answer questions return candidates.
Thus this is a measured capability, not a blanket ranking improvement or solved
abstention. Mean warmed semantic retrieval was about 26 ms on the local CPU;
cold index/model loading about 22 seconds. Timings are illustrative, machine/cache
dependent, and not production performance claims. No semantic test-set tuning or
score-threshold calibration was performed.

### Validation commands

```powershell
# Unit/API tests: no downloads or model required; semantic unit tests need NumPy.
.\.venv\Scripts\python.exe -m pytest -q

# Explicit local-model acceptance: dev RU-to-EN, real API, reindex and token limit.
$env:RAG_TEST_SEMANTIC_MODEL_DIR = $modelDir
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
.\.venv\Scripts\python.exe -m pytest -q tests\test_semantic_local.py
```

The semantic iteration passed 75 tests with its optional real-model check.
The subsequent hybrid iteration passed 85 tests including real-model semantic and
hybrid API checks (one existing TestClient dependency deprecation warning).
Without the opt-in environment variable, the real-model cases are skipped,
not reported as successful model checks.

## Hybrid RRF dev measurement (2026-11-10)

The first hybrid experiment uses **equal weights and fixed c=60**, with no parameter
sweep. Both branches rank the same chunks, joined by corpus-list position, not
document path or snippet. A chunk contributes `1/(60+rank)` per branch, rank starting
at one; missing branches contribute zero. Raw BM25/cosine scores do not enter fusion.
Ties retain corpus/chunk order. Each branch depth is `K * candidate_multiplier`;
the fused list is capped to that depth before the shared document-path dedup.
With K=3 and multiplier=5 this is 15 chunks per branch, not three documents.

Using the same pinned E5 revision, labels, chunking and BM25 settings as above:

| Metric | Overlap | BM25 | Semantic | Hybrid |
|---|---:|---:|---:|---:|
| Recall@3 | 0.750 | 0.833 | 1.000 | 1.000 |
| Precision@3 | 0.278 | 0.306 | 0.361 | 0.361 |
| MRR@3 | 0.750 | 0.833 | 0.958 | 1.000 |
| MAP@3 | 0.736 | 0.833 | 0.958 | 1.000 |
| Pure RU-to-EN Recall@3 | 0 | 0 | 1 | 1 |
| No-answer false-positive rate | 0.5 | 0.5 | 1 | 1 |
| Mean warmed retrieval, ms | 0.205 | 0.010 | 19.737 | 22.347 |

Hybrid fixes the observed `dev-restart-paraphrase` top-rank regression: the relevant
`pod-restarts.md` moves from semantic rank two to hybrid rank one. Both pure RU-to-EN
questions retain relevant top-one hits; identifiers and short-term groups retain
Recall/MRR=1. These are small synthetic **dev** results, not held-out acceptance
or evidence of improvement on a personal vault. Test was not evaluated or tuned
in this iteration. No default was switched.

All four no-answer questions still return sources. An empty BM25 branch does not
veto semantic candidates; RRF is not an abstention policy or calibrated confidence.
The first measured semantic/hybrid index times were about 9.0s/1.3s, but evaluation
loads semantic first: hybrid benefits from warmed imports/filesystem caches and
still loads its own encoder. These numbers do not prove cheaper hybrid cold starts.

Reproduce without a running API (PowerShell, from the project root):

```powershell
$modelDir = Join-Path $env:LOCALAPPDATA "infrastructure-rag\models\multilingual-e5-small-614241f"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
.\.venv\Scripts\python.exe -m app.rag.evaluate --split dev --k 3 `
    --semantic-model-dir $modelDir --output hybrid-dev-results.json

$r = Get-Content .\hybrid-dev-results.json -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($mode in "overlap", "bm25", "semantic", "hybrid") {
    $x = $r.retrievers.$mode
    [pscustomobject]@{
        retriever = $mode
        recall = $x.overall.ranking.recall_at_k
        precision = $x.overall.ranking.precision_at_k
        mrr = $x.overall.ranking.mrr_at_k
        map = $x.overall.ranking.map_at_k
        no_answer_fpr = $x.overall.no_answer.false_positive_rate
        mean_ms = $x.overall.latency_ms.mean
    }
}
$r.retrievers.hybrid.queries |
    Where-Object { $_.id -eq "dev-restart-paraphrase" } |
    ConvertTo-Json -Depth 6

# Full suite, including both real-model modes; no downloads.
$env:RAG_TEST_SEMANTIC_MODEL_DIR = $modelDir
.\.venv\Scripts\python.exe -m pytest -q
```

Reports additionally record `hybrid_rrf_c`, equal `hybrid_weights`, chunk fusion
unit and per-branch depth. For a manual two-terminal API check, see
[Optional hybrid RRF retrieval](../README.md#optional-hybrid-rrf-retrieval).
Future weight/smoothing/depth selection must be a separate dev experiment; freeze
the configuration before evaluating held-out test.
