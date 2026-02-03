from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    database_url: str | None = None
    auth_enabled: bool = True
    dev_mode: bool = True
    secret_key: str | None = None
    admin_username: str | None = None
    admin_password: str | None = None
    session_cookie_name: str = "capa_session"
    session_ttl_days: int = 7

    @property
    def session_cookie_secure(self) -> bool:
        return not self.dev_mode

    @property
    def required_secret_key(self) -> str:
        if self.auth_enabled and not self.secret_key:
            raise RuntimeError("SECRET_KEY must be set when AUTH_ENABLED=true.")
        return self.secret_key or ""

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url
        repo_root = Path(__file__).resolve().parents[3]
        default_path = repo_root / "data" / "actions_api.db"
        return f"sqlite:///{default_path}"


settings = Settings()
