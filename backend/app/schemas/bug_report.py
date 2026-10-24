"""A bug report written by the Reporter agent."""

from datetime import datetime

from pydantic import Field

from app.core.constants import (
    BugCategory,
    GenerationMode,
    LifecycleStage,
    QuestionState,
    QuestionType,
    Severity,
)
from app.schemas.common import ContractModel, EvidenceMeta, new_id, utc_now


class AssessmentContext(ContractModel):
    """Where in the assessment the bug happened. Every field is optional."""

    section_id: str | None = Field(default=None, max_length=64)
    question_id: str | None = Field(default=None, max_length=64)
    question_type: QuestionType | None = None
    state: QuestionState | None = None
    lifecycle_stage: LifecycleStage | None = None


class BugReport(ContractModel):
    id: str = Field(default_factory=lambda: new_id("bug"), min_length=1, max_length=64)
    run_id: str = Field(min_length=1, max_length=64)
    test_case_id: str | None = Field(default=None, max_length=64)
    journey_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=5, max_length=200)
    severity: Severity
    category: BugCategory
    description: str = Field(min_length=1)
    steps_to_reproduce: list[str] = Field(min_length=1, max_length=50)
    expected_behavior: str = Field(min_length=1)
    actual_behavior: str = Field(min_length=1)
    page_url: str | None = Field(default=None, max_length=1000)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    assessment_context: AssessmentContext | None = None
    reproducibility: str | None = Field(
        default=None, pattern=r"^\d+/\d+$", description='Replay result such as "2/2".'
    )
    evidence: list[EvidenceMeta] = Field(default_factory=list)
    generated_by: GenerationMode = GenerationMode.MOCK
    created_at: datetime = Field(default_factory=utc_now)