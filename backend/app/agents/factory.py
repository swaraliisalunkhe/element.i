"""Agent factory providing the production AgentSet for Code Apex.

Owner: Member C.
"""

from __future__ import annotations

from app.core.agent_interface import AgentSet
from app.core.config import Settings


def build_agents(settings: Settings) -> AgentSet:
    """Construct and return the AgentSet containing Member C's agent implementations."""
    from app.agents.explorer import ExplorerAgent
    from app.agents.reporter import ReporterAgent
    from app.agents.tester import TesterAgent

    explorer = ExplorerAgent()
    tester = TesterAgent(assessment_map_provider=lambda: explorer.last_assessment_map)
    reporter = ReporterAgent()

    return AgentSet(
        explorer=explorer,
        tester=tester,
        reporter=reporter,
    )
