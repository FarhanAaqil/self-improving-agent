from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "docker_available" in data


def test_openapi_and_docs_available():
    # Verify Swagger /docs UI and OpenAPI schema
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200

    schema_resp = client.get("/openapi.json")
    assert schema_resp.status_code == 200
    schema = schema_resp.json()
    paths = schema["paths"]

    # Verify all 6 required endpoints exist in the API specification
    assert "/generate" in paths
    assert "/execute/{run_id}" in paths
    assert "/generate-and-repair" in paths
    assert "/runs/{run_id}" in paths
    assert "/eval/latest" in paths
    assert "/eval/run" in paths


def test_runs_error_handling():
    # 404 for missing run
    resp = client.get("/runs/non-existent-uuid")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

    # 404 for execute on missing run
    resp = client.post("/execute/non-existent-uuid")
    assert resp.status_code == 404


def test_generate_validation_error():
    # 422 for task_description shorter than 5 chars
    resp = client.post("/generate", json={"task_description": "hi"})
    assert resp.status_code == 422


def test_eval_endpoints():
    latest_resp = client.get("/eval/latest")
    assert latest_resp.status_code == 200
    assert "benchmark_name" in latest_resp.json()

    # Run eval request
    run_resp = client.post("/eval/run", json={"benchmark": "humaneval", "subset_size": 2})
    assert run_resp.status_code == 200
    assert run_resp.json()["status"] == "started"
