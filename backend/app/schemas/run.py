"""A QA run: the request to start one and the response describing it."""

from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from app.core.constants import AgentMode, RunMode, RunStatus
from app.schemas.assessment import AssessmentMap
from app.schemas.common import ContractModel, new_id, utc_now, validate_http_url
from app.schemas.testsuite import Coverage, TestSuite


class RunCreate(ContractModel):
    """Body of POST /api/runs. Unknown fields are rejected so typos are caught."""

    model_config = ConfigDict(extra="forbid")

    target_url: str = Field(description="Address of the web app to test.")
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    mode: RunMode = RunMode.ASSESSMENT
    max_pages: int = Field(default=10, ge=1, le=50)
    max_depth: int = Field(default=2, ge=1, le=5)
    max_tests: int = Field(default=20, ge=1, le=100)
    agent_mode: AgentMode = AgentMode.MOCK

    @field_validator("target_url")
    @classmethod
    def _url_ok(cls, value: str) -> str:
        return validate_http_url(value)


class RunSummary(ContractModel):
    """Counts. The database layer computes these; agents never set them."""

    journeys_count: int = Field(default=0, ge=0)
    tests_total: int = Field(default=0, ge=0)
    tests_passed: int = Field(default=0, ge=0)
    tests_failed: int = Field(default=0, ge=0)
    bugs_count: int = Field(default=0, ge=0)


class RunResponse(ContractModel):
    """What the API returns for a run in lists and after POST."""

    id: str = Field(default_factory=lambda: new_id("run"), min_length=1, max_length=64)
    name: str | None = None
    description: str | None = None
    target_url: str
    mode: RunMode = RunMode.ASSESSMENT
    status: RunStatus = RunStatus.PENDING
    agent_mode: AgentMode = AgentMode.MOCK
    max_pages: int = Field(default=10, ge=1, le=50)
    max_depth: int = Field(default=2, ge=1, le=5)
    max_tests: int = Field(default=20, ge=1, le=100)
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    summary: RunSummary = Field(default_factory=RunSummary)


class RunDetail(RunResponse):
    """GET /api/runs/{id}: the run plus what the agents learned. Extras are null until they exist."""

    assessment_map: AssessmentMap | None = None
    suite: TestSuite | None = None
    coverage: Coverage | None = None