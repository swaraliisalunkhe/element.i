# Contract changelog

## v1.1.0 (additive, backward compatible)

Assessment QA revision. Every v1.0.0 example still validates. Nothing was removed or renamed.

- New enums: RunMode, QuestionType, QuestionState, LifecycleStage, ScenarioTag, SuiteSource.
- New enum values: BugCategory (validation, server_error, ui, answer_state, timer, evaluation),
  BrowserAction (submit, type_code, run_code, wait_timer, assert_state, assert_value),
  EvidenceKind (network_log, trace, dom_snapshot).
- New schemas: AssessmentMap (with nested models), TestSuite, CoverageTarget, Coverage, RunDetail.
- New optional fields: RunCreate and RunResponse (description, mode), TestStep (question_ref),
  TestCase (suite_id, scenario, covers), StepResult (observed), BugReport (assessment_context,
  reproducibility).
- GET /api/runs/{id} now returns RunDetail (assessment_map, suite, coverage are null until they exist).
- New examples: assessment_map.json, test_suite.json, run_detail.json.

## v1.0.0 (tag cp1-contracts)

Initial freeze.