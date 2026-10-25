import type { AgentEvent, BugReport, Evidence, Journey, Run, TestWithResult } from "@/lib/types";

// Copied from Member A's shared/contracts examples (one story: login accepts an empty password).
const RUN = "run_7f3a9c21b4d8";
const TC = "tc_9e8d7c6b5a40";

const mockShotSvg = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><rect width="1280" height="720" fill="%230f172a"/><rect x="40" y="40" width="1200" height="640" rx="12" fill="%23ffffff"/><rect x="40" y="40" width="1200" height="50" rx="12" fill="%231e293b"/><circle cx="70" cy="65" r="7" fill="%23ef4444"/><circle cx="95" cy="65" r="7" fill="%23f59e0b"/><circle cx="120" cy="65" r="7" fill="%2310b981"/><rect x="150" y="50" width="900" height="30" rx="6" fill="%23334155"/><text x="170" y="70" fill="%23f8fafc" font-family="monospace" font-size="14">http://localhost:5000/dashboard</text><rect x="80" y="120" width="1120" height="90" rx="8" fill="%23fef2f2" stroke="%23ef4444" stroke-width="2"/><text x="110" y="160" fill="%23b91c1c" font-family="sans-serif" font-weight="bold" font-size="22">CRITICAL VALIDATION FAILURE: Empty password was accepted</text><text x="110" y="190" fill="%237f1d1d" font-family="sans-serif" font-size="16">Expected: &apos;Password is required&apos; validation error | Actual: Visitor redirected directly to /dashboard</text><rect x="80" y="240" width="540" height="360" rx="8" fill="%23f8fafc" stroke="%23e2e8f0"/><text x="110" y="280" fill="%230f172a" font-family="sans-serif" font-weight="bold" font-size="20">User Session Details</text><text x="110" y="320" fill="%23475569" font-family="sans-serif" font-size="16">Account: user@example.com</text><text x="110" y="350" fill="%23475569" font-family="sans-serif" font-size="16">Session: Authenticated (Bypassed Form Check)</text><rect x="110" y="380" width="200" height="40" rx="6" fill="%23ef4444"/><text x="140" y="405" fill="%23ffffff" font-family="sans-serif" font-weight="bold" font-size="14">FAILED ASSERTION</text><rect x="660" y="240" width="540" height="360" rx="8" fill="%23f8fafc" stroke="%23e2e8f0"/><text x="690" y="280" fill="%230f172a" font-family="sans-serif" font-weight="bold" font-size="20">Autonomous QA Summary</text><text x="690" y="320" fill="%23475569" font-family="sans-serif" font-size="16">Test Case: Login without password shows error</text><text x="690" y="350" fill="%23b91c1c" font-family="sans-serif" font-size="16">Status: FAILED at Step 4 (assert_text)</text><text x="690" y="380" fill="%23475569" font-family="sans-serif" font-size="16">Captured: 2026-10-17T10:01:04Z</text></svg>`;

export const mockEvidence: Evidence = {
  id: "ev_5a4b3c2d1e0f", run_id: RUN, test_case_id: TC, step_index: 4, kind: "screenshot",
  path: `${RUN}/${TC}_step4.png`, url: mockShotSvg, mime_type: "image/svg+xml",
  width: 1280, height: 720, size_bytes: 48213,
  caption: "Dashboard shown after submitting without a password", created_at: "2026-10-17T10:01:04Z",
};

export const mockRun: Run = {
  id: RUN, name: "Smoke run on sample app", target_url: "http://localhost:5000", status: "completed",
  agent_mode: "mock", max_pages: 10, max_depth: 2, max_tests: 20,
  created_at: "2026-10-17T10:00:00Z", started_at: "2026-10-17T10:00:01Z", finished_at: "2026-10-17T10:02:30Z",
  error_message: null,
  summary: { journeys_count: 1, tests_total: 1, tests_passed: 0, tests_failed: 1, bugs_count: 1 },
};

export const mockJourney: Journey = {
  id: "jny_1a2b3c4d5e6f", run_id: RUN, name: "Log in with an email address",
  description: "A visitor opens the login page, enters credentials and submits the form.",
  priority: 1, start_url: "http://localhost:5000/login",
  pages: [
    { url: "http://localhost:5000/", title: "Home", depth: 0, elements: [
      { element_type: "link", selector: "a[href='/login']", label: "Log in", href: "/login", input_type: null, required: false }] },
    { url: "http://localhost:5000/login", title: "Log in", depth: 1, elements: [
      { element_type: "input", selector: "#email", label: "Email", href: null, input_type: "email", required: true },
      { element_type: "input", selector: "#password", label: "Password", href: null, input_type: "password", required: true },
      { element_type: "button", selector: "button[type='submit']", label: "Sign in", href: null, input_type: null, required: false }] },
  ],
  generated_by: "mock", created_at: "2026-10-17T10:00:20Z",
};

export const mockTest: TestWithResult = {
  test_case: {
    id: TC, run_id: RUN, journey_id: mockJourney.id, title: "Login without a password shows an error",
    description: "Submitting the login form with only an email must be rejected.", priority: 1,
    steps: [
      { index: 1, action: "navigate", selector: null, value: null, url: "http://localhost:5000/login", description: "Open the login page" },
      { index: 2, action: "fill", selector: "#email", value: "user@example.com", url: null, description: "Type an email address and leave the password empty" },
      { index: 3, action: "click", selector: "button[type='submit']", value: null, url: null, description: "Press Sign in" },
      { index: 4, action: "assert_text", selector: "#error-message", value: "Password is required", url: null, description: "An error message must be shown" },
    ],
    expected_result: "The form is rejected and the message 'Password is required' is shown.",
    generated_by: "mock", created_at: "2026-10-17T10:00:40Z",
  },
  result: {
    id: "tr_0f1e2d3c4b5a", run_id: RUN, test_case_id: TC, status: "failed",
    started_at: "2026-10-17T10:01:00Z", finished_at: "2026-10-17T10:01:04Z", duration_ms: 4000,
    error_message: "Step 4 failed: element '#error-message' was not found.",
    step_results: [
      { step_index: 1, action: "navigate", status: "passed", duration_ms: 800, error_message: null, actual: "Opened http://localhost:5000/login", evidence_id: null },
      { step_index: 2, action: "fill", status: "passed", duration_ms: 120, error_message: null, actual: "Filled #email", evidence_id: null },
      { step_index: 3, action: "click", status: "passed", duration_ms: 900, error_message: null, actual: "Clicked the submit button; the browser moved to /dashboard", evidence_id: null },
      { step_index: 4, action: "assert_text", status: "failed", duration_ms: 2180, error_message: "Element '#error-message' was not found.", actual: "No error message. The page is /dashboard.", evidence_id: mockEvidence.id },
    ],
    evidence: [mockEvidence], generated_by: "mock",
  },
};

export const mockBug: BugReport = {
  id: "bug_c0ffee123456", run_id: RUN, test_case_id: TC, journey_id: mockJourney.id,
  title: "Login accepts an empty password", severity: "high", category: "form_validation",
  description: "The login form lets a visitor sign in with an email only. No validation message is shown.",
  steps_to_reproduce: ["Open http://localhost:5000/login", "Type user@example.com into the Email field", "Leave the Password field empty", "Click Sign in"],
  expected_behavior: "The form is rejected and 'Password is required' is shown.",
  actual_behavior: "The visitor is taken to /dashboard with no error message.",
  page_url: "http://localhost:5000/login", confidence: 0.9, evidence: [mockEvidence],
  generated_by: "mock", created_at: "2026-10-17T10:02:00Z",
};

const ev = (seq: number, type: AgentEvent["type"], agent: AgentEvent["agent"], message: string, data: Record<string, unknown> | null = null): AgentEvent => ({
  id: `evt_mock${seq}`, run_id: RUN, seq, type, agent, level: "info", message, data,
  timestamp: new Date(Date.UTC(2026, 9, 17, 10, 0, seq * 10)).toISOString(),
});

export const mockEvents: AgentEvent[] = [
  ev(0, "run_created", "orchestrator", "Run created: Initializing autonomous testing suite", { current_url: "http://localhost:5000/", action: "initialize" }),
  ev(1, "agent_started", "explorer", "Explorer started: Crawling landing page and interactive links", { current_url: "http://localhost:5000/", action: "navigate", selector: "a[href='/login']" }),
  ev(2, "journey_discovered", "orchestrator", "Journey found: Log in with an email address", { current_url: "http://localhost:5000/login", action: "explore", selector: "#email" }),
  ev(3, "agent_started", "tester", "Tester started: Formulating and executing auth test cases", { current_url: "http://localhost:5000/login", action: "fill", selector: "#email", value: "user@example.com" }),
  ev(4, "test_completed", "orchestrator", "Test failed: Login without a password shows an error", { current_url: "http://localhost:5000/login", action: "click", selector: "button[type='submit']" }),
  ev(5, "bug_reported", "reporter", "Reporter filed bug: Login accepts an empty password", { current_url: "http://localhost:5000/dashboard", action: "assert_failed", selector: "#error-message", screenshot_url: mockShotSvg }),
  ev(6, "run_completed", "orchestrator", "Run completed: 1 critical bug filed with screenshot evidence", { current_url: "http://localhost:5000/dashboard", action: "completed" }),
];

export const mockRuns: Run[] = [mockRun];
