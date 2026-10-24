"""Focused repository tests for assessment artifacts and coverage."""

import pytest

from app.core.constants import Severity, TestStatus
from app.core.errors import BadRequestError, ConflictError
from app.db.repository import Repository
from app.schemas import (
    AssessmentMap,
    BugReport,
    EvidenceMeta,
    RunCreate,
    TestCase,
    TestResult,
    TestSuite,
)


def make_run(repo: Repository, run_id: str = "run_assessment"):
    return repo.create_run(
        RunCreate(target_url="http://localhost:8001"),
        run_id=run_id,
    )


def map_payload(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "assessment": {"title": "Assessment", "duration_seconds": 300},
        "sections": [{"id": "s1", "title": "Section 1", "question_ids": ["q1", "q2"]}],
        "questions": [
            {
                "id": "q1",
                "section_id": "s1",
                "index": 1,
                "type": "mcq",
                "observed_states": ["answered", "skipped"],
            },
            {
                "id": "q2",
                "section_id": "s1",
                "index": 2,
                "type": "coding",
                "observed_states": ["answered"],
            },
        ],
    }


def suite_payload(run_id: str, suite_id: str = "ts_assessment") -> dict:
    return {
        "id": suite_id,
        "run_id": run_id,
        "source": "template_fallback",
        "coverage_targets": [
            {"question_id": "q1", "scenario": "answer_persistence"},
            {"question_id": "q2", "scenario": "coding_behavior"},
            {"question_id": "q2", "scenario": "coding_behavior"},
        ],
    }


def make_case(run_id: str, case_id: str, *, scenario=None, covers=None, suite_id=None):
    return TestCase(
        id=case_id,
        run_id=run_id,
        suite_id=suite_id,
        scenario=scenario,
        covers=covers or [],
        title=f"Case {case_id}",
        expected_result="The expected result occurs.",
        steps=[{"index": 1, "action": "screenshot"}],
    )


def make_result(run_id: str, case_id: str, result_id: str, status: TestStatus, observed=None):
    return TestResult(
        id=result_id,
        run_id=run_id,
        test_case_id=case_id,
        status=status,
        step_results=(
            [{
                "step_index": 1,
                "action": "screenshot",
                "status": status,
                "observed": observed,
            }]
            if observed is not None
            else []
        ),
    )


def test_assessment_map_is_saved_retrieved_and_updated(repo):
    run = make_run(repo)
    first = map_payload(run.id)

    saved = repo.save_assessment_map(run.id, first)
    assert repo.get_assessment_map(run.id) == saved

    updated = map_payload(run.id)
    updated["assessment"]["title"] = "Updated Assessment"
    repo.save_assessment_map(run.id, AssessmentMap.model_validate(updated))
    assert repo.get_assessment_map(run.id)["assessment"]["title"] == "Updated Assessment"


def test_test_suite_is_saved_retrieved_and_not_duplicated(repo):
    run = make_run(repo)
    payload = suite_payload(run.id)

    saved = repo.save_test_suite(run.id, payload)
    assert repo.get_test_suite(run.id) == saved

    replacement = suite_payload(run.id)
    replacement["coverage_targets"] = [{"question_id": "q1", "scenario": "navigation"}]
    repo.save_test_suite(run.id, TestSuite.model_validate(replacement))
    assert repo.get_test_suite(run.id)["coverage_targets"][0]["scenario"] == "navigation"

    with pytest.raises(ConflictError):
        repo.save_test_suite(run.id, suite_payload(run.id, "ts_other"))


def test_test_suite_rejects_wrong_run(repo):
    run = make_run(repo)
    with pytest.raises(BadRequestError):
        repo.save_test_suite(run.id, suite_payload("run_other"))


def test_assessment_fields_round_trip(repo):
    run = make_run(repo)
    suite = repo.save_test_suite(run.id, suite_payload(run.id))
    case = make_case(
        run.id,
        "tc_assessment",
        suite_id=suite["id"],
        scenario="answer_persistence",
        covers=[{"question_id": "q1", "state": "answered"}],
    )
    assert repo.add_test_case(case) == case

    result = make_result(
        run.id,
        case.id,
        "tr_assessment",
        TestStatus.PASSED,
        {"question_id": "q1", "state": "answered"},
    )
    assert repo.save_test_result(result) == result

    bug = BugReport(
        run_id=run.id,
        title="Assessment bug",
        severity=Severity.HIGH,
        category="answer_state",
        description="Answer state was not preserved.",
        steps_to_reproduce=["Answer q1", "Navigate away"],
        expected_behavior="The answer remains selected.",
        actual_behavior="The answer is cleared.",
        assessment_context={"question_id": "q1", "state": "answered"},
        reproducibility="2/2",
        evidence=[EvidenceMeta(run_id=run.id, path=f"{run.id}/q1.png")],
    )
    assert repo.add_bug_report(bug) == bug


def test_question_coverage_counts_only_executed_unique_questions(repo):
    run = make_run(repo)
    repo.save_assessment_map(run.id, map_payload(run.id))
    repo.save_test_suite(run.id, suite_payload(run.id))
    passed = make_case(
        run.id,
        "tc_q1",
        scenario="answer_persistence",
        covers=[{"question_id": "q1"}, {"question_id": "q1"}],
    )
    unrun = make_case(run.id, "tc_q2", scenario="coding_behavior", covers=[{"question_id": "q2"}])
    repo.add_test_case(passed)
    repo.add_test_case(unrun)
    repo.save_test_result(
        make_result(run.id, passed.id, "tr_q1", TestStatus.FAILED, {"question_id": "q1", "state": "answered"})
    )

    coverage = repo.get_coverage(run.id)
    assert coverage.questions.total == 2
    assert coverage.questions.exercised == 1


def test_coverage_is_zero_before_any_test_executes(repo):
    run = make_run(repo)
    repo.save_assessment_map(run.id, map_payload(run.id))
    repo.save_test_suite(run.id, suite_payload(run.id))

    coverage = repo.get_coverage(run.id)
    assert coverage.questions.exercised == 0
    assert coverage.states.exercised == 0
    assert coverage.scenarios.exercised == 0


def test_state_coverage_uses_observed_states_and_applicability(repo):
    run = make_run(repo)
    repo.save_assessment_map(run.id, map_payload(run.id))
    case = make_case(run.id, "tc_state", covers=[{"question_id": "q1", "state": "skipped"}])
    repo.add_test_case(case)
    repo.save_test_result(
        make_result(run.id, case.id, "tr_state", TestStatus.PASSED, {"question_id": "q1", "state": "answered"})
    )

    coverage = repo.get_coverage(run.id)
    assert coverage.states.total == 3
    assert coverage.states.exercised == 1


def test_scenario_coverage_counts_passed_failed_not_skipped_or_unrun(repo):
    run = make_run(repo)
    repo.save_assessment_map(run.id, map_payload(run.id))
    repo.save_test_suite(run.id, suite_payload(run.id))
    passed = make_case(run.id, "tc_s1", scenario="answer_persistence")
    failed = make_case(run.id, "tc_s2", scenario="coding_behavior")
    skipped = make_case(run.id, "tc_s3", scenario="navigation")
    for case in (passed, failed, skipped):
        repo.add_test_case(case)
    repo.save_test_result(make_result(run.id, passed.id, "tr_s1", TestStatus.PASSED))
    repo.save_test_result(make_result(run.id, failed.id, "tr_s2", TestStatus.FAILED))
    repo.save_test_result(make_result(run.id, skipped.id, "tr_s3", TestStatus.SKIPPED))

    coverage = repo.get_coverage(run.id)
    assert coverage.scenarios.total == 2
    assert coverage.scenarios.exercised == 2


def test_generic_run_has_no_assessment_coverage(repo):
    run = make_run(repo)
    assert repo.get_coverage(run.id) is None
