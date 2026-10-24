"""Test cases (what to do), step results, and test results (what happened)."""

from datetime import datetime

from pydantic import Field, model_validator

from app.core.constants import BrowserAction, GenerationMode, QuestionState, ScenarioTag, TestStatus
from app.schemas.common import ContractModel, EvidenceMeta, new_id, utc_now, validate_http_url

_NEEDS_SELECTOR = frozenset({
    BrowserAction.CLICK, BrowserAction.FILL, BrowserAction.SELECT, BrowserAction.CHECK,
    BrowserAction.UNCHECK, BrowserAction.HOVER, BrowserAction.ASSERT_VISIBLE,
    BrowserAction.ASSERT_TEXT, BrowserAction.SUBMIT, BrowserAction.TYPE_CODE,
    BrowserAction.RUN_CODE, BrowserAction.ASSERT_STATE, BrowserAction.ASSERT_VALUE,
})
_NEEDS_VALUE = frozenset({
    BrowserAction.FILL, BrowserAction.SELECT, BrowserAction.PRESS, BrowserAction.ASSERT_TEXT,
    BrowserAction.ASSERT_URL, BrowserAction.TYPE_CODE, BrowserAction.ASSERT_STATE,
    BrowserAction.ASSERT_VALUE,
})


class TestStep(ContractModel):
    """One browser action. Steps are numbered from 1.

    Required fields per action:
      navigate -> url
      click, hover, check, uncheck, assert_visible, submit, run_code -> selector
      fill, select, assert_text, type_code, assert_state, assert_value -> selector + value
      press -> value (key name, e.g. "Enter")
      assert_url -> value (text the URL must contain)
      wait, wait_timer -> value optional (milliseconds / seconds)
      screenshot -> nothing
    question_ref (optional) names the question the step works on, e.g. "q2".
    """

    __test__ = False  # not a pytest test class

    index: int = Field(ge=1)
    action: BrowserAction
    selector: str | None = Field(default=None, max_length=500)
    value: str | None = Field(default=None, max_length=2000)
    url: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=500)
    question_ref: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _check_required_fields(self) -> "TestStep":
        if self.action == BrowserAction.NAVIGATE:
            if not self.url:
                raise ValueError("navigate step needs 'url'")
            validate_http_url(self.url)
        if self.action in _NEEDS_SELECTOR and not self.selector:
            raise ValueError(f"'{self.action.value}' step needs 'selector'")
        if self.action in _NEEDS_VALUE and self.value is None:
            raise ValueError(f"'{self.action.value}' step needs 'value'")
        return self


class CaseCover(ContractModel):
    """One question (and optionally one state) that a test case is meant to cover."""

    question_id: str = Field(min_length=1, max_length=64)
    state: QuestionState | None = None


class TestCase(ContractModel):
    __test__ = False  # not a pytest test class

    id: str = Field(default_factory=lambda: new_id("tc"), min_length=1, max_length=64)
    run_id: str = Field(min_length=1, max_length=64)
    journey_id: str | None = Field(default=None, max_length=64)
    suite_id: str | None = Field(default=None, max_length=64)
    scenario: ScenarioTag | None = None
    covers: list[CaseCover] = Field(default_factory=list)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: int = Field(default=3, ge=1, le=5)
    steps: list[TestStep] = Field(min_length=1, max_length=50)
    expected_result: str = Field(min_length=1, max_length=1000)
    generated_by: GenerationMode = GenerationMode.MOCK
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _steps_are_numbered_in_order(self) -> "TestCase":
        for position, step in enumerate(self.steps, start=1):
            if step.index != position:
                raise ValueError(
                    f"step at position {position} has index {step.index}; indexes must be 1, 2, 3, ..."
                )
        return self


class StepObservation(ContractModel):
    """What the Tester saw on the page after a step. Feeds the coverage numbers."""

    question_id: str | None = Field(default=None, max_length=64)
    state: QuestionState | None = None
    timer_text: str | None = Field(default=None, max_length=30)


class StepResult(ContractModel):
    step_index: int = Field(ge=1)
    action: BrowserAction
    status: TestStatus
    duration_ms: int = Field(default=0, ge=0)
    error_message: str | None = None
    actual: str | None = Field(default=None, description="What really happened, in words.")
    evidence_id: str | None = Field(default=None, max_length=64)
    observed: StepObservation | None = None


class TestResult(ContractModel):
    __test__ = False  # not a pytest test class

    id: str = Field(default_factory=lambda: new_id("tr"), min_length=1, max_length=64)
    run_id: str = Field(min_length=1, max_length=64)
    test_case_id: str = Field(min_length=1, max_length=64)
    status: TestStatus
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    duration_ms: int = Field(default=0, ge=0)
    error_message: str | None = None
    step_results: list[StepResult] = Field(default_factory=list)
    evidence: list[EvidenceMeta] = Field(default_factory=list)
    generated_by: GenerationMode = GenerationMode.MOCK

    @model_validator(mode="after")
    def _consistency(self) -> "TestResult":
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("finished_at cannot be earlier than started_at")
        known = {e.id for e in self.evidence}
        for step in self.step_results:
            if step.evidence_id is not None and step.evidence_id not in known:
                raise ValueError(
                    f"step {step.step_index} refers to evidence '{step.evidence_id}' "
                    "which is not in 'evidence'"
                )
        return self


class TestCaseWithResult(ContractModel):
    """Item returned by GET /api/runs/{id}/tests. `result` is null until the test has run."""

    __test__ = False  # not a pytest test class

    test_case: TestCase
    result: TestResult | None = None