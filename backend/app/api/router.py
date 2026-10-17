"""Collects every route under /api. Owner: Member A."""

from fastapi import APIRouter

from app.api.routes import evidence, runs
from app.core.constants import API_PREFIX

api_router = APIRouter(prefix=API_PREFIX)
api_router.include_router(runs.router)
api_router.include_router(evidence.router)