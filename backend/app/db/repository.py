"""Repository: save and load contract objects. Owner: Member A.

Usage:
    with session_scope() as session:
        repo = Repository(session)
        run = repo.create_run(RunCreate(target_url="http://localhost:5000"))
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.core.constants import (
    SEVERITY_ORDER,
    TERMINAL_STATUSES,
    RunStatus,
    Severity,
    TestStatus,
    can_transition,
)
from app.core.errors import (
    AppError,
    BadRequestError,
    ConflictError,
    DatabaseError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from app.db.models import (
    AgentEventRow,
    BugRow,
    EvidenceRow,
    JourneyRow,
    RunRow,
    StepResultRow,
    TestCaseRow,
    TestResultRow,
    AssessmentMapRow,
    TestSuiteRow,
)
from app.schemas import (
    AgentEvent,
    AssessmentMap,
    BugReport,
    Coverage,
    CoverageCount,
    EvidenceMeta,
    Journey,
    RunCreate,
    RunResponse,
    RunSummary,
    TestCase,
    TestCaseWithResult,
    TestResult,
    TestSuite,
    new_id,
    utc_now,
)


class Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------ helpers

    @contextmanager
    def _write(self) -> Iterator[None]:
        """Run a block, commit at the end, roll back and raise a clear error on failure."""
        try:
            yield
            self.session.commit()
        except AppError:
            self.session.rollback()
            raise
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                "The database rejected this change (duplicate id or a link to a missing record)."
            ) from exc
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise DatabaseError("The database could not save this change.") from exc
        except Exception:
            self.session.rollback()
            raise

    def _require_run(self, run_id: str) -> RunRow:
        row = self.session.get(RunRow, run_id)
        if row is None:
            raise NotFoundError(f"Run '{run_id}' was not found.")
        return row

    def _count(self, model, *conditions) -> int:
        statement = select(func.count()).select_from(model).where(*conditions)
        return self.session.scalar(statement) or 0

    def _summary(self, run_id: str) -> RunSummary:
        return RunSummary(
            journeys_count=self._count(JourneyRow, JourneyRow.run_id == run_id),
            tests_total=self._count(TestCaseRow, TestCaseRow.run_id == run_id),
            tests_passed=self._count(
                TestResultRow,
                TestResultRow.run_id == run_id,
                TestResultRow.status == TestStatus.PASSED.value,
            ),
            tests_failed=self._count(
                TestResultRow,
                TestResultRow.run_id == run_id,
                TestResultRow.status == TestStatus.FAILED.value,
            ),
            bugs_count=self._count(BugRow, BugRow.run_id == run_id),
        )

    def _run_schema(self, row: RunRow) -> RunResponse:
        run = RunResponse.model_validate(row)
        run.summary = self._summary(row.id)
        return run

    # --------------------------------------------------------------------- runs

    def create_run(self, data: RunCreate, run_id: str | None = None) -> RunResponse:
        row = RunRow(
            id=run_id or new_id("run"),
            name=data.name,
            target_url=data.target_url,
            status=RunStatus.PENDING.value,
            agent_mode=data.agent_mode.value,
            mode=getattr(data.mode, "value", data.mode),
            max_pages=data.max_pages,
            max_depth=data.max_depth,
            max_tests=data.max_tests,
            created_at=utc_now(),
        )
        with self._write():
            self.session.add(row)
        return self._run_schema(row)

    def get_run(self, run_id: str) -> RunResponse:
        return self._run_schema(self._require_run(run_id))

    def list_runs(self, limit: int = 50, offset: int = 0) -> list[RunResponse]:
        statement = (
            select(RunRow).order_by(RunRow.created_at.desc(), RunRow.id.desc()).limit(limit).offset(offset)
        )
        return [self._run_schema(row) for row in self.session.scalars(statement)]

    def update_run_status(
        self, run_id: str, new_status: RunStatus, error_message: str | None = None
    ) -> RunResponse:
        new_status = RunStatus(new_status)
        row = self._require_run(run_id)
        current = RunStatus(row.status)
        if not can_transition(current, new_status):
            raise InvalidStatusTransitionError(
                f"A run cannot move from '{current.value}' to '{new_status.value}'."
            )
        with self._write():
            row.status = new_status.value
            if row.started_at is None:
                row.started_at = utc_now()
            if new_status in TERMINAL_STATUSES:
                row.finished_at = utc_now()
            if new_status == RunStatus.FAILED:
                row.error_message = error_message or "The run failed."
        return self._run_schema(row)

    def fail_run(self, run_id: str, message: str) -> RunResponse:
        """Mark a run failed. Does nothing if it already finished."""
        row = self._require_run(run_id)
        if RunStatus(row.status) in TERMINAL_STATUSES:
            return self._run_schema(row)
        return self.update_run_status(run_id, RunStatus.FAILED, message)

    def fail_incomplete_runs(
        self, message: str = "The server stopped before this run finished."
    ) -> int:
        """Call at server start: any unfinished run belongs to a dead process. Returns the count."""
        terminal = [status.value for status in TERMINAL_STATUSES]
        rows = list(self.session.scalars(select(RunRow).where(RunRow.status.not_in(terminal))))
        now = utc_now()
        with self._write():
            for row in rows:
                row.status = RunStatus.FAILED.value
                row.error_message = message
                row.finished_at = now
                if row.started_at is None:
                    row.started_at = now
        return len(rows)

    # ------------------------------------------------------ assessment artifacts

    def save_assessment_map(self, run_id: str, data: AssessmentMap | dict) -> dict:
        """Create or replace the assessment map for a run."""
        self._require_run(run_id)
        assessment_map = self._validate_assessment_map(run_id, data)
        serialized = assessment_map.model_dump(mode="json")

        with self._write():
            row = self.session.get(AssessmentMapRow, run_id)

            if row is None:
                row = AssessmentMapRow(
                    run_id=run_id,
                    data=serialized,
                )
                self.session.add(row)
            else:
                row.data = serialized

        return row.data

    def get_assessment_map(self, run_id: str) -> dict | None:
        """Return the assessment map, or None if not generated yet."""
        self._require_run(run_id)

        row = self.session.get(AssessmentMapRow, run_id)

        return None if row is None else row.data

    def save_test_suite(self, run_id: str, data: TestSuite | dict) -> dict:
        """Create or replace the generated test suite for a run."""
        self._require_run(run_id)
        suite = self._validate_test_suite(run_id, data)
        suite_id = suite.id
        serialized = suite.model_dump(mode="json")

        with self._write():
            row = self.session.scalar(
                select(TestSuiteRow).where(
                    TestSuiteRow.run_id == run_id
                )
            )

            if row is None:
                row = TestSuiteRow(
                    id=suite_id,
                    run_id=run_id,
                    data=serialized,
                )
                self.session.add(row)
            else:
                if row.id != suite_id:
                    raise ConflictError(
                        "A different test suite already exists for this run."
                    )
                row.data = serialized

        return row.data

    def get_coverage(self, run_id: str) -> Coverage | None:
        """Calculate assessment coverage from persisted artifacts and executions."""
        self._require_run(run_id)
        stored_map = self.get_assessment_map(run_id)
        stored_suite = self.get_test_suite(run_id)
        if stored_map is None and stored_suite is None:
            return None

        assessment_map = AssessmentMap.model_validate(stored_map) if stored_map else None
        suite = TestSuite.model_validate(stored_suite) if stored_suite else None
        question_ids = {question.id for question in assessment_map.questions} if assessment_map else set()
        question_by_id = {
            question.id: question for question in assessment_map.questions
        } if assessment_map else {}

        executed_statuses = {
            TestStatus.PASSED.value,
            TestStatus.FAILED.value,
            TestStatus.ERROR.value,
        }
        result_rows = list(
            self.session.scalars(
                select(TestResultRow)
                .where(
                    TestResultRow.run_id == run_id,
                    TestResultRow.status.in_(executed_statuses),
                )
                .options(selectinload(TestResultRow.step_results))
            )
        )
        case_ids = {row.test_case_id for row in result_rows}
        cases = {
            case.id: case
            for case in self.session.scalars(
                select(TestCaseRow).where(TestCaseRow.id.in_(case_ids))
            )
        } if case_ids else {}

        exercised_questions: set[str] = set()
        observed_states: set[tuple[str, str]] = set()
        executed_scenarios: set[str] = set()
        for result in result_rows:
            case = cases.get(result.test_case_id)
            if case is None:
                continue
            if case.scenario is not None:
                executed_scenarios.add(case.scenario)
            for cover in case.covers or []:
                question_id = cover.get("question_id") if isinstance(cover, dict) else None
                if question_id in question_ids:
                    exercised_questions.add(question_id)
            for step in result.step_results:
                observed = step.observed or {}
                question_id = observed.get("question_id")
                if question_id not in question_ids:
                    continue
                exercised_questions.add(question_id)
                state = observed.get("state")
                question = question_by_id[question_id]
                if state is not None and state in {item.value for item in question.observed_states}:
                    observed_states.add((question.type.value, state))

        question_counts = CoverageCount(
            total=len(question_ids),
            exercised=len(exercised_questions),
        )
        questions_by_type = {
            question_type.value: CoverageCount(
                total=sum(question.type.value == question_type.value for question in question_by_id.values()),
                exercised=sum(
                    question.type.value == question_type.value and question.id in exercised_questions
                    for question in question_by_id.values()
                ),
            )
            for question_type in {question.type for question in question_by_id.values()}
        }
        applicable_states = {
            (question.type.value, state.value)
            for question in question_by_id.values()
            for state in question.observed_states
        }
        planned_scenarios = {
            target.scenario.value for target in suite.coverage_targets
        } if suite else set()
        scenario_counts = CoverageCount(
            total=len(planned_scenarios),
            exercised=len(planned_scenarios & executed_scenarios),
        )
        return Coverage(
            questions=question_counts,
            questions_by_type=questions_by_type,
            states=CoverageCount(
                total=len(applicable_states),
                exercised=len(applicable_states & observed_states),
            ),
            scenarios=scenario_counts,
        )

    @staticmethod
    def _validate_assessment_map(run_id: str, data: AssessmentMap | dict) -> AssessmentMap:
        assessment_map = data if isinstance(data, AssessmentMap) else AssessmentMap.model_validate(data)
        if assessment_map.run_id != run_id:
            raise BadRequestError("The assessment map run_id must match the requested run.")
        return assessment_map

    @staticmethod
    def _validate_test_suite(run_id: str, data: TestSuite | dict) -> TestSuite:
        suite = data if isinstance(data, TestSuite) else TestSuite.model_validate(data)
        if suite.run_id != run_id:
            raise BadRequestError("The test suite run_id must match the requested run.")
        return suite

    def get_test_suite(self, run_id: str) -> dict | None:
        """Return the generated test suite, or None if not generated."""
        self._require_run(run_id)

        row = self.session.scalar(
            select(TestSuiteRow).where(
                TestSuiteRow.run_id == run_id
            )
        )

        return None if row is None else row.data
    
    # ---------------------------------------------------------------- journeys

    def add_journey(self, journey: Journey) -> Journey:
        self._require_run(journey.run_id)
        row = JourneyRow(
            id=journey.id,
            run_id=journey.run_id,
            name=journey.name,
            description=journey.description,
            priority=journey.priority,
            start_url=journey.start_url,
            pages=[page.model_dump(mode="json") for page in journey.pages],
            generated_by=journey.generated_by.value,
            created_at=journey.created_at,
        )
        with self._write():
            self.session.add(row)
        return Journey.model_validate(row)

    def list_journeys(self, run_id: str) -> list[Journey]:
        self._require_run(run_id)
        statement = (
            select(JourneyRow)
            .where(JourneyRow.run_id == run_id)
            .order_by(JourneyRow.priority, JourneyRow.created_at, JourneyRow.id)
        )
        return [Journey.model_validate(row) for row in self.session.scalars(statement)]

    # -------------------------------------------------------------- test cases

    def add_test_case(self, test_case: TestCase) -> TestCase:
        self._require_run(test_case.run_id)
        if test_case.journey_id is not None:
            journey = self.session.get(JourneyRow, test_case.journey_id)
            if journey is None or journey.run_id != test_case.run_id:
                raise BadRequestError(
                    f"Journey '{test_case.journey_id}' does not exist in run '{test_case.run_id}'."
                )
        if test_case.suite_id is not None:
            suite = self.session.get(TestSuiteRow, test_case.suite_id)
            if suite is None or suite.run_id != test_case.run_id:
                raise BadRequestError(
                    f"Test suite '{test_case.suite_id}' does not exist in run '{test_case.run_id}'."
                )
        row = TestCaseRow(
            id=test_case.id,
            run_id=test_case.run_id,
            journey_id=test_case.journey_id,
            title=test_case.title,
            description=test_case.description,
            priority=test_case.priority,
            steps=[step.model_dump(mode="json") for step in test_case.steps],
            expected_result=test_case.expected_result,
            generated_by=test_case.generated_by.value,
            created_at=test_case.created_at,
            suite_id=test_case.suite_id,
            scenario=(
                getattr(test_case.scenario, "value", test_case.scenario)
                if test_case.scenario is not None
                else None
            ),
            covers=[cover.model_dump(mode="json") for cover in test_case.covers],
        )
        with self._write():
            self.session.add(row)
        return TestCase.model_validate(row)

    def list_test_cases(self, run_id: str) -> list[TestCase]:
        self._require_run(run_id)
        statement = (
            select(TestCaseRow)
            .where(TestCaseRow.run_id == run_id)
            .order_by(TestCaseRow.priority, TestCaseRow.created_at, TestCaseRow.id)
        )
        return [TestCase.model_validate(row) for row in self.session.scalars(statement)]

    def get_test_case(self, test_case_id: str) -> TestCase:
        row = self.session.get(TestCaseRow, test_case_id)
        if row is None:
            raise NotFoundError(f"Test case '{test_case_id}' was not found.")
        return TestCase.model_validate(row)

    # ---------------------------------------------------------------- evidence

    def _upsert_evidence(self, meta: EvidenceMeta, test_result_id: str | None = None) -> EvidenceRow:
        """Insert the evidence row, or update it if the id already exists."""
        row = self.session.get(EvidenceRow, meta.id)
        if row is None:
            row = EvidenceRow(id=meta.id, run_id=meta.run_id)
            self.session.add(row)
        elif row.run_id != meta.run_id:
            raise BadRequestError(f"Evidence '{meta.id}' already belongs to a different run.")
        row.test_case_id = meta.test_case_id
        row.step_index = meta.step_index
        row.kind = meta.kind.value
        row.path = meta.path
        row.mime_type = meta.mime_type
        row.width = meta.width
        row.height = meta.height
        row.size_bytes = meta.size_bytes
        row.caption = meta.caption
        row.created_at = meta.created_at
        if test_result_id is not None:  # never erase an existing link
            row.test_result_id = test_result_id
        return row

    def save_evidence(self, meta: EvidenceMeta) -> EvidenceMeta:
        self._require_run(meta.run_id)
        with self._write():
            row = self._upsert_evidence(meta)
        return EvidenceMeta.model_validate(row)

    def get_evidence(self, evidence_id: str) -> EvidenceMeta:
        row = self.session.get(EvidenceRow, evidence_id)
        if row is None:
            raise NotFoundError(f"Evidence '{evidence_id}' was not found.")
        return EvidenceMeta.model_validate(row)

    def list_evidence(self, run_id: str) -> list[EvidenceMeta]:
        self._require_run(run_id)
        statement = (
            select(EvidenceRow)
            .where(EvidenceRow.run_id == run_id)
            .order_by(EvidenceRow.created_at, EvidenceRow.id)
        )
        return [EvidenceMeta.model_validate(row) for row in self.session.scalars(statement)]

    # ------------------------------------------------------------ test results

    def save_test_result(self, result: TestResult) -> TestResult:
        self._require_run(result.run_id)
        case = self.session.get(TestCaseRow, result.test_case_id)
        if case is None or case.run_id != result.run_id:
            raise NotFoundError(
                f"Test case '{result.test_case_id}' was not found in run '{result.run_id}'."
            )
        already = self.session.scalar(
            select(TestResultRow.id).where(TestResultRow.test_case_id == result.test_case_id)
        )
        if already is not None:
            raise ConflictError(f"Test case '{result.test_case_id}' already has a result.")
        for meta in result.evidence:
            if meta.run_id != result.run_id:
                raise BadRequestError(f"Evidence '{meta.id}' belongs to a different run.")

        row = TestResultRow(
            id=result.id,
            run_id=result.run_id,
            test_case_id=result.test_case_id,
            status=result.status.value,
            started_at=result.started_at,
            finished_at=result.finished_at,
            duration_ms=result.duration_ms,
            error_message=result.error_message,
            generated_by=result.generated_by.value,
        )
        row.step_results = [
            StepResultRow(
                step_index=step.step_index,
                action=step.action.value,
                status=step.status.value,
                duration_ms=step.duration_ms,
                error_message=step.error_message,
                actual=step.actual,
                observed=(
                    step.observed.model_dump(mode="json")
                    if step.observed is not None
                    else None
                ),
                evidence_id=step.evidence_id,
            )
            for step in result.step_results
        ]
        with self._write():
            self.session.add(row)
            self.session.flush()  # the result must exist before evidence points at it
            for meta in result.evidence:
                self._upsert_evidence(meta, test_result_id=result.id)
        return self._result_schema(result.id)

    def _result_schema(self, result_id: str) -> TestResult:
        statement = (
            select(TestResultRow)
            .where(TestResultRow.id == result_id)
            .options(selectinload(TestResultRow.step_results), selectinload(TestResultRow.evidence))
        )
        row = self.session.scalars(statement).one()
        return TestResult.model_validate(row)

    def get_test_result_for_case(self, test_case_id: str) -> TestResult | None:
        result_id = self.session.scalar(
            select(TestResultRow.id).where(TestResultRow.test_case_id == test_case_id)
        )
        return None if result_id is None else self._result_schema(result_id)

    def list_tests_with_results(self, run_id: str) -> list[TestCaseWithResult]:
        """What GET /api/runs/{id}/tests returns: every test case, with its result or null."""
        cases = self.list_test_cases(run_id)
        statement = (
            select(TestResultRow)
            .where(TestResultRow.run_id == run_id)
            .options(selectinload(TestResultRow.step_results), selectinload(TestResultRow.evidence))
        )
        results = {row.test_case_id: TestResult.model_validate(row) for row in self.session.scalars(statement)}
        return [TestCaseWithResult(test_case=case, result=results.get(case.id)) for case in cases]

    # -------------------------------------------------------------------- bugs

    def add_bug_report(self, bug: BugReport) -> BugReport:
        self._require_run(bug.run_id)
        for meta in bug.evidence:
            if meta.run_id != bug.run_id:
                raise BadRequestError(f"Evidence '{meta.id}' belongs to a different run.")
        row = BugRow(
            id=bug.id,
            run_id=bug.run_id,
            test_case_id=bug.test_case_id,
            journey_id=bug.journey_id,
            title=bug.title,
            severity=bug.severity.value,
            category=bug.category.value,
            description=bug.description,
            steps_to_reproduce=list(bug.steps_to_reproduce),
            expected_behavior=bug.expected_behavior,
            actual_behavior=bug.actual_behavior,
            page_url=bug.page_url,
            confidence=bug.confidence,
            generated_by=bug.generated_by.value,
            created_at=bug.created_at,
            assessment_context=(
            bug.assessment_context.model_dump(mode="json")
               if hasattr(bug.assessment_context, "model_dump")
               else bug.assessment_context
),
reproducibility=(
    getattr(bug.reproducibility, "value", bug.reproducibility)
    if bug.reproducibility is not None
    else None
),
        )
        with self._write():
            self.session.add(row)
            self.session.flush()
            evidence_rows = [self._upsert_evidence(meta) for meta in bug.evidence]
            self.session.flush()
            row.evidence = evidence_rows
        return self.get_bug_report(bug.id)

    def get_bug_report(self, bug_id: str) -> BugReport:
        statement = select(BugRow).where(BugRow.id == bug_id).options(selectinload(BugRow.evidence))
        row = self.session.scalars(statement).one_or_none()
        if row is None:
            raise NotFoundError(f"Bug report '{bug_id}' was not found.")
        return BugReport.model_validate(row)

    def list_bug_reports(self, run_id: str) -> list[BugReport]:
        """Most severe first, then oldest first."""
        self._require_run(run_id)
        statement = (
            select(BugRow).where(BugRow.run_id == run_id).options(selectinload(BugRow.evidence))
        )
        bugs = [BugReport.model_validate(row) for row in self.session.scalars(statement)]
        bugs.sort(key=lambda bug: (SEVERITY_ORDER.index(Severity(bug.severity)), bug.created_at, bug.id))
        return bugs

    # ------------------------------------------------------------------ events

    def add_event(self, event: AgentEvent) -> AgentEvent:
        """Save an event. The backend assigns `seq` (0, 1, 2, ... per run); the input seq is ignored."""
        self._require_run(event.run_id)
        highest = self.session.scalar(
            select(func.max(AgentEventRow.seq)).where(AgentEventRow.run_id == event.run_id)
        )
        row = AgentEventRow(
            id=event.id,
            run_id=event.run_id,
            seq=0 if highest is None else highest + 1,
            type=event.type.value,
            agent=event.agent.value,
            level=event.level.value,
            message=event.message,
            data=event.model_dump(mode="json")["data"],
            timestamp=event.timestamp,
        )
        with self._write():
            self.session.add(row)
        return AgentEvent.model_validate(row)

    def list_events(self, run_id: str, after_seq: int = -1, limit: int = 1000) -> list[AgentEvent]:
        """Events with seq greater than `after_seq`, oldest first. Used by SSE to resume."""
        self._require_run(run_id)
        statement = (
            select(AgentEventRow)
            .where(AgentEventRow.run_id == run_id, AgentEventRow.seq > after_seq)
            .order_by(AgentEventRow.seq)
            .limit(limit)
        )
        return [AgentEvent.model_validate(row) for row in self.session.scalars(statement)]
