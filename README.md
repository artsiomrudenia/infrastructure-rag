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
