from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    app_name: str = "AXM Residuos API"
    app_env: str = "${APP_ENV:?Set APP_ENV in .env}"
    api_v1_prefix: str = "/api/v1"
    app_port: int = Field(default=8000, gt=0, le=65_535)
    postgres_db: str = "${POSTGRES_DB:?Set POSTGRES_DB in .env}"
    postgres_user: str = "${POSTGRES_USER:?Set POSTGRES_USER in .env}"
    postgres_password: SecretStr = SecretStr("${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}")
    postgres_host: str = "${POSTGRES_HOST:?Set POSTGRES_HOST in .env}"
    postgres_container_port: int = Field(default=5432, gt=0, le=65_535)
    timezone: str = "${TIMEZONE:?Set TIMEZONE in .env}"
    allowed_origins: list[str] = Field(default_factory=list)
    admin_api_key: SecretStr = SecretStr("${ADMIN_API_KEY:?Set ADMIN_API_KEY in .env}")
    admin_username: str = "${ADMIN_USERNAME:?Set ADMIN_USERNAME in .env}"
    admin_password: SecretStr = SecretStr("${ADMIN_PASSWORD:?Set ADMIN_PASSWORD in .env}")
    admin_session_secret: SecretStr = SecretStr("${ADMIN_SESSION_SECRET:?Set ADMIN_SESSION_SECRET in .env}")
    admin_session_ttl_seconds: int = Field(default=28_800, gt=0)
    admin_cookie_secure: bool = False

    @property
    def database_url(self) -> str:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_container_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    model_config = SettingsConfigDict(
        env_file=(REPOSITORY_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
