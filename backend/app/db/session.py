"""Database engine and session handling. Owner: Member A."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.errors import DatabaseError
from app.db.models import Base

_SQLITE_PREFIX = "sqlite:///"


def _is_memory_url(url: str) -> bool:
    return url.startswith("sqlite") and (":memory:" in url or url in ("sqlite://", "sqlite:///"))


def make_engine(database_url: str) -> Engine:
    """Create an engine. Tests call this with their own temporary database file."""
    is_sqlite = database_url.startswith("sqlite")
    options: dict = {}

    if is_sqlite:
        options["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if _is_memory_url(database_url):
            options["poolclass"] = StaticPool  # keep one shared connection for in-memory DBs
        elif database_url.startswith(_SQLITE_PREFIX):
            Path(database_url[len(_SQLITE_PREFIX):]).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(database_url, **options)

    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _sqlite_settings(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine)


@lru_cache
def get_engine() -> Engine:
    """The one engine used by the running application."""
    settings = get_settings()
    settings.ensure_directories()
    return make_engine(settings.resolved_database_url)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return make_session_factory(get_engine())


def reset_db_caches() -> None:
    """Forget the cached engine. Used by tests."""
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()


def init_db(engine: Engine | None = None) -> None:
    """Create all tables if they do not exist yet. Safe to call many times."""
    try:
        Base.metadata.create_all(engine or get_engine())
    except SQLAlchemyError as exc:
        raise DatabaseError(f"Could not create the database tables: {exc}") from exc


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope(factory: sessionmaker[Session] | None = None) -> Iterator[Session]:
    """Use in background code (the orchestrator): `with session_scope() as session:`.

    Repository methods commit by themselves; this only guarantees the session is closed.
    """
    session = (factory or get_session_factory())()
    try:
        yield session
    finally:
        session.close()