"""Focused tests for the rule-based BFS ExplorerAgent.

Owner: Member C.
Verifies starting page discovery, BFS link traversal, max pages and depth limits,
URL normalization, external link exclusion, graceful error handling, clean driver
closure, and Journey schema compliance using a mock BrowserDriver.
Also includes a real-browser smoke test against example.com.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from app.agents.explorer import ExplorerAgent
from app.core.agent_interface import AgentContext
from app.core.config import get_settings
from app.core.constants import (
    AgentName,
    ElementType,
    EventLevel,
    EventType,
    GenerationMode,
)
from app.schemas.run import RunResponse


class MockBrowserDriver:
    """Mock BrowserDriver simulating page loading and DOM summaries offline."""

    def __init__(
        self,
        pages_map: dict[str, dict[str, Any]],
        fail_urls: set[str] | None = None,
    ) -> None:
        self.pages_map = pages_map
        self.fail_urls = fail_urls or set()
        self.started = False
        self.closed = False
        self.visited_urls: list[str] = []
        self._current_page: dict[str, Any] = {}

    def _lookup(self, url: str) -> dict[str, Any] | None:
        if url in self.pages_map:
            return self.pages_map[url]
        alt = url.rstrip("/") if url.endswith("/") else f"{url}/"
        return self.pages_map.get(alt)

    def _is_fail(self, url: str) -> bool:
        if url in self.fail_urls:
            return True
        alt = url.rstrip("/") if url.endswith("/") else f"{url}/"
        return alt in self.fail_urls

    async def start(self, headless: bool = True) -> None:
        self.started = True

    async def open(self, url: str) -> dict[str, Any]:
        self.visited_urls.append(url)
        if self._is_fail(url):
            raise RuntimeError(f"Network error connecting to {url}")
        page = self._lookup(url)
        if not page:
            page = {
                "title": "Page Not Found",
                "status": 404,
                "dom": {"title": "404", "url": url, "links": [], "buttons": [], "inputs": []},
            }
        self._current_page = page
        return {"url": url, "title": page.get("title", ""), "status": page.get("status", 200)}

    async def get_dom_summary(self) -> dict[str, Any]:
        return self._current_page.get("dom", {
            "title": self._current_page.get("title", ""),
            "url": self._current_page.get("url", ""),
            "headings": [],
            "buttons": [],
            "inputs": [],
            "links": [],
        })

    async def close(self) -> None:
        self.closed = True


def _make_context(
    tmp_path: Path,
    target_url: str = "https://example.local",
    max_pages: int = 5,
    max_depth: int = 2,
    max_tests: int = 5,
) -> tuple[AgentContext, list[dict[str, Any]]]:
    """Helper to create an AgentContext and an event recorder."""
    events: list[dict[str, Any]] = []

    def mock_emit(
        event_type: EventType,
        agent: AgentName,
        message: str,
        level: EventLevel = EventLevel.INFO,
        data: dict[str, Any] | None = None,
    ) -> None:
        events.append({
            "type": event_type,
            "agent": agent,
            "message": message,
            "level": level,
            "data": data or {},
        })

    run = RunResponse(
        target_url=target_url,
        max_pages=max_pages,
        max_depth=max_depth,
        max_tests=max_tests,
    )
    ctx = AgentContext(
        run=run,
        settings=get_settings(),
        evidence_dir=tmp_path,
        emit=mock_emit,
    )
    return ctx, events


def test_explorer_single_page_discovery(tmp_path: Path) -> None:
    """Verifies single starting page discovery, element extraction, and Journey output."""
    pages = {
        "https://example.local/": {
            "title": "Welcome Home",
            "status": 200,
            "dom": {
                "title": "Welcome Home",
                "url": "https://example.local/",
                "headings": [{"tag": "h1", "text": "Main Heading"}],
                "buttons": [{"text": "Submit Now", "id": "btn-sub", "name": "submit"}],
                "inputs": [
                    {"tag": "input", "type": "email", "name": "email", "id": "inp-email", "placeholder": "Email"}
                ],
                "links": [{"text": "About Us", "href": "/about"}],
            },
        }
    }
    mock_driver = MockBrowserDriver(pages)
    ctx, events = _make_context(tmp_path, target_url="https://example.local", max_pages=1)

    explorer = ExplorerAgent(driver=mock_driver)
    journeys = explorer.explore(ctx)

    assert mock_driver.started is True
    assert mock_driver.closed is True
    assert len(journeys) >= 1

    primary = journeys[0]
    assert primary.run_id == ctx.run.id
    assert primary.start_url == "https://example.local"
    assert primary.generated_by == GenerationMode.RULE_BASED
    assert len(primary.pages) == 1

    page = primary.pages[0]
    assert page.url == "https://example.local/"
    assert page.title == "Welcome Home"
    assert page.depth == 0

    element_types = [e.element_type for e in page.elements]
    assert ElementType.BUTTON in element_types
    assert ElementType.INPUT in element_types
    assert ElementType.LINK in element_types

    # Verify progress events were emitted with EventType.AGENT_PROGRESS
    progress_events = [e for e in events if e["type"] == EventType.AGENT_PROGRESS]
    assert len(progress_events) >= 2
    assert all(e["agent"] == AgentName.EXPLORER for e in progress_events)


def test_explorer_bfs_traversal_and_depth_limits(tmp_path: Path) -> None:
    """Verifies that BFS explores reachable links and strictly honors max_depth."""
    pages = {
        "https://example.local/": {
            "title": "Home",
            "status": 200,
            "dom": {"links": [{"text": "L1", "href": "/level1"}]},
        },
        "https://example.local/level1": {
            "title": "Level 1",
            "status": 200,
            "dom": {"links": [{"text": "L2", "href": "/level2"}]},
        },
        "https://example.local/level2": {
            "title": "Level 2",
            "status": 200,
            "dom": {"links": [{"text": "L3", "href": "/level3"}]},
        },
        "https://example.local/level3": {
            "title": "Level 3",
            "status": 200,
            "dom": {"links": [{"text": "L4", "href": "/level4"}]},
        },
    }
    mock_driver = MockBrowserDriver(pages)
    # Set max_depth=2. /level3 (depth 3) must NOT be crawled.
    ctx, _ = _make_context(tmp_path, max_pages=10, max_depth=2)

    explorer = ExplorerAgent(driver=mock_driver)
    journeys = explorer.explore(ctx)

    discovered_urls = [p.url for p in journeys[0].pages]
    assert "https://example.local/" in discovered_urls
    assert "https://example.local/level1" in discovered_urls
    assert "https://example.local/level2" in discovered_urls
    assert "https://example.local/level3" not in discovered_urls

    depths = [p.depth for p in journeys[0].pages]
    assert max(depths) <= 2


def test_explorer_max_pages_limit(tmp_path: Path) -> None:
    """Verifies that BFS stops once max_pages is reached."""
    pages = {
        "https://example.local/": {
            "title": "Home",
            "status": 200,
            "dom": {
                "links": [
                    {"text": "P1", "href": "/p1"},
                    {"text": "P2", "href": "/p2"},
                    {"text": "P3", "href": "/p3"},
                    {"text": "P4", "href": "/p4"},
                ]
            },
        },
        "https://example.local/p1": {"title": "P1", "status": 200, "dom": {}},
        "https://example.local/p2": {"title": "P2", "status": 200, "dom": {}},
        "https://example.local/p3": {"title": "P3", "status": 200, "dom": {}},
        "https://example.local/p4": {"title": "P4", "status": 200, "dom": {}},
    }
    mock_driver = MockBrowserDriver(pages)
    ctx, _ = _make_context(tmp_path, max_pages=3, max_depth=2)

    explorer = ExplorerAgent(driver=mock_driver)
    journeys = explorer.explore(ctx)

    assert len(journeys[0].pages) == 3


def test_explorer_url_normalization_and_duplicate_prevention(tmp_path: Path) -> None:
    """Verifies URL normalization so duplicate paths, trailing slashes, and anchors are visited once."""
    pages = {
        "https://example.local/": {
            "title": "Home",
            "status": 200,
            "dom": {
                "links": [
                    {"text": "About 1", "href": "/about"},
                    {"text": "About 2", "href": "/about/"},
                    {"text": "About 3", "href": "/about#team"},
                    {"text": "About 4", "href": "https://example.local/about"},
                ]
            },
        },
        "https://example.local/about": {
            "title": "About",
            "status": 200,
            "dom": {"links": []},
        },
    }
    mock_driver = MockBrowserDriver(pages)
    ctx, _ = _make_context(tmp_path, max_pages=10, max_depth=2)

    explorer = ExplorerAgent(driver=mock_driver)
    journeys = explorer.explore(ctx)

    # /about should only be visited once
    assert mock_driver.visited_urls.count("https://example.local/about") == 1
    assert len(journeys[0].pages) == 2


def test_explorer_external_links_exclusion(tmp_path: Path) -> None:
    """Verifies that external domains and non-HTTP protocols are excluded from crawling."""
    pages = {
        "https://example.local/": {
            "title": "Home",
            "status": 200,
            "dom": {
                "links": [
                    {"text": "External 1", "href": "https://google.com/search"},
                    {"text": "External 2", "href": "https://external.domain.org/docs"},
                    {"text": "JS", "href": "javascript:void(0)"},
                    {"text": "Mail", "href": "mailto:hello@example.local"},
                    {"text": "Internal", "href": "/contact"},
                ]
            },
        },
        "https://example.local/contact": {
            "title": "Contact Us",
            "status": 200,
            "dom": {"links": []},
        },
    }
    mock_driver = MockBrowserDriver(pages)
    ctx, _ = _make_context(tmp_path, max_pages=10, max_depth=2)

    explorer = ExplorerAgent(driver=mock_driver)
    journeys = explorer.explore(ctx)

    discovered_urls = [p.url for p in journeys[0].pages]
    assert "https://example.local/" in discovered_urls
    assert "https://example.local/contact" in discovered_urls
    assert not any("google.com" in u for u in mock_driver.visited_urls)
    assert not any("external.domain.org" in u for u in mock_driver.visited_urls)


def test_explorer_graceful_navigation_failure(tmp_path: Path) -> None:
    """Verifies navigation errors on child links are caught and do not abort exploration."""
    pages = {
        "https://example.local/": {
            "title": "Home",
            "status": 200,
            "dom": {
                "links": [
                    {"text": "Broken Link", "href": "/broken-page"},
                    {"text": "Healthy Link", "href": "/healthy-page"},
                ]
            },
        },
        "https://example.local/healthy-page": {
            "title": "Healthy",
            "status": 200,
            "dom": {"links": []},
        },
    }
    fail_urls = {"https://example.local/broken-page"}
    mock_driver = MockBrowserDriver(pages, fail_urls=fail_urls)
    ctx, events = _make_context(tmp_path, max_pages=10, max_depth=2)

    explorer = ExplorerAgent(driver=mock_driver)
    journeys = explorer.explore(ctx)

    # Exploration continues despite the broken link
    discovered_urls = [p.url for p in journeys[0].pages]
    assert "https://example.local/" in discovered_urls
    assert "https://example.local/healthy-page" in discovered_urls
    assert mock_driver.closed is True

    # Warning event emitted for failure
    warning_events = [e for e in events if e["level"] == EventLevel.WARNING]
    assert any("broken-page" in e["message"] for e in warning_events)


def test_explorer_unreachable_start_url_fails(tmp_path: Path) -> None:
    """Verifies that an unreachable start URL raises an exception and releases the driver."""
    mock_driver = MockBrowserDriver(pages_map={}, fail_urls={"https://example.local"})
    ctx, _ = _make_context(tmp_path, target_url="https://example.local")

    explorer = ExplorerAgent(driver=mock_driver)
    with pytest.raises(RuntimeError, match="could not discover any reachable pages"):
        explorer.explore(ctx)

    assert mock_driver.closed is True


@pytest.mark.asyncio
async def test_explorer_nested_event_loop_safety(tmp_path: Path) -> None:
    """Verifies that explore() safely executes when called from an active asyncio event loop."""
    pages = {
        "https://example.local/": {
            "title": "Home",
            "status": 200,
            "dom": {"links": []},
        }
    }
    mock_driver = MockBrowserDriver(pages)
    ctx, _ = _make_context(tmp_path, target_url="https://example.local")

    explorer = ExplorerAgent(driver=mock_driver)
    journeys = explorer.explore(ctx)
    assert len(journeys) == 1
    assert journeys[0].pages[0].url == "https://example.local/"


def test_explorer_real_browser_integration(tmp_path: Path) -> None:
    """End-to-end integration test of ExplorerAgent with real BrowserDriver on example.com."""
    ctx, events = _make_context(tmp_path, target_url="https://example.com", max_pages=1, max_depth=1)
    explorer = ExplorerAgent()  # Instantiates real BrowserDriver
    journeys = explorer.explore(ctx)

    assert len(journeys) >= 1
    primary = journeys[0]
    assert primary.run_id == ctx.run.id
    assert primary.generated_by == GenerationMode.RULE_BASED
    assert len(primary.pages) == 1
    assert "example.com" in primary.pages[0].url
    assert primary.pages[0].depth == 0
    assert primary.pages[0].title is not None
    assert "Example Domain" in primary.pages[0].title
