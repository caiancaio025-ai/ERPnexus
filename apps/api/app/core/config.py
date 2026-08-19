from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def find_env_file() -> str:
    candidates = [Path.cwd() / ".env"]
    candidates.extend(parent / ".env" for parent in Path(__file__).resolve().parents)

    return str(
        next(
            (path for path in candidates if path.is_file()),
            ".env",
        )
    )


class Settings(BaseSettings):
    app_env: str = "development"

    database_url: str = "postgresql+psycopg://nexus:nexus@db:5432/nexus"

    allowed_hosts: str = "localhost,127.0.0.1,api,testserver"
    cors_origins: str = "http://localhost:5173"

    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout: int = 10
    db_pool_recycle: int = 1800

    session_hours: int = 12
    session_cookie_name: str = "nexus_session"

    login_rate_limit_window_seconds: int = 900
    login_rate_limit_identifier_failures: int = 5
    login_rate_limit_ip_failures: int = 20
    login_rate_limit_retention_seconds: int = 86400
    storage_root: str = "/app/storage"
    tracking_base_url: str = "http://localhost:8000/e"
    gemini_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [value.strip() for value in self.allowed_hosts.split(",") if value.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]

    @property
    def secure_cookies(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
