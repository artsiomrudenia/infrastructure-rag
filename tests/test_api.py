from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_info() -> None:
    response = client.get("/info")
    assert response.status_code == 200
    payload = response.json()
    assert payload["project"] == "infrastructure-rag"
