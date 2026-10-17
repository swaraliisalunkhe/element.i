"""Collects every route under /api. Owner: Member A."""

from fastapi import APIRouter

from app.api.routes import evidence, runs, stream
from app.core.constants import API_PREFIX

api_router = APIRouter(prefix=API_PREFIX)
api_router.include_router(runs.router)
api_router.include_router(stream.router)
api_router.include_router(evidence.router)