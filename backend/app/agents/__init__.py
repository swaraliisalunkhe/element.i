"""Agents package for Code Apex backend.

Owner: Member C.
"""

from typing import Any

from app.agents.assessment_map import AssessmentMap, PaletteState
from app.agents.explorer import ExplorerAgent
from app.agents.reporter import ReporterAgent

__all__ = [
    "AssessmentMap",
    "ExplorerAgent",
    "PaletteState",
    "ReporterAgent",
    "TesterAgent",
    "build_agents",
]


def __getattr__(name: str) -> Any:
    if name == "TesterAgent":
        from app.agents.tester import TesterAgent
        return TesterAgent
    if name == "build_agents":
        from app.agents.factory import build_agents
        return build_agents
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
