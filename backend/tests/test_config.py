"""Tests for app.core.config."""

from pathlib import Path

from app.core.config import REPO_ROOT, Settings
from app.core.constants import LLMProvider


def test_repo_root_contains_backend_folder():
    assert (REPO_ROOT / "backend").is_dir()


def test_defaults_without_env_file():
    s = Settings(_env_file=None)
    assert s.backend_port == 8000
    assert s.llm_provider == LLMProvider.NONE
    assert s.frontend_origin == "http://localhost:3000"


def test_relative_paths_become_absolute_under_repo_root():
    s = Settings(_env_file=None)
    assert s.data_path.is_absolute()
    assert str(s.evidence_path).startswith(str(REPO_ROOT))
    assert s.resolved_database_url.startswith("sqlite:///")
    assert "code_apex.db" in s.resolved_database_url


def test_memory_database_url_is_unchanged():
    s = Settings(_env_file=None, database_url="sqlite:///:memory:")
    assert s.resolved_database_url == "sqlite:///:memory:"


def test_environment_variable_overrides_default(monkeypatch):
    monkeypatch.setenv("BACKEND_PORT", "9001")
    s = Settings(_env_file=None)
    assert s.backend_port == 9001


def test_cors_origins_include_both_localhost_spellings():
    s = Settings(_env_file=None)
    assert "http://localhost:3000" in s.cors_origins
    assert "http://127.0.0.1:3000" in s.cors_origins


def test_api_key_is_not_leaked_in_repr():
    s = Settings(_env_file=None, gemini_api_key="super-secret-value")
    assert "super-secret-value" not in repr(s)
    assert s.gemini_api_key.get_secret_value() == "super-secret-value"


def test_ensure_directories_creates_folders(tmp_path: Path):
    s = Settings(
        _env_file=None,
        data_dir=str(tmp_path / "d"),
        evidence_dir=str(tmp_path / "d" / "e"),
    )
    s.ensure_directories()
    assert (tmp_path / "d").is_dir()
    assert (tmp_path / "d" / "e").is_dir()


def test_nvidia_api_key_resolution_and_provider_auto_detect(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", '"nvapi-secret-key-123" ')
    s = Settings(_env_file=None)
    assert s.resolved_nvidia_api_key == "nvapi-secret-key-123"
    assert s.resolved_llm_provider == LLMProvider.NVIDIA