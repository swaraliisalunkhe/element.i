"""Shared FastAPI dependencies. Owner: Member A."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import Repository, get_db


def get_repo(session: Session = Depends(get_db)) -> Repository:
    return Repository(session)