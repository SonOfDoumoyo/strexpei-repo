"""Application settings.

All configuration comes from environment variables (or a `.env` file next to
this backend). Every value has a safe development default except secrets,
which must be provided in production.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

logger = logging.getLogger("streixpei.config")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ app
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    APP_NAME: str = "Streixpei"
    COMPANY_NAME: str = "Streixcorp"
    FRONTEND_URL: str = "http://localhost:5173"
    API_URL: str = "http://localhost:8000"
    SUPPORT_EMAIL: str = "support@streixpei.com"
    TIMEZONE: str = "Africa/Lagos"
    LOG_LEVEL: str = "INFO"

    # ------------------------------------------------------------- database
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/streixpei"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # ---------------------------------------------------------------- redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # ----------------------------------------------------------------- auth
    JWT_SECRET_KEY: str = "dev-only-change-me-dev-only-change-me-0000"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 30
    REFRESH_TOKEN_SHORT_TTL_HOURS: int = 24
    COOKIE_SECURE: bool | None = None  # defaults to True in production
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str | None = None
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---------------------------------------------------------------- email
    MAIL_ENABLED: bool = True
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_FROM_NAME: str = "Streixpei"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    MAIL_TIMEOUT_SECONDS: int = 20

    # ------------------------------------------------------------- payments
    PAYMENTS_PROVIDER: Literal["paystack", "fake"] = "paystack"
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"
    PAYSTACK_DVA_ENABLED: bool = False
    PAYSTACK_DVA_PREFERRED_BANK: str = "wema-bank"
    PAYSTACK_TIMEOUT_SECONDS: int = 30

    # ------------------------------------------------------------------- ai
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "claude-sonnet-5-5"
    AI_MAX_TOKENS: int = 1200
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"

    # ---------------------------------------------------------------- admin
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""

    # ------------------------------------------------------------ scheduler
    SCHEDULER_ENABLED: bool = True

    # ---------------------------------------------------------- validators
    @field_validator("DATABASE_URL")
    @classmethod
    def _normalise_db_url(cls, value: str) -> str:
        # Hosting providers hand out postgres:// URLs; SQLAlchemy needs the driver.
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value[len("postgresql://") :]
        if value.startswith("postgresql+asyncpg://"):
            value = "postgresql+psycopg://" + value[len("postgresql+asyncpg://") :]
        return value

    @field_validator("FRONTEND_URL", "API_URL")
    @classmethod
    def _strip_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            problems: list[str] = []
            if len(self.JWT_SECRET_KEY) < 32 or self.JWT_SECRET_KEY.startswith("dev-only"):
                problems.append("JWT_SECRET_KEY must be a random string of at least 32 characters")
            if self.PAYMENTS_PROVIDER != "paystack":
                problems.append("PAYMENTS_PROVIDER must be 'paystack' in production")
            if not self.PAYSTACK_SECRET_KEY:
                problems.append("PAYSTACK_SECRET_KEY is required in production")
            if self.COOKIE_SAMESITE == "none" and self.COOKIE_SECURE is False:
                problems.append("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
            if problems:
                raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self

    # ------------------------------------------------------------- helpers
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cookie_secure(self) -> bool:
        if self.COOKIE_SECURE is None:
            return self.is_production
        return self.COOKIE_SECURE

    @property
    def cors_origins(self) -> list[str]:
        origins = [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.FRONTEND_URL not in origins:
            origins.append(self.FRONTEND_URL)
        return origins

    @property
    def mail_from(self) -> str:
        return self.MAIL_FROM or self.MAIL_USERNAME

    @property
    def mail_configured(self) -> bool:
        return bool(self.MAIL_ENABLED and self.MAIL_USERNAME and self.MAIL_PASSWORD and self.mail_from)

    @property
    def ai_configured(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
