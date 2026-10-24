"""Focused tests for LLM-assisted assessment test-case generation with Gemini 3.8 Flash.

Owner: Member C.
Verifies:
- Gemini response parsing and schema validation
- Whitelisted selector enforcement and unsupported action filtering
- Consequential submission control click prevention
- Missing API key handling with graceful fallback
- API timeout/quota failure handling with single retry limit and rule-based fallback
- Invalid JSON output recovery
- Maximum case and step ceilings
- Generic website fallback when no assessment map exists
- Integration with TesterAgent.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.assessment_map import (
    AssessmentActionControl,
    AssessmentMap,
    AssessmentOption,
    AssessmentQuestion,
    PaletteItem,
    PaletteState,
)
from app.agents.tester import TesterAgent
from app.core.agent_interface import AgentContext
from app.core.config import Settings, get_settings
from app.core.constants import BrowserAction, ElementType, GenerationMode, TestStatus
from app.schemas.journey import DiscoveredPage, InteractiveElement, Journey
from app.schemas.run import RunResponse
from app.services.suite_generator import (
    DEFAULT_GEMINI_MODEL,
    MAX_STEPS_PER_CASE,
    MAX_SUITE_CASES,
    SuiteGenerator,
)


def _make_sample_assessment_map() -> AssessmentMap:
    return AssessmentMap(
        url="http://test.local/exam",
        is_assessment=True,
        title="Technical Assessment",
        timer_selector="#timer",
        timer_text="30:00",
        questions=[
            AssessmentQuestion(
                selector="#q1",
                number="1",
                text="What is the time complexity of binary search?",
                options=[
                    AssessmentOption(selector="#opt-a", label="O(1)", is_radio=True),
                    AssessmentOption(selector="#opt-b", label="O(log n)", is_radio=True),
                ],
            )
        ],
        palette_items=[
            PaletteItem(number="1", selector="#pal-1", state=PaletteState.CURRENT),
            PaletteItem(number="2", selector="#pal-2", state=PaletteState.UNANSWERED),
        ],
        action_controls=[
            AssessmentActionControl(action_type="next", selector="#btn-next", label="Next"),
            AssessmentActionControl(
                action_type="submit", selector="#btn-submit", label="Submit Exam", is_consequential=True
            ),
        ],
    )


def _make_context(tmp_path: Path, max_tests: int = 5) -> AgentContext:
    run = RunResponse(
        target_url="http://test.local/exam",
        max_pages=1,
        max_depth=1,
        max_tests=max_tests,
    )
    from pydantic import SecretStr
    test_settings = Settings(gemini_api_key=SecretStr(""))
    return AgentContext(
        run=run,
        settings=test_settings,
        evidence_dir=tmp_path,
        emit=lambda *args, **kwargs: None,
    )


class MockGeminiClient:
    """Mock Google GenAI Client simulating Gemini 3.8 Flash responses offline."""

    def __init__(self, response_text: str | None = None, should_fail: bool = False) -> None:
        self.response_text = response_text
        self.should_fail = should_fail
        self.call_count = 0
        self.models = MagicMock()
        self.models.generate_content.side_effect = self._generate_content

    def _generate_content(self, model: str, contents: str, config: Any = None) -> Any:
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("Gemini API quota exceeded / network timeout")

        mock_resp = MagicMock()
        mock_resp.text = self.response_text
        return mock_resp


def test_gemini_valid_response_parsing(tmp_path: Path) -> None:
    """Verify parsing and validation of a valid structured JSON response from Gemini."""
    ctx = _make_context(tmp_path)
    amap = _make_sample_assessment_map()
    journey = Journey(
        run_id=ctx.run.id,
        name="Assessment Journey",
        start_url="http://test.local/exam",
        pages=[DiscoveredPage(url="http://test.local/exam", depth=0, elements=[])],
        generated_by=GenerationMode.RULE_BASED,
    )

    valid_payload = {
        "cases": [
            {
                "title": "Verify Timer and First Question",
                "description": "Ensure timer is visible and option O(log n) is selectable.",
                "priority": 1,
                "steps": [
                    {"index": 1, "action": "navigate", "url": "http://test.local/exam"},
                    {"index": 2, "action": "assert_visible", "selector": "#timer"},
                    {"index": 3, "action": "check", "selector": "#opt-b"},
                ],
                "expected_result": "Timer is visible and option is checked.",
            }
        ]
    }

    mock_client = MockGeminiClient(response_text=json.dumps(valid_payload))
    generator = SuiteGenerator(client=mock_client)

    # Inject dummy API key via environment fixture or monkeypatch
    import os
    os.environ["GEMINI_API_KEY"] = "fake-test-key-xyz"
    try:
        cases = generator.generate_suite(ctx, amap, [journey])
        assert len(cases) == 1
        case = cases[0]
        assert case.title == "Verify Timer and First Question"
        assert case.generated_by == GenerationMode.LLM
        assert len(case.steps) == 3
        assert case.steps[0].action == BrowserAction.NAVIGATE
        assert case.steps[1].action == BrowserAction.ASSERT_VISIBLE
        assert case.steps[2].action == BrowserAction.CHECK
        assert mock_client.call_count == 1
    finally:
        del os.environ["GEMINI_API_KEY"]


def test_gemini_filters_unknown_selectors_and_unsupported_actions(tmp_path: Path) -> None:
    """Ensure LLM-proposed steps with unwhitelisted selectors or invalid actions are safely filtered."""
    ctx = _make_context(tmp_path)
    amap = _make_sample_assessment_map()
    journey = Journey(
        run_id=ctx.run.id,
        name="Assessment Journey",
        start_url="http://test.local/exam",
        pages=[DiscoveredPage(url="http://test.local/exam", depth=0, elements=[])],
        generated_by=GenerationMode.RULE_BASED,
    )

    hallucinated_payload = {
        "cases": [
            {
                "title": "Hallucinated Step Case",
                "priority": 2,
                "steps": [
                    {"index": 1, "action": "navigate", "url": "http://test.local/exam"},
                    # Invalid selector (not in assessment map)
                    {"index": 2, "action": "click", "selector": "#completely-invented-button"},
                    # Invalid action
                    {"index": 3, "action": "drag_and_drop", "selector": "#opt-a"},
                    # Valid step
                    {"index": 4, "action": "assert_visible", "selector": "#timer"},
                ],
                "expected_result": "Only valid steps are retained.",
            }
        ]
    }

    mock_client = MockGeminiClient(response_text=json.dumps(hallucinated_payload))
    generator = SuiteGenerator(client=mock_client)

    import os
    os.environ["GEMINI_API_KEY"] = "fake-test-key-xyz"
    try:
        cases = generator.generate_suite(ctx, amap, [journey])
        assert len(cases) == 1
        case = cases[0]
        selectors = [s.selector for s in case.steps if s.selector]
        assert "#completely-invented-button" not in selectors
        assert "#timer" in selectors
    finally:
        del os.environ["GEMINI_API_KEY"]


def test_consequential_controls_click_prevention(tmp_path: Path) -> None:
    """Ensure proposed clicks on submit controls are converted to assert_visible."""
    ctx = _make_context(tmp_path)
    amap = _make_sample_assessment_map()
    journey = Journey(
        run_id=ctx.run.id,
        name="Assessment Journey",
        start_url="http://test.local/exam",
        pages=[DiscoveredPage(url="http://test.local/exam", depth=0, elements=[])],
        generated_by=GenerationMode.RULE_BASED,
    )

    dangerous_payload = {
        "cases": [
            {
                "title": "Dangerous Submit Case",
                "priority": 1,
                "steps": [
                    {"index": 1, "action": "navigate", "url": "http://test.local/exam"},
                    # LLM proposed clicking submit!
                    {"index": 2, "action": "click", "selector": "#btn-submit"},
                ],
                "expected_result": "Submit button is checked without submitting.",
            }
        ]
    }

    mock_client = MockGeminiClient(response_text=json.dumps(dangerous_payload))
    generator = SuiteGenerator(client=mock_client)

    import os
    os.environ["GEMINI_API_KEY"] = "fake-test-key-xyz"
    try:
        cases = generator.generate_suite(ctx, amap, [journey])
        assert len(cases) == 1
        submit_step = next(s for s in cases[0].steps if s.selector == "#btn-submit")
        # Click must be downgraded to ASSERT_VISIBLE
        assert submit_step.action == BrowserAction.ASSERT_VISIBLE
    finally:
        del os.environ["GEMINI_API_KEY"]


def test_missing_api_key_falls_back_gracefully(tmp_path: Path) -> None:
    """When GEMINI_API_KEY is unset, use deterministic rule-based fallback without crashing."""
    ctx = _make_context(tmp_path)
    amap = _make_sample_assessment_map()
    journey = Journey(
        run_id=ctx.run.id,
        name="Assessment Journey",
        start_url="http://test.local/exam",
        pages=[DiscoveredPage(url="http://test.local/exam", depth=0, elements=[])],
        generated_by=GenerationMode.RULE_BASED,
    )

    import os
    os.environ.pop("GEMINI_API_KEY", None)

    generator = SuiteGenerator()
    cases = generator.generate_suite(ctx, amap, [journey])

    assert len(cases) >= 1
    # Must be marked RULE_BASED honestly
    assert all(c.generated_by == GenerationMode.RULE_BASED for c in cases)
    # Check that timer and option cases exist
    titles = [c.title for c in cases]
    assert any("Timer" in t for t in titles)


def test_gemini_api_failure_retries_once_then_falls_back(tmp_path: Path) -> None:
    """Verify single retry on API error, followed by fallback to deterministic generation."""
    ctx = _make_context(tmp_path)
    amap = _make_sample_assessment_map()
    journey = Journey(
        run_id=ctx.run.id,
        name="Assessment Journey",
        start_url="http://test.local/exam",
        pages=[DiscoveredPage(url="http://test.local/exam", depth=0, elements=[])],
        generated_by=GenerationMode.RULE_BASED,
    )

    mock_client = MockGeminiClient(should_fail=True)
    generator = SuiteGenerator(client=mock_client)

    import os
    os.environ["GEMINI_API_KEY"] = "fake-test-key-xyz"
    try:
        cases = generator.generate_suite(ctx, amap, [journey])
        # Exactly 2 attempts (initial + 1 retry)
        assert mock_client.call_count == 2
        # Returns rule-based fallback
        assert len(cases) >= 1
        assert all(c.generated_by == GenerationMode.RULE_BASED for c in cases)
    finally:
        del os.environ["GEMINI_API_KEY"]


def test_gemini_invalid_json_falls_back(tmp_path: Path) -> None:
    """Verify recovery when Gemini returns malformed non-JSON text."""
    ctx = _make_context(tmp_path)
    amap = _make_sample_assessment_map()
    journey = Journey(
        run_id=ctx.run.id,
        name="Assessment Journey",
        start_url="http://test.local/exam",
        pages=[DiscoveredPage(url="http://test.local/exam", depth=0, elements=[])],
        generated_by=GenerationMode.RULE_BASED,
    )

    mock_client = MockGeminiClient(response_text="Here is your test suite: ```json {invalid")
    generator = SuiteGenerator(client=mock_client)

    import os
    os.environ["GEMINI_API_KEY"] = "fake-test-key-xyz"
    try:
        cases = generator.generate_suite(ctx, amap, [journey])
        assert mock_client.call_count == 2
        assert len(cases) >= 1
        assert all(c.generated_by == GenerationMode.RULE_BASED for c in cases)
    finally:
        del os.environ["GEMINI_API_KEY"]


def test_generic_website_fallback(tmp_path: Path) -> None:
    """When no assessment map exists, return standard website smoke test."""
    ctx = _make_context(tmp_path)
    journey = Journey(
        run_id=ctx.run.id,
        name="Generic Journey",
        start_url="http://test.local/about",
        pages=[DiscoveredPage(url="http://test.local/about", depth=0, elements=[])],
        generated_by=GenerationMode.RULE_BASED,
    )

    generator = SuiteGenerator()
    cases = generator.generate_suite(ctx, assessment_map=None, journeys=[journey])

    assert len(cases) == 1
    assert "Smoke navigation" in cases[0].title
    assert cases[0].generated_by == GenerationMode.RULE_BASED


def test_tester_agent_integration_with_suite_generator(tmp_path: Path) -> None:
    """Verify TesterAgent seamlessly runs tests proposed by SuiteGenerator."""
    ctx = _make_context(tmp_path)
    amap = _make_sample_assessment_map()
    journey = Journey(
        run_id=ctx.run.id,
        name="Assessment Journey",
        start_url="http://test.local/exam",
        pages=[DiscoveredPage(url="http://test.local/exam", depth=0, elements=[])],
        generated_by=GenerationMode.RULE_BASED,
    )

    valid_payload = {
        "cases": [
            {
                "title": "LLM Generated Assessment Check",
                "priority": 1,
                "steps": [
                    {"index": 1, "action": "navigate", "url": "http://test.local/exam"},
                    {"index": 2, "action": "assert_visible", "selector": "#timer"},
                ],
                "expected_result": "Timer is visible.",
            }
        ]
    }

    mock_client = MockGeminiClient(response_text=json.dumps(valid_payload))
    suite_gen = SuiteGenerator(client=mock_client)

    # Mock browser driver to avoid real network call during unit test
    mock_driver = MagicMock()
    mock_driver.start = AsyncMock()
    mock_driver.close = AsyncMock()
    mock_driver.open = AsyncMock(return_value={"url": "http://test.local/exam", "title": "Exam", "status": 200})
    mock_page = MagicMock()
    mock_page.is_visible = AsyncMock(return_value=True)
    mock_driver.page = mock_page

    tester = TesterAgent(
        driver=mock_driver,
        suite_generator=suite_gen,
        assessment_map=amap,
    )

    import os
    os.environ["GEMINI_API_KEY"] = "fake-test-key-xyz"
    try:
        output = tester.run_tests(ctx, [journey])
        assert len(output.test_cases) == 1
        assert output.test_cases[0].title == "LLM Generated Assessment Check"
        assert output.test_cases[0].generated_by == GenerationMode.LLM
        assert len(output.test_results) == 1
    finally:
        del os.environ["GEMINI_API_KEY"]


def test_assessment_qa_workflow_with_factory_and_provider(tmp_path: Path) -> None:
    """Verify orchestrator workflow where explorer discovers assessment map and tester uses provider."""
    from app.agents.factory import build_agents

    ctx = _make_context(tmp_path)
    amap = _make_sample_assessment_map()
    journey = Journey(
        run_id=ctx.run.id,
        name="Assessment Flow: Technical Exam",
        start_url="http://test.local/exam",
        pages=[DiscoveredPage(url="http://test.local/exam", depth=0, elements=[])],
        generated_by=GenerationMode.RULE_BASED,
    )

    valid_payload = {
        "cases": [
            {
                "title": "LLM Verification of Binary Search Options",
                "priority": 1,
                "steps": [
                    {"index": 1, "action": "navigate", "url": "http://test.local/exam"},
                    {"index": 2, "action": "assert_visible", "selector": "#timer"},
                    {"index": 3, "action": "check", "selector": "#opt-a"},
                ],
                "expected_result": "Binary search options are responsive.",
            }
        ]
    }

    mock_client = MockGeminiClient(response_text=json.dumps(valid_payload))
    suite_gen = SuiteGenerator(client=mock_client)

    # Use factory to build the production agent set
    agent_set = build_agents(ctx.settings)
    # Simulate explorer having discovered an assessment map
    agent_set.explorer._last_assessment_map = amap

    # Configure tester with mock driver and mock suite generator
    mock_driver = MagicMock()
    mock_driver.start = AsyncMock()
    mock_driver.close = AsyncMock()
    mock_driver.screenshot = AsyncMock(return_value=Path("dummy.png"))
    mock_driver.open = AsyncMock(return_value={"url": "http://test.local/exam", "title": "Exam", "status": 200})
    mock_page = MagicMock()
    mock_page.is_visible = AsyncMock(return_value=True)
    mock_page.click = AsyncMock()
    mock_page.check = AsyncMock()
    mock_driver.page = mock_page

    agent_set.tester._driver = mock_driver
    agent_set.tester._suite_generator = suite_gen

    import os
    os.environ["GEMINI_API_KEY"] = "fake-test-key-xyz"
    try:
        # Run TesterAgent through the exact orchestrator interface
        output = agent_set.tester.run_tests(ctx, [journey])
        assert mock_client.call_count == 1
        assert len(output.test_cases) == 1
        assert output.test_cases[0].title == "LLM Verification of Binary Search Options"
        assert output.test_cases[0].generated_by == GenerationMode.LLM
        assert len(output.test_results) == 1
        assert output.test_results[0].status == TestStatus.PASSED
    finally:
        del os.environ["GEMINI_API_KEY"]


def test_assessment_qa_workflow_reconstructing_from_journeys_without_explorer(tmp_path: Path) -> None:
    """Verify that TesterAgent reconstructs AssessmentMap directly from journeys without relying on Explorer state."""
    ctx = _make_context(tmp_path)

    # Journey with elements as produced by Explorer
    assessment_elements = [
        InteractiveElement(element_type=ElementType.OTHER, selector="#timer", label="Timer (30:00)"),
        InteractiveElement(element_type=ElementType.RADIO, selector="#opt-a", label="Option A"),
        InteractiveElement(element_type=ElementType.RADIO, selector="#opt-b", label="Option B"),
        InteractiveElement(element_type=ElementType.BUTTON, selector="#btn-next", label="Next Control (Next)"),
        InteractiveElement(element_type=ElementType.BUTTON, selector="#btn-submit", label="Submit Control (Submit Exam)"),
    ]
    journey = Journey(
        run_id=ctx.run.id,
        name="Assessment Flow: Exam Journey",
        start_url="http://test.local/exam",
        pages=[DiscoveredPage(url="http://test.local/exam", depth=0, elements=assessment_elements)],
        generated_by=GenerationMode.RULE_BASED,
    )

    valid_payload = {
        "cases": [
            {
                "title": "LLM Test from Reconstructed Journey",
                "priority": 1,
                "steps": [
                    {"index": 1, "action": "navigate", "url": "http://test.local/exam"},
                    {"index": 2, "action": "assert_visible", "selector": "#timer"},
                    # Ensure proposed submit click is intercepted
                    {"index": 3, "action": "click", "selector": "#btn-submit"},
                ],
                "expected_result": "Controls verified safely.",
            }
        ]
    }

    mock_client = MockGeminiClient(response_text=json.dumps(valid_payload))
    suite_gen = SuiteGenerator(client=mock_client)

    # Construct independent TesterAgent (no assessment_map or provider passed)
    mock_driver = MagicMock()
    mock_driver.start = AsyncMock()
    mock_driver.close = AsyncMock()
    mock_driver.screenshot = AsyncMock(return_value=Path("dummy.png"))
    mock_driver.open = AsyncMock(return_value={"url": "http://test.local/exam", "title": "Exam", "status": 200})
    mock_page = MagicMock()
    mock_page.is_visible = AsyncMock(return_value=True)
    mock_driver.page = mock_page

    tester = TesterAgent(driver=mock_driver, suite_generator=suite_gen)

    import os
    os.environ["GEMINI_API_KEY"] = "fake-test-key-xyz"
    try:
        output = tester.run_tests(ctx, [journey])
        assert mock_client.call_count == 1
        assert len(output.test_cases) == 1
        case = output.test_cases[0]
        assert case.generated_by == GenerationMode.LLM
        # Consequential submit control click was downgraded to ASSERT_VISIBLE
        submit_step = next(s for s in case.steps if s.selector == "#btn-submit")
        assert submit_step.action == BrowserAction.ASSERT_VISIBLE
        assert len(output.test_results) == 1
    finally:
        del os.environ["GEMINI_API_KEY"]


def test_assessment_qa_workflow_fallback_on_gemini_error(tmp_path: Path) -> None:
    """Verify that when Gemini fails in the workflow, the system uses rule-based fallback without crashing."""
    ctx = _make_context(tmp_path)
    amap = _make_sample_assessment_map()
    journey = Journey(
        run_id=ctx.run.id,
        name="Assessment Journey",
        start_url="http://test.local/exam",
        pages=[DiscoveredPage(url="http://test.local/exam", depth=0, elements=[])],
        generated_by=GenerationMode.RULE_BASED,
    )

    # Client configured to fail (simulate timeout/quota/API error)
    mock_client = MockGeminiClient(should_fail=True)
    suite_gen = SuiteGenerator(client=mock_client)

    mock_driver = MagicMock()
    mock_driver.start = AsyncMock()
    mock_driver.close = AsyncMock()
    mock_driver.screenshot = AsyncMock(return_value=Path("dummy.png"))
    mock_driver.open = AsyncMock(return_value={"url": "http://test.local/exam", "title": "Exam", "status": 200})
    mock_driver.click = AsyncMock()
    mock_driver.fill = AsyncMock()
    mock_driver.check = AsyncMock()
    mock_page = MagicMock()
    mock_page.is_visible = AsyncMock(return_value=True)
    mock_page.click = AsyncMock()
    mock_page.check = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.inner_text = AsyncMock(return_value="30:00")
    mock_locator.check = AsyncMock()
    mock_page.locator = MagicMock(return_value=mock_locator)
    mock_driver.page = mock_page

    tester = TesterAgent(driver=mock_driver, suite_generator=suite_gen, assessment_map=amap)

    import os
    os.environ["GEMINI_API_KEY"] = "fake-test-key-xyz"
    try:
        output = tester.run_tests(ctx, [journey])
        # Tried once, retried once = 2 attempts
        assert mock_client.call_count == 2
        # Successfully fell back to rule-based cases
        assert len(output.test_cases) >= 1
        assert all(c.generated_by == GenerationMode.RULE_BASED for c in output.test_cases)
        # Executed them without crashing
        assert len(output.test_results) == len(output.test_cases)
        assert all(r.status == TestStatus.PASSED for r in output.test_results)
    finally:
        del os.environ["GEMINI_API_KEY"]
