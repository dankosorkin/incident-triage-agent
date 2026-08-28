"""Typed application settings, loaded from environment variables and .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    daily_budget_usd: float = 5.0


settings = Settings()
