"""Focused tests for the rule-based ReporterAgent.

Owner: Member C.
Verifies synthesis of BugReport models from failed TestResults, deterministic
category and severity heuristics, evidence preservation, reproduction steps
truncation, missing association tolerance, and Pydantic contract compliance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.agents.reporter import ReporterAgent
from app.core.agent_interface import AgentContext
from app.core.config import get_settings
from app.core.constants import (
    AgentName,
    BrowserAction,
    BugCategory,
    EventLevel,
    EventType,
    EvidenceKind,
    GenerationMode,
    Severity,
    TestStatus,
)
from app.schemas.bug_report import BugReport
from app.schemas.common import EvidenceMeta
from app.schemas.journey import DiscoveredPage, InteractiveElement, Journey
from app.schemas.run import RunResponse
from app.schemas.test_case import StepResult, TestCase, TestResult, TestStep


def _make_context(
    tmp_path: Path,
    target_url: str = "https://example.local/",
) -> tuple[AgentContext, list[dict[str, Any]]]:
    """Helper to create an AgentContext and an event recorder."""
    events: list[dict[str, Any]] = []

    def mock_emit(
        event_type: EventType,
        agent: AgentName,
        message: str,
        level: EventLevel = EventLevel.INFO,
        data: dict[str, Any] | None = None,
    ) -> None:
        events.append({
            "type": event_type,
            "agent": agent,
            "message": message,
            "level": level,
            "data": data or {},
        })

    run = RunResponse(target_url=target_url)
    ctx = AgentContext(
        run=run,
        settings=get_settings(),
        evidence_dir=tmp_path,
        emit=mock_emit,
    )
    return ctx, events


def _make_test_case(run_id: str, journey_id: str | None = None) -> TestCase:
    """Helper to create a sample TestCase with 4 steps."""
    steps = [
        TestStep(index=1, action=BrowserAction.NAVIGATE, url="https://example.local/login", description="Open login page"),
        TestStep(index=2, action=BrowserAction.FILL, selector="#email", value="user@example.local", description="Fill email"),
        TestStep(index=3, action=BrowserAction.CLICK, selector="#btn-submit", description="Click submit"),
        TestStep(index=4, action=BrowserAction.ASSERT_VISIBLE, selector="#dashboard", description="Verify dashboard loaded"),
    ]
    return TestCase(
        run_id=run_id,
        journey_id=journey_id,
        title="Form submission: Login Page",
        description="Submit login credentials",
        priority=1,
        steps=steps,
        expected_result="Dashboard element is visible upon submission.",
        generated_by=GenerationMode.RULE_BASED,
    )


def test_reporter_no_results_or_all_passing(tmp_path: Path) -> None:
    """Verifies that an empty result list or all-passing test results return an empty list."""
    ctx, _ = _make_context(tmp_path)
    reporter = ReporterAgent()

    # Empty list
    assert reporter.report(ctx, journeys=[], test_cases=[], test_results=[]) == []

    # All passing results
    case = _make_test_case(ctx.run.id)
    passed_result = TestResult(
        run_id=ctx.run.id,
        test_case_id=case.id,
        status=TestStatus.PASSED,
        generated_by=GenerationMode.RULE_BASED,
    )
    bugs = reporter.report(ctx, journeys=[], test_cases=[case], test_results=[passed_result])
    assert bugs == []


def test_reporter_single_failure_creates_valid_bug_report(tmp_path: Path) -> None:
    """Verifies that a failed test result produces a fully validated BugReport with evidence."""
    ctx, events = _make_context(tmp_path)
    journey = Journey(
        run_id=ctx.run.id,
        name="Auth Journey",
        start_url="https://example.local/login",
        pages=[DiscoveredPage(url="https://example.local/login", depth=0)],
        generated_by=GenerationMode.RULE_BASED,
    )
    case = _make_test_case(ctx.run.id, journey_id=journey.id)

    evidence = EvidenceMeta(
        run_id=ctx.run.id,
        test_case_id=case.id,
        step_index=3,
        path=f"{ctx.run.id}/click_failed.png",
        caption="Screenshot at failed click step",
    )

    failed_result = TestResult(
        run_id=ctx.run.id,
        test_case_id=case.id,
        status=TestStatus.FAILED,
        error_message="Step 3 failed: element '#btn-submit' is blocked",
        step_results=[
            StepResult(step_index=1, action=BrowserAction.NAVIGATE, status=TestStatus.PASSED),
            StepResult(step_index=2, action=BrowserAction.FILL, status=TestStatus.PASSED),
            StepResult(
                step_index=3,
                action=BrowserAction.CLICK,
                status=TestStatus.FAILED,
                error_message="element '#btn-submit' is blocked",
                actual="Button click timed out",
                evidence_id=evidence.id,
            ),
            StepResult(step_index=4, action=BrowserAction.ASSERT_VISIBLE, status=TestStatus.SKIPPED),
        ],
        evidence=[evidence],
        generated_by=GenerationMode.RULE_BASED,
    )

    reporter = ReporterAgent()
    bugs = reporter.report(ctx, journeys=[journey], test_cases=[case], test_results=[failed_result])

    assert len(bugs) == 1
    bug = bugs[0]

    # Verify Pydantic validation
    assert isinstance(bug, BugReport)
    assert bug.run_id == ctx.run.id
    assert bug.test_case_id == case.id
    assert bug.journey_id == journey.id
    assert bug.generated_by == GenerationMode.RULE_BASED
    assert len(bug.title) >= 5
    assert bug.page_url == "https://example.local/login"
    assert bug.category in (BugCategory.FORM_VALIDATION, BugCategory.FUNCTIONAL)

    # Verify evidence preservation
    assert len(bug.evidence) == 1
    assert bug.evidence[0].id == evidence.id
    assert bug.evidence[0].path == evidence.path

    # Verify reproduction steps stop at failed step 3 (steps 1, 2, 3 only)
    assert len(bug.steps_to_reproduce) == 3
    assert "Step 1:" in bug.steps_to_reproduce[0]
    assert "Step 2:" in bug.steps_to_reproduce[1]
    assert "Step 3:" in bug.steps_to_reproduce[2]

    # Verify progress events
    progress = [e for e in events if e["type"] == EventType.AGENT_PROGRESS]
    assert len(progress) == 1
    assert progress[0]["agent"] == AgentName.REPORTER


def test_reporter_categorization_and_severity_heuristics(tmp_path: Path) -> None:
    """Verifies that navigation, form, network, and functional errors map to correct enums."""
    ctx, _ = _make_context(tmp_path)
    reporter = ReporterAgent()

    # 1. Navigation Failure
    nav_case = TestCase(
        run_id=ctx.run.id,
        title="Page Navigation Test",
        steps=[TestStep(index=1, action=BrowserAction.NAVIGATE, url="https://example.local/404")],
        expected_result="Page loads",
        generated_by=GenerationMode.RULE_BASED,
    )
    nav_result = TestResult(
        run_id=ctx.run.id,
        test_case_id=nav_case.id,
        status=TestStatus.FAILED,
        error_message="Navigation returned HTTP 404 Not Found",
        step_results=[StepResult(step_index=1, action=BrowserAction.NAVIGATE, status=TestStatus.FAILED)],
        generated_by=GenerationMode.RULE_BASED,
    )
    nav_bug = reporter.report(ctx, [], [nav_case], [nav_result])[0]
    assert nav_bug.category == BugCategory.NAVIGATION
    assert nav_bug.severity == Severity.HIGH

    # 2. Network / Connection Error
    net_case = TestCase(
        run_id=ctx.run.id,
        title="API Check",
        steps=[TestStep(index=1, action=BrowserAction.NAVIGATE, url="https://example.local/api")],
        expected_result="API loads",
        generated_by=GenerationMode.RULE_BASED,
    )
    net_result = TestResult(
        run_id=ctx.run.id,
        test_case_id=net_case.id,
        status=TestStatus.FAILED,
        error_message="Network connection refused by host 502 Bad Gateway",
        step_results=[StepResult(step_index=1, action=BrowserAction.NAVIGATE, status=TestStatus.FAILED)],
        generated_by=GenerationMode.RULE_BASED,
    )
    net_bug = reporter.report(ctx, [], [net_case], [net_result])[0]
    assert net_bug.category == BugCategory.NETWORK_ERROR
    assert net_bug.severity == Severity.HIGH

    # 3. Functional UI Assertion Failure
    func_case = TestCase(
        run_id=ctx.run.id,
        title="Header Text Check",
        steps=[
            TestStep(index=1, action=BrowserAction.NAVIGATE, url="https://example.local/"),
            TestStep(index=2, action=BrowserAction.ASSERT_TEXT, selector="h1", value="Dashboard"),
        ],
        expected_result="Header says Dashboard",
        generated_by=GenerationMode.RULE_BASED,
    )
    func_result = TestResult(
        run_id=ctx.run.id,
        test_case_id=func_case.id,
        status=TestStatus.FAILED,
        error_message="Expected 'Dashboard' not found in 'Welcome Home'",
        step_results=[
            StepResult(step_index=1, action=BrowserAction.NAVIGATE, status=TestStatus.PASSED),
            StepResult(step_index=2, action=BrowserAction.ASSERT_TEXT, status=TestStatus.FAILED),
        ],
        generated_by=GenerationMode.RULE_BASED,
    )
    func_bug = reporter.report(ctx, [], [func_case], [func_result])[0]
    assert func_bug.category == BugCategory.FUNCTIONAL
    assert func_bug.severity == Severity.MEDIUM


def test_reporter_missing_associations_handled_gracefully(tmp_path: Path) -> None:
    """Verifies that orphan test results (missing test_case or journey) do not crash the reporter."""
    ctx, _ = _make_context(tmp_path)
    reporter = ReporterAgent()

    orphan_result = TestResult(
        run_id=ctx.run.id,
        test_case_id="tc_nonexistent_12345",
        status=TestStatus.FAILED,
        error_message="Unexpected failure in unmapped test",
        step_results=[],
        generated_by=GenerationMode.RULE_BASED,
    )

    bugs = reporter.report(ctx, journeys=[], test_cases=[], test_results=[orphan_result])
    assert len(bugs) == 1
    bug = bugs[0]
    assert bug.test_case_id == "tc_nonexistent_12345"
    assert bug.journey_id is None
    assert len(bug.title) >= 5
    assert len(bug.steps_to_reproduce) >= 1
    assert bug.page_url == ctx.run.target_url


def test_reporter_multiple_failures(tmp_path: Path) -> None:
    """Verifies that multiple failing test results produce corresponding BugReports."""
    ctx, _ = _make_context(tmp_path)
    reporter = ReporterAgent()

    cases = [_make_test_case(ctx.run.id) for _ in range(3)]
    results = [
        TestResult(
            run_id=ctx.run.id,
            test_case_id=c.id,
            status=TestStatus.FAILED,
            error_message=f"Failure in {c.title}",
            generated_by=GenerationMode.RULE_BASED,
        )
        for c in cases
    ]
    # Add a passing result that should be ignored
    results.append(
        TestResult(
            run_id=ctx.run.id,
            test_case_id="tc_pass_999",
            status=TestStatus.PASSED,
            generated_by=GenerationMode.RULE_BASED,
        )
    )

    bugs = reporter.report(ctx, journeys=[], test_cases=cases, test_results=results)
    assert len(bugs) == 3
    reported_case_ids = {b.test_case_id for b in bugs}
    assert reported_case_ids == {c.id for c in cases}
