"""FastAPI application entry point. Owner: Member A.

Run from the backend/ folder:
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.router import api_router
from app.api.routes import health
from app.core.config import get_settings
from app.core.constants import CONTRACT_VERSION
from app.db import Repository, init_db, session_scope

logger = logging.getLogger("code_apex")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once when the server starts."""
    settings = get_settings()
    settings.ensure_directories()
    init_db()
    with session_scope() as session:
        stuck = Repository(session).fail_incomplete_runs()
    if stuck:
        logger.warning("Marked %s unfinished run(s) from a previous session as failed.", stuck)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Code Apex API",
        version=CONTRACT_VERSION,
        description="Backend for the Autonomous AI QA Engineer (Team No Limits).",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # the Next.js dashboard only
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router)
    return app


app = create_app()