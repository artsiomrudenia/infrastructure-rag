# AGENTS.md

Guidance for AI coding agents working in this repository. Humans: see [README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## What this is

A small FastAPI service that answers infrastructure questions from markdown runbooks.
Retrieval is **lexical token-overlap scoring** (no embeddings, no LLM, no vector DB) over an **in-memory** index built at startup.
[docs/architecture.md](docs/architecture.md) shows a "Vector Store" — that is target architecture, not current code.

## Where to start

| Task | Look here first |
|------|-----------------|
| HTTP API, request/response models, env config | [app/main.py](app/main.py) |
| Query flow, dedup by path, summary, recommended actions | [app/rag/service.py](app/rag/service.py) |
| Scoring, tokenizer, `STOP_WORDS` | [app/rag/retrieval.py](app/rag/retrieval.py) |
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
# Unit + API tests (no network, no server needed). Expected: "9 passed" today.
.\.venv\Scripts\python.exe -m pytest -q
```

`pwsh -File .\scripts\run-tests.ps1 -Quiet` runs the same thing, but see the exit-code gotcha below.

Linux/macOS / CI equivalent: `pytest -q` from the repo root with the venv activated.

Safe but starts a local server on `127.0.0.1:8080` (stop it afterwards):

```powershell
pwsh -File .\scripts\dev-check.ps1 -IncludeQuery   # tests + start API + smoke + sample query, then stops API
```

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
- **The index is built at import time of `app.main`.** `RAG_DOCS_DIR`, `RAG_INCLUDE_FOLDERS`, `RAG_EXCLUDE_FOLDERS` are read once on import. Tests set these env vars *before* `from app.main import app`; keep that order in new API tests. Editing docs while the server runs requires `POST /reindex`.
- **The Docker image contains no documents.** [Dockerfile](Dockerfile) copies only `app/`, so the default docs dir `/app/sample_docs` does not exist and the service starts with 0 documents (`rglob` on a missing dir returns nothing, no error). Helm/manifests mount no docs either. Queries return "No relevant information" until docs are provided.
- **`sample_docs/` are test fixtures.** [tests/test_rag_query.py](tests/test_rag_query.py) asserts specific queries hit specific files (e.g. `kubernetes-troubleshooting`, `gitlab-pipeline-failure`, `prometheus-alerts`). Editing those docs, `STOP_WORDS`, scoring weights, or tokenization can silently change rankings — run the tests.
- **Tag parsing is currently broken.** `_extract_tags` in [ingest.py](app/rag/ingest.py) takes the first line starting with `#` and containing a space — that is the `# Title` line, so every sample doc gets `tags == ['']` and the tag bonus in `_score_chunk` never applies. Treat a fix as a behavior change (rankings may shift): do it only when asked, add a test, and run the suite.
- **Tokens shorter than 3 chars are dropped** and `STOP_WORDS` includes `current`, `next`, `step`. Queries made only of such words return no results by design.
- `top_k` is validated to `1..10` in [app/main.py](app/main.py); `RAGService.query` fetches `top_k * 5` candidates before deduplicating by path.

## Keeping this file current

- Owner / reviewer: repository maintainer (@artsiomrudenia). Changes to this file go through a normal PR.
- Review this file in any PR that changes: commands or scripts in `scripts/`, `pytest.ini`, `requirements.txt`, CI workflow, repo layout, env vars in `app/main.py`, deployment files, or contribution/security policy.
- Update the expected test count above when tests are added or removed.
- Only add gotchas that were reproduced or verified against current code; remove ones that get fixed (e.g. if `run-tests.ps1` starts propagating exit codes).
