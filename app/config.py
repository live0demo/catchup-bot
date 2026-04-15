"""Runtime configuration loaded from .env / environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _get(name: str, default: str = "") -> str:
    val = os.environ.get(name)
    return val if val is not None and val != "" else default


def _get_int(name: str, default: int) -> int:
    try:
        return int(_get(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    bot_token: str
    bot_display_name: str
    bot_username_hint: str
    bot_short_description: str
    bot_brand_emoji: str

    database_url: str
    message_retention_days: int
    default_timezone: str
    default_delivery_mode: str
    log_level: str

    llm_api_key: str
    llm_base_url: str
    llm_model: str
    summary_language: str

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)


settings = Settings(
    bot_token=_get("BOT_TOKEN"),
    bot_display_name=_get("BOT_DISPLAY_NAME", "Catchup Bot"),
    bot_username_hint=_get("BOT_USERNAME_HINT", "@your_bot"),
    bot_short_description=_get(
        "BOT_SHORT_DESCRIPTION", "Group catch-up summaries and reminders."
    ),
    bot_brand_emoji=_get("BOT_BRAND_EMOJI", "🦉"),
    database_url=_get("DATABASE_URL", "sqlite:///./data/bot.db"),
    message_retention_days=_get_int("MESSAGE_RETENTION_DAYS", 14),
    default_timezone=_get("DEFAULT_TIMEZONE", "UTC"),
    default_delivery_mode=_get("DEFAULT_DELIVERY_MODE", "private"),
    log_level=_get("LOG_LEVEL", "INFO"),
    llm_api_key=_get("LLM_API_KEY", ""),
    llm_base_url=_get("LLM_BASE_URL", "https://api.openai.com/v1"),
    llm_model=_get("LLM_MODEL", "gpt-4o-mini"),
    summary_language=_get("SUMMARY_LANGUAGE", "auto"),
)


def require_token() -> str:
    if not settings.bot_token:
        raise RuntimeError(
            "BOT_TOKEN is not set. Copy .env.example to .env and fill it in."
        )
    return settings.bot_token
