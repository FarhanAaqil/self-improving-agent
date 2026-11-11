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
    import pytest

    from app.main import _FRONTEND_DIST

    if not (_FRONTEND_DIST / "index.html").exists():
        pytest.skip("frontend/dist not built")
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

    # When API_KEY is set in config, protected endpoints require authentication
    with patch("app.config.API_KEY", "secret-test-key"):
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




def test_reads_require_key_when_configured():
    from unittest.mock import patch

    with patch("app.config.API_KEY", "secret-test-key"):
        assert client.get("/runs").status_code == 401
        assert client.get("/runs", headers={"X-API-Key": "secret-test-key"}).status_code == 200
        # Health stays public so load balancers and the UI can probe it
        assert client.get("/health").status_code == 200


def test_production_without_key_fails_closed():
    from unittest.mock import patch

    with patch("app.config.API_KEY", None), patch("app.config.IS_DEV", False):
        resp = client.post("/generate", json={"task_description": "hello world"})
        assert resp.status_code == 503
        assert client.get("/runs").status_code == 503


def test_unknown_model_and_oversized_task_rejected():
    assert client.post(
        "/generate", json={"task_description": "hello world", "model": "gpt-who-knows"}
    ).status_code == 422
    assert client.post("/generate", json={"task_description": "x" * 5000}).status_code == 422


def test_eval_subset_size_bounded():
    assert client.post("/eval/run", json={"subset_size": -5}).status_code == 422
    assert client.post("/eval/run", json={"subset_size": 10_000}).status_code == 422


def test_code_override_disabled_by_default():
    from app.db import insert_attempt, insert_run

    insert_run("run_override", "task", final_status="generated", total_attempts=1)
    insert_attempt(run_id="run_override", attempt_number=1, generated_code="print(1)", success=False)
    resp = client.post("/execute/run_override", json={"code_override": "import os; os.system('id')"})
    assert resp.status_code == 403


def test_execute_unknown_attempt_is_404_and_numbers_never_repeat():
    from unittest.mock import patch

    from app.db import get_run_with_attempts, insert_attempt, insert_run

    insert_run("run_exec", "task", final_status="generated", total_attempts=1)
    insert_attempt(run_id="run_exec", attempt_number=1, generated_code="print(1)", success=False)

    assert client.post("/execute/run_exec", json={"attempt_number": 7}).status_code == 404

    ok = {"success": True, "output": "1", "error": "", "exit_code": 0, "latency_ms": 5, "sandboxed": True}
    with patch("app.main.run_code", return_value=ok):
        first = client.post("/execute/run_exec").json()
        second = client.post("/execute/run_exec", json={"attempt_number": 1}).json()
    assert (first["attempt_number"], second["attempt_number"]) == (2, 3)
    numbers = [a["attempt_number"] for a in get_run_with_attempts("run_exec")["attempts"]]
    assert numbers == [1, 2, 3]


def test_rate_limiter_blocks_bursts():
    import pytest
    from fastapi import HTTPException

    from app.security import RateLimiter

    limiter = RateLimiter(per_minute=2)
    limiter.check("client")
    limiter.check("client")
    with pytest.raises(HTTPException) as exc:
        limiter.check("client")
    assert exc.value.status_code == 429
    limiter.check("someone-else")


def test_browser_navigation_gets_the_app_while_fetch_gets_json():
    import pytest

    from app.main import _FRONTEND_DIST

    if not (_FRONTEND_DIST / "index.html").exists():
        pytest.skip("frontend/dist not built")
    page = client.get("/runs/run_whatever", headers={"Accept": "text/html,application/xhtml+xml"})
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    api = client.get("/runs/run_whatever", headers={"Accept": "*/*"})
    assert api.status_code == 404 and api.headers["content-type"].startswith("application/json")
    # API docs are HTML too, but must stay Swagger, not the React shell
    assert "swagger" in client.get("/docs", headers={"Accept": "text/html"}).text.lower()


def test_app_shell_is_never_cached_in_place_of_json():
    """A page and its API share URLs, so caches must vary on Accept and skip the shell."""
    import pytest

    from app.main import _FRONTEND_DIST

    if not (_FRONTEND_DIST / "index.html").exists():
        pytest.skip("frontend/dist not built")
    page = client.get("/shared/some-token", headers={"Accept": "text/html"})
    assert "Accept" in page.headers["vary"].split(", ")
    assert page.headers["cache-control"] == "no-cache"  # revalidated every time, bfcache-friendly
    assert "no-store" in client.get("/shared/some-token").headers["cache-control"]


def test_frontend_types_only_use_fields_the_api_really_returns():
    """Hand-written TypeScript interfaces drift silently; this fails when one names a field
    the matching response model does not have."""
    import re
    from pathlib import Path

    from app import schemas

    source = (Path(__file__).resolve().parent.parent / "frontend" / "src" / "api" / "types.ts").read_text("utf-8")

    def ts_fields(name: str) -> set[str]:
        body = re.search(rf"export interface {name} (?:extends \w+ )?\{{(.*?)\n\}}", source, re.S).group(1)
        return set(re.findall(r"^  (\w+)\??:", body, re.M))

    pairs = {
        "AttemptOut": schemas.AttemptOut,
        "RunOut": schemas.RunOut,
        "RunSummary": schemas.RunSummary,
        "RunPage": schemas.RunPage,
        "RunAccepted": schemas.RunAccepted,
    }
    for ts_name, model in pairs.items():
        unknown = ts_fields(ts_name) - set(model.model_fields)
        assert not unknown, f"{ts_name} in types.ts uses fields the API does not return: {sorted(unknown)}"

    health = set(client.get("/health").json())
    assert not (ts_fields("HealthResponse") - health), ts_fields("HealthResponse") - health
    usage = set(client.get("/usage").json())
    assert not (ts_fields("Usage") - usage)


def test_responses_are_compressed_but_the_live_event_stream_is_not():
    from app.db import insert_run

    for i in range(30):  # enough rows that the run list is worth compressing
        insert_run(f"run_gzip_{i}", "a fairly long task description " * 4, final_status="success")
    listed = client.get("/runs", params={"page_size": 30}, headers={"Accept-Encoding": "gzip"})
    assert listed.headers.get("content-encoding") == "gzip"

    with client.stream("GET", "/runs/run_gzip_0/events", headers={"Accept-Encoding": "gzip"}) as resp:
        assert resp.headers.get("content-encoding") is None   # events must flush one by one
        assert "run_finished" in "".join(resp.iter_text())


def test_public_endpoints_revalidate_with_etags():
    first = client.get("/models")
    assert first.headers["cache-control"] == "no-cache"
    etag = first.headers["etag"]
    again = client.get("/models", headers={"If-None-Match": etag})
    assert again.status_code == 304 and again.content == b""
    # Private, per-user data is never stored
    assert client.get("/runs").headers["cache-control"].startswith("no-store")


def test_hashed_build_assets_are_cached_for_a_year():
    import pytest

    from app.main import _FRONTEND_DIST

    assets = list((_FRONTEND_DIST / "assets").glob("*.js")) if (_FRONTEND_DIST / "assets").exists() else []
    if not assets:
        pytest.skip("frontend/dist not built")
    resp = client.get(f"/assets/{assets[0].name}")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"
