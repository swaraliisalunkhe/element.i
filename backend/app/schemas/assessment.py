"""What the Explorer learns about an online assessment (contract v1.1). Owner: Member A."""

from pydantic import Field, model_validator

from app.core.constants import LifecycleStage, QuestionState, QuestionType
from app.schemas.common import ContractModel


class AssessmentInfo(ContractModel):
    title: str = Field(min_length=1, max_length=200)
    duration_seconds: int | None = Field(default=None, ge=1)
    instructions_found: bool = False


class SectionInfo(ContractModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    question_ids: list[str] = Field(default_factory=list)


class QuestionInfo(ContractModel):
    id: str = Field(min_length=1, max_length=64)
    section_id: str = Field(min_length=1, max_length=64)
    index: int = Field(ge=1, description="Position in the assessment, starting at 1.")
    type: QuestionType
    selectors: dict[str, str] = Field(
        default_factory=dict, description="Named CSS selectors, e.g. {'palette': '#palette-q1'}."
    )
    options_count: int | None = Field(default=None, ge=0)
    languages: list[str] = Field(default_factory=list)
    observed_states: list[QuestionState] = Field(default_factory=list)


class NavigationInfo(ContractModel):
    next: str | None = None
    prev: str | None = None
    skip: str | None = None
    mark: str | None = None
    palette: str | None = None


class TimerInfo(ContractModel):
    selector: str | None = None
    scope: str = Field(default="assessment", max_length=30)
    initial_text: str | None = Field(default=None, max_length=30)
    ticking: bool | None = None


class SubmissionInfo(ContractModel):
    review_url: str | None = None
    submit_selector: str | None = None
    confirm_selector: str | None = None


class ResultInfo(ContractModel):
    url: str | None = None
    score_selector: str | None = None
    row_selector: str | None = None


class AssessmentMap(ContractModel):
    """The Explorer's only hand-over about the target. Later agents need nothing else."""

    run_id: str = Field(min_length=1, max_length=64)
    assessment: AssessmentInfo
    sections: list[SectionInfo] = Field(min_length=1)
    questions: list[QuestionInfo] = Field(min_length=1)
    navigation: NavigationInfo = Field(default_factory=NavigationInfo)
    timer: TimerInfo | None = None
    submission: SubmissionInfo = Field(default_factory=SubmissionInfo)
    result: ResultInfo = Field(default_factory=ResultInfo)
    lifecycle_found: list[LifecycleStage] = Field(default_factory=list)

    @model_validator(mode="after")
    def _links_are_consistent(self) -> "AssessmentMap":
        question_ids = [q.id for q in self.questions]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("question ids must be unique")
        section_ids = [s.id for s in self.sections]
        if len(set(section_ids)) != len(section_ids):
            raise ValueError("section ids must be unique")
        for question in self.questions:
            if question.section_id not in section_ids:
                raise ValueError(
                    f"question '{question.id}' refers to unknown section '{question.section_id}'"
                )
        for section in self.sections:
            for question_id in section.question_ids:
                if question_id not in question_ids:
                    raise ValueError(f"section '{section.id}' lists unknown question '{question_id}'")
        return self