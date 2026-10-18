"""Rule-based Breadth-First Search (BFS) Explorer Agent.

Owner: Member C.
Discovers reachable web pages and interactive elements starting from
ctx.run.target_url, respecting maximum page count and depth limits,
and producing validated Journey instances for the QA pipeline.
"""

from __future__ import annotations

import asyncio
from collections import deque
import concurrent.futures
import logging
import urllib.parse
from typing import Any

from app.core.agent_interface import AgentContext
from app.core.constants import (
    AgentName,
    ElementType,
    EventLevel,
    EventType,
    GenerationMode,
)
from app.schemas.journey import DiscoveredPage, InteractiveElement, Journey
from app.services.browser_driver import BrowserDriver

logger = logging.getLogger("code_apex.agents.explorer")


def _run_async(coro: Any) -> Any:
    """Safely execute an asynchronous coroutine from synchronous code.

    Avoids 'asyncio.run() cannot be called from a running event loop' errors
    if called within an already-active event loop (such as in async tests).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class ExplorerAgent:
    """Autonomous explorer utilizing rule-based BFS to crawl a target application."""

    def __init__(self, driver: BrowserDriver | None = None) -> None:
        self._driver = driver

    def explore(self, ctx: AgentContext) -> list[Journey]:
        """Synchronously explore the application and return a list of Journeys."""
        return _run_async(self._async_explore(ctx))

    async def _async_explore(self, ctx: AgentContext) -> list[Journey]:
        run_id = ctx.run.id
        start_url = ctx.run.target_url.strip()
        max_pages = ctx.run.max_pages
        max_depth = ctx.run.max_depth

        start_parsed = urllib.parse.urlparse(start_url)
        if not start_parsed.scheme or not start_parsed.netloc:
            raise ValueError(f"Invalid target URL: {start_url!r}")

        base_origin = f"{start_parsed.scheme}://{start_parsed.netloc}".lower()

        driver = self._driver or BrowserDriver(
            evidence_dir=ctx.evidence_dir, settings=ctx.settings
        )

        ctx.emit(
            EventType.AGENT_PROGRESS,
            AgentName.EXPLORER,
            f"Explorer started BFS exploration at {start_url} (max pages: {max_pages}, max depth: {max_depth}).",
            level=EventLevel.INFO,
            data={"target_url": start_url, "max_pages": max_pages, "max_depth": max_depth},
        )

        discovered_pages: list[DiscoveredPage] = []
        normalized_start = self._normalize_url(start_url, start_url, base_origin) or start_url
        visited_urls: set[str] = {normalized_start}
        queue: deque[tuple[str, int]] = deque([(normalized_start, 0)])

        try:
            await driver.start(headless=True)

            while queue and len(discovered_pages) < max_pages:
                current_url, depth = queue.popleft()

                try:
                    page_info = await driver.open(current_url)
                    status_code = page_info.get("status", 200)
                    if status_code and status_code >= 400:
                        ctx.emit(
                            EventType.AGENT_PROGRESS,
                            AgentName.EXPLORER,
                            f"HTTP {status_code} encountered on {current_url}",
                            level=EventLevel.WARNING,
                            data={"url": current_url, "status": status_code},
                        )
                except Exception as exc:
                    ctx.emit(
                        EventType.AGENT_PROGRESS,
                        AgentName.EXPLORER,
                        f"Navigation failed for {current_url}: {exc}",
                        level=EventLevel.WARNING,
                        data={"url": current_url, "error": str(exc)},
                    )
                    continue

                dom_summary = await driver.get_dom_summary()
                elements = self._extract_interactive_elements(dom_summary)
                title = dom_summary.get("title") or page_info.get("title") or current_url

                page = DiscoveredPage(
                    url=current_url[:1000],
                    title=title[:300] if title else None,
                    depth=depth,
                    elements=elements,
                )
                discovered_pages.append(page)

                ctx.emit(
                    EventType.AGENT_PROGRESS,
                    AgentName.EXPLORER,
                    f"Discovered page: {current_url} (depth {depth}) with {len(elements)} interactive element(s).",
                    level=EventLevel.INFO,
                    data={"url": current_url, "depth": depth, "elements_count": len(elements)},
                )

                # Enqueue internal links if depth limit allows
                if depth < max_depth:
                    for link_data in dom_summary.get("links", []):
                        raw_href = link_data.get("href")
                        if not raw_href:
                            continue
                        normalized = self._normalize_url(raw_href, current_url, base_origin)
                        if normalized and normalized not in visited_urls:
                            visited_urls.add(normalized)
                            if len(visited_urls) <= max_pages * 3:
                                queue.append((normalized, depth + 1))

        finally:
            await driver.close()

        if not discovered_pages:
            raise RuntimeError(f"Explorer could not discover any reachable pages at {start_url}.")

        journeys = self._build_journeys(run_id, start_url, discovered_pages, ctx.run.max_tests)

        ctx.emit(
            EventType.AGENT_PROGRESS,
            AgentName.EXPLORER,
            f"Exploration finished: {len(discovered_pages)} page(s) discovered, {len(journeys)} journey(s) formed.",
            level=EventLevel.INFO,
            data={"pages_count": len(discovered_pages), "journeys_count": len(journeys)},
        )

        return journeys

    def _normalize_url(self, raw_url: str, current_page_url: str, base_origin: str) -> str | None:
        """Resolve, validate origin, and normalize a URL to prevent duplicate visits."""
        if not raw_url:
            return None

        # Discard script and protocol-specific links
        stripped_lower = raw_url.strip().lower()
        if stripped_lower.startswith(("javascript:", "mailto:", "tel:", "data:", "#")):
            return None

        resolved = urllib.parse.urljoin(current_page_url, raw_url.strip())
        parsed = urllib.parse.urlparse(resolved)

        if parsed.scheme not in ("http", "https"):
            return None

        resolved_origin = f"{parsed.scheme}://{parsed.netloc}".lower()
        if resolved_origin != base_origin:
            return None

        # Normalize path
        path = parsed.path or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")

        return urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            parsed.query,
            "",  # Strip fragment
        ))

    def _extract_interactive_elements(self, dom_summary: dict[str, Any]) -> list[InteractiveElement]:
        """Convert elements from BrowserDriver.get_dom_summary() into InteractiveElements."""
        elements: list[InteractiveElement] = []

        # 1. Links
        for link in dom_summary.get("links", []):
            href = link.get("href")
            text = (link.get("text") or "").strip()
            if href:
                safe_href = href.replace('"', '\\"')[:200]
                selector = f'a[href="{safe_href}"]'
            elif text:
                safe_text = text.replace('"', '\\"')[:50]
                selector = f'a:has-text("{safe_text}")'
            else:
                selector = "a"

            elements.append(
                InteractiveElement(
                    element_type=ElementType.LINK,
                    selector=selector[:500],
                    label=text[:300] if text else None,
                    href=href[:1000] if href else None,
                )
            )

        # 2. Buttons
        for btn in dom_summary.get("buttons", []):
            b_id = btn.get("id")
            b_name = btn.get("name")
            b_text = (btn.get("text") or "").strip()

            if b_id:
                selector = f"#{b_id}"
            elif b_name:
                selector = f"button[name='{b_name}']"
            elif b_text:
                safe_text = b_text.replace('"', '\\"')[:50]
                selector = f'button:has-text("{safe_text}")'
            else:
                selector = "button"

            label = (b_text or b_name or b_id or "").strip()
            elements.append(
                InteractiveElement(
                    element_type=ElementType.BUTTON,
                    selector=selector[:500],
                    label=label[:300] if label else None,
                )
            )

        # 3. Inputs & Form Fields
        for inp in dom_summary.get("inputs", []):
            tag = (inp.get("tag") or "input").lower()
            i_type = (inp.get("type") or "text").lower()
            i_name = inp.get("name")
            i_id = inp.get("id")
            i_ph = inp.get("placeholder")

            if tag == "textarea":
                el_type = ElementType.TEXTAREA
            elif tag == "select":
                el_type = ElementType.SELECT
            elif i_type == "checkbox":
                el_type = ElementType.CHECKBOX
            elif i_type == "radio":
                el_type = ElementType.RADIO
            else:
                el_type = ElementType.INPUT

            if i_id:
                selector = f"#{i_id}"
            elif i_name:
                selector = f"{tag}[name='{i_name}']"
            else:
                selector = f"{tag}[type='{i_type}']" if tag == "input" else tag

            label = (i_ph or i_name or i_id or "").strip()
            elements.append(
                InteractiveElement(
                    element_type=el_type,
                    selector=selector[:500],
                    label=label[:300] if label else None,
                    input_type=i_type[:50],
                    required=False,
                )
            )

        return elements

    def _build_journeys(
        self,
        run_id: str,
        start_url: str,
        discovered_pages: list[DiscoveredPage],
        max_tests: int,
    ) -> list[Journey]:
        """Group discovered pages into coherent user journeys for testing."""
        journeys: list[Journey] = []

        # 1. Primary Comprehensive Journey: Full reachable site flow
        root_title = discovered_pages[0].title or "Home"
        primary_journey = Journey(
            run_id=run_id,
            name=f"Explore {root_title} and navigation flow"[:200],
            description=(
                f"Rule-based crawl traversing {len(discovered_pages)} reachable page(s) "
                f"starting from {start_url}."
            ),
            priority=1,
            start_url=start_url[:1000],
            pages=discovered_pages,
            generated_by=GenerationMode.RULE_BASED,
        )
        journeys.append(primary_journey)

        # 2. Focused Journeys for interactive/form pages (login, signup, contact, etc.)
        for page in discovered_pages:
            # Check if page has forms or interactive inputs
            interactive_inputs = [
                e for e in page.elements
                if e.element_type in (
                    ElementType.INPUT,
                    ElementType.TEXTAREA,
                    ElementType.BUTTON,
                    ElementType.SELECT,
                )
            ]
            if interactive_inputs and page.url != start_url:
                page_title = page.title or page.url
                journey = Journey(
                    run_id=run_id,
                    name=f"User interaction flow: {page_title}"[:200],
                    description=f"Fill and interact with form fields on {page.url} ({len(interactive_inputs)} controls).",
                    priority=2,
                    start_url=page.url[:1000],
                    pages=[page],
                    generated_by=GenerationMode.RULE_BASED,
                )
                journeys.append(journey)
                if len(journeys) >= max_tests:
                    break

        return journeys
