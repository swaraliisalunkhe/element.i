"""Run endpoints. Owner: Member A.

POST /api/runs                 start a run
GET  /api/runs                 list runs (newest first)
GET  /api/runs/{run_id}        one run, with summary counts
GET  /api/runs/{run_id}/journeys
GET  /api/runs/{run_id}/tests  every test case, with its result or null
GET  /api/runs/{run_id}/bugs   most severe first
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.api.deps import get_repo
from app.core.constants import AgentName, EventType
from app.db import Repository
from app.orchestrator import start_run
from app.schemas import (
    AgentEvent,
    BugReport,
    Journey,
    RunCreate,
    RunResponse,
    TestCaseWithResult,
)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=201)
def create_run(
    body: RunCreate,
    background_tasks: BackgroundTasks,
    repo: Repository = Depends(get_repo),
) -> RunResponse:
    """Save the run, return it at once, and start the pipeline in the background."""
    run = repo.create_run(body)
    repo.add_event(
        AgentEvent(
            run_id=run.id,
            type=EventType.RUN_CREATED,
            agent=AgentName.ORCHESTRATOR,
            message=f"Run created for {run.target_url} (mode: {run.agent_mode.value}).",
            data={"agent_mode": run.agent_mode.value, "target_url": run.target_url},
        )
    )
    background_tasks.add_task(start_run, run.id)
    return run


@router.get("", response_model=list[RunResponse])
def list_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    repo: Repository = Depends(get_repo),
) -> list[RunResponse]:
    return repo.list_runs(limit=limit, offset=offset)


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, repo: Repository = Depends(get_repo)) -> RunResponse:
    return repo.get_run(run_id)


@router.get("/{run_id}/journeys", response_model=list[Journey])
def list_journeys(run_id: str, repo: Repository = Depends(get_repo)) -> list[Journey]:
    return repo.list_journeys(run_id)


@router.get("/{run_id}/tests", response_model=list[TestCaseWithResult])
def list_tests(run_id: str, repo: Repository = Depends(get_repo)) -> list[TestCaseWithResult]:
    return repo.list_tests_with_results(run_id)


@router.get("/{run_id}/bugs", response_model=list[BugReport])
def list_bugs(run_id: str, repo: Repository = Depends(get_repo)) -> list[BugReport]:
    return repo.list_bug_reports(run_id)