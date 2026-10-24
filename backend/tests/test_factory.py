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


def test_no_circular_imports_in_agents_and_services() -> None:
    """Ensure modules can be imported in any order without circular import errors."""
    import subprocess
    import sys

    modules_to_test = [
        "app.services.suite_generator",
        "app.agents.assessment_map",
        "app.agents.tester",
        "app.agents.factory",
        "app.agents",
        "app.services",
    ]
    for mod in modules_to_test:
        res = subprocess.run(
            [sys.executable, "-c", f"import {mod}"],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"Importing {mod} failed:\n{res.stderr}"


def test_agents_and_services_package_exports() -> None:
    """Verify package __init__.py files resolve public exports cleanly."""
    from app.agents import AssessmentMap, ExplorerAgent, ReporterAgent, TesterAgent, build_agents
    from app.services import BrowserDriver, SuiteGenerator

    assert AssessmentMap is not None
    assert ExplorerAgent is not None
    assert ReporterAgent is not None
    assert TesterAgent is not None
    assert callable(build_agents)
    assert BrowserDriver is not None
    assert SuiteGenerator is not None
