from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    database_url: str | None = None

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url
        repo_root = Path(__file__).resolve().parents[3]
        default_path = repo_root / "data" / "actions_api.db"
        return f"sqlite:///{default_path}"


settings = Settings()
