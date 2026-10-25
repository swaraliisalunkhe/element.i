"""Shared building blocks: base model, helpers, evidence, error and health shapes."""

import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import CONTRACT_VERSION, EVIDENCE_URL_PREFIX, EvidenceKind


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    """Create an id like 'run_7f3a9c21b4d8'."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def validate_http_url(value: str) -> str:
    """Accept only absolute http/https URLs and block SSRF vectors like cloud metadata."""
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("must be an absolute http:// or https:// URL")
    hostname = (parsed.hostname or "").lower().strip()
    if hostname in ("169.254.169.254", "metadata.google.internal", "instance-data", "169.254.169.253"):
        raise ValueError(f"access to target host '{hostname}' is prohibited")
    return value


class ContractModel(BaseModel):
    """Base class for every contract model.

    extra='ignore': unknown fields are dropped, so newer producers do not crash older consumers.
    from_attributes: lets us build a model straight from a database row.
    """

    model_config = ConfigDict(extra="ignore", from_attributes=True)


class EvidenceMeta(ContractModel):
    """Describes one piece of evidence (usually a screenshot). The file itself is on disk."""

    id: str = Field(default_factory=lambda: new_id("ev"), min_length=1, max_length=64)
    run_id: str = Field(min_length=1, max_length=64)
    test_case_id: str | None = Field(default=None, max_length=64)
    step_index: int | None = Field(default=None, ge=1)
    kind: EvidenceKind = EvidenceKind.SCREENSHOT
    # Path relative to the evidence folder, always with forward slashes.
    path: str = Field(min_length=1, max_length=300)
    # Filled automatically as /api/evidence/<path> if you leave it out.
    url: str | None = None
    mime_type: str = "image/png"
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    size_bytes: int | None = Field(default=None, ge=0)
    caption: str | None = Field(default=None, max_length=300)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("path")
    @classmethod
    def _path_must_be_safe(cls, value: str) -> str:
        parts = value.split("/")
        if (
            "\\" in value
            or "\x00" in value
            or ":" in value
            or value.startswith("/")
            or any(part in ("", ".", "..") for part in parts)
        ):
            raise ValueError(
                "path must be relative, use '/' separators and contain no '..', ':' or empty parts"
            )
        return value

    @model_validator(mode="after")
    def _url_matches_path(self) -> "EvidenceMeta":
        expected = f"{EVIDENCE_URL_PREFIX}/{self.path}"
        if self.url is None:
            self.url = expected
        elif self.url != expected:
            raise ValueError(f"url must be '{expected}'")
        return self


class ErrorDetail(ContractModel):
    code: str
    message: str
    details: dict | None = None


class ErrorResponse(ContractModel):
    """Every API error uses this shape: {"error": {"code": "...", "message": "..."}}"""

    error: ErrorDetail


class HealthResponse(ContractModel):
    status: str = "ok"
    service: str = "code-apex-backend"
    contract_version: str = CONTRACT_VERSION
    time: datetime = Field(default_factory=utc_now)