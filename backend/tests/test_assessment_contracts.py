"""Tests for the assessment extension of the contracts (v1.1). Owner: Member A."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.constants import (
    CONTRACT_VERSION, BrowserAction, BugCategory, EvidenceKind, LifecycleStage,
    QuestionState, QuestionType, RunMode, ScenarioTag, SuiteSource,
)
from app.schemas import (
    AssessmentMap, BugReport, CoverageCount, CoverageTarget, RunCreate, RunDetail,
    TestCase, TestStep, TestSuite,
)


def test_new_enum_values():
    assert {e.value for e in QuestionType} == {"mcq", "coding"}
    assert {e.value for e in QuestionState} == {
        "not_visited", "not_answered", "answered", "skipped",
        "marked_for_review", "answered_and_marked"}
    assert {e.value for e in LifecycleStage} == {
        "assessment", "section", "question", "answer", "navigation",
        "timer", "submission", "evaluation", "score", "result"}
    assert {e.value for e in ScenarioTag} == {
        "answer_persistence", "navigation", "skip_review", "timer", "submission",
        "mcq_behavior", "coding_behavior", "evaluation", "negative_edge"}
    assert {e.value for e in RunMode} == {"assessment", "generic"}
    assert {e.value for e in SuiteSource} == {"llm", "template_fallback"}
    assert {"answer_state", "timer", "evaluation", "validation", "server_error", "ui"} <= {
        e.value for e in BugCategory}
    assert {"submit", "type_code", "run_code", "wait_timer", "assert_state", "assert_value"} <= {
        e.value for e in BrowserAction}
    assert {"network_log", "trace", "dom_snapshot"} <= {e.value for e in EvidenceKind}
    assert CONTRACT_VERSION.startswith("1.1")


def test_v1_examples_still_parse_and_new_fields_default(load_contract):
    run = RunCreate.model_validate(load_contract("run_create.json"))
    assert run.mode == RunMode.ASSESSMENT and run.description is None
    case = TestCase.model_validate(load_contract("test_case.json"))
    assert case.suite_id is None and case.scenario is None and case.covers == []
    assert all(step.question_ref is None for step in case.steps)
    bug = BugReport.model_validate(load_contract("bug_report.json"))
    assert bug.assessment_context is None and bug.reproducibility is None


def test_run_mode_can_be_generic_but_not_anything_else():
    assert RunCreate(target_url="http://localhost:8001", mode="generic").mode == RunMode.GENERIC
    with pytest.raises(ValidationError):
        RunCreate(target_url="http://localhost:8001", mode="exam")


def test_new_settings_defaults():
    s = Settings(_env_file=None)
    assert s.sample_app_url == "http://localhost:8001"
    assert s.target_reset_path == "/reset"
    assert s.sample_assessment_duration == 300
    assert s.testsuite_max_cases == 25
    assert s.trace_enabled is True


def test_assessment_map_example_matches_the_sample_design(load_contract):
    amap = AssessmentMap.model_validate(load_contract("assessment_map.json"))
    types = [q.type for q in amap.questions]
    assert types.count(QuestionType.MCQ) == 4 and types.count(QuestionType.CODING) == 2
    assert [s.id for s in amap.sections] == ["s1", "s2"]
    assert amap.timer is not None and amap.timer.scope == "assessment"
    assert set(amap.lifecycle_found) == set(LifecycleStage)


def test_map_rejects_broken_links(load_contract):
    data = load_contract("assessment_map.json")
    data["sections"][0]["question_ids"].append("q99")
    with pytest.raises(ValidationError):
        AssessmentMap.model_validate(data)

    data = load_contract("assessment_map.json")
    data["questions"][0]["section_id"] = "s9"
    with pytest.raises(ValidationError):
        AssessmentMap.model_validate(data)

    data = load_contract("assessment_map.json")
    data["questions"][1]["id"] = "q1"  # duplicate id
    with pytest.raises(ValidationError):
        AssessmentMap.model_validate(data)

    data = load_contract("assessment_map.json")
    data["questions"] = []
    with pytest.raises(ValidationError):
        AssessmentMap.model_validate(data)


def test_coverage_target_needs_a_question_or_a_type():
    CoverageTarget(question_id="q1", scenario="navigation")
    CoverageTarget(question_type="mcq", scenario="skip_review")
    with pytest.raises(ValidationError):
        CoverageTarget(scenario="timer")


def test_llm_suite_names_its_model_but_fallback_does_not_need_to():
    with pytest.raises(ValidationError):
        TestSuite(run_id="run_x", source="llm")
    fallback = TestSuite(run_id="run_x", source="template_fallback")
    assert fallback.id.startswith("ts_") and fallback.generated_by is None
    TestSuite(run_id="run_x", source="llm", generated_by={"provider": "gemini", "model": "m"})


def test_coverage_count_cannot_exceed_total():
    CoverageCount(total=6, exercised=6)
    with pytest.raises(ValidationError):
        CoverageCount(total=2, exercised=3)


@pytest.mark.parametrize("bad", [
    {"index": 1, "action": "type_code"},
    {"index": 1, "action": "type_code", "selector": "#editor"},
    {"index": 1, "action": "run_code"},
    {"index": 1, "action": "assert_state", "selector": "#palette-q3"},
    {"index": 1, "action": "assert_value", "value": "12"},
    {"index": 1, "action": "submit"},
])
def test_new_actions_need_their_fields(bad):
    with pytest.raises(ValidationError):
        TestStep.model_validate(bad)


def test_new_actions_accept_valid_steps():
    TestStep(index=1, action="type_code", selector="#editor", value="print(1)")
    TestStep(index=2, action="run_code", selector="#btn-run")
    TestStep(index=3, action="assert_state", selector="#palette-q3", value="skipped", question_ref="q3")
    TestStep(index=4, action="assert_value", selector="#run-output", value="12")
    TestStep(index=5, action="submit", selector="#btn-submit")
    TestStep(index=6, action="wait_timer", value="20")


def test_bug_assessment_context_and_reproducibility(load_contract):
    data = load_contract("bug_report.json")
    data["reproducibility"] = "2/2"
    data["assessment_context"] = {
        "section_id": "s1", "question_id": "q2", "question_type": "mcq",
        "state": "answered", "lifecycle_stage": "answer",
    }
    bug = BugReport.model_validate(data)
    assert bug.reproducibility == "2/2"
    assert bug.assessment_context.question_type == QuestionType.MCQ
    data["reproducibility"] = "twice"
    with pytest.raises(ValidationError):
        BugReport.model_validate(data)


def test_run_detail_example_matches_its_parts(load_contract):
    detail = RunDetail.model_validate(load_contract("run_detail.json"))
    assert detail.assessment_map == AssessmentMap.model_validate(load_contract("assessment_map.json"))
    assert detail.suite == TestSuite.model_validate(load_contract("test_suite.json"))
    assert detail.id == detail.assessment_map.run_id == detail.suite.run_id
    assert detail.coverage.questions.total == len(detail.assessment_map.questions)