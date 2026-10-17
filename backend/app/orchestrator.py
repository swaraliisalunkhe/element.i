"""The orchestrator: runs Explorer -> Tester -> Reporter for one run. Owner: Member A.

    start_run(run_id)   <- called by POST /api/runs in the background
"""

import importlib
import logging
from collections.abc import Callable
from types import ModuleType
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.agent_interface import AgentContext, AgentSet
from app.core.config import Settings, get_settings
from app.core.constants import AgentMode, AgentName, EventLevel, EventType, RunStatus
from app.core.errors import AppError
from app.core.mock_agents import build_mock_agents
from app.db import Repository, get_session_factory, session_scope
from app.schemas import AgentEvent, BugReport, Journey, RunResponse, TestCase, TestResult

logger = logging.getLogger("code_apex")

REAL_AGENT_FACTORY_MODULE = "app.agents.factory"


class AgentsNotAvailableError(AppError):
    status_code = 500
    code = "agents_not_available"


class EventEmitter:
    """Saves a live event for one run. Each call uses its own short database session."""

    def __init__(self, session_factory: sessionmaker[Session], run_id: str) -> None:
        self.session_factory = session_factory
        self.run_id = run_id

    def __call__(
        self,
        event_type: EventType,
        agent: AgentName,
        message: str,
        level: EventLevel = EventLevel.INFO,
        data: dict[str, Any] | None = None,
    ) -> None:
        event = AgentEvent(
            run_id=self.run_id,
            type=event_type,
            agent=agent,
            level=level,
            message=message[:1000],
            data=data or {},
        )
        with session_scope(self.session_factory) as session:
            Repository(session).add_event(event)


# ------------------------------------------------------------------ agent choice


def _load_real_agents(
    settings: Settings, import_fn: Callable[[str], ModuleType] = importlib.import_module
) -> AgentSet:
    """Load Member C's agents from app/agents/factory.py (function build_agents)."""
    try:
        module = import_fn(REAL_AGENT_FACTORY_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == REAL_AGENT_FACTORY_MODULE:
            raise AgentsNotAvailableError(
                "Real agents are not available yet: backend/app/agents/factory.py does not exist. "
                "Member C must add it. Use agent_mode 'mock' meanwhile."
            ) from exc
        raise
    build = getattr(module, "build_agents", None)
    if not callable(build):
        raise AgentsNotAvailableError("app/agents/factory.py must define build_agents(settings).")
    agents = build(settings)
    if not isinstance(agents, AgentSet):
        raise AgentsNotAvailableError("build_agents(settings) must return an AgentSet.")
    return agents


def _select_agents(run: RunResponse, settings: Settings) -> AgentSet:
    if run.agent_mode == AgentMode.MOCK:
        return build_mock_agents()
    return _load_real_agents(settings)


# ---------------------------------------------------------------------- helpers


def _check_items(items: Any, expected_type: type, run_id: str, label: str) -> list:
    if not isinstance(items, list):
        raise TypeError(f"{label} must return a list, but returned {type(items).__name__}.")
    for item in items:
        if not isinstance(item, expected_type):
            raise TypeError(f"{label} returned a {type(item).__name__}, expected {expected_type.__name__}.")
        if item.run_id != run_id:
            raise ValueError(
                f"{label} returned an item with run_id '{item.run_id}', but this run is '{run_id}'."
            )
    return items


def _set_status(
    factory: sessionmaker[Session], run_id: str, status: RunStatus, emit: EventEmitter
) -> None:
    with session_scope(factory) as session:
        Repository(session).update_run_status(run_id, status)
    emit(
        EventType.RUN_STATUS_CHANGED,
        AgentName.ORCHESTRATOR,
        f"Run status is now '{status.value}'.",
        data={"status": status.value},
    )


def _fail(
    factory: sessionmaker[Session],
    run_id: str,
    emit: EventEmitter,
    agent: AgentName,
    exc: Exception,
) -> None:
    """Mark the run failed, then tell the dashboard. Never raises."""
    message = exc.message if isinstance(exc, AppError) else f"{type(exc).__name__}: {exc}"
    message = message[:1000]
    logger.error("Run %s failed during %s: %s", run_id, agent.value, message, exc_info=exc)
    try:
        with session_scope(factory) as session:
            Repository(session).fail_run(run_id, message)
    except Exception:
        logger.exception("Could not mark run %s as failed.", run_id)
    try:
        if agent != AgentName.ORCHESTRATOR:
            emit(EventType.AGENT_FAILED, agent, f"{agent.value} failed: {message}", EventLevel.ERROR)
        emit(EventType.RUN_FAILED, AgentName.ORCHESTRATOR, f"Run failed: {message}",
             EventLevel.ERROR, {"error": message})
    except Exception:
        logger.exception("Could not save the failure events for run %s.", run_id)


# --------------------------------------------------------------------- pipeline


def run_pipeline(
    run_id: str,
    agents: AgentSet | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> None:
    """Run the whole pipeline. Never raises: any problem marks the run 'failed'."""
    factory = session_factory or get_session_factory()
    emit = EventEmitter(factory, run_id)
    current = AgentName.ORCHESTRATOR
    try:
        with session_scope(factory) as session:
            run = Repository(session).get_run(run_id)
        if run.status != RunStatus.PENDING:
            logger.warning("Run %s is '%s', not 'pending'. Not starting it again.", run_id, run.status.value)
            return

        settings = get_settings()
        agent_set = agents or _select_agents(run, settings)
        evidence_dir = settings.evidence_path / run_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        ctx = AgentContext(run=run, settings=settings, evidence_dir=evidence_dir, emit=emit)

        # ---------------------------------------------------------- 1. Explorer
        current = AgentName.EXPLORER
        _set_status(factory, run_id, RunStatus.EXPLORING, emit)
        emit(EventType.AGENT_STARTED, current,
             f"Explorer started ({run.agent_mode.value} mode).", data={"agent_mode": run.agent_mode.value})
        journeys: list[Journey] = _check_items(agent_set.explorer.explore(ctx), Journey, run_id, "Explorer")
        with session_scope(factory) as session:
            repo = Repository(session)
            for journey in journeys:
                repo.add_journey(journey)
        for journey in journeys:
            emit(EventType.JOURNEY_DISCOVERED, current, f"Journey discovered: {journey.name}",
                 data={"journey_id": journey.id, "generated_by": journey.generated_by.value})
        emit(EventType.AGENT_COMPLETED, current, f"Explorer finished: {len(journeys)} journey(s).")

        # ----------------------------------------------------------- 2. Tester
        current = AgentName.TESTER
        _set_status(factory, run_id, RunStatus.TESTING, emit)
        emit(EventType.AGENT_STARTED, current, "Tester started.")
        output = agent_set.tester.run_tests(ctx, journeys)
        cases: list[TestCase] = _check_items(output.test_cases, TestCase, run_id, "Tester (test_cases)")
        results: list[TestResult] = _check_items(output.test_results, TestResult, run_id, "Tester (test_results)")
        with session_scope(factory) as session:
            repo = Repository(session)
            for case in cases:
                repo.add_test_case(case)
            for result in results:
                repo.save_test_result(result)
        for result in results:
            emit(EventType.TEST_COMPLETED, current, f"Test {result.status.value}: {result.test_case_id}",
                 data={"test_case_id": result.test_case_id, "status": result.status.value})
            for meta in result.evidence:
                emit(EventType.EVIDENCE_SAVED, current, f"Evidence saved: {meta.path}",
                     data={"evidence_id": meta.id, "url": meta.url})
        emit(EventType.AGENT_COMPLETED, current,
             f"Tester finished: {len(results)} result(s) for {len(cases)} test(s).")

        # --------------------------------------------------------- 3. Reporter
        current = AgentName.REPORTER
        _set_status(factory, run_id, RunStatus.REPORTING, emit)
        emit(EventType.AGENT_STARTED, current, "Reporter started.")
        bugs: list[BugReport] = _check_items(
            agent_set.reporter.report(ctx, journeys, cases, results), BugReport, run_id, "Reporter"
        )
        with session_scope(factory) as session:
            repo = Repository(session)
            for bug in bugs:
                repo.add_bug_report(bug)
        for bug in bugs:
            emit(EventType.BUG_REPORTED, current, f"Bug reported: {bug.title}",
                 data={"bug_id": bug.id, "severity": bug.severity.value,
                       "generated_by": bug.generated_by.value})
        emit(EventType.AGENT_COMPLETED, current, f"Reporter finished: {len(bugs)} bug(s).")

        # ------------------------------------------------------------- finish
        current = AgentName.ORCHESTRATOR
        _set_status(factory, run_id, RunStatus.COMPLETED, emit)
        with session_scope(factory) as session:
            summary = Repository(session).get_run(run_id).summary.model_dump()
        emit(EventType.RUN_COMPLETED, current, "Run completed.", data={"summary": summary})

    except Exception as exc:  # noqa: BLE001  (we must catch everything to avoid a stuck run)
        _fail(factory, run_id, emit, current, exc)


def start_run(run_id: str, session_factory: sessionmaker[Session] | None = None) -> None:
    """Entry point used by the API (as a background task)."""
    run_pipeline(run_id, session_factory=session_factory)