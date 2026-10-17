"""Orchestrator tests. Owner: Member A."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.agent_interface import AgentSet
from app.core.config import get_settings
from app.core.constants import AgentName, EventType, GenerationMode, RunStatus
from app.core.mock_agents import MockExplorer, MockReporter, MockTester
from app.db import Repository, init_db, session_scope
from app.orchestrator import (
    AgentsNotAvailableError,
    _load_real_agents,
    run_pipeline,
    start_run,
)
from app.schemas import RunCreate


@pytest.fixture(autouse=True)
def prepared(app_env, monkeypatch):
    monkeypatch.setattr("app.core.mock_agents.DEFAULT_DELAY_SECONDS", 0)
    init_db()


def make_run(mode: str = "mock") -> str:
    with session_scope() as session:
        return Repository(session).create_run(
            RunCreate(target_url="http://localhost:5000", agent_mode=mode)
        ).id


def get_run(run_id: str):
    with session_scope() as session:
        return Repository(session).get_run(run_id)


def get_events(run_id: str):
    with session_scope() as session:
        return Repository(session).list_events(run_id)


# ------------------------------------------------------------------ happy path


def test_mock_run_completes_and_saves_everything():
    run_id = make_run()
    run_pipeline(run_id)

    run = get_run(run_id)
    assert run.status == RunStatus.COMPLETED
    assert run.started_at is not None and run.finished_at is not None
    summary = run.summary
    assert (summary.journeys_count, summary.tests_total, summary.tests_failed, summary.bugs_count) == (1, 1, 1, 1)

    events = get_events(run_id)
    assert [e.seq for e in events] == list(range(len(events)))
    types = [e.type for e in events]
    assert types[-1] == EventType.RUN_COMPLETED
    for expected in (
        EventType.JOURNEY_DISCOVERED, EventType.TEST_STARTED, EventType.STEP_COMPLETED,
        EventType.TEST_COMPLETED, EventType.EVIDENCE_SAVED, EventType.BUG_REPORTED,
    ):
        assert expected in types
    assert [e.agent for e in events if e.type == EventType.AGENT_STARTED] == [
        AgentName.EXPLORER, AgentName.TESTER, AgentName.REPORTER,
    ]
    assert [e.data["status"] for e in events if e.type == EventType.RUN_STATUS_CHANGED] == [
        "exploring", "testing", "reporting", "completed",
    ]
    assert any(e.type == EventType.AGENT_PROGRESS and e.agent == AgentName.TESTER for e in events) is False
    assert any(e.type == EventType.AGENT_PROGRESS and e.agent == AgentName.EXPLORER for e in events)


def test_mock_output_is_honestly_labelled_and_evidence_file_exists():
    run_id = make_run()
    run_pipeline(run_id)
    with session_scope() as session:
        repo = Repository(session)
        journeys = repo.list_journeys(run_id)
        cases = repo.list_test_cases(run_id)
        bugs = repo.list_bug_reports(run_id)
    assert all(j.generated_by == GenerationMode.MOCK for j in journeys)
    assert all(c.generated_by == GenerationMode.MOCK for c in cases)
    assert all(b.generated_by == GenerationMode.MOCK for b in bugs)
    assert "MOCK" in bugs[0].title

    image = get_settings().evidence_path / bugs[0].evidence[0].path
    assert image.is_file()
    assert image.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_start_run_wrapper_runs_the_pipeline():
    run_id = make_run()
    start_run(run_id)
    assert get_run(run_id).status == RunStatus.COMPLETED


def test_pipeline_does_not_start_a_finished_run_again():
    run_id = make_run()
    run_pipeline(run_id)
    count = len(get_events(run_id))
    run_pipeline(run_id)
    assert len(get_events(run_id)) == count
    assert get_run(run_id).status == RunStatus.COMPLETED


def test_unknown_run_does_not_raise():
    run_pipeline("run_missing")


# -------------------------------------------------------------------- failures


class ExplodingExplorer:
    def explore(self, ctx):
        raise RuntimeError("boom")


class ExplodingTester:
    def run_tests(self, ctx, journeys):
        raise RuntimeError("tester broke")


class WrongRunExplorer:
    def explore(self, ctx):
        journey = MockExplorer().explore(ctx)[0]
        return [journey.model_copy(update={"run_id": "run_other"})]


class NotAListExplorer:
    def explore(self, ctx):
        return None


def assert_failed_cleanly(run_id: str, text: str):
    run = get_run(run_id)
    assert run.status == RunStatus.FAILED
    assert text in (run.error_message or "")
    assert run.finished_at is not None
    events = get_events(run_id)
    assert events[-1].type == EventType.RUN_FAILED
    return events


def test_exception_in_explorer_fails_the_run():
    run_id = make_run()
    run_pipeline(run_id, agents=AgentSet(ExplodingExplorer(), MockTester(), MockReporter()))
    events = assert_failed_cleanly(run_id, "boom")
    assert any(e.type == EventType.AGENT_FAILED and e.agent == AgentName.EXPLORER for e in events)


def test_exception_in_tester_keeps_earlier_work_and_fails_the_run():
    run_id = make_run()
    run_pipeline(run_id, agents=AgentSet(MockExplorer(), ExplodingTester(), MockReporter()))
    events = assert_failed_cleanly(run_id, "tester broke")
    assert any(e.type == EventType.AGENT_FAILED and e.agent == AgentName.TESTER for e in events)
    assert get_run(run_id).summary.journeys_count == 1


def test_agent_output_with_wrong_run_id_is_rejected():
    run_id = make_run()
    run_pipeline(run_id, agents=AgentSet(WrongRunExplorer(), MockTester(), MockReporter()))
    assert_failed_cleanly(run_id, "run_other")
    assert get_run(run_id).summary.journeys_count == 0


def test_agent_returning_wrong_type_is_rejected():
    run_id = make_run()
    run_pipeline(run_id, agents=AgentSet(NotAListExplorer(), MockTester(), MockReporter()))
    assert_failed_cleanly(run_id, "list")


# ------------------------------------------------------------------- real mode


def test_real_mode_without_agents_fails_with_a_clear_message(monkeypatch):
    def not_available(settings):
        raise AgentsNotAvailableError("Real agents are not available yet.")

    monkeypatch.setattr("app.orchestrator._load_real_agents", not_available)
    run_id = make_run("real")
    run_pipeline(run_id)
    assert_failed_cleanly(run_id, "not available")


def test_load_real_agents_reports_missing_factory():
    def missing(name):
        raise ModuleNotFoundError(f"No module named '{name}'", name=name)

    with pytest.raises(AgentsNotAvailableError):
        _load_real_agents(get_settings(), import_fn=missing)


def test_load_real_agents_needs_build_agents_and_an_agentset():
    with pytest.raises(AgentsNotAvailableError):
        _load_real_agents(get_settings(), import_fn=lambda name: SimpleNamespace())
    with pytest.raises(AgentsNotAvailableError):
        _load_real_agents(
            get_settings(), import_fn=lambda name: SimpleNamespace(build_agents=lambda s: "nope")
        )
    good = AgentSet(MockExplorer(), MockTester(), MockReporter())
    result = _load_real_agents(
        get_settings(), import_fn=lambda name: SimpleNamespace(build_agents=lambda s: good)
    )
    assert result is good


# ------------------------------------------------------------ through the API


def test_post_run_in_mock_mode_runs_the_whole_pipeline():
    from app.main import create_app

    with TestClient(create_app()) as client:
        created = client.post(
            "/api/runs", json={"target_url": "http://localhost:5000", "agent_mode": "mock"}
        )
        assert created.status_code == 201
        run_id = created.json()["id"]

        run = client.get(f"/api/runs/{run_id}").json()
        assert run["status"] == "completed"
        assert run["summary"]["bugs_count"] == 1

        bug = client.get(f"/api/runs/{run_id}/bugs").json()[0]
        assert bug["generated_by"] == "mock"
        image = client.get(bug["evidence"][0]["url"])
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"

        tests = client.get(f"/api/runs/{run_id}/tests").json()
        assert tests[0]["result"]["status"] == "failed"