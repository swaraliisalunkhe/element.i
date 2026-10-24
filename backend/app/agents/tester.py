"""Rule-based Tester Agent for Code Apex.

Owner: Member C.
Generates deterministic test cases from discovered Journeys and executes them
via BrowserDriver, recording StepResults, TestResults, and screenshot evidence.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import concurrent.futures
from datetime import datetime
import logging
import time
import urllib.parse
from typing import TYPE_CHECKING, Any

from app.agents.assessment_map import AssessmentMap
from app.core.agent_interface import AgentContext, TesterOutput
from app.core.constants import (
    AgentName,
    BrowserAction,
    ElementType,
    EventLevel,
    EventType,
    EvidenceKind,
    GenerationMode,
    TestStatus,
)
from app.schemas.common import EvidenceMeta, new_id, utc_now
from app.schemas.journey import DiscoveredPage, InteractiveElement, Journey
from app.schemas.test_case import StepResult, TestCase, TestResult, TestStep
from app.services.browser_driver import BrowserDriver

if TYPE_CHECKING:
    from app.services.suite_generator import SuiteGenerator

logger = logging.getLogger("code_apex.agents.tester")


def _run_async(coro: Any) -> Any:
    """Safely execute an asynchronous coroutine from synchronous code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class TesterAgent:
    """Deterministic, rule-based QA Tester Agent."""

    __test__ = False  # Prevents pytest from discovering this class as a test suite

    def __init__(
        self,
        driver: BrowserDriver | None = None,
        suite_generator: SuiteGenerator | None = None,
        assessment_map: AssessmentMap | None = None,
        assessment_map_provider: Callable[[], AssessmentMap | None] | None = None,
    ) -> None:
        self._driver = driver
        if suite_generator is not None:
            self._suite_generator = suite_generator
        else:
            from app.services.suite_generator import SuiteGenerator

            self._suite_generator = SuiteGenerator()
        self._assessment_map = assessment_map
        self._assessment_map_provider = assessment_map_provider

    def _get_assessment_map(self, journeys: list[Journey]) -> AssessmentMap | None:
        """Resolve AssessmentMap explicitly, from provider, or by reconstructing from journeys."""
        if self._assessment_map is not None:
            return self._assessment_map
        if self._assessment_map_provider is not None:
            try:
                amap = self._assessment_map_provider()
                if amap is not None:
                    return amap
            except Exception:
                pass
        return AssessmentMap.from_journeys(journeys)

    def run_tests(self, ctx: AgentContext, journeys: list[Journey]) -> TesterOutput:
        """Synchronously execute tests for the given journeys and return TesterOutput."""
        return _run_async(self._async_run_tests(ctx, journeys))

    async def _async_run_tests(self, ctx: AgentContext, journeys: list[Journey]) -> TesterOutput:
        driver = self._driver or BrowserDriver(
            evidence_dir=ctx.evidence_dir, settings=ctx.settings
        )

        test_cases = self._generate_test_cases(ctx, journeys)
        test_results: list[TestResult] = []

        try:
            await driver.start(headless=True)

            for case in test_cases:
                result = await self._execute_test_case(ctx, driver, case)
                test_results.append(result)

        finally:
            await driver.close()

        ctx.emit(
            EventType.AGENT_PROGRESS,
            AgentName.TESTER,
            f"Tester completed execution: {len(test_results)} test(s) run.",
            level=EventLevel.INFO,
            data={"tests_count": len(test_results)},
        )

        return TesterOutput(test_cases=test_cases, test_results=test_results)

    def _generate_test_cases(self, ctx: AgentContext, journeys: list[Journey]) -> list[TestCase]:
        """Generate sensible deterministic test cases from discovered Journeys."""
        test_cases: list[TestCase] = []
        max_tests = ctx.run.max_tests
        run_id = ctx.run.id

        amap = self._get_assessment_map(journeys)
        is_assessment = bool(
            amap and amap.is_assessment
            or any("assessment" in (j.name or "").lower() for j in journeys)
            or any(
                e.element_type == ElementType.RADIO
                for j in journeys
                for p in j.pages
                for e in p.elements
            )
        )
        if is_assessment:
            suite_cases = self._suite_generator.generate_suite(ctx, amap, journeys)
            if suite_cases:
                return suite_cases[:max_tests]

        # If journeys are empty, create a baseline smoke test for the target URL
        if not journeys:
            target_url = ctx.run.target_url
            path = urllib.parse.urlparse(target_url).path or "/"
            steps = [
                TestStep(index=1, action=BrowserAction.NAVIGATE, url=target_url, description=f"Navigate to {target_url}"),
                TestStep(index=2, action=BrowserAction.ASSERT_URL, value=path, description=f"Assert URL path contains '{path}'"),
            ]
            case = TestCase(
                run_id=run_id,
                title=f"Smoke navigation to {target_url}"[:200],
                description="Verify that the root target URL loads successfully.",
                priority=1,
                steps=steps,
                expected_result="Page loads with valid URL path.",
                generated_by=GenerationMode.RULE_BASED,
            )
            return [case]

        for journey in journeys:
            for page in journey.pages:
                if len(test_cases) >= max_tests:
                    return test_cases

                # 1. Page Navigation & Verification Test Case
                nav_case = self._create_page_verification_case(run_id, journey.id, page)
                if nav_case:
                    test_cases.append(nav_case)
                if len(test_cases) >= max_tests:
                    return test_cases

                # 2. Form Interaction Test Case (if inputs & buttons exist on page)
                form_case = self._create_form_interaction_case(run_id, journey.id, page)
                if form_case:
                    test_cases.append(form_case)
                if len(test_cases) >= max_tests:
                    return test_cases

                # 3. Link Navigation Test Case (if safe links exist on page)
                link_case = self._create_link_navigation_case(run_id, journey.id, page)
                if link_case:
                    test_cases.append(link_case)
                if len(test_cases) >= max_tests:
                    return test_cases

        # If no cases were generated, ensure at least one baseline case exists
        if not test_cases and journeys and journeys[0].pages:
            first_page = journeys[0].pages[0]
            case = self._create_page_verification_case(run_id, journeys[0].id, first_page)
            if case:
                test_cases.append(case)

        return test_cases

    def _create_page_verification_case(
        self, run_id: str, journey_id: str, page: DiscoveredPage
    ) -> TestCase | None:
        """Create a test verifying page navigation and key element visibility."""
        steps: list[TestStep] = []
        path = urllib.parse.urlparse(page.url).path or "/"

        steps.append(
            TestStep(
                index=1,
                action=BrowserAction.NAVIGATE,
                url=page.url,
                description=f"Open {page.url}",
            )
        )
        steps.append(
            TestStep(
                index=2,
                action=BrowserAction.ASSERT_URL,
                value=path,
                description=f"Assert URL contains '{path}'",
            )
        )

        # Check visibility of first button or link if available
        first_interactive = next(
            (e for e in page.elements if e.element_type in (ElementType.BUTTON, ElementType.LINK, ElementType.INPUT)),
            None,
        )
        if first_interactive:
            steps.append(
                TestStep(
                    index=3,
                    action=BrowserAction.ASSERT_VISIBLE,
                    selector=first_interactive.selector,
                    description=f"Verify visibility of {first_interactive.element_type.value} ({first_interactive.selector})",
                )
            )

        title_label = page.title or page.url
        return TestCase(
            run_id=run_id,
            journey_id=journey_id,
            title=f"Verify page: {title_label}"[:200],
            description=f"Navigate to {page.url} and verify page load and key element visibility.",
            priority=1,
            steps=steps,
            expected_result=f"Page {page.url} loads with matching URL and visible controls.",
            generated_by=GenerationMode.RULE_BASED,
        )

    def _create_form_interaction_case(
        self, run_id: str, journey_id: str, page: DiscoveredPage
    ) -> TestCase | None:
        """Create a test interacting with form inputs and submit button if detected."""
        inputs = [
            e for e in page.elements
            if e.element_type in (ElementType.INPUT, ElementType.TEXTAREA)
            and (e.input_type or "text").lower() not in ("hidden", "button", "submit")
        ]
        button = next((e for e in page.elements if e.element_type == ElementType.BUTTON), None)

        if not inputs or not button:
            return None

        steps: list[TestStep] = [
            TestStep(index=1, action=BrowserAction.NAVIGATE, url=page.url, description=f"Open {page.url}")
        ]

        # Fill up to 3 input fields
        for inp in inputs[:3]:
            idx = len(steps) + 1
            itype = (inp.input_type or "text").lower()
            if "email" in itype:
                val = "qa_user@example.com"
            elif "password" in itype:
                val = "ValidPassword123!"
            else:
                val = "Test Sample Input"

            steps.append(
                TestStep(
                    index=idx,
                    action=BrowserAction.FILL,
                    selector=inp.selector,
                    value=val,
                    description=f"Fill {inp.label or inp.selector} with sample data",
                )
            )

        # Click submit button
        steps.append(
            TestStep(
                index=len(steps) + 1,
                action=BrowserAction.CLICK,
                selector=button.selector,
                description=f"Click submit button {button.label or button.selector}",
            )
        )

        # Wait briefly for response
        steps.append(
            TestStep(
                index=len(steps) + 1,
                action=BrowserAction.WAIT,
                value="500",
                description="Wait for form response",
            )
        )

        title_label = page.title or page.url
        return TestCase(
            run_id=run_id,
            journey_id=journey_id,
            title=f"Form submission: {title_label}"[:200],
            description=f"Fill discovered input controls on {page.url} and trigger submit.",
            priority=2,
            steps=steps,
            expected_result="Inputs filled and form submitted without client exceptions.",
            generated_by=GenerationMode.RULE_BASED,
        )

    def _create_link_navigation_case(
        self, run_id: str, journey_id: str, page: DiscoveredPage
    ) -> TestCase | None:
        """Create a test verifying link clicking on the page."""
        link = next((e for e in page.elements if e.element_type == ElementType.LINK and e.href and not e.href.startswith("#")), None)
        if not link:
            return None

        steps: list[TestStep] = [
            TestStep(index=1, action=BrowserAction.NAVIGATE, url=page.url, description=f"Open {page.url}"),
            TestStep(index=2, action=BrowserAction.ASSERT_VISIBLE, selector=link.selector, description=f"Verify link {link.selector} is visible"),
            TestStep(index=3, action=BrowserAction.CLICK, selector=link.selector, description=f"Click link '{link.label or link.href}'"),
            TestStep(index=4, action=BrowserAction.WAIT, value="500", description="Wait for page transition"),
        ]

        title_label = page.title or page.url
        return TestCase(
            run_id=run_id,
            journey_id=journey_id,
            title=f"Link click: {link.label or link.href} on {title_label}"[:200],
            description=f"Click link '{link.label or link.href}' from {page.url}.",
            priority=3,
            steps=steps,
            expected_result="Link click navigates or updates view cleanly.",
            generated_by=GenerationMode.RULE_BASED,
        )

    async def _execute_test_case(
        self, ctx: AgentContext, driver: BrowserDriver, case: TestCase
    ) -> TestResult:
        """Execute all steps in a test case, capturing step outcomes and screenshot evidence."""
        ctx.emit(
            EventType.TEST_STARTED,
            AgentName.TESTER,
            f"Starting test: {case.title}",
            data={"test_case_id": case.id},
        )

        started_at = utc_now()
        step_results: list[StepResult] = []
        evidence_list: list[EvidenceMeta] = []
        overall_status = TestStatus.PASSED
        overall_error: str | None = None

        for i, step in enumerate(case.steps):
            # If an earlier step failed, mark remaining steps SKIPPED
            if overall_status != TestStatus.PASSED:
                skipped_res = StepResult(
                    step_index=step.index,
                    action=step.action,
                    status=TestStatus.SKIPPED,
                    duration_ms=0,
                    actual="Skipped due to prior step failure.",
                )
                step_results.append(skipped_res)
                ctx.emit(
                    EventType.STEP_COMPLETED,
                    AgentName.TESTER,
                    f"Step {step.index} skipped",
                    data={"test_case_id": case.id, "step_index": step.index},
                )
                continue

            step_start = time.perf_counter()
            evidence_id: str | None = None
            step_status = TestStatus.PASSED
            step_error: str | None = None
            actual_text: str | None = None

            try:
                actual_text = await self._execute_step_action(driver, step)

                # If explicit screenshot action, capture evidence
                if step.action == BrowserAction.SCREENSHOT:
                    evidence_meta = await self._capture_screenshot(
                        ctx, driver, case.id, step.index, "Explicit step screenshot"
                    )
                    if evidence_meta:
                        evidence_list.append(evidence_meta)
                        evidence_id = evidence_meta.id

            except AssertionError as exc:
                step_status = TestStatus.FAILED
                step_error = str(exc) or "Assertion failed"
                overall_status = TestStatus.FAILED
                overall_error = f"Step {step.index} failed assertion: {step_error}"
                actual_text = f"Assertion failed: {step_error}"

                # Capture screenshot evidence on failure
                evidence_meta = await self._capture_screenshot(
                    ctx, driver, case.id, step.index, f"Failure at step {step.index}: {step_error}"
                )
                if evidence_meta:
                    evidence_list.append(evidence_meta)
                    evidence_id = evidence_meta.id

            except Exception as exc:
                step_status = TestStatus.FAILED
                step_error = f"{type(exc).__name__}: {exc}"
                overall_status = TestStatus.FAILED
                overall_error = f"Step {step.index} execution error: {step_error}"
                actual_text = f"Action error: {step_error}"

                evidence_meta = await self._capture_screenshot(
                    ctx, driver, case.id, step.index, f"Execution error at step {step.index}: {step_error}"
                )
                if evidence_meta:
                    evidence_list.append(evidence_meta)
                    evidence_id = evidence_meta.id

            step_duration_ms = max(0, int((time.perf_counter() - step_start) * 1000))
            step_res = StepResult(
                step_index=step.index,
                action=step.action,
                status=step_status,
                duration_ms=step_duration_ms,
                error_message=step_error,
                actual=actual_text,
                evidence_id=evidence_id,
            )
            step_results.append(step_res)

            ctx.emit(
                EventType.STEP_COMPLETED,
                AgentName.TESTER,
                f"Step {step.index} {step_status.value}",
                data={"test_case_id": case.id, "step_index": step.index},
            )

        finished_at = utc_now()
        total_duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))

        return TestResult(
            run_id=ctx.run.id,
            test_case_id=case.id,
            status=overall_status,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=total_duration_ms,
            error_message=overall_error,
            step_results=step_results,
            evidence=evidence_list,
            generated_by=GenerationMode.RULE_BASED,
        )

    async def _execute_step_action(self, driver: BrowserDriver, step: TestStep) -> str:
        """Execute a single browser action and return a descriptive actual outcome."""
        action = step.action

        if action == BrowserAction.NAVIGATE:
            if not step.url:
                raise ValueError("Navigate step missing url")
            info = await driver.open(step.url)
            status_code = info.get("status", 200)
            if status_code >= 400:
                raise AssertionError(f"Navigation to {step.url} returned HTTP {status_code}")
            return f"Navigated to {info.get('url', step.url)} (status {status_code})"

        if action == BrowserAction.CLICK:
            if not step.selector:
                raise ValueError("Click step missing selector")
            await driver.click(step.selector)
            return f"Clicked element matching '{step.selector}'"

        if action == BrowserAction.FILL:
            if not step.selector or step.value is None:
                raise ValueError("Fill step requires selector and value")
            await driver.fill(step.selector, step.value)
            return f"Filled '{step.selector}' with '{step.value}'"

        if action == BrowserAction.ASSERT_URL:
            if step.value is None:
                raise ValueError("Assert URL step missing value")
            page = driver.page
            current_url = page.url if page else ""
            if step.value not in current_url:
                raise AssertionError(f"Expected '{step.value}' in URL, got '{current_url}'")
            return f"Verified current URL '{current_url}' contains '{step.value}'"

        if action == BrowserAction.ASSERT_VISIBLE:
            if not step.selector:
                raise ValueError("Assert visible step missing selector")
            page = driver.page
            if not page:
                raise AssertionError("Browser page is not available")
            is_visible = await page.is_visible(step.selector)
            if not is_visible:
                raise AssertionError(f"Element '{step.selector}' is not visible")
            return f"Element '{step.selector}' is visible"

        if action == BrowserAction.ASSERT_TEXT:
            if not step.selector or step.value is None:
                raise ValueError("Assert text step requires selector and value")
            page = driver.page
            if not page:
                raise AssertionError("Browser page is not available")
            loc = page.locator(step.selector)
            text = (await loc.inner_text()).strip()
            if step.value not in text:
                raise AssertionError(f"Expected '{step.value}' inside element '{step.selector}', got '{text}'")
            return f"Element '{step.selector}' contains expected text '{step.value}'"

        if action == BrowserAction.WAIT:
            ms = int(step.value) if step.value and step.value.isdigit() else 1000
            page = driver.page
            if page:
                await page.wait_for_timeout(ms)
            else:
                await asyncio.sleep(ms / 1000.0)
            return f"Waited {ms}ms"

        if action == BrowserAction.SELECT:
            if not step.selector or step.value is None:
                raise ValueError("Select step requires selector and value")
            page = driver.page
            if page:
                await page.select_option(step.selector, step.value)
            return f"Selected '{step.value}' in '{step.selector}'"

        if action == BrowserAction.CHECK:
            if not step.selector:
                raise ValueError("Check step missing selector")
            page = driver.page
            if page:
                await page.check(step.selector)
            return f"Checked checkbox/radio '{step.selector}'"

        if action == BrowserAction.UNCHECK:
            if not step.selector:
                raise ValueError("Uncheck step missing selector")
            page = driver.page
            if page:
                await page.uncheck(step.selector)
            return f"Unchecked '{step.selector}'"

        if action == BrowserAction.PRESS:
            if not step.value:
                raise ValueError("Press step missing value")
            page = driver.page
            if page:
                await page.keyboard.press(step.value)
            return f"Pressed key '{step.value}'"

        if action == BrowserAction.HOVER:
            if not step.selector:
                raise ValueError("Hover step missing selector")
            page = driver.page
            if page:
                await page.hover(step.selector)
            return f"Hovered over '{step.selector}'"

        if action == BrowserAction.SCREENSHOT:
            return "Captured screenshot"

        return f"Completed action {action.value}"

    async def _capture_screenshot(
        self,
        ctx: AgentContext,
        driver: BrowserDriver,
        case_id: str,
        step_index: int,
        caption: str,
    ) -> EvidenceMeta | None:
        """Capture a screenshot and create a validated EvidenceMeta record."""
        try:
            filename = f"{case_id}_step{step_index}.png"
            abs_path, rel_path = ctx.new_evidence_target(filename)
            await driver.screenshot(abs_path.name, output_dir=abs_path.parent)

            size_bytes = abs_path.stat().st_size if abs_path.exists() else None
            return EvidenceMeta(
                run_id=ctx.run.id,
                test_case_id=case_id,
                step_index=step_index,
                kind=EvidenceKind.SCREENSHOT,
                path=rel_path,
                size_bytes=size_bytes,
                caption=caption[:300],
            )
        except Exception as exc:
            logger.warning("Failed to capture screenshot for test %s step %d: %s", case_id, step_index, exc)
            return None
