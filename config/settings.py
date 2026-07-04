"""
Application settings loaded from .env via pydantic-settings.
Only 3 variables are required to start: BOT_TOKEN, OPENAI_API_KEY, ADMIN_ID.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Required
    bot_token: str
    openai_api_key: str
    admin_id: int

    # Optional — sensible defaults for local development
    database_url: str = "sqlite:///./bot.db"
    redis_url: str = "redis://localhost:6379/0"
    openai_model: str = "gpt-4o-mini"
    debug: bool = False
    log_level: str = "INFO"


settings = Settings()
