"""GET /api/evidence/{path}: serve screenshots safely. Owner: Member A."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.errors import NotFoundError

router = APIRouter(tags=["evidence"])

# Only these file types can ever be served. HTML is sent as plain text so it can never run.
ALLOWED_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".txt": "text/plain",
    ".log": "text/plain",
    ".html": "text/plain",
}


def resolve_evidence_file(base: Path, relative: str) -> Path:
    """Return the real file for `relative` inside `base`, or raise NotFoundError."""

    def not_found() -> NotFoundError:
        return NotFoundError("Evidence file not found.")

    if (
        not relative
        or relative.startswith("/")
        or "\\" in relative
        or ":" in relative
        or "\x00" in relative
    ):
        raise not_found()
    if any(part in ("", ".", "..") for part in relative.split("/")):
        raise not_found()
    if Path(relative).suffix.lower() not in ALLOWED_TYPES:
        raise not_found()

    base_resolved = base.resolve()
    candidate = (base_resolved / relative).resolve()
    if not candidate.is_relative_to(base_resolved) or not candidate.is_file():
        raise not_found()
    return candidate


@router.get("/evidence/{file_path:path}")
def get_evidence(file_path: str) -> FileResponse:
    file = resolve_evidence_file(get_settings().evidence_path, file_path)
    return FileResponse(
        file,
        media_type=ALLOWED_TYPES[file.suffix.lower()],
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"},
    )