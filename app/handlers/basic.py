"""Start, help, and a tiny ping."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.config import settings

router = Router(name="basic")


def _brand(line: str = "") -> str:
    name = f"{settings.bot_brand_emoji} <b>{settings.bot_display_name}</b>".strip()
    return f"{name}\n{line}" if line else name


@router.message(CommandStart())
async def start(msg: Message) -> None:
    text = (
        f"{_brand(settings.bot_short_description)}\n\n"
        "I help you <b>catch up on group chats</b> and <b>set reminders</b>.\n\n"
        "<b>Catch-up</b>\n"
        "• /markread — set your checkpoint here\n"
        "• /catchup — summarize new messages since checkpoint\n"
        "• /catchup_short  /catchup_detailed\n"
        "• /autosummary on|off\n\n"
        "<b>Reminders</b>\n"
        "• /remind in 30 minutes water plants\n"
        "• /remind tomorrow 9am submit report\n"
        "• /remind every monday 8:00 team sync\n"
        "• /list_reminders   /delete_reminder &lt;id&gt;\n"
        "• /set_timezone Europe/Berlin\n\n"
        "Type /help for the full list and how to use me in groups."
    )
    await msg.answer(text)


@router.message(Command("help"))
async def help_cmd(msg: Message) -> None:
    text = (
        f"{_brand()}\n\n"
        "<b>Limitations to know</b>\n"
        "• Telegram does not tell bots what you've read. /catchup uses an explicit "
        "<b>checkpoint</b> you set with /markread.\n"
        "• In groups, I can only summarize messages I actually saw. Ask the admin to "
        "disable <b>Privacy Mode</b> in BotFather and add me to the group so I can read messages.\n"
        "• I cannot fetch messages from before I joined.\n\n"
        "<b>Commands</b>\n"
        "/start, /help\n"
        "/markread — set your catch-up checkpoint in this chat\n"
        "/catchup, /catchup_short, /catchup_detailed\n"
        "/autosummary on|off — daily DM digest of this group (best-effort)\n"
        "/remind &lt;when&gt; &lt;text&gt;\n"
        "/list_reminders\n"
        "/delete_reminder &lt;id&gt;\n"
        "/set_timezone &lt;IANA tz&gt;  e.g. <code>Europe/Berlin</code>\n"
    )
    await msg.answer(text)


@router.message(Command("ping"))
async def ping(msg: Message) -> None:
    await msg.answer("pong")
