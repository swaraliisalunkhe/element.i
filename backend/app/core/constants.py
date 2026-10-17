"""
Frozen enums and constants shared by the whole project (CP1).

Owner: Member A.
Rule: do NOT rename or remove values after CP1 without telling all members.
Adding a new value is allowed only through a PR that all members approve.
"""

from enum import StrEnum

CONTRACT_VERSION = "1.0.0"
API_PREFIX = "/api"
EVIDENCE_URL_PREFIX = "/api/evidence"


class RunStatus(StrEnum):
    """Where a QA run currently is."""

    PENDING = "pending"          # created, not started yet
    EXPLORING = "exploring"      # Explorer agent is working
    TESTING = "testing"          # Tester agent is working
    REPORTING = "reporting"      # Reporter agent is working
    COMPLETED = "completed"      # finished successfully (terminal)
    FAILED = "failed"            # crashed or aborted (terminal)


TERMINAL_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.FAILED})

ALLOWED_STATUS_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.PENDING: frozenset({RunStatus.EXPLORING, RunStatus.FAILED}),
    RunStatus.EXPLORING: frozenset({RunStatus.TESTING, RunStatus.FAILED}),
    RunStatus.TESTING: frozenset({RunStatus.REPORTING, RunStatus.FAILED}),
    RunStatus.REPORTING: frozenset({RunStatus.COMPLETED, RunStatus.FAILED}),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
}


def can_transition(current: RunStatus, new: RunStatus) -> bool:
    """Return True if a run may move from `current` to `new`."""
    return new in ALLOWED_STATUS_TRANSITIONS[current]


class Severity(StrEnum):
    """How bad a bug is."""

    CRITICAL = "critical"   # app unusable, data loss, security hole
    HIGH = "high"           # a main feature is broken
    MEDIUM = "medium"       # a feature partly broken, workaround exists
    LOW = "low"             # cosmetic or minor


SEVERITY_ORDER = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]


class BugCategory(StrEnum):
    """What kind of bug it is."""

    FUNCTIONAL = "functional"
    FORM_VALIDATION = "form_validation"
    NAVIGATION = "navigation"
    UI_LAYOUT = "ui_layout"
    CONTENT = "content"
    ACCESSIBILITY = "accessibility"
    PERFORMANCE = "performance"
    SECURITY = "security"
    CONSOLE_ERROR = "console_error"
    NETWORK_ERROR = "network_error"


class BrowserAction(StrEnum):
    """The only actions a test step may use. The Tester must support all of them."""

    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    CHECK = "check"
    UNCHECK = "uncheck"
    PRESS = "press"
    HOVER = "hover"
    WAIT = "wait"
    ASSERT_VISIBLE = "assert_visible"
    ASSERT_TEXT = "assert_text"
    ASSERT_URL = "assert_url"
    SCREENSHOT = "screenshot"


class AgentName(StrEnum):
    """Who produced an event."""

    ORCHESTRATOR = "orchestrator"
    EXPLORER = "explorer"
    TESTER = "tester"
    REPORTER = "reporter"


class TestStatus(StrEnum):
    """Result of a test case or of one step."""

    __test__ = False  # stops pytest from mistaking this class for a test

    PASSED = "passed"
    FAILED = "failed"     # an assertion did not hold: this is a likely bug
    SKIPPED = "skipped"   # not run (an earlier step failed)
    ERROR = "error"       # the test itself broke (timeout, crash): not necessarily an app bug


class ElementType(StrEnum):
    """Kinds of interactive elements the Explorer can report."""

    LINK = "link"
    BUTTON = "button"
    INPUT = "input"
    TEXTAREA = "textarea"
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    FORM = "form"
    OTHER = "other"


class EvidenceKind(StrEnum):
    SCREENSHOT = "screenshot"
    CONSOLE_LOG = "console_log"
    HTML_SNAPSHOT = "html_snapshot"


class EventType(StrEnum):
    """Names of the live events sent over SSE. See Part 4 for how they are used."""

    RUN_CREATED = "run_created"
    RUN_STATUS_CHANGED = "run_status_changed"
    AGENT_STARTED = "agent_started"
    AGENT_PROGRESS = "agent_progress"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    JOURNEY_DISCOVERED = "journey_discovered"
    TEST_STARTED = "test_started"
    STEP_COMPLETED = "step_completed"
    TEST_COMPLETED = "test_completed"
    EVIDENCE_SAVED = "evidence_saved"
    BUG_REPORTED = "bug_reported"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"


class EventLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AgentMode(StrEnum):
    """What the user asked for when creating a run."""

    MOCK = "mock"   # fixed fake data, no browser, no AI. Used for demos of the plumbing.
    REAL = "real"   # real browser automation (and AI if configured)


class GenerationMode(StrEnum):
    """How a journey / test / bug was actually produced. Keeps the demo honest."""

    MOCK = "mock"              # hard-coded fixture
    RULE_BASED = "rule_based"  # produced by code rules, no AI
    LLM = "llm"                # produced with an AI model


class LLMProvider(StrEnum):
    GEMINI = "gemini"
    CLAUDE = "claude"
    NONE = "none"