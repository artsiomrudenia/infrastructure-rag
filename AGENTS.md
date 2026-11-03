# AGENTS.md

Guidance for AI coding agents working in this repository. Humans: see [README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## What this is

A small FastAPI service that answers infrastructure questions from markdown runbooks.
Retrieval is **lexical**, using the default token-overlap baseline or opt-in BM25 (`RAG_RETRIEVER=bm25`), over an **in-memory** index built at startup.
There are no embeddings, LLM, or vector DB. See [docs/architecture.md](docs/architecture.md).

## Where to start

| Task | Look here first |
|------|-----------------|
| Domain vocabulary and canonical terms | [GLOSSARY.md](GLOSSARY.md) |
| HTTP API, request/response models, env config | [app/main.py](app/main.py) |
| Query flow, dedup by path, summary, recommended actions | [app/rag/service.py](app/rag/service.py) |
| Scoring, tokenizer, `STOP_WORDS` | [app/rag/retrieval.py](app/rag/retrieval.py) |
| BM25 statistics and short-term/identifier tokenization | [app/rag/bm25.py](app/rag/bm25.py) |
| Ranking evaluation, dataset labels, dev/test selection | [evaluation/README.md](evaluation/README.md), [app/rag/evaluate.py](app/rag/evaluate.py) |
| Markdown loading, title/tag parsing (tags: see gotchas), include/exclude folders | [app/rag/ingest.py](app/rag/ingest.py) |
| Chunking | [app/rag/chunking.py](app/rag/chunking.py) |
| Data classes (`Document`, `Chunk`, `RetrievalItem`, `QueryResult`) | [app/rag/models.py](app/rag/models.py) |
| Tests | [tests/](tests/) (config in [pytest.ini](pytest.ini)) |
| Default corpus (also test fixtures) | [sample_docs/](sample_docs/) |
| Local dev scripts (Windows) | [scripts/](scripts/) — usage in [README.md](README.md#windows-powershell-scripts) |
| CI | [.github/workflows/ci.yml](.github/workflows/ci.yml) — `pytest -q` + `docker build` on Ubuntu, Python 3.12 |
| Deployment (do not run) | [Dockerfile](Dockerfile), [helm/infrastructure-rag/](helm/infrastructure-rag/), [manifests/](manifests/), [demo/README.md](demo/README.md) |
| Decisions | [docs/adr/](docs/adr/) |

Recommended actions in `/query` responses are parsed from the top document's `## Checks` numbered list and the line after `## Typical fix` (see `_extract_actions_from_text` in [service.py](app/rag/service.py)).

## Commands

All commands run from the **repo root** (`infrastructure-rag/`). Prerequisite: a venv at `.venv` with `requirements.txt` installed (Python 3.12, matching CI).

Safe to run automatically (verified locally on Windows):

```powershell
# Unit + API tests (no network, no server needed).
.\.venv\Scripts\python.exe -m pytest -q
```

`pwsh -File .\scripts\run-tests.ps1 -Quiet` runs the same thing, but see the exit-code gotcha below.

Linux/macOS / CI equivalent: `pytest -q` from the repo root with the venv activated.

Safe but starts a local server on `127.0.0.1:8080` (stop it afterwards):

```powershell
pwsh -File .\scripts\dev-check.ps1 -IncludeQuery   # tests + start API + smoke + sample query, then stops API
```

Manual check against the personal Obsidian vault (two terminals; keep the API terminal open):

```powershell
# Terminal 1, from repo root
pwsh -File .\scripts\run-api.ps1 `
	-DocsDir "C:\Obsidian\brain2nd" `
	-IncludeFolders "3. Permanent Notes,4. Projects/RAG" `
	-ExcludeFolders ".git,.obsidian,attachments,draw.io"

# Terminal 2: use -NoProxy for every localhost request on this corporate network
Invoke-RestMethod -NoProxy -Method Get -Uri "http://127.0.0.1:8080/healthz" | ConvertTo-Json
Invoke-RestMethod -NoProxy -Method Get -Uri "http://127.0.0.1:8080/info" | ConvertTo-Json -Depth 6
Invoke-RestMethod -NoProxy -Method Post -Uri "http://127.0.0.1:8080/reindex" | ConvertTo-Json -Depth 5

$r = Invoke-RestMethod -NoProxy -Method Post -Uri "http://127.0.0.1:8080/query" `
	-ContentType "application/json" `
	-Body '{"question":"What is current RAG project status and next step?","top_k":5}'
$r | ConvertTo-Json -Depth 8
$r.sources.path
$duplicates = $r.sources.path | Group-Object | Where-Object { $_.Count -gt 1 }
if ($duplicates) { $duplicates } else { "No duplicate source paths" }
```

Expected checks: `/healthz` returns `status=ok`; `/info` shows the configured docs directory and folder filters; `/reindex` returns positive document/chunk counts. Counts vary as the vault changes. The RAG-status query should rank the RAG project notes above unrelated notes; with `top_k=5`, a lower-ranked unrelated result is possible because retrieval is lexical. No duplicate `sources.path` values should be returned.

Stop a manually started API with `Ctrl+C` in its terminal. `dev-check.ps1` starts a separate local API process and stops that process when the script finishes.

No linter or formatter is configured in this repo. Do not invent one; say so if asked to lint.

**Not** safe to run without explicit human approval:

- `kubectl apply ...`, `helm upgrade --install ...` (deploys to whatever cluster the current kube-context points to)
- `docker push`, or any registry login/publish
- `git push`, creating tags/releases, or changing GitHub settings
- `pip install` of new packages / editing `requirements.txt` (pinned versions; CI installs exactly these)

`docker build -t infrastructure-rag:local .` is non-deploying and matches CI, but is slow and needs network through the corporate proxy; run only if asked.

## Boundaries

- Do not deploy, apply manifests, or change cluster/registry state. Image tag `latest` in [values.yaml](helm/infrastructure-rag/values.yaml) and [manifests/deployment.yaml](manifests/deployment.yaml) is shared — do not change it casually.
- Do not change the public API shape (`/query`, `/reindex`, `/info`, `/healthz` request/response fields in [app/main.py](app/main.py)) without asking; scripts and clients depend on it.
- The README shows indexing a personal Obsidian vault via `RAG_DOCS_DIR`. Never copy content from an external docs directory into this repo (including `sample_docs/`) or into commits, issues, or PRs.
- Keep Helm and raw manifests in sync when changing deployment behavior — they are two parallel deploy paths.
- Security issues: follow [SECURITY.md](SECURITY.md) (private disclosure, no public issues).
- PRs: use [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md).

## Verified gotchas

- **`run-tests.ps1` hides test failures in its exit code.** It calls pytest as the last statement without `exit $LASTEXITCODE`, so `pwsh -File .\scripts\run-tests.ps1` exits `0` even when pytest exits non-zero. Consequence: `dev-check.ps1` keeps going after failing tests. Read the pytest summary line, or call `.\.venv\Scripts\python.exe -m pytest -q` directly and check `$LASTEXITCODE`.
- **Corporate proxy breaks localhost calls.** `HTTP_PROXY`/`HTTPS_PROXY` are set on this machine; `Invoke-RestMethod http://127.0.0.1:<port>/healthz` without `-NoProxy` returns `502 (cannotconnect)`. Use `-NoProxy` (as the scripts do) or `curl --noproxy '*'`.
- **The index is built at import time of `app.main`.** Document filters and retriever settings (`RAG_RETRIEVER`, `RAG_BM25_K1`, `RAG_BM25_B`, `RAG_CANDIDATE_MULTIPLIER`) are read once on import. Tests set these env vars *before* `from app.main import app`; keep that order in new API tests. Editing docs while the server runs requires `POST /reindex`.
- **Vault folder filters use relative paths.** `RAG_INCLUDE_FOLDERS` and `RAG_EXCLUDE_FOLDERS` are comma-separated paths relative to `RAG_DOCS_DIR`; matching is case-insensitive and includes a folder plus its descendants. Restart the API to change environment configuration; use `POST /reindex` only to reload files with the existing configuration.
- **The Docker image contains no documents.** [Dockerfile](Dockerfile) copies only `app/`, so the default docs dir `/app/sample_docs` does not exist and the service starts with 0 documents (`rglob` on a missing dir returns nothing, no error). Helm/manifests mount no docs either. Queries return "No relevant information" until docs are provided.
- **`sample_docs/` are test fixtures.** [tests/test_rag_query.py](tests/test_rag_query.py) asserts specific queries hit specific files (e.g. `kubernetes-troubleshooting`, `gitlab-pipeline-failure`, `prometheus-alerts`). Editing those docs, `STOP_WORDS`, scoring weights, or tokenization can silently change rankings — run the tests.
- **Retrieval score is not confidence.** The baseline counts matching tokens and adds metadata bonuses; BM25 uses term rarity, saturation, and length normalization. Neither establishes that the corpus answers a question. The baseline drops tokens shorter than three characters; BM25 retains short terms.
- **Retrieval deduplicates by document path.** `RAGService.query` retrieves up to `top_k * 5` chunk candidates, then returns at most one highest-ranked chunk per path. If fewer than `top_k` unique paths occur in that candidate pool, fewer sources are returned.
- **Recommended actions have a generic fallback.** The top document is parsed for numbered entries under `## Checks` and the line following `## Typical fix`; if neither yields actions, the API returns generic default actions. Project/status notes usually trigger this fallback, so those actions are not evidence-based recommendations.
- **Tag parsing is currently broken.** `_extract_tags` in [ingest.py](app/rag/ingest.py) takes the first line starting with `#` and containing a space — that is the `# Title` line, so every sample doc gets `tags == ['']` and the tag bonus in `_score_chunk` never applies. Treat a fix as a behavior change (rankings may shift): do it only when asked, add a test, and run the suite.
- `top_k` is validated to `1..10` in [app/main.py](app/main.py).

## Keeping this file current

- Owner / reviewer: repository maintainer (@artsiomrudenia). Changes to this file go through a normal PR.
- Review this file in any PR that changes: commands or scripts in `scripts/`, `pytest.ini`, `requirements.txt`, CI workflow, repo layout, env vars in `app/main.py`, deployment files, or contribution/security policy.
- Update the expected test count above when tests are added or removed.
- Only add gotchas that were reproduced or verified against current code; remove ones that get fixed (e.g. if `run-tests.ps1` starts propagating exit codes).
