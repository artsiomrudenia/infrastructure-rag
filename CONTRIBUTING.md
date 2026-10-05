# Contributing

Thanks for your interest in contributing.

## Workflow

1. Fork the repository.
2. Create a branch: `feature/<short-name>` or `fix/<short-name>`.
3. Run tests locally.
4. Open a pull request to `main`.

## Local checks

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
docker build -t infrastructure-rag:local .
```

## Pull request expectations

- Keep PRs focused and small.
- Update docs when behavior changes.
- Ensure CI is green.
