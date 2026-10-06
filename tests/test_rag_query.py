from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_query_returns_sources() -> None:
    response = client.post(
        "/query",
        json={"question": "How to troubleshoot CrashLoopBackOff pod restarts?", "top_k": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert "Most relevant runbook" in data["summary"]
    assert len(data["evidence"]) > 0
    assert len(data["recommended_actions"]) > 0
    assert len(data["sources"]) > 0


def test_query_kubernetes_hits_runbook() -> None:
    response = client.post(
        "/query",
        json={"question": "Pod CrashLoopBackOff and restart count", "top_k": 2},
    )
    assert response.status_code == 200
    data = response.json()
    source_paths = [item["path"] for item in data["sources"]]
    assert any("kubernetes-troubleshooting" in path for path in source_paths)


def test_query_gitlab_hits_pipeline_doc() -> None:
    response = client.post(
        "/query",
        json={"question": "GitLab pipeline cannot pull image from registry", "top_k": 2},
    )
    assert response.status_code == 200
    data = response.json()
    source_paths = [item["path"] for item in data["sources"]]
    assert any("gitlab-pipeline-failure" in path for path in source_paths)


def test_query_prometheus_hits_alerts_doc() -> None:
    response = client.post(
        "/query",
        json={"question": "error rate alert after release", "top_k": 2},
    )
    assert response.status_code == 200
    data = response.json()
    source_paths = [item["path"] for item in data["sources"]]
    assert any("prometheus-alerts" in path for path in source_paths)


def test_query_no_results() -> None:
    response = client.post(
        "/query",
        json={"question": "quantum entanglement for satellite photons", "top_k": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sources"] == []
    assert "No relevant information" in data["summary"]


def test_reindex_endpoint() -> None:
    response = client.post("/reindex")
    assert response.status_code == 200
    payload = response.json()
    assert payload["indexed_documents"] >= 1
    assert payload["indexed_chunks"] >= payload["indexed_documents"]
