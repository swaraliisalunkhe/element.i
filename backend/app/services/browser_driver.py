"""Asynchronous Playwright wrapper for Code Apex agents.

Provides browser automation utilities: starting Chromium, navigation, element
interactions, DOM summarization, screenshot capture, console log retrieval,
network failure/HTTP error diagnostics, Playwright execution tracing,
browser session resetting, and clean resource teardown.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import time
from typing import Any
import urllib.parse

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from app.core.config import Settings, get_settings

logger = logging.getLogger("code_apex.services.browser_driver")

SENSITIVE_PARAM_NAMES = frozenset({
    "token",
    "auth",
    "authorization",
    "password",
    "passwd",
    "pwd",
    "secret",
    "key",
    "api_key",
    "apikey",
    "session",
    "session_id",
    "sessionid",
    "jwt",
    "sig",
    "signature",
    "access_token",
    "refresh_token",
})


def _sanitize_url(url: str) -> str:
    """Strip or redact sensitive query parameters from URLs in logs and diagnostics.

    Preserves standard query keys while replacing values of known sensitive
    credentials (tokens, passwords, api keys, signatures) with '[REDACTED]'.
    """
    if not url or "?" not in url:
        return url
    try:
        parsed = urllib.parse.urlsplit(url)
        if not parsed.query:
            return url
        pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        sanitized_pairs: list[tuple[str, str]] = []
        for k, v in pairs:
            k_lower = k.lower()
            if k_lower in SENSITIVE_PARAM_NAMES or any(
                s in k_lower for s in ("token", "secret", "password", "auth", "key")
            ):
                sanitized_pairs.append((k, "[REDACTED]"))
            else:
                sanitized_pairs.append((k, v))
        new_query = urllib.parse.urlencode(sanitized_pairs)
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
        )
    except Exception:
        return url.split("?", 1)[0]


def _validate_safe_filename(name: str) -> None:
    """Validate that a filename does not contain path traversal characters."""
    bad = (
        not name
        or name in (".", "..")
        or any(char in name for char in ("/", "\\", ":", "\x00"))
    )
    if bad:
        raise ValueError(f"Unsafe filename: {name!r}")


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
        self._request_failures: list[dict[str, Any]] = []
        self._http_errors: list[dict[str, Any]] = []
        self._is_tracing: bool = False
        self._trace_name: str | None = None

    @property
    def page(self) -> Page | None:
        """Access the underlying Playwright Page if initialized."""
        return self._page

    @property
    def context(self) -> BrowserContext | None:
        """Access the underlying Playwright BrowserContext if initialized."""
        return self._context

    @property
    def evidence_dir(self) -> Path:
        """Configured folder for storing screenshot and trace evidence."""
        return self._evidence_dir

    @property
    def is_tracing(self) -> bool:
        """Whether Playwright execution tracing is currently active."""
        return self._is_tracing

    def _ensure_page(self) -> Page:
        if self._page is None:
            raise RuntimeError("BrowserDriver has not been started. Call start() first.")
        return self._page

    def _ensure_context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("BrowserDriver has not been started. Call start() first.")
        return self._context

    async def start(self, headless: bool = True) -> None:
        """Launch Chromium, configure a browser context, and create a page."""
        if self._page is not None:
            return

        launch_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ]
        if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
            render_browsers = Path("/opt/render/project/src/.ms-playwright")
            if render_browsers.is_dir():
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(render_browsers)
        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.launch(
                headless=headless,
                args=launch_args,
            )
        except Exception as exc:
            err_msg = str(exc)
            if "Executable doesn't exist" in err_msg or "executable doesn't exist" in err_msg:
                logger.warning(
                    "Playwright Chromium executable was not found (%s). "
                    "Running on-demand fallback: python -m playwright install chromium...",
                    err_msg,
                )
                import subprocess
                import sys

                install_proc = subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if install_proc.returncode != 0:
                    logger.error(
                        "Fallback playwright installation failed (exit code %d):\nSTDOUT: %s\nSTDERR: %s",
                        install_proc.returncode,
                        install_proc.stdout,
                        install_proc.stderr,
                    )
                    raise
                logger.info("Fallback playwright chromium installation succeeded. Retrying launch...")
                self._browser = await self._playwright.chromium.launch(
                    headless=headless,
                    args=launch_args,
                )
            else:
                raise
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()

        def _on_console(msg: Any) -> None:
            self._console_logs.append({
                "type": msg.type,
                "text": msg.text,
                "location": msg.location,
            })

        def _on_request_failed(request: Any) -> None:
            try:
                failure = request.failure
                reason = (
                    failure
                    if isinstance(failure, str)
                    else (failure.get("errorText") if isinstance(failure, dict) else str(failure))
                    if failure
                    else "Request failed"
                )
                self._request_failures.append({
                    "url": _sanitize_url(request.url),
                    "method": request.method,
                    "failure_reason": reason,
                    "resource_type": getattr(request, "resource_type", None),
                })
            except Exception as exc:
                logger.debug(f"Failed to record failed request: {exc}")

        def _on_response(response: Any) -> None:
            try:
                if response.status >= 400:
                    req = getattr(response, "request", None)
                    method = getattr(req, "method", "GET") if req else "GET"
                    self._http_errors.append({
                        "url": _sanitize_url(response.url),
                        "status": response.status,
                        "status_text": response.status_text,
                        "method": method,
                    })
            except Exception as exc:
                logger.debug(f"Failed to record HTTP error response: {exc}")

        self._page.on("console", _on_console)
        self._page.on("requestfailed", _on_request_failed)
        self._page.on("response", _on_response)

    async def open(self, url: str) -> dict[str, Any]:
        """Navigate to url and return page information (url, title, status)."""
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Prohibited navigation scheme: {parsed.scheme!r}")
        hostname = (parsed.hostname or "").lower().strip()
        if hostname in ("169.254.169.254", "metadata.google.internal", "instance-data", "169.254.169.253"):
            raise ValueError(f"Prohibited navigation destination host: {hostname!r}")
        page = self._ensure_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
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
        _validate_safe_filename(name)
        folder = Path(output_dir) if output_dir is not None else self._evidence_dir
        folder.mkdir(parents=True, exist_ok=True)

        filename = name if name.lower().endswith(".png") else f"{name}.png"
        target_path = folder / filename
        await page.screenshot(path=str(target_path))
        return target_path

    # ---------- Diagnostic and Network Error Methods ----------

    def console_logs(self) -> list[dict[str, Any]]:
        """Retrieve collected browser console messages."""
        return list(self._console_logs)

    def request_failures(self) -> list[dict[str, Any]]:
        """Retrieve network request failures captured via page 'requestfailed'."""
        return list(self._request_failures)

    def http_errors(self) -> list[dict[str, Any]]:
        """Retrieve HTTP responses with status code >= 400."""
        return list(self._http_errors)

    def get_diagnostics(self) -> dict[str, list[dict[str, Any]]]:
        """Return all collected diagnostic information across console and network."""
        return {
            "console_logs": list(self._console_logs),
            "request_failures": list(self._request_failures),
            "http_errors": list(self._http_errors),
        }

    def clear_diagnostics(self) -> None:
        """Clear all collected console logs and network diagnostic records."""
        self._console_logs.clear()
        self._request_failures.clear()
        self._http_errors.clear()

    # ---------- Playwright Tracing ----------

    async def start_tracing(
        self,
        name: str | None = None,
        screenshots: bool = True,
        snapshots: bool = True,
    ) -> None:
        """Start Playwright execution tracing on the active browser context.

        Captures screenshots and DOM snapshots for deep diagnostic replays.
        """
        context = self._ensure_context()
        if self._is_tracing:
            logger.warning("Tracing already active; stopping previous trace before restart.")
            try:
                await context.tracing.stop()
            except Exception as exc:
                logger.debug(f"Error stopping prior trace: {exc}")
            self._is_tracing = False

        await context.tracing.start(
            name=name,
            screenshots=screenshots,
            snapshots=snapshots,
        )
        self._is_tracing = True
        self._trace_name = name

    async def stop_tracing(
        self,
        name: str | None = None,
        output_dir: Path | str | None = None,
        discard: bool = False,
    ) -> Path | None:
        """Stop tracing and save the resulting ZIP archive into evidence_dir.

        If discard is True, the trace is closed without saving an artifact.
        """
        if not self._is_tracing or self._context is None:
            return None

        context = self._context
        try:
            if discard:
                await context.tracing.stop(path=None)
                return None

            file_stem = name or self._trace_name or f"trace_{int(time.time() * 1000)}"
            _validate_safe_filename(file_stem)
            filename = file_stem if file_stem.lower().endswith(".zip") else f"{file_stem}.zip"

            folder = Path(output_dir) if output_dir is not None else self._evidence_dir
            folder.mkdir(parents=True, exist_ok=True)
            target_path = folder / filename

            await context.tracing.stop(path=str(target_path))
            return target_path
        finally:
            self._is_tracing = False
            self._trace_name = None

    # ---------- Session Reset ----------

    async def reset_session(self) -> None:
        """Clear client-side browser cookies, localStorage, and sessionStorage.

        Operates safely across all origins within the active browser context.
        Note:
            This resets client-side browser state only. It does not reset
            server-side application database state.
        """
        if self._context is not None:
            await self._context.clear_cookies()

        if self._page is not None and not self._page.is_closed():
            current_url = self._page.url
            if current_url and not current_url.startswith("about:"):
                try:
                    await self._page.evaluate(
                        """() => {
                            try { window.localStorage && window.localStorage.clear(); } catch (e) {}
                            try { window.sessionStorage && window.sessionStorage.clear(); } catch (e) {}
                        }"""
                    )
                except Exception as exc:
                    logger.debug(f"Could not clear web storage for page {current_url}: {exc}")

    # ---------- Teardown & Lifecycle ----------

    async def close(self) -> None:
        """Cleanly release all browser and Playwright resources in order.

        Stops active tracing before closing context and browser, and is safe
        to call multiple times or after partial startup.
        """
        if self._is_tracing and self._context is not None:
            try:
                await self._context.tracing.stop()
            except Exception as exc:
                logger.debug(f"Error stopping trace on close: {exc}")
            self._is_tracing = False

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
