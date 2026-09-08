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


def test_frontend_spa_serving():
    # Root / serves React HTML
    resp = client.get("/")
    assert resp.status_code == 200
    assert "html" in resp.headers.get("content-type", "").lower()


def test_security_headers():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in resp.headers

    # Dynamic API routes should not be cached
    runs_resp = client.get("/runs")
    assert runs_resp.status_code == 200
    assert "no-store" in runs_resp.headers.get("cache-control", "")


def test_static_file_path_traversal_blocked():
    # Direct traversal escaping frontend/dist should be blocked with 403
    resp_encoded = client.get("/%2e%2e/%2e%2e/etc/passwd")
    assert resp_encoded.status_code in (403, 404)

    # Missing file asset with extension should 404 rather than serve index.html
    resp_missing = client.get("/package.json")
    assert resp_missing.status_code == 404


def test_api_key_authentication(monkeypatch):
    from unittest.mock import patch

    # When API_KEY is set in config, mutating endpoints require authentication
    with patch("app.main.API_KEY", "secret-test-key"):
        # Without key -> 401
        unauth_resp = client.post("/generate", json={"task_description": "hi"})
        assert unauth_resp.status_code == 401
        assert "unauthorized" in unauth_resp.json()["detail"].lower()

        # With invalid key -> 401
        bad_key_resp = client.post(
            "/generate",
            json={"task_description": "hi"},
            headers={"X-API-Key": "wrong-token"},
        )
        assert bad_key_resp.status_code == 401

        # With valid X-API-Key -> reaches route handler (validation fails 422 because < 5 chars, proving auth passed)
        valid_header_resp = client.post(
            "/generate",
            json={"task_description": "hi"},
            headers={"X-API-Key": "secret-test-key"},
        )
        assert valid_header_resp.status_code == 422

        # With valid Bearer token -> reaches route handler
        bearer_resp = client.post(
            "/generate",
            json={"task_description": "hi"},
            headers={"Authorization": "Bearer secret-test-key"},
        )
        assert bearer_resp.status_code == 422


def test_sandbox_fail_closed_when_docker_down():
    from unittest.mock import patch

    from app.sandbox import run_code

    with patch("app.sandbox._is_docker_available", return_value=False), \
         patch("app.sandbox.ALLOW_UNSAFE_HOST_SUBPROCESS", False):
        res = run_code("print('hello')")
        assert res["success"] is False
        assert res["sandboxed"] is False
        assert "Docker daemon is unavailable" in res["error"]


