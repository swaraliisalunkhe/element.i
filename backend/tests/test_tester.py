"""Focused tests for the rule-based TesterAgent.

Owner: Member C.
Verifies deterministic test generation from Journeys, step-by-step execution,
passing tests, assertion failures with screenshot evidence, skipping later steps,
error handling, sequential step indexing, max_tests limit, event emissions,
and proper browser cleanup.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from app.agents.tester import TesterAgent
from app.core.agent_interface import AgentContext
from app.core.config import get_settings
from app.core.constants import (
    AgentName,
    BrowserAction,
    ElementType,
    EventLevel,
    EventType,
    GenerationMode,
    TestStatus,
)
from app.schemas.journey import DiscoveredPage, InteractiveElement, Journey
from app.schemas.run import RunResponse


class MockLocator:
    """Mock Playwright Locator."""

    def __init__(self, text: str = "Welcome to Code Apex") -> None:
        self._text = text

    async def inner_text(self) -> str:
        return self._text


class MockKeyboard:
    """Mock Playwright Keyboard."""

    def __init__(self) -> None:
        self.pressed_keys: list[str] = []

    async def press(self, key: str) -> None:
        self.pressed_keys.append(key)


class MockPage:
    """Mock Playwright Page object."""

    def __init__(
        self,
        current_url: str = "https://example.local/",
        visible_selectors: set[str] | None = None,
        element_texts: dict[str, str] | None = None,
    ) -> None:
        self.url = current_url
        self.visible_selectors = visible_selectors if visible_selectors is not None else {"#btn-submit", "#email", "a"}
        self.element_texts = element_texts or {}
        self.keyboard = MockKeyboard()
        self.selected_options: list[tuple[str, str]] = []
        self.checked_selectors: list[str] = []
        self.unchecked_selectors: list[str] = []
        self.hovered_selectors: list[str] = []

    async def is_visible(self, selector: str) -> bool:
        return selector in self.visible_selectors

    def locator(self, selector: str) -> MockLocator:
        text = self.element_texts.get(selector, "Default Element Text")
        return MockLocator(text)

    async def wait_for_timeout(self, ms: int) -> None:
        pass

    async def select_option(self, selector: str, value: str) -> None:
        self.selected_options.append((selector, value))

    async def check(self, selector: str) -> None:
        self.checked_selectors.append(selector)

    async def uncheck(self, selector: str) -> None:
        self.unchecked_selectors.append(selector)

    async def hover(self, selector: str) -> None:
        self.hovered_selectors.append(selector)


class MockBrowserDriverForTester:
    """Mock BrowserDriver for TesterAgent unit testing."""

    def __init__(
        self,
        mock_page: MockPage | None = None,
        fail_nav_urls: set[str] | None = None,
        fail_click_selectors: set[str] | None = None,
    ) -> None:
        self._page = mock_page or MockPage()
        self.fail_nav_urls = fail_nav_urls or set()
        self.fail_click_selectors = fail_click_selectors or set()
        self.started = False
        self.closed = False
        self.visited_urls: list[str] = []
        self.clicked_selectors: list[str] = []
        self.filled_values: list[tuple[str, str]] = []
        self.screenshots_taken: list[str] = []

    @property
    def page(self) -> MockPage | None:
        return self._page

    async def start(self, headless: bool = True) -> None:
        self.started = True

    async def open(self, url: str) -> dict[str, Any]:
        self.visited_urls.append(url)
        self._page.url = url
        if url in self.fail_nav_urls:
            return {"url": url, "status": 500, "title": "Error"}
        return {"url": url, "status": 200, "title": "Test Page"}

    async def click(self, selector: str) -> None:
        self.clicked_selectors.append(selector)
        if selector in self.fail_click_selectors:
            raise RuntimeError(f"Element '{selector}' is not clickable or blocked")

    async def fill(self, selector: str, value: str) -> None:
        self.filled_values.append((selector, value))

    async def screenshot(self, name: str, output_dir: Path | str | None = None) -> Path:
        self.screenshots_taken.append(name)
        folder = Path(output_dir) if output_dir else Path(".")
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (name if name.endswith(".png") else f"{name}.png")
        target.write_bytes(b"\x89PNG\r\n\x1a\nfake-image-bytes")
        return target

    async def close(self) -> None:
        self.closed = True


def _make_context(
    tmp_path: Path,
    target_url: str = "https://example.local/",
    max_tests: int = 10,
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

    run = RunResponse(
        target_url=target_url,
        max_tests=max_tests,
    )
    ctx = AgentContext(
        run=run,
        settings=get_settings(),
        evidence_dir=tmp_path,
        emit=mock_emit,
    )
    return ctx, events


def _make_sample_journey(run_id: str) -> Journey:
    """Helper creating a Journey with a discovered page containing form controls."""
    elements = [
        InteractiveElement(
            element_type=ElementType.INPUT,
            selector="#email",
            label="Email Address",
            input_type="email",
        ),
        InteractiveElement(
            element_type=ElementType.BUTTON,
            selector="#btn-submit",
            label="Log In",
        ),
        InteractiveElement(
            element_type=ElementType.LINK,
            selector="a[href='/help']",
            label="Help",
            href="/help",
        ),
    ]
    page = DiscoveredPage(
        url="https://example.local/login",
        title="Login Page",
        depth=1,
        elements=elements,
    )
    return Journey(
        run_id=run_id,
        name="User Login Journey",
        description="Navigate to login page and submit credentials",
        priority=1,
        start_url="https://example.local/login",
        pages=[page],
        generated_by=GenerationMode.RULE_BASED,
    )


def test_tester_passing_test_execution(tmp_path: Path) -> None:
    """Verifies that all steps pass and output records accurate TestResult and StepResults."""
    ctx, events = _make_context(tmp_path)
    journey = _make_sample_journey(ctx.run.id)

    mock_driver = MockBrowserDriverForTester()
    tester = TesterAgent(driver=mock_driver)

    output = tester.run_tests(ctx, [journey])

    assert mock_driver.started is True
    assert mock_driver.closed is True
    assert len(output.test_cases) >= 1
    assert len(output.test_results) == len(output.test_cases)

    # Inspect first result
    first_res = output.test_results[0]
    assert first_res.run_id == ctx.run.id
    assert first_res.test_case_id == output.test_cases[0].id
    assert first_res.status == TestStatus.PASSED
    assert first_res.error_message is None
    assert first_res.generated_by == GenerationMode.RULE_BASED
    assert len(first_res.step_results) == len(output.test_cases[0].steps)
    assert all(sr.status == TestStatus.PASSED for sr in first_res.step_results)

    # Verify event emissions
    test_started_events = [e for e in events if e["type"] == EventType.TEST_STARTED]
    assert len(test_started_events) == len(output.test_cases)
    assert all(e["agent"] == AgentName.TESTER for e in test_started_events)

    step_completed_events = [e for e in events if e["type"] == EventType.STEP_COMPLETED]
    assert len(step_completed_events) > 0


def test_tester_assertion_failure_and_screenshot_evidence(tmp_path: Path) -> None:
    """Verifies that assertion failure marks step FAILED, captures evidence, and marks result FAILED."""
    ctx, events = _make_context(tmp_path)
    journey = _make_sample_journey(ctx.run.id)

    # Configure page so #btn-submit is NOT visible -> triggers ASSERT_VISIBLE failure
    mock_page = MockPage(
        current_url="https://example.local/login",
        visible_selectors=set(),  # No visible selectors
    )
    mock_driver = MockBrowserDriverForTester(mock_page=mock_page)
    tester = TesterAgent(driver=mock_driver)

    output = tester.run_tests(ctx, [journey])

    # The verification case checks visibility of #email or #btn-submit
    failed_results = [r for r in output.test_results if r.status == TestStatus.FAILED]
    assert len(failed_results) >= 1

    failed_result = failed_results[0]
    assert failed_result.error_message is not None
    assert len(failed_result.evidence) >= 1

    # Ensure evidence consistency
    evidence = failed_result.evidence[0]
    assert evidence.run_id == ctx.run.id
    assert evidence.test_case_id == failed_result.test_case_id
    assert evidence.path.startswith(f"{ctx.run.id}/")
    assert evidence.size_bytes is not None and evidence.size_bytes > 0

    # Ensure referenced evidence_id exists in result evidence
    failed_step = next(sr for sr in failed_result.step_results if sr.status == TestStatus.FAILED)
    assert failed_step.evidence_id == evidence.id


def test_tester_skipping_later_steps_after_failure(tmp_path: Path) -> None:
    """Verifies that once a step fails, subsequent steps in that test case are marked SKIPPED."""
    ctx, _ = _make_context(tmp_path)
    journey = _make_sample_journey(ctx.run.id)

    # Make the click action on #btn-submit fail
    mock_driver = MockBrowserDriverForTester(fail_click_selectors={"#btn-submit"})
    tester = TesterAgent(driver=mock_driver)

    output = tester.run_tests(ctx, [journey])

    # Find the form submission test case
    form_results = [
        r for r in output.test_results
        if any(sr.action == BrowserAction.CLICK for sr in r.step_results)
    ]
    assert len(form_results) >= 1
    form_res = form_results[0]
    assert form_res.status == TestStatus.FAILED

    # Check step sequence: earlier passed, failed step, followed by SKIPPED
    failed_indices = [sr.step_index for sr in form_res.step_results if sr.status == TestStatus.FAILED]
    skipped_indices = [sr.step_index for sr in form_res.step_results if sr.status == TestStatus.SKIPPED]

    assert len(failed_indices) == 1
    failed_idx = failed_indices[0]
    assert all(idx > failed_idx for idx in skipped_indices)


def test_tester_sequential_step_indices(tmp_path: Path) -> None:
    """Verifies that all generated test cases have strictly sequential 1-indexed steps."""
    ctx, _ = _make_context(tmp_path)
    journey = _make_sample_journey(ctx.run.id)

    mock_driver = MockBrowserDriverForTester()
    tester = TesterAgent(driver=mock_driver)

    output = tester.run_tests(ctx, [journey])

    for case in output.test_cases:
        for expected_idx, step in enumerate(case.steps, start=1):
            assert step.index == expected_idx


def test_tester_respects_max_tests(tmp_path: Path) -> None:
    """Verifies that test case generation strictly respects ctx.run.max_tests."""
    ctx, _ = _make_context(tmp_path, max_tests=1)
    journey = _make_sample_journey(ctx.run.id)

    mock_driver = MockBrowserDriverForTester()
    tester = TesterAgent(driver=mock_driver)

    output = tester.run_tests(ctx, [journey])

    assert len(output.test_cases) == 1
    assert len(output.test_results) == 1


def test_tester_browser_cleanup_on_unexpected_error(tmp_path: Path) -> None:
    """Verifies that browser driver close() is called even if an exception occurs."""
    ctx, _ = _make_context(tmp_path)

    class CrashingBrowserDriver(MockBrowserDriverForTester):
        async def open(self, url: str) -> dict[str, Any]:
            raise SystemError("Fatal unexpected crash in browser process")

    mock_driver = CrashingBrowserDriver()
    tester = TesterAgent(driver=mock_driver)
    journey = _make_sample_journey(ctx.run.id)

    output = tester.run_tests(ctx, [journey])

    assert mock_driver.closed is True
    assert all(r.status == TestStatus.FAILED for r in output.test_results)


def test_tester_real_browser_integration(tmp_path: Path) -> None:
    """Live browser integration test executing a real test case against example.com."""
    ctx, events = _make_context(tmp_path, target_url="https://example.com/", max_tests=1)
    page = DiscoveredPage(
        url="https://example.com/",
        title="Example Domain",
        depth=0,
        elements=[],
    )
    journey = Journey(
        run_id=ctx.run.id,
        name="Example Integration Journey",
        start_url="https://example.com/",
        pages=[page],
        generated_by=GenerationMode.RULE_BASED,
    )

    tester = TesterAgent()  # Instantiates real BrowserDriver
    output = tester.run_tests(ctx, [journey])

    assert len(output.test_cases) == 1
    assert len(output.test_results) == 1
    assert output.test_results[0].status == TestStatus.PASSED
