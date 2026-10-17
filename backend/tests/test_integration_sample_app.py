"""Integration test: real agents against the real sample app. Owner: Member A.

Skipped automatically until Member C's app/agents/factory.py exists AND the sample app
answers at SAMPLE_APP_URL (from .env, default http://localhost:5000).
"""

import importlib.util
import urllib.request

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings

SAMPLE_APP_URL = get_settings().sample_app_url


def _agents_exist() -> bool:
    try:
        return importlib.util.find_spec("app.agents.factory") is not None
    except ModuleNotFoundError:
        return False


def _sample_app_is_up() -> bool:
    try:
        urllib.request.urlopen(SAMPLE_APP_URL, timeout=2)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (_agents_exist() and _sample_app_is_up()),
    reason="Needs Member C's app/agents/factory.py and the sample app running at SAMPLE_APP_URL",
)


def test_real_pipeline_finds_a_bug_with_a_screenshot(app_env):
    from app.main import create_app

    with TestClient(create_app()) as client:
        created = client.post(
            "/api/runs", json={"target_url": SAMPLE_APP_URL, "agent_mode": "real"}
        )
        assert created.status_code == 201
        run_id = created.json()["id"]

        run = client.get(f"/api/runs/{run_id}").json()  # the pipeline finished inside the POST
        assert run["status"] == "completed", run.get("error_message")

        bugs = client.get(f"/api/runs/{run_id}/bugs").json()
        assert bugs, "The real pipeline reported no bugs against the sample app."
        assert all(bug["generated_by"] != "mock" for bug in bugs), "Real mode must not return mock data."

        urls = [e["url"] for bug in bugs for e in bug["evidence"]]
        assert urls, "No bug has screenshot evidence."
        image = client.get(urls[0])
        assert image.status_code == 200
        assert image.headers["content-type"].startswith("image/")