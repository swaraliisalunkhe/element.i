"""
Application settings, loaded from environment variables / the root .env file.

Owner: Member A.
Usage:
    from app.core.config import get_settings
    settings = get_settings()
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import LLMProvider

# config.py lives at <repo>/backend/app/core/config.py, so the repo root is 3 levels up.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",  # ignore variables meant for other members, e.g. NEXT_PUBLIC_*
    )

    app_env: str = "development"

    backend_host: str = "127.0.0.1"
    backend_port: int = 8000

    frontend_origin: str = "http://localhost:3000"

    data_dir: str = "data"
    database_url: str = "sqlite:///data/code_apex.db"
    evidence_dir: str = "data/evidence"

    sample_app_url: str = "http://localhost:8001"
    target_reset_path: str = "/reset"
    sample_assessment_duration: int = 300
    testsuite_max_cases: int = 25
    trace_enabled: bool = True
    headless: bool = True
    llm_model: str = ""

    llm_provider: LLMProvider = LLMProvider.NONE
    gemini_api_key: SecretStr = SecretStr("")
    google_api_key: SecretStr = SecretStr("")
    anthropic_api_key: SecretStr = SecretStr("")

    @property
    def resolved_gemini_api_key(self) -> str:
        """Get cleaned Gemini API key from settings or environment without secrets."""
        for key in (self.gemini_api_key, self.google_api_key):
            try:
                val = key.get_secret_value().strip().strip('"').strip("'")
                if val:
                    return val
            except Exception:
                pass
        import os
        for env_var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            val = os.environ.get(env_var, "").strip().strip('"').strip("'")
            if val:
                return val
        return ""

    # ---------- helpers ----------

    @staticmethod
    def _absolute(path_text: str) -> Path:
        path = Path(path_text)
        return path if path.is_absolute() else (REPO_ROOT / path)

    @property
    def repo_root(self) -> Path:
        return REPO_ROOT

    @property
    def data_path(self) -> Path:
        return self._absolute(self.data_dir)

    @property
    def evidence_path(self) -> Path:
        return self._absolute(self.evidence_dir)

    @property
    def resolved_database_url(self) -> str:
        """Same as database_url, but a relative SQLite file becomes an absolute path."""
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            return self.database_url
        raw = self.database_url[len(prefix):]
        is_memory = raw in ("", ":memory:")
        is_absolute = raw.startswith("/") or (len(raw) > 1 and raw[1] == ":")
        if is_memory or is_absolute:
            return self.database_url
        return prefix + (REPO_ROOT / raw).as_posix()

    @property
    def cors_origins(self) -> list[str]:
        """Origins allowed to call the API from a browser (the Next.js dashboard)."""
        configured = [o.strip().rstrip("/") for o in self.frontend_origin.split(",") if o.strip()]
        defaults = [
            "https://element-i-frontend.onrender.com",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
        origins = []
        for o in configured + defaults:
            clean = o.rstrip("/")
            origins.append(clean)
            if not clean.startswith("http://") and not clean.startswith("https://"):
                origins.append(f"https://{clean}")
            if "localhost" in clean:
                origins.append(clean.replace("localhost", "127.0.0.1"))
            elif "127.0.0.1" in clean:
                origins.append(clean.replace("127.0.0.1", "localhost"))
        return list(dict.fromkeys(origins))

    def ensure_directories(self) -> None:
        """Create the data and evidence folders if they do not exist."""
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.evidence_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Create the settings once and reuse them."""
    return Settings()