"""Database tests. Owner: Member A."""

from datetime import timedelta

import pytest
from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.core.constants import AgentName, EventType, RunStatus, Severity, TestStatus
from app.core.errors import (
    BadRequestError,
    ConflictError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from app.db import Repository, get_engine, init_db, reset_db_caches
from app.schemas import (
    AgentEvent,
    BugReport,
    EvidenceMeta,
    Journey,
    RunCreate,
    RunResponse,
    TestCase,
    TestResult,
)

RUN_ID = "run_7f3a9c21b4d8"


def new_run(repo: Repository, run_id: str | None = None):
    return repo.create_run(RunCreate(target_url="http://localhost:5000"), run_id=run_id)


def simple_case(run_id: str, **extra) -> TestCase:
    return TestCase(
        run_id=run_id,
        title="Simple test",
        expected_result="Works",
        steps=[{"index": 1, "action": "screenshot"}],
        **extra,
    )


def simple_bug(run_id: str, severity: str, title: str) -> BugReport:
    return BugReport(
        run_id=run_id,
        title=title,
        severity=severity,
        category="functional",
        description="Something is wrong.",
        steps_to_reproduce=["Open the page"],
        expected_behavior="It works",
        actual_behavior="It does not",
    )


def simple_event(run_id: str, message: str = "hello") -> AgentEvent:
    return AgentEvent(
        run_id=run_id,
        type=EventType.AGENT_PROGRESS,
        agent=AgentName.EXPLORER,
        message=message,
    )


# ------------------------------------------------------------- engine and tables


def test_all_tables_are_created(engine):
    names = set(inspect(engine).get_table_names())
    assert names >= {
        "runs", "journeys", "test_cases", "test_results", "step_results",
        "evidence", "bug_reports", "bug_evidence", "agent_events",
    }


def test_foreign_keys_are_switched_on(engine):
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_default_engine_uses_configured_database_url(tmp_path, monkeypatch):
    db_file = tmp_path / "nested" / "app.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EVIDENCE_DIR", str(tmp_path / "data" / "evidence"))
    get_settings.cache_clear()
    reset_db_caches()
    try:
        init_db()
        assert db_file.exists()
        assert str(get_engine().url).endswith("app.db")
    finally:
        reset_db_caches()
        get_settings.cache_clear()


# ------------------------------------------------------------------------- runs


def test_create_and_get_run(repo):
    run = new_run(repo)
    assert run.status == RunStatus.PENDING
    assert run.id.startswith("run_")
    assert repo.get_run(run.id) == run
    assert run.summary.bugs_count == 0


def test_datetimes_come_back_timezone_aware_utc(repo):
    run = repo.get_run(new_run(repo).id)
    assert run.created_at.tzinfo is not None
    assert run.created_at.utcoffset() == timedelta(0)


def test_unknown_run_raises_not_found(repo):
    with pytest.raises(NotFoundError):
        repo.get_run("run_missing")
    with pytest.raises(NotFoundError):
        repo.list_journeys("run_missing")
    with pytest.raises(NotFoundError):
        repo.list_events("run_missing")
    with pytest.raises(NotFoundError):
        repo.update_run_status("run_missing", RunStatus.EXPLORING)


def test_duplicate_run_id_is_a_conflict(repo):
    new_run(repo, "run_same")
    with pytest.raises(ConflictError):
        new_run(repo, "run_same")


def test_list_runs_newest_first(repo):
    first = new_run(repo)
    second = new_run(repo)
    ids = [run.id for run in repo.list_runs()]
    assert ids.index(second.id) < ids.index(first.id)
    assert len(repo.list_runs(limit=1)) == 1


# --------------------------------------------------------------- status changes


def test_full_status_path_sets_times(repo):
    run = new_run(repo)
    assert run.started_at is None

    for status in (RunStatus.EXPLORING, RunStatus.TESTING, RunStatus.REPORTING):
        run = repo.update_run_status(run.id, status)
        assert run.status == status
        assert run.started_at is not None
        assert run.finished_at is None

    run = repo.update_run_status(run.id, RunStatus.COMPLETED)
    assert run.status == RunStatus.COMPLETED
    assert run.finished_at is not None
    assert run.error_message is None


def test_failed_status_stores_message(repo):
    run = new_run(repo)
    run = repo.update_run_status(run.id, RunStatus.EXPLORING)
    run = repo.update_run_status(run.id, RunStatus.FAILED, "browser crashed")
    assert run.status == RunStatus.FAILED
    assert run.error_message == "browser crashed"
    assert run.finished_at is not None


def test_invalid_transitions_are_rejected(repo):
    run = new_run(repo)
    with pytest.raises(InvalidStatusTransitionError):
        repo.update_run_status(run.id, RunStatus.COMPLETED)
    assert repo.get_run(run.id).status == RunStatus.PENDING

    for status in (RunStatus.EXPLORING, RunStatus.TESTING, RunStatus.REPORTING, RunStatus.COMPLETED):
        repo.update_run_status(run.id, status)
    with pytest.raises(InvalidStatusTransitionError):
        repo.update_run_status(run.id, RunStatus.EXPLORING)


def test_fail_run_ignores_finished_runs(repo):
    run = new_run(repo)
    failed = repo.fail_run(run.id, "boom")
    assert failed.status == RunStatus.FAILED
    again = repo.fail_run(run.id, "second message")
    assert again.error_message == "boom"


def test_fail_incomplete_runs_cleans_up_stuck_runs(repo):
    pending = new_run(repo)
    exploring = new_run(repo)
    repo.update_run_status(exploring.id, RunStatus.EXPLORING)
    done = new_run(repo)
    for status in (RunStatus.EXPLORING, RunStatus.TESTING, RunStatus.REPORTING, RunStatus.COMPLETED):
        repo.update_run_status(done.id, status)

    assert repo.fail_incomplete_runs() == 2

    assert repo.get_run(pending.id).status == RunStatus.FAILED
    stuck = repo.get_run(exploring.id)
    assert stuck.status == RunStatus.FAILED
    assert stuck.finished_at is not None
    assert stuck.error_message
    assert repo.get_run(done.id).status == RunStatus.COMPLETED
    assert repo.fail_incomplete_runs() == 0


# ------------------------------------------- contract examples saved and loaded


def test_contract_examples_round_trip(repo, load_contract):
    run = repo.create_run(RunCreate.model_validate(load_contract("run_create.json")), run_id=RUN_ID)
    assert run.id == RUN_ID

    journey = Journey.model_validate(load_contract("journey.json"))
    case = TestCase.model_validate(load_contract("test_case.json"))
    result = TestResult.model_validate(load_contract("test_result.json"))
    bug = BugReport.model_validate(load_contract("bug_report.json"))
    event = AgentEvent.model_validate(load_contract("agent_event.json"))

    assert repo.add_journey(journey) == journey
    assert repo.add_test_case(case) == case
    assert repo.save_test_result(result) == result
    assert repo.add_bug_report(bug) == bug

    saved_event = repo.add_event(event)
    assert saved_event.seq == 0  # the backend decides seq
    assert saved_event.model_copy(update={"seq": event.seq}) == event

    # Reading back gives the same objects.
    assert repo.list_journeys(RUN_ID) == [journey]
    assert repo.list_test_cases(RUN_ID) == [case]
    assert repo.get_test_result_for_case(case.id) == result
    assert repo.list_bug_reports(RUN_ID) == [bug]
    assert repo.get_bug_report(bug.id) == bug

    # The screenshot is stored once, and the result still owns it after the bug was saved.
    evidence = EvidenceMeta.model_validate(load_contract("evidence.json"))
    assert repo.list_evidence(RUN_ID) == [evidence]
    assert repo.get_evidence(evidence.id) == evidence
    assert repo.get_test_result_for_case(case.id).evidence == [evidence]

    # The summary computed from the rows matches the JSON example.
    expected = RunResponse.model_validate(load_contract("run_response.json")).summary
    assert repo.get_run(RUN_ID).summary == expected


# ------------------------------------------------------------------ test cases


def test_test_case_with_unknown_journey_is_rejected(repo):
    run = new_run(repo)
    with pytest.raises(BadRequestError):
        repo.add_test_case(simple_case(run.id, journey_id="jny_missing"))


def test_get_unknown_test_case(repo):
    with pytest.raises(NotFoundError):
        repo.get_test_case("tc_missing")


def test_tests_with_results_lists_unrun_tests_with_null_result(repo):
    run = new_run(repo)
    case = repo.add_test_case(simple_case(run.id))

    items = repo.list_tests_with_results(run.id)
    assert len(items) == 1
    assert items[0].test_case == case
    assert items[0].result is None

    repo.save_test_result(TestResult(run_id=run.id, test_case_id=case.id, status=TestStatus.PASSED))
    items = repo.list_tests_with_results(run.id)
    assert items[0].result is not None
    assert items[0].result.status == TestStatus.PASSED
    assert repo.get_run(run.id).summary.tests_passed == 1


# ----------------------------------------------------------------- test results


def test_result_for_unknown_test_case_is_not_found(repo):
    run = new_run(repo)
    with pytest.raises(NotFoundError):
        repo.save_test_result(TestResult(run_id=run.id, test_case_id="tc_missing", status=TestStatus.PASSED))


def test_second_result_for_same_test_case_is_a_conflict(repo):
    run = new_run(repo)
    case = repo.add_test_case(simple_case(run.id))
    repo.save_test_result(TestResult(run_id=run.id, test_case_id=case.id, status=TestStatus.PASSED))
    with pytest.raises(ConflictError):
        repo.save_test_result(TestResult(run_id=run.id, test_case_id=case.id, status=TestStatus.FAILED))


def test_result_with_evidence_from_another_run_is_rejected(repo):
    run_a = new_run(repo)
    run_b = new_run(repo)
    case = repo.add_test_case(simple_case(run_a.id))
    foreign = EvidenceMeta(run_id=run_b.id, path=f"{run_b.id}/shot.png")
    result = TestResult(
        run_id=run_a.id, test_case_id=case.id, status=TestStatus.FAILED, evidence=[foreign]
    )
    with pytest.raises(BadRequestError):
        repo.save_test_result(result)
    assert repo.get_test_result_for_case(case.id) is None  # nothing half-saved


def test_failed_result_counts_in_summary(repo):
    run = new_run(repo)
    case = repo.add_test_case(simple_case(run.id))
    repo.save_test_result(TestResult(run_id=run.id, test_case_id=case.id, status=TestStatus.FAILED))
    summary = repo.get_run(run.id).summary
    assert (summary.tests_total, summary.tests_passed, summary.tests_failed) == (1, 0, 1)


# ------------------------------------------------------------------------- bugs


def test_bugs_are_listed_most_severe_first(repo):
    run = new_run(repo)
    repo.add_bug_report(simple_bug(run.id, Severity.LOW, "A low severity bug"))
    repo.add_bug_report(simple_bug(run.id, Severity.CRITICAL, "A critical bug here"))
    repo.add_bug_report(simple_bug(run.id, Severity.HIGH, "A high severity bug"))
    severities = [bug.severity for bug in repo.list_bug_reports(run.id)]
    assert severities == [Severity.CRITICAL, Severity.HIGH, Severity.LOW]
    assert repo.get_run(run.id).summary.bugs_count == 3


def test_unknown_bug_is_not_found(repo):
    with pytest.raises(NotFoundError):
        repo.get_bug_report("bug_missing")


def test_bug_for_unknown_run_is_not_found(repo):
    with pytest.raises(NotFoundError):
        repo.add_bug_report(simple_bug("run_missing", Severity.LOW, "Orphan bug report"))


# ----------------------------------------------------------------------- events


def test_event_seq_counts_up_per_run(repo):
    run_a = new_run(repo)
    run_b = new_run(repo)
    seqs_a = [repo.add_event(simple_event(run_a.id, f"m{i}")).seq for i in range(3)]
    seqs_b = [repo.add_event(simple_event(run_b.id)).seq]
    assert seqs_a == [0, 1, 2]
    assert seqs_b == [0]


def test_list_events_after_seq(repo):
    run = new_run(repo)
    for i in range(4):
        repo.add_event(simple_event(run.id, f"m{i}"))
    assert [e.seq for e in repo.list_events(run.id)] == [0, 1, 2, 3]
    assert [e.seq for e in repo.list_events(run.id, after_seq=1)] == [2, 3]
    assert repo.list_events(run.id, after_seq=3) == []
    assert len(repo.list_events(run.id, limit=2)) == 2


def test_event_data_is_saved_as_json(repo):
    run = new_run(repo)
    event = simple_event(run.id)
    event.data = {"bug_id": "bug_1", "count": 3}
    saved = repo.add_event(event)
    assert repo.list_events(run.id)[0].data == {"bug_id": "bug_1", "count": 3}
    assert saved.data == {"bug_id": "bug_1", "count": 3}