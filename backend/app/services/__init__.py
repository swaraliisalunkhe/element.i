"""Services package for Code Apex backend.

Owner: Member C.
"""

from typing import Any

from app.services.browser_driver import BrowserDriver

__all__ = ["BrowserDriver", "SuiteGenerator"]


def __getattr__(name: str) -> Any:
    if name == "SuiteGenerator":
        from app.services.suite_generator import SuiteGenerator
        return SuiteGenerator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
