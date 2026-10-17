"""GET /api/runs/{run_id}/stream: live events over SSE. Owner: Member A.

Events are read from the database every POLL_INTERVAL_SECONDS. Every event saved by the
orchestrator or an agent therefore reaches the dashboard, and a reconnecting client
replays whatever it missed (Last-Event-ID header or ?after=<seq>).
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from app.core.constants import TERMINAL_STATUSES, EventType
from app.core.errors import NotFoundError
from app.db import Repository, get_session_factory
from app.schemas import AgentEvent

POLL_INTERVAL_SECONDS = 0.5
HEARTBEAT_INTERVAL_SECONDS = 15.0
RETRY_MILLISECONDS = 3000
FINAL_EVENT_TYPES = frozenset({EventType.RUN_COMPLETED, EventType.RUN_FAILED})

router = APIRouter(tags=["events"])


def format_sse(event: AgentEvent) -> str:
    """One SSE message. The JSON has no raw newlines, so `data:` is always a single line."""
    return f"id: {event.seq}\nevent: {event.type.value}\ndata: {event.model_dump_json()}\n\n"


def format_stream_end(run_id: str, last_seq: int) -> str:
    payload = json.dumps({"run_id": run_id, "last_seq": last_seq})
    return f"event: stream_end\ndata: {payload}\n\n"


def _poll(factory: sessionmaker[Session], run_id: str, after_seq: int):
    """Read the status FIRST, then the events, so a finished run never hides its last events."""
    with factory() as session:
        repo = Repository(session)
        status = repo.get_run(run_id).status
        events = repo.list_events(run_id, after_seq=after_seq)
    return events, status


def _ensure_run_exists(factory: sessionmaker[Session], run_id: str) -> None:
    with factory() as session:
        Repository(session).get_run(run_id)


async def event_stream(
    request: Request,
    run_id: str,
    after_seq: int = -1,
    session_factory: sessionmaker[Session] | None = None,
    poll_interval: float | None = None,
    heartbeat_interval: float | None = None,
) -> AsyncIterator[str]:
    factory = session_factory or get_session_factory()
    poll = POLL_INTERVAL_SECONDS if poll_interval is None else poll_interval
    beat = HEARTBEAT_INTERVAL_SECONDS if heartbeat_interval is None else heartbeat_interval

    last_seq = after_seq
    quiet_polls_after_finish = 0
    last_sent = time.monotonic()

    yield f"retry: {RETRY_MILLISECONDS}\n\n"

    while True:
        if await request.is_disconnected():
            return  # the browser closed the page: stop quietly

        try:
            events, status = await asyncio.to_thread(_poll, factory, run_id, last_seq)
        except NotFoundError:
            return

        for event in events:
            yield format_sse(event)
            last_seq = event.seq
            last_sent = time.monotonic()
            if event.type in FINAL_EVENT_TYPES:
                yield format_stream_end(run_id, last_seq)
                return

        if events:
            quiet_polls_after_finish = 0
        elif status in TERMINAL_STATUSES:
            # Finished without a final event (for example failed by the startup cleanup).
            # Wait for two quiet polls so a last event that is still being written is not lost.
            quiet_polls_after_finish += 1
            if quiet_polls_after_finish >= 2:
                yield format_stream_end(run_id, last_seq)
                return

        if not events and time.monotonic() - last_sent >= beat:
            yield ": keepalive\n\n"
            last_sent = time.monotonic()

        await asyncio.sleep(poll)


@router.get("/runs/{run_id}/stream")
async def stream_run_events(
    run_id: str,
    request: Request,
    after: int = Query(-1, ge=-1, description="Only send events with seq greater than this."),
    last_event_id: str | None = Header(default=None),
) -> StreamingResponse:
    start_after = after
    if last_event_id is not None:
        try:
            start_after = max(-1, int(last_event_id))
        except ValueError:
            pass

    factory = get_session_factory()
    await asyncio.to_thread(_ensure_run_exists, factory, run_id)  # 404 JSON before streaming starts

    return StreamingResponse(
        event_stream(request, run_id, start_after, factory),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )