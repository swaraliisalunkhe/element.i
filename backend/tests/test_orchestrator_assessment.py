"""Focused assessment-mode orchestration tests."""

import pytest

from app.core.agent_interface import AgentSet, TesterOutput
from app.core.constants import EventType, GenerationMode, RunMode, TestStatus
from app.core.mock_agents import MockExplorer, MockReporter, MockTester
from app.db import Repository, init_db, session_scope
from app.orchestrator import run_pipeline
from app.schemas import (
    AssessmentMap,
    AssessmentContext,
    BugReport,
    RunCreate,
    TestCase,
    TestResult,
    TestSuite,
)


@pytest.fixture(autouse=True)
def prepared(app_env, monkeypatch):
    monkeypatch.setattr("app.core.mock_agents.DEFAULT_DELAY_SECONDS", 0)
    init_db()


def make_run() -> str:
    with session_scope() as session:
        return Repository(session).create_run(
            RunCreate(target_url="http://localhost:8001", mode=RunMode.ASSESSMENT),
        ).id


def get_run_artifacts(run_id: str):
    with session_scope() as session:
        repo = Repository(session)
        cases = repo.list_test_cases(run_id)
        return (
            repo.get_assessment_map(run_id),
            repo.get_test_suite(run_id),
            cases,
            repo.get_test_result_for_case(cases[0].id) if cases else None,
            repo.list_bug_reports(run_id),
            repo.get_coverage(run_id),
            repo.list_events(run_id),
        )


def assessment_map(run_id: str) -> AssessmentMap:
    return AssessmentMap(
        run_id=run_id,
        assessment={"title": "Assessment"},
        sections=[{"id": "s1", "title": "Section", "question_ids": ["q1"]}],
        questions=[
            {
                "id": "q1",
                "section_id": "s1",
                "index": 1,
                "type": "mcq",
                "observed_states": ["answered"],
            }
        ],
    )


class AssessmentExplorer(MockExplorer):
    def explore_assessment(self, ctx):
        return assessment_map(ctx.run.id)


class AssessmentTester(MockTester):
    def generate_test_suite(self, ctx, journeys):
        return TestSuite(
            run_id=ctx.run.id,
            source="template_fallback",
            coverage_targets=[{"question_id": "q1", "scenario": "answer_persistence"}],
        )

    def run_assessment_tests(self, ctx, journeys, suite):
        case = TestCase(
            id="tc_assessment_orchestration",
            run_id=ctx.run.id,
            scenario="answer_persistence",
            covers=[{"question_id": "q1", "state": "answered"}],
            title="Exercise assessment question",
            expected_result="The answer remains selected.",
            steps=[{"index": 1, "action": "screenshot"}],
            generated_by=GenerationMode.RULE_BASED,
        )
        return TesterOutput(
            test_cases=[case],
            test_results=[
                TestResult(
                    id="tr_assessment_orchestration",
                    run_id=ctx.run.id,
                    test_case_id=case.id,
                    status=TestStatus.FAILED,
                    step_results=[
                        {
                            "step_index": 1,
                            "action": "screenshot",
                            "status": "failed",
                            "observed": {"question_id": "q1", "state": "answered"},
                        }
                    ],
                    generated_by=GenerationMode.RULE_BASED,
                )
            ],
        )


class AssessmentReporter(MockReporter):
    def report_assessment(self, ctx, journeys, test_cases, test_results, assessment_map, suite):
        return [
            BugReport(
                run_id=ctx.run.id,
                test_case_id=test_cases[0].id,
                title="Answer state is lost",
                severity="high",
                category="answer_state",
                description="The answer state did not persist.",
                steps_to_reproduce=["Answer q1"],
                expected_behavior="The answer remains selected.",
                actual_behavior="The answer is lost.",
                assessment_context=AssessmentContext(
                    question_id="q1",
                    state="answered",
                ),
                reproducibility="1/1",
                generated_by=GenerationMode.RULE_BASED,
            )
        ]


def test_assessment_mode_persists_map_suite_execution_bug_and_coverage():
    run_id = make_run()
    run_pipeline(
        run_id,
        agents=AgentSet(AssessmentExplorer(), AssessmentTester(), AssessmentReporter()),
    )

    stored_map, suite, cases, result, bugs, coverage, events = get_run_artifacts(run_id)
    assert stored_map["run_id"] == run_id
    assert suite["test_case_ids"] == ["tc_assessment_orchestration"]
    assert cases[0].suite_id == suite["id"]
    assert result.step_results[0].observed.question_id == "q1"
    assert bugs[0].assessment_context.question_id == "q1"
    assert bugs[0].reproducibility == "1/1"
    assert coverage.questions.exercised == 1
    assert coverage.states.exercised == 1
    assert coverage.scenarios.exercised == 1
    assert any(
        event.type == EventType.AGENT_PROGRESS
        and event.data.get("artifact") in {"assessment_map", "test_suite"}
        for event in events
    )


def test_assessment_mode_does_not_fabricate_missing_outputs():
    run_id = make_run()
    run_pipeline(run_id, agents=AgentSet(MockExplorer(), MockTester(), MockReporter()))

    stored_map, suite, cases, result, bugs, coverage, _ = get_run_artifacts(run_id)
    assert stored_map is None
    assert suite is None
    assert cases and result is not None and bugs
    assert coverage is None


def test_generic_mode_keeps_existing_workflow():
    with session_scope() as session:
        run_id = Repository(session).create_run(
            RunCreate(target_url="http://localhost:5000", mode=RunMode.GENERIC),
        ).id
    run_pipeline(run_id)

    stored_map, suite, cases, result, bugs, coverage, events = get_run_artifacts(run_id)
    assert stored_map is None and suite is None and coverage is None
    assert cases and result is not None and bugs
    assert all(event.data.get("artifact") not in {"assessment_map", "test_suite"} for event in events)


def test_assessment_artifact_run_id_mismatch_fails_cleanly():
    class WrongMapExplorer(MockExplorer):
        def explore_assessment(self, ctx):
            return assessment_map("run_other")

    run_id = make_run()
    run_pipeline(run_id, agents=AgentSet(WrongMapExplorer(), MockTester(), MockReporter()))

    with session_scope() as session:
        repo = Repository(session)
        run = repo.get_run(run_id)
        events = repo.list_events(run_id)
    assert run.status.value == "failed"
    assert "run_other" in run.error_message
    assert events[-1].type == EventType.RUN_FAILED
