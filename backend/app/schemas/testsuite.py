"""The generated test suite and the derived coverage numbers (contract v1.1). Owner: Member A."""

from datetime import datetime

from pydantic import Field, model_validator

from app.core.constants import QuestionType, ScenarioTag, SuiteSource
from app.schemas.common import ContractModel, new_id, utc_now


class CoverageTarget(ContractModel):
    """What one planned test is meant to cover: a question or a whole question type."""

    question_id: str | None = Field(default=None, max_length=64)
    question_type: QuestionType | None = None
    scenario: ScenarioTag

    @model_validator(mode="after")
    def _needs_a_target(self) -> "CoverageTarget":
        if self.question_id is None and self.question_type is None:
            raise ValueError("a coverage target needs question_id or question_type")
        return self


class SuiteGenerator(ContractModel):
    provider: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=100)


class SuiteValidation(ContractModel):
    status: str = Field(default="valid", max_length=20)
    repaired: bool = False
    dropped_cases: int = Field(default=0, ge=0)


class TestSuite(ContractModel):
    __test__ = False  # not a pytest class

    id: str = Field(default_factory=lambda: new_id("ts"), min_length=1, max_length=64)
    run_id: str = Field(min_length=1, max_length=64)
    source: SuiteSource = SuiteSource.LLM
    generated_by: SuiteGenerator | None = None
    prompt_version: str | None = Field(default=None, max_length=40)
    coverage_targets: list[CoverageTarget] = Field(default_factory=list)
    test_case_ids: list[str] = Field(default_factory=list)
    validation: SuiteValidation = Field(default_factory=SuiteValidation)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _llm_suites_name_their_model(self) -> "TestSuite":
        if self.source == SuiteSource.LLM and self.generated_by is None:
            raise ValueError("a suite with source 'llm' must say which provider and model made it")
        return self


class CoverageCount(ContractModel):
    total: int = Field(ge=0)
    exercised: int = Field(ge=0)

    @model_validator(mode="after")
    def _exercised_within_total(self) -> "CoverageCount":
        if self.exercised > self.total:
            raise ValueError("exercised cannot be larger than total")
        return self


class Coverage(ContractModel):
    """Derived by the backend from the map and the results. Never stored, never set by agents."""

    questions: CoverageCount
    questions_by_type: dict[QuestionType, CoverageCount] = Field(default_factory=dict)
    states: CoverageCount       # (question type x QuestionState) pairs: possible vs observed
    scenarios: CoverageCount    # ScenarioTags defined vs executed