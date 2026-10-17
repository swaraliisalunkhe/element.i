"""CP1 contract tests: JSON examples must parse and agree with each other."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.constants import (
    AgentMode, AgentName, BrowserAction, BugCategory, EventType, GenerationMode,
    RunStatus, Severity, TestStatus, can_transition,
)
from app.schemas import (
    AgentEvent, BugReport, EvidenceMeta, Journey, RunCreate, RunResponse,
    TestCase, TestResult, TestStep,
)

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "shared" / "contracts"

MODEL_FOR_FILE = {
    "run_create.json": RunCreate,
    "run_response.json": RunResponse,
    "journey.json": Journey,
    "test_case.json": TestCase,
    "test_result.json": TestResult,
    "bug_report.json": BugReport,
    "evidence.json": EvidenceMeta,
    "agent_event.json": AgentEvent,
}


def load(name: str) -> dict:
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


# ---------- the frozen enum values ----------

def test_frozen_enum_values():
    assert {e.value for e in RunStatus} == {
        "pending", "exploring", "testing", "reporting", "completed", "failed"}
    assert {e.value for e in Severity} == {"critical", "high", "medium", "low"}
    assert {e.value for e in BugCategory} == {
        "functional", "form_validation", "navigation", "ui_layout", "content",
        "accessibility", "performance", "security", "console_error", "network_error"}
    assert {e.value for e in BrowserAction} == {
        "navigate", "click", "fill", "select", "check", "uncheck", "press", "hover",
        "wait", "assert_visible", "assert_text", "assert_url", "screenshot"}
    assert {e.value for e in AgentName} == {"orchestrator", "explorer", "tester", "reporter"}
    assert {e.value for e in TestStatus} == {"passed", "failed", "skipped", "error"}
    assert {e.value for e in AgentMode} == {"mock", "real"}
    assert {e.value for e in GenerationMode} == {"mock", "rule_based", "llm"}
    assert len(list(EventType)) == 14


def test_status_transitions():
    assert can_transition(RunStatus.PENDING, RunStatus.EXPLORING)
    assert can_transition(RunStatus.TESTING, RunStatus.FAILED)
    assert not can_transition(RunStatus.PENDING, RunStatus.COMPLETED)
    assert not can_transition(RunStatus.COMPLETED, RunStatus.EXPLORING)
    assert not can_transition(RunStatus.FAILED, RunStatus.PENDING)


# ---------- the JSON examples ----------

@pytest.mark.parametrize("filename", sorted(MODEL_FOR_FILE))
def test_example_is_valid_json_and_parses(filename):
    model = MODEL_FOR_FILE[filename].model_validate(load(filename))
    assert model is not None


@pytest.mark.parametrize("filename", sorted(MODEL_FOR_FILE))
def test_example_round_trips(filename):
    model_cls = MODEL_FOR_FILE[filename]
    first = model_cls.model_validate(load(filename))
    second = model_cls.model_validate(first.model_dump(mode="json"))
    assert first == second


def test_all_contract_files_are_covered():
    on_disk = {p.name for p in CONTRACTS_DIR.glob("*.json")}
    assert on_disk == set(MODEL_FOR_FILE)


def test_examples_agree_with_each_other():
    run = load("run_response.json")
    journey = load("journey.json")
    case = load("test_case.json")
    result = load("test_result.json")
    bug = load("bug_report.json")
    evidence = load("evidence.json")
    event = load("agent_event.json")

    for doc in (journey, case, result, bug, evidence, event):
        assert doc["run_id"] == run["id"]
    assert case["journey_id"] == journey["id"]
    assert result["test_case_id"] == case["id"]
    assert bug["test_case_id"] == case["id"]
    assert bug["journey_id"] == journey["id"]
    assert result["evidence"][0] == evidence
    assert bug["evidence"][0] == evidence
    assert event["data"]["bug_id"] == bug["id"]
    assert len(case["steps"]) == len(result["step_results"])
    assert RunCreate.model_validate(load("run_create.json")).target_url == run["target_url"]


# ---------- things that must be rejected ----------

def test_run_create_rejects_bad_url():
    with pytest.raises(ValidationError):
        RunCreate(target_url="ftp://localhost")
    with pytest.raises(ValidationError):
        RunCreate(target_url="localhost:5000")


def test_run_create_rejects_unknown_field_and_bad_limits():
    with pytest.raises(ValidationError):
        RunCreate(target_url="http://localhost:5000", nonsense=1)
    with pytest.raises(ValidationError):
        RunCreate(target_url="http://localhost:5000", max_pages=0)


def test_invalid_severity_rejected():
    data = load("bug_report.json")
    data["severity"] = "urgent"
    with pytest.raises(ValidationError):
        BugReport.model_validate(data)


def test_bug_needs_reproduction_steps_and_valid_confidence():
    data = load("bug_report.json")
    data["steps_to_reproduce"] = []
    with pytest.raises(ValidationError):
        BugReport.model_validate(data)
    data = load("bug_report.json")
    data["confidence"] = 2
    with pytest.raises(ValidationError):
        BugReport.model_validate(data)


@pytest.mark.parametrize("bad_step", [
    {"index": 1, "action": "navigate"},                       # no url
    {"index": 1, "action": "navigate", "url": "/login"},      # url not absolute
    {"index": 1, "action": "click"},                          # no selector
    {"index": 1, "action": "fill", "selector": "#a"},         # no value
    {"index": 1, "action": "press"},                          # no key
    {"index": 1, "action": "dance"},                          # unknown action
    {"index": 0, "action": "screenshot"},                     # index starts at 1
])
def test_invalid_steps_rejected(bad_step):
    with pytest.raises(ValidationError):
        TestStep.model_validate(bad_step)


def test_valid_minimal_steps_accepted():
    TestStep(index=1, action="screenshot")
    TestStep(index=2, action="wait")
    TestStep(index=3, action="press", value="Enter")


def test_step_indexes_must_be_sequential():
    data = load("test_case.json")
    data["steps"][2]["index"] = 7
    with pytest.raises(ValidationError):
        TestCase.model_validate(data)


def test_test_case_needs_steps():
    data = load("test_case.json")
    data["steps"] = []
    with pytest.raises(ValidationError):
        TestCase.model_validate(data)


def test_result_step_must_reference_known_evidence():
    data = load("test_result.json")
    data["step_results"][3]["evidence_id"] = "ev_doesnotexist"
    with pytest.raises(ValidationError):
        TestResult.model_validate(data)


def test_result_finish_time_cannot_precede_start():
    data = load("test_result.json")
    data["finished_at"] = "2026-10-17T09:00:00Z"
    with pytest.raises(ValidationError):
        TestResult.model_validate(data)


@pytest.mark.parametrize("bad_path", [
    "../secret.png", "/etc/passwd", "a\\b.png", "C:/x.png", "a/../b.png", "a//b.png", "",
])
def test_evidence_path_traversal_rejected(bad_path):
    with pytest.raises(ValidationError):
        EvidenceMeta(run_id="run_x", path=bad_path)


def test_evidence_url_is_filled_and_checked():
    ev = EvidenceMeta(run_id="run_x", path="run_x/shot.png")
    assert ev.url == "/api/evidence/run_x/shot.png"
    with pytest.raises(ValidationError):
        EvidenceMeta(run_id="run_x", path="run_x/shot.png", url="/somewhere/else.png")


def test_defaults_are_honest_mock():
    case = TestCase(
        run_id="run_x", title="t", expected_result="e",
        steps=[{"index": 1, "action": "screenshot"}],
    )
    assert case.generated_by == GenerationMode.MOCK