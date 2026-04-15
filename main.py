"""Entry point. Single process: aiogram polling + APScheduler in the same loop."""
from __future__ import annotations

import asyncio
import logging
import os
import signal

from app.bot import build_bot_and_dispatcher
from app.config import settings
from app.db import init_db
from app.handlers import register_handlers
from app.logging_setup import configure_logging
from app.scheduler.scheduler import ReminderScheduler

log = logging.getLogger(__name__)


async def amain() -> None:
    configure_logging(settings.log_level)
    # On Replit, REPL_ID is always set. Start a tiny HTTP server so UptimeRobot
    # (or similar) can ping us and keep the repl from sleeping. No-op elsewhere.
    if os.environ.get("REPL_ID"):
        from keep_alive import keep_alive

        keep_alive()
    init_db()

    bot, dp = build_bot_and_dispatcher()
    scheduler = ReminderScheduler(bot)
    register_handlers(dp, scheduler)
    scheduler.start()
    scheduler.load_persisted_reminders()

    log.info(
        "Starting %s (%s) — polling mode",
        settings.bot_display_name,
        settings.bot_username_hint,
    )

    stop_event = asyncio.Event()

    def _request_stop(*_: object) -> None:
        log.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            # Windows: signal handlers via add_signal_handler not supported.
            signal.signal(sig, _request_stop)

    polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    stop_task = asyncio.create_task(stop_event.wait())

    done, _ = await asyncio.wait(
        {polling_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
    )

    if stop_task in done:
        await dp.stop_polling()
        try:
            await polling_task
        except Exception:  # noqa: BLE001
            log.exception("Polling task ended with error")

    scheduler.shutdown()
    await bot.session.close()
    log.info("Bye.")


if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
