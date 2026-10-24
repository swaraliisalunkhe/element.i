"""Tests for the agent factory module (app.agents.factory).

Owner: Member C.
"""

from __future__ import annotations

import pytest

from app.agents.explorer import ExplorerAgent
from app.agents.factory import build_agents
from app.agents.reporter import ReporterAgent
from app.agents.tester import TesterAgent
from app.core.agent_interface import AgentSet
from app.core.config import get_settings
from app.orchestrator import _load_real_agents


def test_build_agents_returns_agentset() -> None:
    settings = get_settings()
    agents = build_agents(settings)

    assert isinstance(agents, AgentSet)
    assert isinstance(agents.explorer, ExplorerAgent)
    assert isinstance(agents.tester, TesterAgent)
    assert isinstance(agents.reporter, ReporterAgent)


def test_build_agents_has_required_agent_methods() -> None:
    settings = get_settings()
    agents = build_agents(settings)

    assert callable(getattr(agents.explorer, "explore", None))
    assert callable(getattr(agents.tester, "run_tests", None))
    assert callable(getattr(agents.reporter, "report", None))


def test_orchestrator_loads_real_agents_via_factory() -> None:
    settings = get_settings()
    # Ensure orchestrator's _load_real_agents directly finds app.agents.factory.build_agents
    agents = _load_real_agents(settings)

    assert isinstance(agents, AgentSet)
    assert isinstance(agents.explorer, ExplorerAgent)
    assert isinstance(agents.tester, TesterAgent)
    assert isinstance(agents.reporter, ReporterAgent)
