"""Smoke test for BrowserDriver service.

Owner: Member C.
Verifies asynchronous Playwright lifecycle: launching Chromium, opening
https://example.com, verifying the title, capturing a screenshot in a
temporary directory, and ensuring clean browser closure on completion or failure.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.services.browser_driver import BrowserDriver


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
