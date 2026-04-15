"""Register all routers with the Dispatcher."""
from __future__ import annotations

from aiogram import Dispatcher

from app.handlers import basic, catchup, messages, reminders, settings as settings_handlers
from app.scheduler.scheduler import ReminderScheduler


def register_handlers(dp: Dispatcher, scheduler: ReminderScheduler) -> None:
    # Order matters only for routers that share the same filters; ours don't.
    reminders.scheduler_ref.set(scheduler)

    dp.include_router(basic.router)
    dp.include_router(settings_handlers.router)
    dp.include_router(catchup.router)
    dp.include_router(reminders.router)
    # Message-cache router last so command routers handle commands first.
    dp.include_router(messages.router)
