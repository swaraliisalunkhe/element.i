"""Smoke and integration tests for BrowserDriver service.

Owner: Member C.
Verifies asynchronous Playwright lifecycle: launching Chromium, opening
pages, verifying titles and DOM elements, capturing screenshots in a
temporary directory, and ensuring clean browser closure on completion or failure.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.services.browser_driver import BrowserDriver

DEPLOYED_SAMPLE_APP_URL = "https://qa-sample-app.onrender.com/"


def _resolve_sample_app_url() -> str:
    """Return SAMPLE_APP_URL from config or environment, defaulting to the Render URL."""
    settings = get_settings()
    url = getattr(settings, "sample_app_url", None)
    # If empty or left at the default local URL (when testing against deployed app), fallback to Render
    if not url or url == "http://localhost:5000":
        return DEPLOYED_SAMPLE_APP_URL
    return url


def test_browser_driver_smoke(tmp_path: Path) -> None:
    """Smoke test navigating to https://example.com, taking screenshot, and cleaning up."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        try:
            await driver.start(headless=True)

            page_info = await driver.open("https://example.com")
            # Verify page title is readable
            assert "Example Domain" in page_info["title"]
            assert page_info["status"] == 200
            assert "example.com" in page_info["url"]

            # Save screenshot in temporary test directory
            screenshot_path = await driver.screenshot("smoke_test.png")
            assert screenshot_path.exists()
            assert screenshot_path.is_file()
            assert screenshot_path.stat().st_size > 0
            assert screenshot_path.parent == tmp_path

            # Verify DOM summary extraction
            dom_summary = await driver.get_dom_summary()
            assert dom_summary["title"] == page_info["title"]
            assert len(dom_summary.get("links", [])) > 0

            # Verify console logs access
            logs = driver.console_logs()
            assert isinstance(logs, list)

        finally:
            await driver.close()
            assert driver.page is None

    asyncio.run(_test())


def test_browser_driver_cleanup_on_failure(tmp_path: Path) -> None:
    """Ensure driver cleans up browser resources even if an assertion fails."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        try:
            await driver.start(headless=True)
            with pytest.raises(AssertionError):
                info = await driver.open("https://example.com")
                assert info["title"] == "ThisTitleDefinitelyDoesNotExist"
        finally:
            await driver.close()
            assert driver.page is None

    asyncio.run(_test())


def test_browser_driver_sample_app_integration(tmp_path: Path) -> None:
    """Integration smoke test opening the deployed sample application.

    Navigates to the configured SAMPLE_APP_URL (defaulting to the deployed Render app),
    verifies successful navigation, inspects the page title, URL, and headings,
    saves a screenshot to a temporary directory, and guarantees browser cleanup.
    """

    async def _test() -> None:
        target_url = _resolve_sample_app_url()
        driver = BrowserDriver(evidence_dir=tmp_path)
        try:
            await driver.start(headless=True)

            # Render free tier spin-up handling: retry briefly if 503 or loading
            page_info: dict[str, Any] = {}
            for _ in range(6):
                page_info = await driver.open(target_url)
                if page_info.get("status") == 200 and "loading" not in page_info.get("title", "").lower():
                    break
                await asyncio.sleep(4)

            print(f"\n[Sample App Integration] Target URL: {target_url}")
            print(f"[Sample App Integration] Final URL: {page_info.get('url')}")
            print(f"[Sample App Integration] Page Title: {page_info.get('title')}")
            print(f"[Sample App Integration] Status Code: {page_info.get('status')}")

            # Check navigation succeeds
            assert page_info.get("status") == 200
            assert page_info.get("url", "").startswith("http")

            # Inspect title
            title = page_info.get("title", "")
            assert len(title.strip()) > 0
            assert "Code Apex" in title

            # Inspect DOM summary based on live inspection
            dom_summary = await driver.get_dom_summary()
            assert dom_summary.get("title") == title
            headings = dom_summary.get("headings", [])
            print(f"[Sample App Integration] Detected Headings: {headings}")
            assert any("Code Apex" in h.get("text", "") for h in headings)

            links = dom_summary.get("links", [])
            print(f"[Sample App Integration] Detected Links ({len(links)}): {[l.get('href') for l in links[:5]]}")
            assert len(links) > 0

            # Save screenshot in temporary test directory
            screenshot_path = await driver.screenshot("sample_app_integration.png")
            assert screenshot_path.exists()
            assert screenshot_path.is_file()
            assert screenshot_path.stat().st_size > 0
            assert screenshot_path.parent == tmp_path
            print(f"[Sample App Integration] Screenshot saved to: {screenshot_path}")

        finally:
            await driver.close()
            assert driver.page is None

    asyncio.run(_test())
