"""SSE tests. Owner: Member A."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.api.routes.stream import event_stream, format_sse
from app.core.constants import AgentName, EventType
from app.db import Repository, get_session_factory, init_db, session_scope
from app.orchestrator import run_pipeline
from app.schemas import AgentEvent, RunCreate


@pytest.fixture(autouse=True)
def prepared(app_env, monkeypatch):
    monkeypatch.setattr("app.core.mock_agents.DEFAULT_DELAY_SECONDS", 0)
    monkeypatch.setattr("app.api.routes.stream.POLL_INTERVAL_SECONDS", 0.01)
    init_db()


@pytest.fixture
def client():
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def make_run() -> str:
    with session_scope() as session:
        return Repository(session).create_run(RunCreate(target_url="http://localhost:5000")).id


def saved_events(run_id: str):
    with session_scope() as session:
        return Repository(session).list_events(run_id)


def parse_sse(text: str) -> list[dict]:
    messages = []
    for block in text.split("\n\n"):
        block = block.strip("\n")
        if not block or block.startswith(":") or block.startswith("retry:"):
            continue
        message = {}
        for line in block.split("\n"):
            if line.startswith(":"):
                continue
            key, _, value = line.partition(": ")
            message[key] = value
        messages.append(message)
    return messages


class FakeRequest:
    """Pretends to be the browser connection. Reports 'disconnected' after N checks."""

    def __init__(self, disconnect_after: int) -> None:
        self.calls = 0
        self.disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        self.calls += 1
        return self.calls > self.disconnect_after


async def collect(generator) -> list[str]:
    return [chunk async for chunk in generator]


# ----------------------------------------------------------------------- format


def test_format_sse_is_one_valid_message():
    event = AgentEvent(
        run_id="run_x", seq=3, type=EventType.BUG_REPORTED, agent=AgentName.REPORTER,
        message="Reported: line one\nline two", data={"bug_id": "bug_1"},
    )
    text = format_sse(event)
    assert text.startswith("id: 3\nevent: bug_reported\ndata: {")
    assert text.endswith("}\n\n")
    assert text.count("\n") == 4  # id, event, data lines plus the blank line: no stray newlines
    payload = json.loads(text.split("data: ", 1)[1])
    assert AgentEvent.model_validate(payload) == event


# ------------------------------------------------------------------------ route


def test_unknown_run_is_a_json_404(client):
    response = client.get("/api/runs/run_missing/stream")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_finished_run_replays_all_events_then_ends(client):
    run_id = make_run()
    run_pipeline(run_id)

    response = client.get(f"/api/runs/{run_id}/stream")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"

    messages = parse_sse(response.text)
    assert messages[-1]["event"] == "stream_end"
    events = messages[:-1]
    saved = saved_events(run_id)
    assert [int(m["id"]) for m in events] == [e.seq for e in saved]
    assert [m["event"] for m in events] == [e.type.value for e in saved]
    assert events[-1]["event"] == "run_completed"
    assert json.loads(events[0]["data"])["run_id"] == run_id


def test_resume_with_last_event_id_header_and_after_query(client):
    run_id = make_run()
    run_pipeline(run_id)
    total = len(saved_events(run_id))

    by_header = parse_sse(client.get(f"/api/runs/{run_id}/stream", headers={"Last-Event-ID": "2"}).text)
    assert int(by_header[0]["id"]) == 3
    assert len(by_header) == (total - 3) + 1  # remaining events plus stream_end

    by_query = parse_sse(client.get(f"/api/runs/{run_id}/stream", params={"after": 2}).text)
    assert int(by_query[0]["id"]) == 3

    assert client.get(f"/api/runs/{run_id}/stream", params={"after": -5}).status_code == 422


def test_run_finished_without_final_event_still_ends(client):
    run_id = make_run()
    with session_scope() as session:
        Repository(session).fail_run(run_id, "stopped")
    messages = parse_sse(client.get(f"/api/runs/{run_id}/stream").text)
    assert [m["event"] for m in messages] == ["stream_end"]


def test_failed_pipeline_stream_ends_with_run_failed(client):
    class Boom:
        def explore(self, ctx):
            raise RuntimeError("boom")

    from app.core.agent_interface import AgentSet
    from app.core.mock_agents import MockReporter, MockTester

    run_id = make_run()
    run_pipeline(run_id, agents=AgentSet(Boom(), MockTester(), MockReporter()))
    messages = parse_sse(client.get(f"/api/runs/{run_id}/stream").text)
    assert messages[-1]["event"] == "stream_end"
    assert messages[-2]["event"] == "run_failed"
    assert any(m["event"] == "agent_failed" for m in messages)


# ------------------------------------------------------------- generator logic


def test_generator_stops_when_the_client_disconnects():
    run_id = make_run()
    chunks = asyncio.run(
        collect(event_stream(FakeRequest(0), run_id, -1, get_session_factory(), 0, 0))
    )
    assert chunks == ["retry: 3000\n\n"]


def test_generator_sends_keepalive_while_waiting():
    run_id = make_run()  # still pending: nothing will ever happen
    chunks = asyncio.run(
        collect(event_stream(FakeRequest(3), run_id, -1, get_session_factory(), 0, 0))
    )
    assert ": keepalive\n\n" in chunks


def test_generator_streams_events_added_while_connected():
    run_id = make_run()
    with session_scope() as session:
        Repository(session).add_event(
            AgentEvent(run_id=run_id, type=EventType.AGENT_PROGRESS, agent=AgentName.EXPLORER, message="hi")
        )
    chunks = asyncio.run(
        collect(event_stream(FakeRequest(2), run_id, -1, get_session_factory(), 0, 100))
    )
    assert any(chunk.startswith("id: 0\nevent: agent_progress") for chunk in chunks)