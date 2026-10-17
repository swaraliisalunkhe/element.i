"""Shared pytest fixtures. Owner: Member A."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db import Repository, init_db, make_engine, make_session_factory, reset_db_caches

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "shared" / "contracts"


@pytest.fixture
def load_contract():
    """Returns a function: load_contract('bug_report.json') -> dict."""

    def _load(name: str) -> dict:
        return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))

    return _load


@pytest.fixture
def engine(tmp_path):
    db_file = tmp_path / "test.db"
    engine = make_engine(f"sqlite:///{db_file.as_posix()}")
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    factory = make_session_factory(engine)
    with factory() as session:
        yield session


@pytest.fixture
def repo(session):
    return Repository(session)


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    """Point the whole app at a temporary database and evidence folder."""
    data = tmp_path / "data"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(data / 'api_test.db').as_posix()}")
    monkeypatch.setenv("DATA_DIR", str(data))
    monkeypatch.setenv("EVIDENCE_DIR", str(data / "evidence"))
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3000")
    get_settings.cache_clear()
    reset_db_caches()
    yield tmp_path
    reset_db_caches()
    get_settings.cache_clear()


@pytest.fixture
def started_runs(monkeypatch):
    """Replaces the pipeline starter with a recorder: a list of the run ids it was called with."""
    calls: list[str] = []
    monkeypatch.setattr(
        "app.api.routes.runs.start_run", lambda run_id, *a, **k: calls.append(run_id)
    )
    return calls


@pytest.fixture
def client(app_env, started_runs):
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client