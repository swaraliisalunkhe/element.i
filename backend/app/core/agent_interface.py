"""The agent interface: what Member C must implement. Owner: Member A.

HOW IT FITS TOGETHER
  1. The orchestrator creates an AgentContext and calls the agents in order:
       explorer.explore(ctx)                               -> list of Journey
       tester.run_tests(ctx, journeys)                     -> TesterOutput
       reporter.report(ctx, journeys, cases, results)      -> list of BugReport
  2. The orchestrator saves everything the agents return. Agents NEVER touch the database.
  3. Agents report progress with ctx.emit(...). Allowed event types for agents:
     agent_progress, test_started, step_completed.
     The orchestrator emits all the others itself (see Part 4, section 0).

RULES FOR AGENTS
  - Every object returned must have run_id == ctx.run.id.
  - Set generated_by honestly: "rule_based" for code rules, "llm" for AI, never "mock".
  - Save screenshots with ctx.new_evidence_target(filename), then return an EvidenceMeta
    with path = the relative path it gives you.
  - Raise an exception if the work cannot be done. The orchestrator marks the run failed.
    A single test that FAILS an assertion is not an exception: return it as a TestResult.
  - Agents are plain synchronous Python (use Playwright's sync API).

HOW C PLUGS IN
  Create backend/app/agents/factory.py containing:

      from app.core.agent_interface import AgentSet
      def build_agents(settings) -> AgentSet:
          return AgentSet(explorer=MyExplorer(), tester=MyTester(), reporter=MyReporter())
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.core.config import Settings
from app.core.constants import AgentName, EventLevel, EventType
from app.schemas import BugReport, Journey, RunResponse, TestCase, TestResult


class EmitFn(Protocol):
    def __call__(
        self,
        event_type: EventType,
        agent: AgentName,
        message: str,
        level: EventLevel = EventLevel.INFO,
        data: dict[str, Any] | None = None,
    ) -> None: ...


@dataclass(frozen=True)
class AgentContext:
    run: RunResponse          # the run being executed (target_url, limits, ...)
    settings: Settings        # API keys, LLM provider, paths
    evidence_dir: Path        # folder for this run's files (already created)
    emit: EmitFn              # sends a live event to the dashboard

    def new_evidence_target(self, filename: str) -> tuple[Path, str]:
        """Returns (absolute file path to write, relative path to put in EvidenceMeta.path)."""
        bad = (
            not filename
            or filename in (".", "..")
            or any(char in filename for char in ("/", "\\", ":", "\x00"))
        )
        if bad:
            raise ValueError(f"Unsafe evidence filename: {filename!r}")
        return self.evidence_dir / filename, f"{self.run.id}/{filename}"


@dataclass
class TesterOutput:
    __test__ = False  # not a pytest class

    test_cases: list[TestCase]
    test_results: list[TestResult]


class ExplorerAgent(Protocol):
    def explore(self, ctx: AgentContext) -> list[Journey]: ...


class TesterAgent(Protocol):
    __test__ = False  # not a pytest class

    def run_tests(self, ctx: AgentContext, journeys: list[Journey]) -> TesterOutput: ...


class ReporterAgent(Protocol):
    def report(
        self,
        ctx: AgentContext,
        journeys: list[Journey],
        test_cases: list[TestCase],
        test_results: list[TestResult],
    ) -> list[BugReport]: ...


@dataclass
class AgentSet:
    explorer: ExplorerAgent
    tester: TesterAgent
    reporter: ReporterAgent