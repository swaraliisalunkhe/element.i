"""Asynchronous Playwright wrapper for Code Apex agents.

Owner: Member C.
Provides browser automation utilities: starting Chromium, navigation, element
interactions, DOM summarization, screenshot capture, console log retrieval,
and clean resource teardown.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from app.core.config import Settings, get_settings

logger = logging.getLogger("code_apex.services.browser_driver")


class BrowserDriver:
    """A lightweight asynchronous Playwright wrapper for browser automation."""

    def __init__(
        self,
        evidence_dir: Path | str | None = None,
        settings: Settings | None = None,
    ) -> None:
        if evidence_dir is not None:
            self._evidence_dir = Path(evidence_dir)
        else:
            active_settings = settings or get_settings()
            self._evidence_dir = active_settings.evidence_path

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._console_logs: list[dict[str, Any]] = []

    @property
    def page(self) -> Page | None:
        """Access the underlying Playwright Page if initialized."""
        return self._page

    @property
    def evidence_dir(self) -> Path:
        """Configured folder for storing screenshot evidence."""
        return self._evidence_dir

    def _ensure_page(self) -> Page:
        if self._page is None:
            raise RuntimeError("BrowserDriver has not been started. Call start() first.")
        return self._page

    async def start(self, headless: bool = True) -> None:
        """Launch Chromium, configure a browser context, and create a page."""
        if self._page is not None:
            return

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=headless)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()

        def _on_console(msg: Any) -> None:
            self._console_logs.append({
                "type": msg.type,
                "text": msg.text,
                "location": msg.location,
            })

        self._page.on("console", _on_console)

    async def open(self, url: str) -> dict[str, Any]:
        """Navigate to url and return page information (url, title, status)."""
        page = self._ensure_page()
        response = await page.goto(url, wait_until="domcontentloaded")
        title = await page.title()
        status = response.status if response is not None else 200
        return {
            "url": page.url,
            "title": title,
            "status": status,
        }

    async def click(self, selector: str) -> None:
        """Click on the element matching selector."""
        page = self._ensure_page()
        await page.click(selector)

    async def fill(self, selector: str, value: str) -> None:
        """Fill an input or textarea element with value."""
        page = self._ensure_page()
        await page.fill(selector, value)

    async def get_dom_summary(self) -> dict[str, Any]:
        """Return a concise summary of the page structure and interactive elements."""
        page = self._ensure_page()
        summary: dict[str, Any] = await page.evaluate(
            """() => {
                const headings = Array.from(document.querySelectorAll('h1, h2, h3'))
                    .map(h => ({ tag: h.tagName.toLowerCase(), text: (h.innerText || h.textContent || '').trim() }))
                    .filter(h => h.text.length > 0)
                    .slice(0, 15);

                const buttons = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"]'))
                    .map(b => ({
                        text: (b.innerText || b.value || '').trim(),
                        id: b.id || null,
                        name: b.name || null,
                    }))
                    .slice(0, 20);

                const inputs = Array.from(document.querySelectorAll('input:not([type="button"]):not([type="submit"]):not([type="hidden"]), textarea, select'))
                    .map(i => ({
                        tag: i.tagName.toLowerCase(),
                        type: i.type || null,
                        name: i.name || null,
                        id: i.id || null,
                        placeholder: i.placeholder || null,
                    }))
                    .slice(0, 20);

                const links = Array.from(document.querySelectorAll('a[href]'))
                    .map(a => ({
                        text: (a.innerText || a.textContent || '').trim(),
                        href: a.getAttribute('href'),
                    }))
                    .filter(a => a.text.length > 0 || a.href)
                    .slice(0, 20);

                const paragraphs = Array.from(document.querySelectorAll('p'))
                    .map(p => (p.innerText || p.textContent || '').trim())
                    .filter(t => t.length > 0)
                    .slice(0, 5);

                return {
                    title: document.title,
                    url: window.location.href,
                    headings,
                    buttons,
                    inputs,
                    links,
                    text_preview: paragraphs.join(' '),
                };
            }"""
        )
        return summary

    async def screenshot(self, name: str, output_dir: Path | str | None = None) -> Path:
        """Save a screenshot in the evidence directory or custom output directory."""
        page = self._ensure_page()
        folder = Path(output_dir) if output_dir is not None else self._evidence_dir
        folder.mkdir(parents=True, exist_ok=True)

        filename = name if name.lower().endswith(".png") else f"{name}.png"
        target_path = folder / filename
        await page.screenshot(path=str(target_path))
        return target_path

    def console_logs(self) -> list[dict[str, Any]]:
        """Retrieve collected browser console messages."""
        return list(self._console_logs)

    async def close(self) -> None:
        """Cleanly release all browser and Playwright resources."""
        if self._page is not None:
            try:
                await self._page.close()
            except Exception:
                pass
            self._page = None

        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    async def __aenter__(self) -> BrowserDriver:
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
