"""Checks B's sample_app/bugs.json against our contract values. Owner: Member A.

Skipped automatically if the file does not exist.
"""

import json
from pathlib import Path

import pytest

from app.core.constants import BugCategory, Severity

BUGS_FILE = Path(__file__).resolve().parents[2] / "sample_app" / "bugs.json"

pytestmark = pytest.mark.skipif(not BUGS_FILE.exists(), reason="sample_app/bugs.json not found")

# Used only while bugs.json has no "category" field. Ask B to add "category" instead.
TYPE_TO_CATEGORY = {
    "validation": "form_validation",
    "authorization": "security",
    "authentication": "security",
    "functionality": "functional",
    "data_integrity": "functional",
    "navigation": "navigation",
    "calculation": "functional",
    "idempotency": "functional",
    "timer": "timer",
    "evaluation": "evaluation",
    "state": "answer_state",
    "answer": "answer_state",
    "scoring": "evaluation",
    "submission": "functional",
    "persistence": "functional",
    "logic": "functional",
    "ui": "ui_layout",
    "editor": "functional",
    "caching": "functional",
    "cache": "functional",
    "network": "network_error",
    "console": "console_error",
}


def load() -> list[dict]:
    return json.loads(BUGS_FILE.read_text(encoding="utf-8-sig"))


def test_file_is_a_non_empty_list():
    bugs = load()
    assert isinstance(bugs, list) and bugs


def test_ids_are_unique():
    ids = [bug["id"] for bug in load()]
    assert len(ids) == len(set(ids))


def test_required_fields_exist():
    for bug in load():
        for field in ("id", "title", "page", "severity", "description", "steps_to_reproduce"):
            assert field in bug, f"{bug.get('id')} is missing '{field}'"
        assert isinstance(bug["steps_to_reproduce"], list) and bug["steps_to_reproduce"]


def test_severity_values_are_allowed():
    allowed = {s.value for s in Severity}
    for bug in load():
        assert bug["severity"] in allowed, f"{bug['id']}: bad severity {bug['severity']!r}"


def test_every_bug_maps_to_an_allowed_category():
    allowed = {c.value for c in BugCategory}
    for bug in load():
        category = bug.get("category") or TYPE_TO_CATEGORY.get(bug.get("type"))
        assert category in allowed, f"{bug['id']}: cannot map type/category {bug.get('type')!r}"