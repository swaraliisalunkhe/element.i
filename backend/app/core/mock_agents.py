"""MOCK agents: fixed fake data so the pipeline can be tested end to end. Owner: Member A.

Nothing here opens a browser or calls an AI. Everything is labelled generated_by=mock.
"""

import struct
import time
import zlib

from app.core.agent_interface import AgentContext, AgentSet, TesterOutput
from app.core.constants import (
    AgentName,
    BrowserAction,
    BugCategory,
    ElementType,
    EventType,
    GenerationMode,
    Severity,
    TestStatus,
)
from app.schemas import (
    BugReport,
    DiscoveredPage,
    EvidenceMeta,
    InteractiveElement,
    Journey,
    StepResult,
    TestCase,
    TestResult,
    TestStep,
    utc_now,
)

# Pause between fake steps so the live dashboard is watchable. Tests set this to 0.
DEFAULT_DELAY_SECONDS = 0.6

PNG_WIDTH = 640
PNG_HEIGHT = 360


def _pause() -> None:
    time.sleep(DEFAULT_DELAY_SECONDS)


def make_placeholder_png(width: int = PNG_WIDTH, height: int = PNG_HEIGHT) -> bytes:
    """Build a valid PNG (red banner on grey). It is a placeholder, not a real screenshot."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    banner = bytes((170, 40, 40)) * width
    grey = bytes((230, 230, 230)) * width
    rows = [b"\x00" + (banner if y < 48 else grey) for y in range(height)]
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )


def _base(ctx: AgentContext) -> str:
    return ctx.run.target_url.rstrip("/")


class MockExplorer:
    def explore(self, ctx: AgentContext) -> list[Journey]:
        base = _base(ctx)
        ctx.emit(EventType.AGENT_PROGRESS, AgentName.EXPLORER, "[MOCK] Pretending to open the start page.")
        _pause()
        ctx.emit(EventType.AGENT_PROGRESS, AgentName.EXPLORER, "[MOCK] Pretending to find a login form.")
        _pause()
        journey = Journey(
            run_id=ctx.run.id,
            name="Log in with an email address",
            description="[MOCK] A visitor opens the login page, enters credentials and submits.",
            priority=1,
            start_url=f"{base}/login",
            pages=[
                DiscoveredPage(
                    url=f"{base}/",
                    title="Home",
                    depth=0,
                    elements=[
                        InteractiveElement(
                            element_type=ElementType.LINK,
                            selector="a[href='/login']",
                            label="Log in",
                            href="/login",
                        )
                    ],
                ),
                DiscoveredPage(
                    url=f"{base}/login",
                    title="Log in",
                    depth=1,
                    elements=[
                        InteractiveElement(
                            element_type=ElementType.INPUT, selector="#email", label="Email",
                            input_type="email", required=True,
                        ),
                        InteractiveElement(
                            element_type=ElementType.INPUT, selector="#password", label="Password",
                            input_type="password", required=True,
                        ),
                        InteractiveElement(
                            element_type=ElementType.BUTTON, selector="button[type='submit']",
                            label="Sign in",
                        ),
                    ],
                ),
            ],
            generated_by=GenerationMode.MOCK,
        )
        return [journey]


class MockTester:
    def run_tests(self, ctx: AgentContext, journeys: list[Journey]) -> TesterOutput:
        base = _base(ctx)
        case = TestCase(
            run_id=ctx.run.id,
            journey_id=journeys[0].id if journeys else None,
            title="Login without a password shows an error",
            description="[MOCK] Submitting the login form with only an email must be rejected.",
            priority=1,
            steps=[
                TestStep(index=1, action=BrowserAction.NAVIGATE, url=f"{base}/login",
                         description="Open the login page"),
                TestStep(index=2, action=BrowserAction.FILL, selector="#email",
                         value="user@example.com", description="Type an email, leave password empty"),
                TestStep(index=3, action=BrowserAction.CLICK, selector="button[type='submit']",
                         description="Press Sign in"),
                TestStep(index=4, action=BrowserAction.ASSERT_TEXT, selector="#error-message",
                         value="Password is required", description="An error must be shown"),
            ],
            expected_result="The form is rejected and 'Password is required' is shown.",
            generated_by=GenerationMode.MOCK,
        )
        ctx.emit(EventType.TEST_STARTED, AgentName.TESTER, f"[MOCK] Starting test: {case.title}",
                 data={"test_case_id": case.id})

        started = utc_now()
        actual = [
            f"[MOCK] Opened {base}/login",
            "[MOCK] Filled #email",
            "[MOCK] Clicked the submit button; moved to /dashboard",
            "[MOCK] No error message. The page is /dashboard.",
        ]
        step_results: list[StepResult] = []
        for step, text in zip(case.steps, actual):
            _pause()
            failed = step.index == 4
            step_results.append(
                StepResult(
                    step_index=step.index,
                    action=step.action,
                    status=TestStatus.FAILED if failed else TestStatus.PASSED,
                    duration_ms=120,
                    error_message="[MOCK] Element '#error-message' was not found." if failed else None,
                    actual=text,
                )
            )
            ctx.emit(EventType.STEP_COMPLETED, AgentName.TESTER,
                     f"[MOCK] Step {step.index} {'failed' if failed else 'passed'}",
                     data={"test_case_id": case.id, "step_index": step.index})

        png = make_placeholder_png()
        path, relative = ctx.new_evidence_target(f"{case.id}_step4.png")
        path.write_bytes(png)
        evidence = EvidenceMeta(
            run_id=ctx.run.id,
            test_case_id=case.id,
            step_index=4,
            path=relative,
            width=PNG_WIDTH,
            height=PNG_HEIGHT,
            size_bytes=len(png),
            caption="MOCK placeholder image (not a real screenshot)",
        )
        step_results[-1].evidence_id = evidence.id

        finished = utc_now()
        result = TestResult(
            run_id=ctx.run.id,
            test_case_id=case.id,
            status=TestStatus.FAILED,
            started_at=started,
            finished_at=finished,
            duration_ms=int((finished - started).total_seconds() * 1000),
            error_message="[MOCK] Step 4 failed: element '#error-message' was not found.",
            step_results=step_results,
            evidence=[evidence],
            generated_by=GenerationMode.MOCK,
        )
        return TesterOutput(test_cases=[case], test_results=[result])


class MockReporter:
    def report(
        self,
        ctx: AgentContext,
        journeys: list[Journey],
        test_cases: list[TestCase],
        test_results: list[TestResult],
    ) -> list[BugReport]:
        base = _base(ctx)
        cases = {case.id: case for case in test_cases}
        bugs: list[BugReport] = []
        for result in test_results:
            if result.status != TestStatus.FAILED:
                continue
            ctx.emit(EventType.AGENT_PROGRESS, AgentName.REPORTER,
                     "[MOCK] Pretending to analyse a failed test.")
            _pause()
            case = cases.get(result.test_case_id)
            bugs.append(
                BugReport(
                    run_id=ctx.run.id,
                    test_case_id=result.test_case_id,
                    journey_id=case.journey_id if case else None,
                    title="Login accepts an empty password (MOCK fixture)",
                    severity=Severity.HIGH,
                    category=BugCategory.FORM_VALIDATION,
                    description=(
                        "[MOCK FIXTURE, not a real finding] The login form lets a visitor "
                        "sign in with an email only."
                    ),
                    steps_to_reproduce=[
                        f"Open {base}/login",
                        "Type user@example.com into the Email field",
                        "Leave the Password field empty",
                        "Click Sign in",
                    ],
                    expected_behavior="The form is rejected and 'Password is required' is shown.",
                    actual_behavior="The visitor is taken to /dashboard with no error message.",
                    page_url=f"{base}/login",
                    confidence=0.9,
                    evidence=list(result.evidence),
                    generated_by=GenerationMode.MOCK,
                )
            )
        return bugs


def build_mock_agents() -> AgentSet:
    return AgentSet(explorer=MockExplorer(), tester=MockTester(), reporter=MockReporter())