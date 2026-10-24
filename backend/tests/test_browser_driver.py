"""Smoke and integration tests for BrowserDriver service.

Owner: Member C.
Verifies asynchronous Playwright lifecycle: launching Chromium, opening
pages, verifying titles and DOM elements, capturing screenshots in a
temporary directory, network failure and HTTP error collection,
Playwright execution tracing, browser session reset, and ensuring clean
browser closure on completion or failure.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
import zipfile

import pytest

from app.core.config import get_settings
from app.services.browser_driver import BrowserDriver, _sanitize_url, _validate_safe_filename

DEPLOYED_SAMPLE_APP_URL = "https://qa-sample-app.onrender.com/"


def _resolve_sample_app_url() -> str:
    """Return SAMPLE_APP_URL from config or environment, defaulting to the Render URL."""
    settings = get_settings()
    url = getattr(settings, "sample_app_url", None)
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
            assert "Example Domain" in page_info["title"]
            assert page_info["status"] == 200
            assert "example.com" in page_info["url"]

            screenshot_path = await driver.screenshot("smoke_test.png")
            assert screenshot_path.exists()
            assert screenshot_path.is_file()
            assert screenshot_path.stat().st_size > 0
            assert screenshot_path.parent == tmp_path

            dom_summary = await driver.get_dom_summary()
            assert dom_summary["title"] == page_info["title"]
            assert len(dom_summary.get("links", [])) > 0

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


def test_browser_driver_network_diagnostics(tmp_path: Path) -> None:
    """Verify capture of request failures, HTTP >= 400 errors, and diagnostics clearing."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        try:
            await driver.start(headless=True)
            page = driver.page
            assert page is not None

            async def _handle_abort(route: Any) -> None:
                await route.abort("failed")

            async def _handle_500(route: Any) -> None:
                await route.fulfill(
                    status=500,
                    body="error",
                )

            async def _handle_404(route: Any) -> None:
                await route.fulfill(
                    status=404,
                    body="not found",
                )

            # Route 1: Simulate network failure (aborted request)
            await page.route("**/mock-failed-asset.png", _handle_abort)
            # Route 2: Simulate HTTP 500 error response
            await page.route("**/mock-server-error.json*", _handle_500)
            # Route 3: Simulate HTTP 404 error response
            await page.route("**/mock-not-found*", _handle_404)

            await driver.open("https://example.com")

            # Trigger network requests inside the page
            await page.evaluate(
                """async () => {
                    try { await fetch('/mock-failed-asset.png'); } catch (e) {}
                    try { await fetch('/mock-server-error.json?token=secret123&page=2'); } catch (e) {}
                    try { await fetch('/mock-not-found'); } catch (e) {}
                }"""
            )

            # Check request failures
            req_failures = driver.request_failures()
            assert len(req_failures) >= 1
            failed_req = next(r for r in req_failures if "mock-failed-asset" in r["url"])
            assert failed_req["method"] == "GET"
            assert "failure_reason" in failed_req

            # Check HTTP >= 400 errors
            http_errs = driver.http_errors()
            assert len(http_errs) >= 2
            err_500 = next(e for e in http_errs if "mock-server-error" in e["url"])
            assert err_500["status"] == 500
            # Ensure query token was sanitized
            assert "%5BREDACTED%5D" in err_500["url"] or "[REDACTED]" in err_500["url"]
            assert "secret123" not in err_500["url"]
            assert "page=2" in err_500["url"]

            err_404 = next(e for e in http_errs if "mock-not-found" in e["url"])
            assert err_404["status"] == 404

            # Check diagnostics dictionary
            diagnostics = driver.get_diagnostics()
            assert "console_logs" in diagnostics
            assert len(diagnostics["request_failures"]) == len(req_failures)
            assert len(diagnostics["http_errors"]) == len(http_errs)

            # Check clearing diagnostics
            driver.clear_diagnostics()
            cleared = driver.get_diagnostics()
            assert len(cleared["request_failures"]) == 0
            assert len(cleared["http_errors"]) == 0
            assert len(cleared["console_logs"]) == 0

        finally:
            await driver.close()

    asyncio.run(_test())


def test_browser_driver_tracing(tmp_path: Path) -> None:
    """Verify starting Playwright tracing, stopping, and verifying the valid trace ZIP archive."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        try:
            await driver.start(headless=True)
            assert not driver.is_tracing

            # Start tracing
            await driver.start_tracing("test_trace_run")
            assert driver.is_tracing

            # Execute navigation to create trace events
            await driver.open("https://example.com")

            # Stop tracing and save ZIP
            trace_path = await driver.stop_tracing()
            assert trace_path is not None
            assert trace_path.exists()
            assert trace_path.is_file()
            assert trace_path.stat().st_size > 0
            assert trace_path.suffix == ".zip"
            assert not driver.is_tracing

            # Verify it is a valid ZIP archive
            assert zipfile.is_zipfile(trace_path)
            with zipfile.ZipFile(trace_path, "r") as zf:
                namelist = zf.namelist()
                assert len(namelist) > 0

        finally:
            await driver.close()

    asyncio.run(_test())


def test_browser_driver_tracing_discard(tmp_path: Path) -> None:
    """Verify stopping a trace with discard=True closes tracing without creating a file."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        try:
            await driver.start(headless=True)
            await driver.start_tracing("discard_me")
            assert driver.is_tracing

            await driver.open("https://example.com")

            result = await driver.stop_tracing(discard=True)
            assert result is None
            assert not driver.is_tracing

        finally:
            await driver.close()

    asyncio.run(_test())


def test_browser_driver_tracing_safe_close(tmp_path: Path) -> None:
    """Ensure driver.close() safely stops an in-flight trace without leaking resources."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        try:
            await driver.start(headless=True)
            await driver.start_tracing("unclosed_trace")
            assert driver.is_tracing
        finally:
            await driver.close()
            assert not driver.is_tracing
            assert driver.page is None
            assert driver.context is None

    asyncio.run(_test())


def test_browser_driver_session_reset(tmp_path: Path) -> None:
    """Verify reset_session clears cookies and client-side web storage (localStorage, sessionStorage)."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        try:
            await driver.start(headless=True)
            page = driver.page
            context = driver.context
            assert page is not None
            assert context is not None

            await driver.open("https://example.com")

            # Set a cookie
            await context.add_cookies([
                {"name": "session_user", "value": "candidate_123", "url": "https://example.com"}
            ])
            # Set localStorage and sessionStorage
            await page.evaluate(
                """() => {
                    window.localStorage.setItem('exam_state', 'in_progress');
                    window.sessionStorage.setItem('current_q', '5');
                }"""
            )

            # Verify initial state
            cookies_before = await context.cookies()
            assert any(c["name"] == "session_user" for c in cookies_before)
            storage_before = await page.evaluate(
                "() => [window.localStorage.getItem('exam_state'), window.sessionStorage.getItem('current_q')]"
            )
            assert storage_before == ["in_progress", "5"]

            # Reset session
            await driver.reset_session()

            # Verify state after reset
            cookies_after = await context.cookies()
            assert not any(c["name"] == "session_user" for c in cookies_after)
            storage_after = await page.evaluate(
                "() => [window.localStorage.getItem('exam_state'), window.sessionStorage.getItem('current_q')]"
            )
            assert storage_after == [None, None]

        finally:
            await driver.close()

    asyncio.run(_test())


def test_browser_driver_url_sanitization() -> None:
    """Verify sensitive query parameters are redacted from URLs."""
    raw = "https://app.local/api/questions?token=secret123&password=my_secret_pass&api_key=key99&page=1&section=A"
    sanitized = _sanitize_url(raw)
    assert "token=%5BREDACTED%5D" in sanitized or "token=[REDACTED]" in sanitized
    assert "password=%5BREDACTED%5D" in sanitized or "password=[REDACTED]" in sanitized
    assert "api_key=%5BREDACTED%5D" in sanitized or "api_key=[REDACTED]" in sanitized
    assert "secret123" not in sanitized
    assert "my_secret_pass" not in sanitized
    assert "key99" not in sanitized
    assert "page=1" in sanitized
    assert "section=A" in sanitized


def test_browser_driver_filename_validation() -> None:
    """Ensure path traversal characters in evidence filenames are rejected."""
    with pytest.raises(ValueError):
        _validate_safe_filename("../bad_file.png")
    with pytest.raises(ValueError):
        _validate_safe_filename("sub/dir/trace.zip")
    with pytest.raises(ValueError):
        _validate_safe_filename("")


def test_browser_driver_partial_initialization_cleanup(tmp_path: Path) -> None:
    """Ensure driver is resilient to calls prior to start() and multiple close() calls."""

    async def _test() -> None:
        driver = BrowserDriver(evidence_dir=tmp_path)
        # Calling methods before start raises clean RuntimeErrors
        with pytest.raises(RuntimeError):
            await driver.open("https://example.com")
        with pytest.raises(RuntimeError):
            await driver.start_tracing()

        # stop_tracing, reset_session, and close are safe no-ops before start
        assert await driver.stop_tracing() is None
        await driver.reset_session()
        await driver.close()
        # Multiple close calls are idempotent
        await driver.close()

    asyncio.run(_test())


def test_browser_driver_sample_app_integration(tmp_path: Path) -> None:
    """Integration smoke test opening the deployed sample application."""

    async def _test() -> None:
        target_url = _resolve_sample_app_url()
        driver = BrowserDriver(evidence_dir=tmp_path)
        try:
            await driver.start(headless=True)

            page_info: dict[str, Any] = {}
            for _ in range(6):
                page_info = await driver.open(target_url)
                if page_info.get("status") == 200 and "loading" not in page_info.get("title", "").lower():
                    break
                await asyncio.sleep(4)

            assert page_info.get("status") == 200
            assert page_info.get("url", "").startswith("http")

            title = page_info.get("title", "")
            assert len(title.strip()) > 0
            assert "Code Apex" in title

            dom_summary = await driver.get_dom_summary()
            assert dom_summary.get("title") == title
            headings = dom_summary.get("headings", [])
            assert any("Code Apex" in h.get("text", "") for h in headings)

            links = dom_summary.get("links", [])
            assert len(links) > 0

            screenshot_path = await driver.screenshot("sample_app_integration.png")
            assert screenshot_path.exists()
            assert screenshot_path.is_file()
            assert screenshot_path.stat().st_size > 0
            assert screenshot_path.parent == tmp_path

        finally:
            await driver.close()
            assert driver.page is None

    asyncio.run(_test())
