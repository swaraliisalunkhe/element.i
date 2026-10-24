"""Run-detail API tests for assessment-specific data."""

from app.db import Repository, session_scope
from app.schemas import (
    AssessmentMap,
    RunCreate,
    RunDetail,
    TestCase,
    TestResult,
    TestSuite,
)

RUN_ID = "run_api_assessment"


def seed_run(load_contract, *, assessment_map=True, suite=True, execution=False) -> None:
    with session_scope() as session:
        repo = Repository(session)
        repo.create_run(RunCreate(target_url="http://localhost:8001"), run_id=RUN_ID)
        map_data = load_contract("assessment_map.json")
        suite_data = load_contract("test_suite.json")
        map_data["run_id"] = RUN_ID
        suite_data["run_id"] = RUN_ID
        if assessment_map:
            repo.save_assessment_map(RUN_ID, AssessmentMap.model_validate(map_data))
        if suite:
            repo.save_test_suite(RUN_ID, TestSuite.model_validate(suite_data))
        if execution:
            case = TestCase(
                id="tc_api_assessment",
                run_id=RUN_ID,
                suite_id=suite_data["id"],
                scenario="answer_persistence",
                covers=[{"question_id": "q2", "state": "answered"}],
                title="Exercise q2",
                expected_result="The answer remains saved.",
                steps=[{"index": 1, "action": "screenshot"}],
            )
            repo.add_test_case(case)
            repo.save_test_result(
                TestResult(
                    id="tr_api_assessment",
                    run_id=RUN_ID,
                    test_case_id=case.id,
                    status="passed",
                    step_results=[
                        {
                            "step_index": 1,
                            "action": "screenshot",
                            "status": "passed",
                            "observed": {"question_id": "q2", "state": "answered"},
                        }
                    ],
                )
            )


def test_run_detail_returns_assessment_map(client, load_contract):
    seed_run(load_contract, suite=False)

    response = client.get(f"/api/runs/{RUN_ID}")

    assert response.status_code == 200
    detail = RunDetail.model_validate(response.json())
    assert detail.assessment_map is not None
    assert detail.assessment_map.run_id == RUN_ID
    assert detail.suite is None


def test_run_detail_returns_generated_test_suite(client, load_contract):
    seed_run(load_contract, assessment_map=False)

    response = client.get(f"/api/runs/{RUN_ID}")

    assert response.status_code == 200
    detail = RunDetail.model_validate(response.json())
    assert detail.suite is not None
    assert detail.suite.run_id == RUN_ID
    assert detail.assessment_map is None


def test_run_detail_returns_calculated_coverage(client, load_contract):
    seed_run(load_contract, execution=True)

    detail = RunDetail.model_validate(client.get(f"/api/runs/{RUN_ID}").json())

    assert detail.coverage is not None
    assert detail.coverage.questions.total == 6
    assert detail.coverage.questions.exercised == 1
    assert detail.coverage.scenarios.exercised == 1


def test_run_detail_generic_run_keeps_optional_fields_null(client):
    run_id = client.post("/api/runs", json={"target_url": "http://localhost:5000"}).json()["id"]

    detail = RunDetail.model_validate(client.get(f"/api/runs/{run_id}").json())

    assert detail.mode.value == "assessment"
    assert detail.assessment_map is None
    assert detail.suite is None
    assert detail.coverage is None


def test_run_detail_without_assessment_data_is_valid(client):
    with session_scope() as session:
        Repository(session).create_run(
            RunCreate(target_url="http://localhost:5000"),
            run_id=RUN_ID,
        )

    detail = RunDetail.model_validate(client.get(f"/api/runs/{RUN_ID}").json())

    assert detail.assessment_map is None
    assert detail.suite is None
    assert detail.coverage is None


def test_run_detail_unknown_run_uses_existing_error_shape(client):
    response = client.get("/api/runs/run_missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_run_detail_preserves_existing_run_fields(client, load_contract):
    seed_run(load_contract)

    body = client.get(f"/api/runs/{RUN_ID}").json()

    assert {"id", "target_url", "status", "agent_mode", "summary"} <= body.keys()
    assert body["id"] == RUN_ID
    assert set(body["summary"]) == {
        "journeys_count",
        "tests_total",
        "tests_passed",
        "tests_failed",
        "bugs_count",
    }


def test_run_detail_is_validated_by_the_existing_contract(client, load_contract):
    seed_run(load_contract, execution=True)

    response = client.get(f"/api/runs/{RUN_ID}")

    assert response.status_code == 200
    detail = RunDetail.model_validate(response.json())
    assert detail.id == RUN_ID
    assert detail.assessment_map is not None
    assert detail.suite is not None
    assert detail.coverage is not None
