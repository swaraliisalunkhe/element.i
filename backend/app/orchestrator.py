"""STUB orchestrator (Branch 1 only). Replaced by the real one in feat/a-orchestrator."""

import logging

from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger("code_apex")


def start_run(run_id: str, session_factory: sessionmaker[Session] | None = None) -> None:
    logger.warning(
        "STUB orchestrator: run %s was created but no agents were started. "
        "The run stays 'pending'.",
        run_id,
    )