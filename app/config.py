"""Typed application settings, loaded from environment variables and .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    daily_budget_usd: float = 5.0
    # Gates POST /chat when set (see app/api/main.py). Left optional so
    # local dev against localhost doesn't require setting up a key --
    # but that also means auth is OFF by default. Set this before
    # exposing the service anywhere reachable by anyone else.
    service_api_key: str | None = None


settings = Settings()
