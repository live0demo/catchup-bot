"""Bot + Dispatcher factory."""
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import require_token


def build_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    bot = Bot(
        token=require_token(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    return bot, dp
