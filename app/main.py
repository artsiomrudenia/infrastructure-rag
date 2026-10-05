from fastapi import FastAPI

app = FastAPI(title="infrastructure-rag", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/info")
def info() -> dict:
    return {
        "project": "infrastructure-rag",
        "description": "Retrieval-augmented assistant for infrastructure runbooks",
        "domain": "infrastructure",
    }
