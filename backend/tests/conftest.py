"""Shared pytest fixtures. Owner: Member A."""

import json
from pathlib import Path

import pytest

from app.db import Repository, init_db, make_engine, make_session_factory

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