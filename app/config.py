"""
config.py — centralised settings loaded from environment variables.

All defaults are safe for local development. Production deployments must
supply real values via environment (never hard-code secrets here).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://mininetflix:mininetflix@localhost:5432/mininetflix"
    )

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"

    # ── Resilience ────────────────────────────────────────────────────────────
    # Only expose fault-injection query params when explicitly enabled.
    enable_fault_injection: bool = False
    recommendation_timeout_ms: int = 500

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
