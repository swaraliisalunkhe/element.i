"""API tests. Owner: Member A."""

import pytest

from app.api.routes.evidence import resolve_evidence_file
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.db import Repository, session_scope
from app.schemas import (
    BugReport,
    Journey,
    RunCreate,
    RunResponse,
    TestCase,
    TestCaseWithResult,
    TestResult,
    AgentEvent,
)

RUN_ID = "run_7f3a9c21b4d8"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes"


def seed_contract_run(load_contract) -> None:
    """Save the CP1 example data into the temporary database."""
    with session_scope() as session:
        repo = Repository(session)
        repo.create_run(RunCreate.model_validate(load_contract("run_create.json")), run_id=RUN_ID)
        repo.add_journey(Journey.model_validate(load_contract("journey.json")))
        repo.add_test_case(TestCase.model_validate(load_contract("test_case.json")))
        repo.save_test_result(TestResult.model_validate(load_contract("test_result.json")))
        repo.add_bug_report(BugReport.model_validate(load_contract("bug_report.json")))
        repo.add_event(AgentEvent.model_validate(load_contract("agent_event.json")))


# ------------------------------------------------------------------ health, CORS


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_cors_allows_the_dashboard_origin_only(client):
    allowed = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    blocked = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in blocked.headers


def test_unknown_route_uses_error_shape(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# -------------------------------------------------------------------------- runs


def test_create_run_returns_pending_run_and_starts_pipeline(client, started_runs, load_contract):
    response = client.post("/api/runs", json=load_contract("run_create.json"))
    assert response.status_code == 201
    run = RunResponse.model_validate(response.json())
    assert run.status == "pending"
    assert run.id.startswith("run_")
    assert started_runs == [run.id]
    events = client.get(f"/api/runs/{run.id}").json()
    assert events["id"] == run.id


def test_create_run_rejects_bad_input_with_error_shape(client, started_runs):
    response = client.post("/api/runs", json={"target_url": "not-a-url"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"]["problems"]
    assert started_runs == []

    response = client.post("/api/runs", json={"target_url": "http://localhost:5000", "oops": 1})
    assert response.status_code == 422


def test_get_and_list_runs(client):
    first = client.post("/api/runs", json={"target_url": "http://localhost:5000"}).json()
    second = client.post("/api/runs", json={"target_url": "http://localhost:5000"}).json()
    listed = client.get("/api/runs").json()
    ids = [run["id"] for run in listed]
    assert ids.index(second["id"]) < ids.index(first["id"])
    assert client.get("/api/runs", params={"limit": 1}).json().__len__() == 1
    assert client.get("/api/runs", params={"limit": 0}).status_code == 422


def test_unknown_run_is_404_in_every_endpoint(client):
    for suffix in ("", "/journeys", "/tests", "/bugs"):
        response = client.get(f"/api/runs/run_missing{suffix}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


def test_new_run_has_empty_lists(client):
    run_id = client.post("/api/runs", json={"target_url": "http://localhost:5000"}).json()["id"]
    for suffix in ("journeys", "tests", "bugs"):
        assert client.get(f"/api/runs/{run_id}/{suffix}").json() == []


def test_endpoints_return_the_contract_shapes(client, load_contract):
    seed_contract_run(load_contract)

    run = RunResponse.model_validate(client.get(f"/api/runs/{RUN_ID}").json())
    assert run.summary == RunResponse.model_validate(load_contract("run_response.json")).summary

    journeys = client.get(f"/api/runs/{RUN_ID}/journeys").json()
    assert Journey.model_validate(journeys[0]) == Journey.model_validate(load_contract("journey.json"))

    tests = client.get(f"/api/runs/{RUN_ID}/tests").json()
    item = TestCaseWithResult.model_validate(tests[0])
    assert item.test_case.id == "tc_9e8d7c6b5a40"
    assert item.result is not None and item.result.status == "failed"

    bugs = client.get(f"/api/runs/{RUN_ID}/bugs").json()
    assert BugReport.model_validate(bugs[0]) == BugReport.model_validate(load_contract("bug_report.json"))


# ---------------------------------------------------------------------- evidence


def test_evidence_file_is_served(client):
    base = get_settings().evidence_path
    (base / "run_x").mkdir(parents=True, exist_ok=True)
    (base / "run_x" / "shot.png").write_bytes(PNG_BYTES)
    response = client.get("/api/evidence/run_x/shot.png")
    assert response.status_code == 200
    assert response.content == PNG_BYTES
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_evidence_missing_directory_and_bad_type_are_404(client):
    base = get_settings().evidence_path
    (base / "run_x").mkdir(parents=True, exist_ok=True)
    (base / "run_x" / "tool.exe").write_bytes(b"MZ")
    assert client.get("/api/evidence/run_x/nothing.png").status_code == 404
    assert client.get("/api/evidence/run_x").status_code == 404
    assert client.get("/api/evidence/run_x/tool.exe").status_code == 404


def test_evidence_path_traversal_over_http_is_blocked(client, app_env):
    (app_env / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
    (get_settings().data_path / "secret2.txt").write_text("TOP SECRET", encoding="utf-8")
    attempts = [
        "/api/evidence/..%2f..%2fsecret.txt",
        "/api/evidence/..%2fsecret2.txt",
        "/api/evidence/..%5c..%5csecret.txt",
        "/api/evidence/%2e%2e/%2e%2e/secret.txt",
        "/api/evidence/C:/Windows/win.ini",
    ]
    for url in attempts:
        response = client.get(url)
        assert response.status_code in (400, 404), url
        assert "TOP SECRET" not in response.text, url


@pytest.mark.parametrize(
    "bad",
    [
        "../secret.txt", "/etc/passwd", "a\\b.png", "C:/x.png", "a/../b.png",
        "a//b.png", "", "run_x/", "run_x/file.exe", "missing/shot.png",
    ],
)
def test_resolve_evidence_file_rejects_bad_paths(tmp_path, bad):
    base = tmp_path / "evidence"
    base.mkdir()
    (tmp_path / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
    with pytest.raises(NotFoundError):
        resolve_evidence_file(base, bad)


def test_resolve_evidence_file_accepts_real_files(tmp_path):
    base = tmp_path / "evidence"
    (base / "run_x").mkdir(parents=True)
    (base / "run_x" / "shot.png").write_bytes(PNG_BYTES)
    assert resolve_evidence_file(base, "run_x/shot.png") == (base / "run_x" / "shot.png").resolve()