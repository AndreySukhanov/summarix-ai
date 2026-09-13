"""
Settings from .env. The bot serves exactly one person: OWNER_ID.
"""
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramAccountSettings(BaseSettings):
    """Just what the one-time login script needs."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    tg_api_id: int
    tg_api_hash: str
    tg_session: str = "data/owner"  # Telethon appends .session


class Settings(TelegramAccountSettings):
    bot_token: str
    owner_id: int

    # Any OpenAI-compatible API: OpenAI, OpenRouter, DeepSeek, Qwen, a local vLLM...
    llm_api_key: str
    llm_model: str
    llm_base_url: str = "https://api.openai.com/v1"
    vision_model: str | None = None  # defaults to llm_model

    describe_images: bool = True
    max_images_per_run: int = Field(default=20, ge=0)

    digest_time: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = "Europe/Moscow"
    digest_language: Literal["ru", "en", "es", "fr", "kk"] = "ru"  # initial value; change in /settings
    ui_language: Literal["ru", "en"] = "ru"

    lookback_hours: int = Field(default=24, ge=1)
    max_posts_per_channel: int = Field(default=60, ge=1)

    database_url: str = "sqlite+aiosqlite:///data/summarix.db"
    log_level: str = "INFO"
