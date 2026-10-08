# infrastructure-rag

RAG starter for infrastructure runbooks with API service, Docker packaging, Helm chart, Kubernetes manifests, CI/CD, tests, demo guide, and ADR.

## Included

- README
- Architecture diagram (`docs/architecture.md`)
- Dockerfile
- Helm chart (`helm/infrastructure-rag`)
- Kubernetes manifests (`manifests/`)
- CI/CD (`.github/workflows/ci.yml`)
- Tests (`tests/`)
- Demo (`demo/README.md`)
- Architecture decisions (`docs/adr/0001-initial-architecture.md`)

## Local Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Windows PowerShell Scripts

```powershell
# Run API (terminal 1)
pwsh -File .\scripts\run-api.ps1

# Run tests
pwsh -File .\scripts\run-tests.ps1 -Quiet

# Smoke test local endpoints (terminal 2, while API is running)
pwsh -File .\scripts\smoke-local.ps1

# Query sample (terminal 2, while API is running)
pwsh -File .\scripts\query-sample.ps1

# One-command local validation (tests + API + smoke + query)
pwsh -File .\scripts\dev-check.ps1 -IncludeQuery
```

Notes:
- `smoke-local.ps1` forces localhost bypass via `NO_PROXY` and uses `-NoProxy` for REST calls.
- `query-sample.ps1` prints `/query` response JSON with `ConvertTo-Json -Depth 6`.
- If you need another port: `pwsh -File .\scripts\run-api.ps1 -Port 8090`, `pwsh -File .\scripts\smoke-local.ps1 -BaseUrl http://127.0.0.1:8090`, `pwsh -File .\scripts\query-sample.ps1 -BaseUrl http://127.0.0.1:8090`.
- Custom question example: `pwsh -File .\scripts\query-sample.ps1 -Question "error rate after deployment and rollback" -TopK 3`.

## Use Obsidian Vault as Source

You can index your `brain2nd` vault directly.

```powershell
# Terminal 1: run API with external docs source
pwsh -File .\scripts\run-api.ps1 `
	-DocsDir "C:\Obsidian\brain2nd" `
	-IncludeFolders "3. Permanent Notes,4. Projects/RAG" `
	-ExcludeFolders ".git,.obsidian,attachments,draw.io"

# Terminal 2: reindex + query
Invoke-RestMethod -NoProxy -Method Post -Uri "http://127.0.0.1:8080/reindex" | ConvertTo-Json -Depth 5
pwsh -File .\scripts\query-sample.ps1 -Question "What is current RAG project status?" -TopK 5
```

Environment variables supported by app startup:
- `RAG_DOCS_DIR`
- `RAG_INCLUDE_FOLDERS` (comma-separated relative paths)
- `RAG_EXCLUDE_FOLDERS` (comma-separated relative paths)

## API

- `GET /healthz`
- `GET /info`
- `POST /query` — structured RAG response (`summary`, `evidence`, `recommended_actions`, `sources`)
- `POST /reindex` — reload markdown documents without restarting the app

## Query example

```bash
curl -X POST http://localhost:8080/query \
	-H "Content-Type: application/json" \
	-d '{"question":"How to troubleshoot CrashLoopBackOff?","top_k":3}'
```

## Reindex example

```bash
curl -X POST http://localhost:8080/reindex
```
