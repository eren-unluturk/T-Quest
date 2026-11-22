from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Repo-root .env, resolved from this file so the working directory does not matter.
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str | None = None
    port: int = Field(default=8002, validation_alias="INSIGHTS_SPONSORS_PORT")
    auth_mode: Literal["dev", "strict"] = "dev"
    data_backend: Literal["memory", "postgres"] = "memory"
    # Comma-separated browser origins allowed to call this API (the web app's host). "*" is fine in dev
    # because auth is a bearer header, not cookies.
    cors_origins: str = "*"


settings = Settings()


CURRENT_POLICY_VERSION = "2026-11-21"
