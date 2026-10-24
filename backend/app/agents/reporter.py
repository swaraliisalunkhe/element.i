"""Rule-based Reporter Agent for Code Apex.

Owner: Member C.
Analyzes failed TestResults, matches them to TestCases and Journeys,
classifies bug categories and severities deterministically, and produces
validated BugReport models without accessing the database directly.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.agent_interface import AgentContext
from app.core.constants import (
    AgentName,
    BrowserAction,
    BugCategory,
    EventLevel,
    EventType,
    GenerationMode,
    Severity,
    TestStatus,
)
from app.schemas.bug_report import BugReport
from app.schemas.journey import Journey
from app.schemas.test_case import StepResult, TestCase, TestResult, TestStep

logger = logging.getLogger("code_apex.agents.reporter")


class ReporterAgent:
    """Rule-based Reporter Agent synthesizing BugReports from failed test results."""

    def report(
        self,
        ctx: AgentContext,
        journeys: list[Journey],
        test_cases: list[TestCase],
        test_results: list[TestResult],
    ) -> list[BugReport]:
        """Synchronously analyze test results and return a list of BugReports for failures."""
        failed_results = [r for r in test_results if r.status == TestStatus.FAILED]
        if not failed_results:
            return []

        cases_by_id = {case.id: case for case in test_cases}
        journeys_by_id = {j.id: j for j in journeys}
        bugs: list[BugReport] = []

        for result in failed_results:
            case = cases_by_id.get(result.test_case_id)
            journey = journeys_by_id.get(case.journey_id) if case and case.journey_id else None
            journey_id = case.journey_id if case else None

            # Locate the specific step that triggered the failure
            failed_step_res = next(
                (sr for sr in result.step_results if sr.status == TestStatus.FAILED),
                None,
            )

            failed_idx = failed_step_res.step_index if failed_step_res else 1
            failed_action = failed_step_res.action if failed_step_res else None
            err_msg = (
                (failed_step_res.error_message if failed_step_res else None)
                or result.error_message
                or "Unknown error during test execution"
            )

            # Determine affected page URL
            page_url = self._determine_page_url(ctx, case, journey, failed_idx)

            # Determine reproduction steps up to the failure point
            steps_to_reproduce = self._build_steps_to_reproduce(case, failed_idx, result.test_case_id)

            # Determine expected and actual behaviors
            expected_behavior = (
                case.expected_result if case and case.expected_result
                else f"Step {failed_idx} should execute successfully."
            )
            actual_behavior = (
                failed_step_res.actual if failed_step_res and failed_step_res.actual
                else result.error_message or "Step failed during test execution."
            )

            # Determine assessment component if present
            component = self._detect_assessment_component(case, f"{err_msg} {actual_behavior}")

            # Determine category, severity, and confidence via deterministic heuristics
            category, severity, confidence = self._classify_defect(
                case, failed_action, err_msg, actual_behavior, component
            )

            # Construct concise, grounded title and description
            title = self._build_title(case, failed_step_res, result.test_case_id, category, component)
            description = self._build_description(case, failed_step_res, err_msg, actual_behavior, component, category)

            bug = BugReport(
                run_id=ctx.run.id,
                test_case_id=result.test_case_id,
                journey_id=journey_id,
                title=title[:200],
                severity=severity,
                category=category,
                description=description,
                steps_to_reproduce=steps_to_reproduce[:50],
                expected_behavior=expected_behavior[:1000],
                actual_behavior=actual_behavior[:1000],
                page_url=page_url[:1000] if page_url else None,
                confidence=confidence,
                evidence=list(result.evidence),
                generated_by=GenerationMode.RULE_BASED,
            )
            bugs.append(bug)

            ctx.emit(
                EventType.AGENT_PROGRESS,
                AgentName.REPORTER,
                f"Generated bug report for failure in test '{case.title if case else result.test_case_id}': {title}",
                level=EventLevel.INFO,
                data={
                    "test_case_id": result.test_case_id,
                    "bug_title": title,
                    "severity": severity.value,
                    "category": category.value,
                },
            )

        return bugs

    def _determine_page_url(
        self,
        ctx: AgentContext,
        case: TestCase | None,
        journey: Journey | None,
        failed_idx: int,
    ) -> str:
        """Find the most accurate page URL associated with the test failure."""
        if case and case.steps:
            # Look backwards from the failed step for the last NAVIGATE action
            for s in reversed(case.steps[:failed_idx]):
                if s.action == BrowserAction.NAVIGATE and s.url:
                    return s.url

        if journey and journey.start_url:
            return journey.start_url

        return ctx.run.target_url

    def _build_steps_to_reproduce(
        self,
        case: TestCase | None,
        failed_idx: int,
        test_case_id: str,
    ) -> list[str]:
        """Construct reproduction steps stopping at the failed step."""
        if not case or not case.steps:
            return [f"Execute test case '{test_case_id}'"]

        repro_steps: list[str] = []
        for step in case.steps:
            if step.index > failed_idx:
                break

            if step.description:
                action_text = step.description
            elif step.action == BrowserAction.NAVIGATE:
                action_text = f"Navigate to {step.url}"
            elif step.action == BrowserAction.CLICK:
                action_text = f"Click '{step.selector}'"
            elif step.action == BrowserAction.FILL:
                action_text = f"Fill '{step.selector}' with '{step.value}'"
            elif step.action in (BrowserAction.ASSERT_VISIBLE, BrowserAction.ASSERT_TEXT, BrowserAction.ASSERT_URL):
                target = step.selector or step.value or "element"
                action_text = f"Assert {step.action.value} on {target}"
            else:
                action_text = f"Execute action '{step.action.value}'"

            repro_steps.append(f"Step {step.index}: {action_text}"[:200])

        return repro_steps or [f"Execute test case '{test_case_id}'"]

    def _detect_assessment_component(
        self,
        case: TestCase | None,
        combined_text: str,
    ) -> str | None:
        """Identify assessment component context if supported by test case or failure evidence."""
        case_text = f"{case.title if case else ''} {case.description or '' if case else ''}".lower()
        full_text = f"{case_text} {combined_text}".lower()

        # 1. Exam Timer / Countdown
        if any(term in full_text for term in ("timer", "countdown", "time remaining", "exam clock")):
            return "timer"

        # 2. Code Editor
        if any(term in full_text for term in ("code editor", "monaco", "coding challenge", "run code", "code input", "code-editor")) or (
            "editor" in case_text and any(term in full_text for term in ("code", "syntax", "language", "run"))
        ):
            return "code_editor"

        # 3. Question Palette
        if any(term in full_text for term in ("palette", "question grid", "question list button")):
            return "palette"

        # 4. MCQ Option
        if any(term in full_text for term in ("mcq", "option", "radio", "choice", "single-choice", "multiple-choice")):
            return "mcq_option"

        return None

    def _classify_defect(
        self,
        case: TestCase | None,
        failed_action: BrowserAction | None,
        error_message: str,
        actual_behavior: str = "",
        component: str | None = None,
    ) -> tuple[BugCategory, Severity, float]:
        """Classify defect category, severity, and confidence based on action and error heuristics."""
        combined_err = f"{error_message} {actual_behavior}".lower()
        case_text = f"{case.title if case else ''} {case.description or '' if case else ''}".lower()

        # 1. JavaScript Console Errors & Uncaught Script Exceptions
        is_console_error = (
            any(term in combined_err for term in (
                "console error", "uncaught error", "uncaught typeerror", "uncaught referenceerror",
                "uncaught syntaxerror", "javascript error", "typeerror:", "referenceerror:",
                "syntaxerror:", "unhandledrejection", "unhandled promise", "js exception",
            ))
            or ("console" in combined_err and any(w in combined_err for w in ("error", "exception", "failed", "warn")))
        )
        if is_console_error:
            return BugCategory.CONSOLE_ERROR, Severity.HIGH, 0.95

        # 2. Network / Connection / Server Errors
        if any(term in combined_err for term in ("network", "connection", "500", "502", "503", "504", "refused", "timeout", "econnrefused")):
            return BugCategory.NETWORK_ERROR, Severity.HIGH, 0.9

        # 3. Question Palette / Route Failures -> NAVIGATION
        if component == "palette" or any(term in case_text or term in combined_err for term in ("palette", "question grid")):
            sev = Severity.HIGH if any(t in combined_err for t in ("not found", "failed", "error", "route")) else Severity.MEDIUM
            return BugCategory.NAVIGATION, sev, 0.9

        if failed_action in (BrowserAction.NAVIGATE, BrowserAction.ASSERT_URL) or "404" in combined_err or "navigate" in combined_err:
            return BugCategory.NAVIGATION, Severity.HIGH, 0.9

        # 4. Exam Timer / Countdown Failure -> FUNCTIONAL, HIGH
        if component == "timer" or any(term in case_text or term in combined_err for term in ("timer", "countdown", "time remaining", "exam clock")):
            return BugCategory.FUNCTIONAL, Severity.HIGH, 0.9

        # 5. Code Editor Failure -> FUNCTIONAL, HIGH
        if component == "code_editor" or any(term in case_text or term in combined_err for term in ("code editor", "monaco", "coding challenge", "run code", "code input")):
            return BugCategory.FUNCTIONAL, Severity.HIGH, 0.9

        # 6. MCQ Option & Form Validation Errors
        is_mcq_option = component == "mcq_option" or any(term in case_text or term in combined_err for term in ("mcq", "option", "radio", "choice", "single-choice", "multiple-choice"))
        is_form_case = bool(case and any(term in case_text for term in ("form", "login", "signup", "submit")))
        is_form_action = failed_action in (BrowserAction.FILL, BrowserAction.SELECT, BrowserAction.CHECK, BrowserAction.UNCHECK)
        if is_mcq_option or is_form_action or is_form_case or any(term in combined_err for term in ("validation", "invalid", "required")):
            return BugCategory.FORM_VALIDATION, Severity.MEDIUM, 0.85

        # 7. Functional UI / Assertion Mismatch
        if failed_action in (BrowserAction.ASSERT_TEXT, BrowserAction.ASSERT_VISIBLE, BrowserAction.CLICK):
            return BugCategory.FUNCTIONAL, Severity.MEDIUM, 0.85

        # 8. Conservative Fallback
        return BugCategory.FUNCTIONAL, Severity.LOW, 0.7

    def _build_title(
        self,
        case: TestCase | None,
        failed_step_res: StepResult | None,
        test_case_id: str,
        category: BugCategory | None = None,
        component: str | None = None,
    ) -> str:
        """Create a concise, grounded bug title of at least 5 characters."""
        if case and failed_step_res:
            action_str = failed_step_res.action.value
            step_idx = failed_step_res.step_index
            if component == "timer":
                title = f"{case.title}: step {step_idx} failed ({action_str}) - timer display or countdown mismatch"
            elif component == "code_editor":
                title = f"{case.title}: step {step_idx} failed ({action_str}) - code editor interaction failed"
            elif component == "mcq_option":
                title = f"{case.title}: step {step_idx} failed ({action_str}) - option selection failed"
            elif component == "palette":
                title = f"{case.title}: step {step_idx} failed ({action_str}) - question palette navigation failed"
            elif category == BugCategory.CONSOLE_ERROR:
                title = f"{case.title}: step {step_idx} failed ({action_str}) - JavaScript console error"
            else:
                title = f"{case.title}: step {step_idx} failed ({action_str})"
        elif case:
            if category == BugCategory.CONSOLE_ERROR:
                title = f"JavaScript console error in '{case.title}'"
            elif component:
                title = f"Failure in assessment {component} during '{case.title}'"
            else:
                title = f"Test failure in '{case.title}'"
        else:
            title = f"Test case {test_case_id} failed during execution"

        # Ensure title meets Pydantic min_length=5 constraint
        if len(title) < 5:
            title = f"Defect: {title}"
        return title[:200]

    def _build_description(
        self,
        case: TestCase | None,
        failed_step_res: StepResult | None,
        err_msg: str,
        actual_behavior: str,
        component: str | None = None,
        category: BugCategory | None = None,
    ) -> str:
        """Create a truthful description based strictly on recorded outcomes."""
        parts: list[str] = []
        if case:
            parts.append(f"Automated test '{case.title}' failed.")
        else:
            parts.append("Automated test execution failed.")

        if failed_step_res:
            parts.append(f"Failed action was '{failed_step_res.action.value}' at step {failed_step_res.step_index}.")

        if err_msg:
            parts.append(f"Error message: {err_msg.strip()}.")

        if actual_behavior and actual_behavior != err_msg:
            parts.append(f"Observed outcome: {actual_behavior.strip()}.")

        # Grounded assessment impact notes (strictly without assuming backend scoring or persistence bugs)
        if component == "timer":
            parts.append("Assessment impact: The exam countdown or timer element is inaccurate or non-functional, hindering test-taker time awareness.")
        elif component == "code_editor":
            parts.append("Assessment impact: The coding challenge editor failed to accept input or execute as expected, impeding coding challenge completion.")
        elif component == "mcq_option":
            parts.append("Assessment impact: Multiple-choice question option selection or mutual exclusivity did not behave as expected.")
        elif component == "palette":
            parts.append("Assessment impact: Question palette controls failed to transition or reflect question navigation cleanly.")
        elif category == BugCategory.CONSOLE_ERROR:
            parts.append("Assessment impact: An uncaught client-side JavaScript or console error occurred during test execution.")

        return " ".join(parts)
