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
