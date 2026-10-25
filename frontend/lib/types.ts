// Mirrors shared/contracts/*.json from Member A. Unknown extra fields from the API are ignored.

export type RunStatus = "pending" | "exploring" | "testing" | "reporting" | "completed" | "failed";
export type Severity = "critical" | "high" | "medium" | "low";
export type BugCategory =
  | "functional" | "form_validation" | "navigation" | "ui_layout" | "content"
  | "accessibility" | "performance" | "security" | "console_error" | "network_error";
export type BrowserAction =
  | "navigate" | "click" | "fill" | "select" | "check" | "uncheck" | "press" | "hover"
  | "wait" | "assert_visible" | "assert_text" | "assert_url" | "screenshot";
export type AgentName = "orchestrator" | "explorer" | "tester" | "reporter";
export type TestStatus = "passed" | "failed" | "skipped" | "error";
export type AgentMode = "mock" | "real";
export type GeneratedBy = "mock" | "rule_based" | "llm";
export type ElementType = "link" | "button" | "input" | "textarea" | "select" | "checkbox" | "radio" | "form" | "other";
export type EvidenceKind = "screenshot" | "console_log" | "html_snapshot";
export type EventLevel = "info" | "warning" | "error";
export type EventType =
  | "run_created" | "run_status_changed" | "agent_started" | "agent_progress" | "agent_completed"
  | "agent_failed" | "journey_discovered" | "test_started" | "step_completed" | "test_completed"
  | "evidence_saved" | "bug_reported" | "run_completed" | "run_failed";

export const EVENT_TYPES: EventType[] = [
  "run_created", "run_status_changed", "agent_started", "agent_progress", "agent_completed",
  "agent_failed", "journey_discovered", "test_started", "step_completed", "test_completed",
  "evidence_saved", "bug_reported", "run_completed", "run_failed",
];

export interface RunCreate {
  name?: string;
  target_url: string;
  max_pages?: number;   // 1-50
  max_depth?: number;   // 1-5
  max_tests?: number;   // 1-100
  agent_mode?: AgentMode;
}

export interface RunSummary {
  journeys_count: number;
  tests_total: number;
  tests_passed: number;
  tests_failed: number;
  bugs_count: number;
}

export interface Run {
  id: string;
  name: string | null;
  target_url: string;
  status: RunStatus;
  agent_mode: AgentMode;
  max_pages: number;
  max_depth: number;
  max_tests: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  summary: RunSummary | null;
}

export interface PageElement {
  element_type: ElementType;
  selector: string;
  label: string | null;
  href: string | null;
  input_type: string | null;
  required: boolean;
}

export interface JourneyPage { url: string; title: string | null; depth: number; elements: PageElement[] }

export interface Journey {
  id: string;
  run_id: string;
  name: string;
  description: string | null;
  priority: number;
  start_url: string;
  pages: JourneyPage[];
  generated_by: GeneratedBy;
  created_at: string;
}

export interface TestStep {
  index: number;
  action: BrowserAction;
  selector: string | null;
  value: string | null;
  url: string | null;
  description: string | null;
}

export interface TestCase {
  id: string;
  run_id: string;
  journey_id: string;
  title: string;
  description: string | null;
  priority: number;
  steps: TestStep[];
  expected_result: string | null;
  generated_by: GeneratedBy;
  created_at: string;
}

export interface Evidence {
  id: string;
  run_id: string;
  test_case_id: string | null;
  step_index: number | null;
  kind: EvidenceKind;
  path: string;
  url: string; // always /api/evidence/ + path
  mime_type: string;
  width: number | null;
  height: number | null;
  size_bytes: number | null;
  caption: string | null;
  created_at: string;
}

export interface StepResult {
  step_index: number;
  action: BrowserAction;
  status: TestStatus;
  duration_ms: number | null;
  error_message: string | null;
  actual: string | null;
  evidence_id: string | null;
}

export interface TestResult {
  id: string;
  run_id: string;
  test_case_id: string;
  status: TestStatus;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  error_message: string | null;
  step_results: StepResult[];
  evidence: Evidence[];
  generated_by: GeneratedBy;
}

/** GET /api/runs/{id}/tests item. result is null until the test has run. */
export interface TestWithResult { test_case: TestCase; result: TestResult | null }

export interface BugReport {
  id: string;
  run_id: string;
  test_case_id: string | null;
  journey_id: string | null;
  title: string;
  severity: Severity;
  category: BugCategory;
  description: string | null;
  steps_to_reproduce: string[];
  expected_behavior: string;
  actual_behavior: string;
  page_url: string | null;
  confidence: number | null; // 0-1
  evidence: Evidence[];
  generated_by: GeneratedBy;
  created_at: string;
}

export interface AgentEvent {
  id: string;
  run_id: string;
  seq: number;
  type: EventType;
  agent: AgentName;
  level: EventLevel;
  message: string;
  data: Record<string, unknown> | null;
  timestamp: string;
}

export interface ApiErrorBody { error: { code: string; message: string; details: unknown } }
